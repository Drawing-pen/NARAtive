import io
import json
import urllib.request
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.db import models
from app.services import email_templates, invoice, payments
from tests.test_billing import SERVER_KEY, checkout, fresh_user, make_tx, notification, pay

CLIENT_KEY = "SB-Mid-client-contoh"
SANDBOX = "https://app.sandbox.midtrans.com"
PRODUCTION = "https://app.midtrans.com"


@pytest.fixture
def user(make_user):
    return make_user("free")


def snap_checkout(client, auth, user, **body):
    body.setdefault("kind", "upgrade")
    if body["kind"] == "upgrade":
        body.setdefault("plan", "middle")
    return client.post("/billing/checkout", json=body, headers=auth(user))


@pytest.fixture
def midtrans(monkeypatch):
    monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)
    monkeypatch.setattr(settings, "midtrans_client_key", CLIENT_KEY)
    sent = []

    def fake(path, body=None, base=None):
        sent.append({"path": path, "body": body, "base": base})
        return fake.reply

    fake.reply = {"token": "tok-abc-123", "redirect_url": "https://app.sandbox.midtrans.com/snap/v4/redirection/tok-abc-123"}
    monkeypatch.setattr(payments, "_call", fake)
    return SimpleNamespace(sent=sent, fake=fake)


class TestCreateSnap:
    def test_without_a_server_key_a_local_token_is_made_with_no_request(self, monkeypatch):
        def refuse(req, timeout=None):
            raise AssertionError("tidak boleh ada permintaan keluar")

        monkeypatch.setattr(urllib.request, "urlopen", refuse)
        token = payments.create_snap("NAR-1-abc", 29000, "Paket Middle (30 hari)")
        assert token.startswith("SIM-") and len(token) == 4 + 16 and all(c in "0123456789abcdef" for c in token[4:])

    def test_the_gateway_gets_the_order_the_item_and_the_expiry(self, midtrans):
        token = payments.create_snap("NAR-1-abc", 29000, "Paket Middle (30 hari)")
        assert token == "tok-abc-123"
        [call] = midtrans.sent
        assert call["path"] == "/snap/v1/transactions" and call["base"] == SANDBOX
        body = call["body"]
        assert body["transaction_details"] == {"order_id": "NAR-1-abc", "gross_amount": 29000}
        assert body["item_details"] == [{"id": "item-1", "price": 29000, "quantity": 1, "name": "Paket Middle (30 hari)"}]
        assert body["expiry"] == {"unit": "hour", "duration": 24}

    def test_the_item_lines_add_up_to_the_amount(self, midtrans):
        payments.create_snap("NAR-1-abc", 15000, "Analisis tambahan (pay-per-check)", quantity=3)
        [item] = midtrans.sent[0]["body"]["item_details"]
        assert item["price"] == 5000 and item["quantity"] == 3 and item["price"] * item["quantity"] == 15000

    def test_no_personal_details_are_sent(self, midtrans):
        payments.create_snap("NAR-1-abc", 29000, "Paket Middle (30 hari)")
        body = midtrans.sent[0]["body"]
        assert "customer_details" not in body and "email" not in json.dumps(body).lower()

    def test_production_uses_the_production_host(self, midtrans, monkeypatch):
        monkeypatch.setattr(settings, "midtrans_is_production", True)
        payments.create_snap("NAR-1-abc", 29000, "x")
        assert midtrans.sent[0]["base"] == PRODUCTION

    def test_a_missing_client_key_makes_it_unavailable(self, midtrans, monkeypatch):
        monkeypatch.setattr(settings, "midtrans_client_key", "")
        with pytest.raises(payments.PaymentUnavailable):
            payments.create_snap("NAR-1-abc", 29000, "x")
        assert midtrans.sent == []

    def test_an_answer_without_a_token_is_an_error(self, midtrans):
        midtrans.fake.reply = {"error_messages": ["order_id sudah dipakai"]}
        with pytest.raises(payments.PaymentError):
            payments.create_snap("NAR-1-abc", 29000, "x")

    def test_it_is_unavailable_outside_localhost_without_a_server_key(self, monkeypatch):
        monkeypatch.setattr(settings, "midtrans_server_key", "")
        monkeypatch.setattr(settings, "cors_origins", "https://narative.example.com")
        with pytest.raises(payments.PaymentUnavailable):
            payments.create_snap("NAR-1-abc", 29000, "x")


