import json
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.db import models
from app.services import payments
from tests.test_admin import admin  # noqa: F401
from tests.test_billing import SERVER_KEY, fresh_user, invoices, make_tx, past


@pytest.fixture
def gateway(monkeypatch):
    state = SimpleNamespace(asked=[], reply={"transaction_status": "settlement", "gross_amount": "29000.00"}, error=None)

    def fake(order_id):
        state.asked.append(order_id)
        if state.error:
            raise state.error
        return state.reply

    monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)
    monkeypatch.setattr(payments, "fetch_status", fake)
    return state


@pytest.fixture
def user(make_user):
    return make_user("free")


def old_tx(db, user, days, **kw):
    tx = make_tx(db, user, provider="midtrans", **kw)
    tx.created_at = datetime.utcnow() - timedelta(days=days)
    db.commit()
    return tx


def stored(db, tx):
    db.expire_all()
    return db.get(models.Transaction, tx.id)


class TestWiderReconciliation:
    @pytest.mark.parametrize("status", ["expired", "cancelled", "failed"])
    def test_a_recent_final_order_paid_at_the_gateway_is_recorded_when_read(self, client, db, auth, user, gateway, outbox, status):
        tx = old_tx(db, user, 1, status=status)
        res = client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user))
        assert res.json()["status"] == "paid" and gateway.asked == [tx.order_id]
        assert fresh_user(db, user).tier == "middle" and len(invoices(outbox)) == 1

    def test_the_history_list_also_looks_again(self, client, db, auth, user, gateway):
        old_tx(db, user, 2, status="expired")
        assert client.get("/billing/transactions", headers=auth(user)).json()[0]["status"] == "paid"

    def test_an_order_older_than_seven_days_is_not_asked(self, client, db, auth, user, gateway):
        tx = old_tx(db, user, 8, status="expired")
        client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user))
        assert gateway.asked == [] and stored(db, tx).status == "expired"

    def test_the_seventh_day_is_still_asked(self, client, db, auth, user, gateway):
        tx = old_tx(db, user, 6, status="expired")
        client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user))
        assert gateway.asked == [tx.order_id]

    @pytest.mark.parametrize("answer", ["expire", "cancel", "deny", "failure", "pending", "aneh"])
    def test_only_a_paid_answer_changes_a_final_order(self, client, db, auth, user, gateway, answer):
        tx = old_tx(db, user, 1, status="cancelled")
        gateway.reply = {"transaction_status": answer, "gross_amount": "29000.00"}
        client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user))
        assert stored(db, tx).status == "cancelled" and fresh_user(db, user).tier == "free"

    def test_a_pending_order_still_follows_every_answer(self, client, db, auth, user, gateway):
        tx = make_tx(db, user, provider="midtrans")
        gateway.reply = {"transaction_status": "deny", "gross_amount": "29000.00"}
        client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user))
        assert stored(db, tx).status == "failed"

    def test_a_wrong_amount_is_not_applied_and_is_logged_without_personal_data(self, client, db, auth, user, gateway, caplog):
        tx = old_tx(db, user, 1, status="expired")
        gateway.reply = {"transaction_status": "settlement", "gross_amount": "1000.00"}
        with caplog.at_level(logging.WARNING):
            client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user))
        assert stored(db, tx).status == "expired" and fresh_user(db, user).tier == "free"
        assert tx.order_id in caplog.text and "1000" in caplog.text and user.email not in caplog.text and user.name not in caplog.text

    def test_a_wrong_amount_on_a_pending_order_is_logged_too(self, client, db, auth, user, gateway, caplog):
        tx = make_tx(db, user, provider="midtrans")
        gateway.reply = {"transaction_status": "settlement", "gross_amount": "1000.00"}
        with caplog.at_level(logging.WARNING):
            client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user))
        assert stored(db, tx).status == "pending" and tx.order_id in caplog.text

    def test_a_simulated_order_is_never_asked(self, client, db, auth, user, gateway):
        tx = make_tx(db, user, provider="simulated", status="expired")
        client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user))
        assert gateway.asked == []

    def test_a_paid_order_is_never_asked(self, client, db, auth, user, gateway):
        tx = make_tx(db, user, provider="midtrans", status="paid")
        client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user))
        assert gateway.asked == []

    def test_a_gateway_failure_leaves_the_order_alone(self, client, db, auth, user, gateway):
        tx = old_tx(db, user, 1, status="expired")
        gateway.error = payments.PaymentError("mati")
        assert client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user)).json()["status"] == "expired"

    def test_the_payment_method_from_the_gateway_is_kept(self, client, db, auth, user, gateway):
        tx = old_tx(db, user, 1, status="expired")
        gateway.reply = {"transaction_status": "settlement", "gross_amount": "29000.00", "payment_type": "qris"}
        assert client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user)).json()["payment_method"] == "QRIS"