class TestScriptAddress:
    def test_sandbox(self):
        assert payments.snap_script_url() == f"{SANDBOX}/snap/snap.js"

    def test_production(self, monkeypatch):
        monkeypatch.setattr(settings, "midtrans_is_production", True)
        assert payments.snap_script_url() == f"{PRODUCTION}/snap/snap.js"


class TestCallBase:
    def test_a_custom_base_is_used_for_the_request(self, monkeypatch):
        monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)
        seen = []

        def fake(req, timeout=None):
            seen.append(req.full_url)
            return io.BytesIO(b"{}")

        monkeypatch.setattr(urllib.request, "urlopen", fake)
        payments._call("/snap/v1/transactions", {}, base=SANDBOX)
        payments._call("/v2/charge", {})
        assert seen == [f"{SANDBOX}/snap/v1/transactions", "https://api.sandbox.midtrans.com/v2/charge"]


class TestMethodLabel:
    @pytest.mark.parametrize("payload,label", [
        ({"payment_type": "bank_transfer", "va_numbers": [{"bank": "bni", "va_number": "1"}]}, "Virtual Account BNI"),
        ({"payment_type": "bank_transfer", "permata_va_number": "8528"}, "Virtual Account PERMATA"),
        ({"payment_type": "bank_transfer"}, "Virtual Account"),
        ({"payment_type": "echannel"}, "Mandiri Bill"),
        ({"payment_type": "qris"}, "QRIS"),
        ({"payment_type": "gopay"}, "GoPay"),
        ({"payment_type": "shopeepay"}, "ShopeePay"),
        ({"payment_type": "credit_card"}, "Kartu kredit/debit"),
        ({"payment_type": "cstore", "store": "alfamart"}, "Gerai Alfamart"),
        ({"payment_type": "cstore"}, "Gerai"),
        ({"payment_type": "akulaku"}, "Akulaku"),
        ({"payment_type": "kredivo"}, "Kredivo"),
        ({"payment_type": "dana"}, "DANA"),
        ({"payment_type": "danamon_online"}, "Danamon Online"),
    ])
    def test_each_kind_has_a_readable_label(self, payload, label):
        assert payments.method_label(payload) == label

    @pytest.mark.parametrize("payload", [{}, {"payment_type": ""}, {"payment_type": None}])
    def test_no_kind_means_no_label(self, payload):
        assert payments.method_label(payload) is None


class TestCheckoutWithoutBank:
    def test_a_simulated_checkout_has_a_local_token_and_no_account_number(self, client, db, auth, user):
        res = snap_checkout(client, auth, user)
        assert res.status_code == 201
        body = res.json()
        assert body["bank"] is None and body["va_number"] is None and body["payment_method"] is None
        assert body["snap_token"].startswith("SIM-") and body["provider"] == "simulated" and body["status"] == "pending"
        assert body["amount"] == 29000 and body["kind"] == "upgrade" and body["plan"] == "middle"
        assert db.query(models.Transaction).count() == 1

    def test_the_payment_lasts_twenty_four_hours(self, client, db, auth, user):
        body = snap_checkout(client, auth, user).json()
        left = datetime.fromisoformat(body["expires_at"]) - datetime.fromisoformat(body["created_at"])
        assert left == timedelta(hours=24)

    def test_no_payment_instructions_email_is_sent(self, client, auth, user, outbox):
        snap_checkout(client, auth, user)
        assert outbox == []

    def test_extra_analyses_are_priced_by_quantity(self, client, auth, user):
        body = snap_checkout(client, auth, user, kind="pay_per_check", quantity=3).json()
        assert body["amount"] == 15000 and body["quantity"] == 3 and body["plan"] is None

    def test_the_tier_rules_still_apply(self, client, db, auth, make_user):
        high = make_user("high", expires_at=datetime.utcnow() + timedelta(days=10))
        assert snap_checkout(client, auth, high, plan="middle").status_code == 400
        assert snap_checkout(client, auth, high, kind="pay_per_check", quantity=1).status_code == 400
        assert db.query(models.Transaction).count() == 0

    def test_a_token_is_required(self, client):
        assert client.post("/billing/checkout", json={"kind": "upgrade", "plan": "middle"}).status_code == 401

    def test_an_unknown_bank_is_still_refused(self, client, auth, user):
        assert snap_checkout(client, auth, user, bank="mandiri").status_code == 422

    def test_a_checkout_with_a_bank_still_makes_a_virtual_account(self, client, auth, user):
        body = client.post("/billing/checkout", json={"kind": "upgrade", "plan": "middle", "bank": "bni"}, headers=auth(user)).json()
        assert body["bank"] == "bni" and body["va_number"].startswith("8810") and body["snap_token"] is None

    def test_unavailable_outside_localhost_without_a_server_key(self, client, db, auth, user, monkeypatch):
        monkeypatch.setattr(settings, "cors_origins", "https://narative.example.com")
        res = snap_checkout(client, auth, user)
        assert res.status_code == 503 and res.json()["detail"] == "Pembayaran belum tersedia."
        assert db.query(models.Transaction).count() == 0