class TestUserCheck:
    def check(self, client, auth, user, tx):
        return client.post(f"/billing/transactions/{tx.order_id}/check", headers=auth(user))

    def test_a_paid_order_at_the_gateway_becomes_paid(self, client, db, auth, user, gateway, outbox):
        tx = make_tx(db, user, provider="midtrans")
        res = self.check(client, auth, user, tx)
        assert res.status_code == 200 and res.json()["status"] == "paid"
        assert fresh_user(db, user).tier == "middle" and len(invoices(outbox)) == 1

    def test_the_seven_day_window_does_not_apply_to_an_explicit_check(self, client, db, auth, user, gateway):
        tx = old_tx(db, user, 40, status="expired")
        assert self.check(client, auth, user, tx).json()["status"] == "paid"

    @pytest.mark.parametrize("status", ["expired", "cancelled", "failed"])
    def test_final_orders_can_be_recovered(self, client, db, auth, user, gateway, status):
        tx = old_tx(db, user, 1, status=status)
        assert self.check(client, auth, user, tx).json()["status"] == "paid"

    def test_nothing_changes_when_the_gateway_has_no_payment(self, client, db, auth, user, gateway):
        tx = old_tx(db, user, 1, status="expired")
        gateway.reply = {"transaction_status": "expire", "gross_amount": "29000.00"}
        res = self.check(client, auth, user, tx)
        assert res.status_code == 200 and res.json()["status"] == "expired" and fresh_user(db, user).tier == "free"

    def test_an_overdue_pending_order_becomes_expired(self, client, db, auth, user, gateway):
        tx = make_tx(db, user, provider="midtrans", expires_at=past())
        gateway.reply = {"transaction_status": "pending", "gross_amount": "29000.00"}
        assert self.check(client, auth, user, tx).json()["status"] == "expired"

    def test_a_wrong_amount_is_not_applied(self, client, db, auth, user, gateway):
        tx = make_tx(db, user, provider="midtrans")
        gateway.reply = {"transaction_status": "settlement", "gross_amount": "1000.00"}
        assert self.check(client, auth, user, tx).json()["status"] == "pending" and fresh_user(db, user).tier == "free"

    def test_a_gateway_failure_is_not_an_error_for_the_user(self, client, db, auth, user, gateway):
        tx = make_tx(db, user, provider="midtrans")
        gateway.error = payments.PaymentError("mati")
        res = self.check(client, auth, user, tx)
        assert res.status_code == 200 and res.json()["status"] == "pending"

    def test_a_paid_order_is_not_asked_again(self, client, db, auth, user, gateway):
        tx = make_tx(db, user, provider="midtrans", status="paid")
        assert self.check(client, auth, user, tx).json()["status"] == "paid" and gateway.asked == []

    def test_a_simulated_order_is_not_asked(self, client, db, auth, user, gateway):
        tx = make_tx(db, user, provider="simulated")
        assert self.check(client, auth, user, tx).json()["status"] == "pending" and gateway.asked == []

    def test_someone_elses_order_is_not_found_and_not_asked(self, client, db, auth, make_user, user, gateway):
        tx = make_tx(db, user, provider="midtrans")
        res = self.check(client, auth, make_user("free"), tx)
        assert res.status_code == 404 and gateway.asked == []

    def test_an_unknown_order_is_not_found(self, client, auth, user, gateway):
        assert client.post("/billing/transactions/NAR-0-tidakada/check", headers=auth(user)).status_code == 404

    def test_a_token_is_required(self, client, db, user, gateway):
        tx = make_tx(db, user, provider="midtrans")
        assert client.post(f"/billing/transactions/{tx.order_id}/check").status_code == 401

    def test_checking_twice_applies_only_once(self, client, db, auth, user, gateway, outbox):
        tx = make_tx(db, user, kind="pay_per_check", quantity=2, amount=10_000, provider="midtrans")
        gateway.reply = {"transaction_status": "settlement", "gross_amount": "10000.00"}
        self.check(client, auth, user, tx)
        self.check(client, auth, user, tx)
        assert fresh_user(db, user).extra_checks == 2 and len(invoices(outbox)) == 1