class TestMidtransCheckoutWithoutBank:
    def test_the_token_from_the_gateway_is_saved(self, client, db, auth, user, midtrans):
        body = snap_checkout(client, auth, user, plan="high").json()
        assert body["snap_token"] == "tok-abc-123" and body["provider"] == "midtrans" and body["amount"] == 59000
        assert body["bank"] is None and body["va_number"] is None
        [call] = midtrans.sent
        assert call["body"]["transaction_details"] == {"order_id": body["order_id"], "gross_amount": 59000}
        assert call["body"]["item_details"][0]["name"] == "Paket High (30 hari)"

    def test_extra_analyses_name_and_quantity_reach_the_gateway(self, client, auth, user, midtrans):
        snap_checkout(client, auth, user, kind="pay_per_check", quantity=2)
        [item] = midtrans.sent[0]["body"]["item_details"]
        assert item["name"] == "Analisis tambahan (pay-per-check)" and item["quantity"] == 2 and item["price"] == 5000

    def test_no_client_key_means_unavailable_and_nothing_is_saved(self, client, db, auth, user, midtrans, monkeypatch):
        monkeypatch.setattr(settings, "midtrans_client_key", "")
        res = snap_checkout(client, auth, user)
        assert res.status_code == 503 and res.json()["detail"] == "Pembayaran belum tersedia."
        assert db.query(models.Transaction).count() == 0 and midtrans.sent == []

    def test_a_gateway_failure_is_reported_and_nothing_is_saved(self, client, db, auth, user, midtrans):
        midtrans.fake.reply = {"error_messages": ["gangguan"]}
        res = snap_checkout(client, auth, user)
        assert res.status_code == 502 and res.json()["detail"].startswith("Gagal membuat pembayaran.")
        assert db.query(models.Transaction).count() == 0

    def test_an_unreachable_gateway_is_reported(self, client, db, auth, user, midtrans, monkeypatch):
        def down(path, body=None, base=None):
            raise payments.PaymentError("Layanan pembayaran tidak merespons.")

        monkeypatch.setattr(payments, "_call", down)
        res = snap_checkout(client, auth, user)
        assert res.status_code == 502 and "Layanan pembayaran tidak merespons." in res.json()["detail"]
        assert db.query(models.Transaction).count() == 0

    def test_no_email_is_sent(self, client, auth, user, midtrans, outbox):
        snap_checkout(client, auth, user)
        assert outbox == []