class TestAdminInspect:
    def url(self, tx):
        return f"/admin/payments/{tx.order_id}"

    def inspect(self, client, auth, admin, tx):
        res = client.get(self.url(tx), headers=auth(admin))
        assert res.status_code == 200, res.text
        return res.json()

    def test_access(self, client, auth, make_user, db, user):
        tx = make_tx(db, user, provider="midtrans")
        assert client.get(self.url(tx)).status_code == 401
        assert client.get(self.url(tx), headers=auth(make_user())).status_code == 403

    def test_an_unknown_order_is_not_found(self, client, auth, admin):
        res = client.get("/admin/payments/NAR-0-tidakada", headers=auth(admin))
        assert res.status_code == 404 and res.json()["detail"] == "Transaksi tidak ditemukan."

    def test_both_sides_are_shown(self, client, db, auth, admin, user, gateway):
        tx = old_tx(db, user, 1, status="expired")
        gateway.reply = {"transaction_status": "settlement", "gross_amount": "29000.00", "payment_type": "gopay"}
        data = self.inspect(client, auth, admin, tx)
        assert data["order_id"] == tx.order_id and data["provider"] == "midtrans" and data["kind"] == "upgrade" and data["plan"] == "middle"
        assert (data["local_status"], data["local_amount"]) == ("expired", 29000)
        assert data["gateway"] == {"checked": True, "status": "paid", "raw_status": "settlement", "amount": 29000, "method": "GoPay"}
        assert data["can_sync"] is True and data["applied"] is False
        assert "Tekan Sinkronkan" in data["message"]

    def test_looking_never_changes_anything(self, client, db, auth, admin, user, gateway, outbox):
        tx = old_tx(db, user, 1, status="expired")
        self.inspect(client, auth, admin, tx)
        assert stored(db, tx).status == "expired" and fresh_user(db, user).tier == "free" and outbox == []

    def test_a_paid_order_matching_the_gateway(self, client, db, auth, admin, user, gateway):
        tx = make_tx(db, user, provider="midtrans", status="paid")
        tx.paid_at = datetime.utcnow()
        db.commit()
        data = self.inspect(client, auth, admin, tx)
        assert data["can_sync"] is False and data["message"] == "Sudah tercatat berhasil dan sesuai dengan Midtrans."

    def test_a_different_amount_cannot_be_synchronised(self, client, db, auth, admin, user, gateway):
        tx = make_tx(db, user, provider="midtrans")
        gateway.reply = {"transaction_status": "settlement", "gross_amount": "1000.00"}
        data = self.inspect(client, auth, admin, tx)
        assert data["can_sync"] is False and "nominalnya berbeda" in data["message"] and data["gateway"]["amount"] == 1000

    def test_the_gateway_has_no_payment_yet(self, client, db, auth, admin, user, gateway):
        tx = make_tx(db, user, provider="midtrans")
        gateway.reply = {"transaction_status": "pending", "gross_amount": "29000.00"}
        data = self.inspect(client, auth, admin, tx)
        assert data["can_sync"] is False and data["message"] == "Midtrans belum mencatat pembayaran lunas untuk pesanan ini."
        assert data["gateway"]["status"] == "pending" and data["gateway"]["raw_status"] == "pending"

    def test_paid_here_but_not_at_the_gateway(self, client, db, auth, admin, user, gateway):
        tx = make_tx(db, user, provider="midtrans", status="paid")
        tx.paid_at = datetime.utcnow()
        db.commit()
        gateway.reply = {"transaction_status": "expire", "gross_amount": "29000.00"}
        data = self.inspect(client, auth, admin, tx)
        assert data["can_sync"] is False and data["message"].startswith("Tercatat berhasil di NARAtive tetapi Midtrans tidak melaporkan lunas")

    def test_an_unreachable_gateway(self, client, db, auth, admin, user, gateway):
        tx = make_tx(db, user, provider="midtrans")
        gateway.error = payments.PaymentError("mati")
        data = self.inspect(client, auth, admin, tx)
        assert data["gateway"]["checked"] is False and data["gateway"]["status"] is None
        assert data["message"] == "Midtrans tidak merespons. Coba lagi sebentar lagi." and data["can_sync"] is False

    def test_a_simulated_order_has_no_gateway_side(self, client, db, auth, admin, user, gateway):
        tx = make_tx(db, user, provider="simulated")
        data = self.inspect(client, auth, admin, tx)
        assert data["gateway"]["checked"] is False and gateway.asked == []
        assert data["message"] == "Pesanan ini berasal dari mode simulasi; tidak ada data di Midtrans."

    def test_nothing_identifies_the_buyer(self, client, db, auth, admin, user, gateway):
        user.name = "Nama Rahasia Banget"
        db.commit()
        tx = old_tx(db, user, 1, status="expired")
        raw = json.dumps(self.inspect(client, auth, admin, tx))
        for secret in (user.email, "Nama Rahasia", tx.va_number):
            assert secret not in raw
        for key in ('"email"', '"name"', '"user_id"', '"va_number"', '"id"', '"bank"'):
            assert key not in raw