class TestReuseOfPendingOrders:
    def two(self, client, auth, user, **body):
        first = snap_checkout(client, auth, user, **body)
        second = snap_checkout(client, auth, user, **body)
        return first, second

    def test_the_same_pending_order_is_returned_again_with_200(self, client, db, auth, user):
        first, second = self.two(client, auth, user)
        assert first.status_code == 201 and second.status_code == 200
        assert second.json()["order_id"] == first.json()["order_id"] and second.json()["snap_token"] == first.json()["snap_token"]
        assert db.query(models.Transaction).count() == 1

    def test_reuse_sends_no_email(self, client, auth, user, outbox):
        self.two(client, auth, user)
        assert outbox == []

    def test_a_different_plan_makes_a_new_order(self, client, db, auth, user):
        a = snap_checkout(client, auth, user, plan="middle")
        b = snap_checkout(client, auth, user, plan="high")
        assert b.status_code == 201 and a.json()["order_id"] != b.json()["order_id"] and db.query(models.Transaction).count() == 2

    def test_a_different_quantity_makes_a_new_order(self, client, db, auth, user):
        a = snap_checkout(client, auth, user, kind="pay_per_check", quantity=1)
        b = snap_checkout(client, auth, user, kind="pay_per_check", quantity=3)
        assert b.status_code == 201 and a.json()["order_id"] != b.json()["order_id"]

    def test_the_same_quantity_of_extra_analyses_is_reused(self, client, db, auth, user):
        first, second = self.two(client, auth, user, kind="pay_per_check", quantity=3)
        assert second.status_code == 200 and second.json()["order_id"] == first.json()["order_id"]

    def test_a_different_kind_makes_a_new_order(self, client, auth, user):
        a = snap_checkout(client, auth, user)
        b = snap_checkout(client, auth, user, kind="pay_per_check", quantity=1)
        assert b.status_code == 201 and a.json()["order_id"] != b.json()["order_id"]

    def test_an_overdue_order_is_not_reused(self, client, db, auth, user):
        first = snap_checkout(client, auth, user).json()
        row = db.query(models.Transaction).one()
        row.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
        second = snap_checkout(client, auth, user)
        assert second.status_code == 201 and second.json()["order_id"] != first["order_id"]

    @pytest.mark.parametrize("status", ["paid", "cancelled", "expired", "failed"])
    def test_a_finished_order_is_not_reused(self, client, db, auth, user, status):
        first = snap_checkout(client, auth, user).json()
        row = db.query(models.Transaction).one()
        row.status = status
        db.commit()
        second = snap_checkout(client, auth, user)
        assert second.status_code == 201 and second.json()["order_id"] != first["order_id"]

    def test_an_old_virtual_account_order_is_not_reused(self, client, auth, user):
        old = client.post("/billing/checkout", json={"kind": "upgrade", "plan": "middle", "bank": "bca"}, headers=auth(user)).json()
        new = snap_checkout(client, auth, user)
        assert new.status_code == 201 and new.json()["order_id"] != old["order_id"]

    def test_someone_elses_order_is_never_reused(self, client, auth, make_user, user):
        mine = snap_checkout(client, auth, user).json()
        theirs = snap_checkout(client, auth, make_user("free"))
        assert theirs.status_code == 201 and theirs.json()["order_id"] != mine["order_id"]

    def test_an_order_made_in_simulation_is_not_reused_once_midtrans_is_on(self, client, auth, user, monkeypatch):
        first = snap_checkout(client, auth, user).json()
        monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)
        monkeypatch.setattr(settings, "midtrans_client_key", CLIENT_KEY)
        monkeypatch.setattr(payments, "_call", lambda path, body=None, base=None: {"token": "tok-baru"})
        second = snap_checkout(client, auth, user)
        assert second.status_code == 201 and second.json()["order_id"] != first["order_id"] and second.json()["snap_token"] == "tok-baru"

    def test_with_midtrans_a_still_pending_order_is_reused_without_a_second_snap_call(self, client, auth, user, midtrans, monkeypatch):
        monkeypatch.setattr(payments, "fetch_status", lambda order_id: {"transaction_status": "pending", "gross_amount": "29000.00"})
        first, second = self.two(client, auth, user)
        assert second.status_code == 200 and second.json()["order_id"] == first.json()["order_id"] and len(midtrans.sent) == 1

    def test_with_midtrans_an_order_already_paid_at_the_gateway_is_settled_not_reused(self, client, db, auth, user, midtrans, monkeypatch):
        first = snap_checkout(client, auth, user).json()
        monkeypatch.setattr(payments, "fetch_status", lambda order_id: {"transaction_status": "settlement", "gross_amount": "29000.00", "payment_type": "qris"})
        second = snap_checkout(client, auth, user)
        assert second.status_code == 201 and second.json()["order_id"] != first["order_id"]
        db.expire_all()
        assert db.query(models.Transaction).filter_by(order_id=first["order_id"]).one().status == "paid"
        assert fresh_user(db, user).tier == "middle"


class TestOverview:
    def test_it_carries_the_client_key_and_script_in_midtrans_mode(self, client, auth, user, midtrans):
        body = client.get("/billing/overview", headers=auth(user)).json()
        assert body["provider"] == "midtrans" and body["snap_client_key"] == CLIENT_KEY and body["snap_script_url"] == f"{SANDBOX}/snap/snap.js"

    def test_it_never_exposes_the_server_key(self, client, auth, user, midtrans):
        assert SERVER_KEY not in client.get("/billing/overview", headers=auth(user)).text

    def test_without_a_client_key_both_are_null(self, client, auth, user, midtrans, monkeypatch):
        monkeypatch.setattr(settings, "midtrans_client_key", "")
        body = client.get("/billing/overview", headers=auth(user)).json()
        assert body["snap_client_key"] is None and body["snap_script_url"] is None

    def test_in_simulation_both_are_null(self, client, auth, user):
        body = client.get("/billing/overview", headers=auth(user)).json()
        assert body["provider"] == "simulated" and body["snap_client_key"] is None and body["snap_script_url"] is None


class TestSimulatedPaymentMethod:
    def order(self, client, auth, user):
        return snap_checkout(client, auth, user).json()["order_id"]

    @pytest.mark.parametrize("key,label", [
        ("bca", "Virtual Account BCA"), ("bni", "Virtual Account BNI"), ("bri", "Virtual Account BRI"),
        ("permata", "Virtual Account PERMATA"), ("qris", "QRIS"), ("gopay", "GoPay"),
    ])
    def test_the_chosen_method_is_saved_and_the_order_is_paid(self, client, db, auth, user, key, label):
        order = self.order(client, auth, user)
        res = client.post(f"/billing/transactions/{order}/simulate-pay", json={"method": key}, headers=auth(user))
        assert res.status_code == 200 and res.json()["status"] == "paid" and res.json()["payment_method"] == label
        assert fresh_user(db, user).tier == "middle"

    def test_without_a_body_the_default_is_bca(self, client, auth, user):
        order = self.order(client, auth, user)
        assert pay(client, auth, user, order).json()["payment_method"] == "Virtual Account BCA"

    def test_an_unknown_method_is_refused(self, client, db, auth, user):
        order = self.order(client, auth, user)
        res = client.post(f"/billing/transactions/{order}/simulate-pay", json={"method": "bitcoin"}, headers=auth(user))
        assert res.status_code == 422
        db.expire_all()
        assert db.query(models.Transaction).one().status == "pending"

    def test_an_old_virtual_account_order_keeps_no_method_and_falls_back_to_its_bank(self, client, db, auth, user):
        tx = make_tx(db, user)
        res = pay(client, auth, user, tx.order_id)
        assert res.json()["payment_method"] is None
        assert client.get(f"/billing/transactions/{tx.order_id}/invoice", headers=auth(user)).json()["method"] == "Virtual Account BCA"

    def test_the_invoice_shows_the_chosen_method(self, client, auth, user):
        order = self.order(client, auth, user)
        client.post(f"/billing/transactions/{order}/simulate-pay", json={"method": "qris"}, headers=auth(user))
        assert client.get(f"/billing/transactions/{order}/invoice", headers=auth(user)).json()["method"] == "QRIS"

    def test_the_invoice_email_names_the_method_and_has_no_account_number(self, client, auth, user, outbox):
        order = self.order(client, auth, user)
        client.post(f"/billing/transactions/{order}/simulate-pay", json={"method": "gopay"}, headers=auth(user))
        [mail] = [m for m in outbox if m["subject"].startswith("Invoice")]
        assert "GoPay" in mail["body"] and "Virtual Account" not in mail["body"]