class TestAdminSync:
    def sync(self, client, auth, admin, tx):
        return client.post(f"/admin/payments/{tx.order_id}/sync", headers=auth(admin))

    def test_access(self, client, auth, make_user, db, user):
        tx = make_tx(db, user, provider="midtrans")
        assert client.post(f"/admin/payments/{tx.order_id}/sync").status_code == 401
        assert client.post(f"/admin/payments/{tx.order_id}/sync", headers=auth(make_user())).status_code == 403
        assert stored(db, tx).status == "pending"

    def test_an_unknown_order_is_not_found(self, client, auth, admin):
        assert client.post("/admin/payments/NAR-0-tidakada/sync", headers=auth(admin)).status_code == 404

    @pytest.mark.parametrize("status", ["pending", "expired", "cancelled", "failed"])
    def test_a_paid_order_at_the_gateway_is_applied_whatever_the_local_status(self, client, db, auth, admin, user, gateway, outbox, status):
        tx = old_tx(db, user, 30, status=status)
        res = self.sync(client, auth, admin, tx)
        data = res.json()
        assert res.status_code == 200 and data["applied"] is True and data["local_status"] == "paid"
        assert data["message"] == "Pembayaran dicatat berhasil; paket atau analisis pengguna sudah diterapkan dan invoice dikirim."
        assert fresh_user(db, user).tier == "middle" and len(invoices(outbox)) == 1
        assert invoices(outbox)[0]["to"] == user.email

    def test_the_method_from_the_gateway_is_saved(self, client, db, auth, admin, user, gateway):
        tx = make_tx(db, user, provider="midtrans")
        gateway.reply = {"transaction_status": "settlement", "gross_amount": "29000.00", "payment_type": "qris"}
        assert self.sync(client, auth, admin, tx).json()["local_method"] == "QRIS"

    def test_a_second_sync_applies_nothing_more(self, client, db, auth, admin, user, gateway, outbox):
        tx = make_tx(db, user, kind="pay_per_check", quantity=2, amount=10_000, provider="midtrans")
        gateway.reply = {"transaction_status": "settlement", "gross_amount": "10000.00"}
        assert self.sync(client, auth, admin, tx).json()["applied"] is True
        second = self.sync(client, auth, admin, tx).json()
        assert second["applied"] is False and second["message"] == "Sudah tercatat berhasil dan sesuai dengan Midtrans."
        assert fresh_user(db, user).extra_checks == 2 and len(invoices(outbox)) == 1

    def test_a_different_amount_is_not_applied(self, client, db, auth, admin, user, gateway, outbox):
        tx = make_tx(db, user, provider="midtrans")
        gateway.reply = {"transaction_status": "settlement", "gross_amount": "1000.00"}
        data = self.sync(client, auth, admin, tx).json()
        assert data["applied"] is False and "nominalnya berbeda" in data["message"]
        assert stored(db, tx).status == "pending" and fresh_user(db, user).tier == "free" and outbox == []

    def test_nothing_is_applied_when_the_gateway_has_no_payment(self, client, db, auth, admin, user, gateway):
        tx = old_tx(db, user, 1, status="expired")
        gateway.reply = {"transaction_status": "expire", "gross_amount": "29000.00"}
        data = self.sync(client, auth, admin, tx).json()
        assert data["applied"] is False and stored(db, tx).status == "expired"

    def test_a_gateway_failure_applies_nothing(self, client, db, auth, admin, user, gateway):
        tx = make_tx(db, user, provider="midtrans")
        gateway.error = payments.PaymentError("mati")
        data = self.sync(client, auth, admin, tx).json()
        assert data["applied"] is False and data["message"] == "Midtrans tidak merespons. Coba lagi sebentar lagi."

    def test_a_simulated_order_is_not_touched(self, client, db, auth, admin, user, gateway):
        tx = make_tx(db, user, provider="simulated")
        data = self.sync(client, auth, admin, tx).json()
        assert data["applied"] is False and stored(db, tx).status == "pending" and gateway.asked == []

    def test_the_reply_has_no_buyer_data(self, client, db, auth, admin, user, gateway):
        tx = make_tx(db, user, provider="midtrans")
        raw = self.sync(client, auth, admin, tx).text
        assert user.email not in raw and user.name not in raw and tx.va_number not in raw