class TestMethodFromTheGateway:
    @pytest.fixture(autouse=True)
    def configured(self, monkeypatch, outbox):
        monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)

    def webhook(self, client, payload):
        return client.post("/billing/midtrans/notification", json=payload)

    def stored(self, db, tx):
        db.expire_all()
        return db.get(models.Transaction, tx.id)

    def test_a_settlement_saves_the_method(self, client, db, user):
        tx = make_tx(db, user, provider="midtrans")
        self.webhook(client, notification(tx.order_id, "settlement", payment_type="qris"))
        assert self.stored(db, tx).payment_method == "QRIS"

    def test_a_bank_transfer_settlement_names_the_bank(self, client, db, user):
        tx = make_tx(db, user, provider="midtrans")
        self.webhook(client, notification(tx.order_id, "settlement", payment_type="bank_transfer", va_numbers=[{"bank": "bri", "va_number": "9"}]))
        assert self.stored(db, tx).payment_method == "Virtual Account BRI"

    def test_a_settlement_without_a_kind_leaves_the_method_empty(self, client, db, user):
        tx = make_tx(db, user, provider="midtrans")
        self.webhook(client, notification(tx.order_id, "settlement"))
        assert self.stored(db, tx).payment_method is None

    def test_a_pending_notification_does_not_set_the_method(self, client, db, user):
        tx = make_tx(db, user, provider="midtrans")
        self.webhook(client, notification(tx.order_id, "pending", payment_type="gopay"))
        assert self.stored(db, tx).payment_method is None

    def test_a_repeated_settlement_keeps_the_first_method(self, client, db, user):
        tx = make_tx(db, user, provider="midtrans")
        self.webhook(client, notification(tx.order_id, "settlement", payment_type="qris"))
        self.webhook(client, notification(tx.order_id, "settlement", payment_type="gopay"))
        assert self.stored(db, tx).payment_method == "QRIS"

    def test_reading_the_status_also_saves_the_method(self, client, db, auth, user, monkeypatch):
        tx = make_tx(db, user, provider="midtrans", amount=29000)
        monkeypatch.setattr(payments, "fetch_status", lambda order_id: {"transaction_status": "settlement", "gross_amount": "29000", "payment_type": "gopay"})
        res = client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user))
        assert res.json()["status"] == "paid" and res.json()["payment_method"] == "GoPay"


class TestMethodLabelOnInvoices:
    def tx(self, **kw):
        base = dict(bank=None, payment_method=None)
        return SimpleNamespace(**{**base, **kw})

    def test_the_stored_method_wins(self):
        assert invoice.method_label(self.tx(bank="bca", payment_method="QRIS")) == "QRIS"

    def test_the_bank_is_the_fallback(self):
        assert invoice.method_label(self.tx(bank="bni")) == "Virtual Account BNI"

    def test_with_neither_it_says_online_payment(self):
        assert invoice.method_label(self.tx()) == "Pembayaran online"

    def test_the_email_invoice_works_for_an_order_without_a_bank(self, db, user):
        tx = make_tx(db, user, status="paid")
        tx.bank, tx.va_number, tx.payment_method, tx.paid_at = None, None, "GoPay", datetime(2026, 10, 28, 3, 30)
        mail = email_templates.invoice(user, tx)
        assert "GoPay" in mail.text and "None" not in mail.text


class TestTransactionOutput:
    def test_the_new_fields_are_present(self, client, auth, user):
        order = snap_checkout(client, auth, user).json()["order_id"]
        body = client.get(f"/billing/transactions/{order}", headers=auth(user)).json()
        assert {"snap_token", "payment_method", "bank", "va_number"} <= set(body)

    def test_an_old_order_keeps_its_bank_and_number(self, client, db, auth, user):
        tx = make_tx(db, user)
        body = client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user)).json()
        assert body["bank"] == "bca" and body["va_number"] == "3935800000000001" and body["snap_token"] is None
