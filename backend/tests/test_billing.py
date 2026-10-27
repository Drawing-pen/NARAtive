import hashlib
import io
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.db import models
from app.services import billing, payments

SERVER_KEY = "SB-Mid-server-rahasia"


def future(days=10):
    return datetime.utcnow() + timedelta(days=days)


def past(days=1):
    return datetime.utcnow() - timedelta(days=days)


def checkout(client, auth, user, **body):
    body.setdefault("kind", "upgrade")
    body.setdefault("bank", "bca")
    if body["kind"] == "upgrade":
        body.setdefault("plan", "middle")
    return client.post("/billing/checkout", json=body, headers=auth(user))


def pay(client, auth, user, order_id):
    return client.post(f"/billing/transactions/{order_id}/simulate-pay", headers=auth(user))


def fresh_user(db, user):
    db.expire_all()
    return db.get(models.User, user.id)


def make_tx(db, user, kind="upgrade", plan="middle", quantity=1, amount=None, provider="simulated", status="pending", expires_at=None, order_id=None):
    tx = models.Transaction(
        user_id=user.id, order_id=order_id or f"NAR-{user.id}-{abs(hash((kind, plan, quantity, provider, status))) % 10**10:010d}",
        kind=kind, plan=plan if kind == "upgrade" else None, quantity=quantity,
        amount=amount if amount is not None else (29000 if kind == "upgrade" else 5000 * quantity),
        bank="bca", va_number="3935800000000001", provider=provider, status=status,
        created_at=datetime.utcnow(), expires_at=expires_at or future(1),
    )
    db.add(tx)
    db.commit()
    return tx


class TestOverview:
    def test_a_standard_user_sees_limits_and_prices(self, client, auth, make_user):
        user = make_user("free")
        body = client.get("/billing/overview", headers=auth(user)).json()
        assert body["tier"] == "free" and body["paid_tier"] == "free" and body["tier_expires_at"] is None
        usage = body["usage"]
        assert (usage["used"], usage["monthly_limit"], usage["extra_checks"]) == (0, 3, 0)
        assert (usage["active_books"], usage["max_active"], usage["max_pages"]) == (0, 3, 50)
        assert body["upgrade_prices"] == {"middle": 29000, "high": 59000}
        assert body["period_days"] == 30 and body["pay_per_check_price"] == 5000 and body["pay_per_check_max"] == 10
        assert body["banks"] == ["bca", "bni", "bri", "permata"]
        assert body["provider"] == "simulated"

    def test_usage_reflects_books_and_analyses(self, client, db, auth, make_user, make_doc):
        user = make_user("free", extra_checks=2)
        make_doc(user)
        db.add(models.UsageQuota(user_id=user.id, period=billing.current_period(), used=2))
        db.commit()
        usage = client.get("/billing/overview", headers=auth(user)).json()["usage"]
        assert (usage["used"], usage["active_books"], usage["extra_checks"]) == (2, 1, 2)

    def test_high_has_no_limits(self, client, auth, make_user):
        user = make_user("high", expires_at=future())
        body = client.get("/billing/overview", headers=auth(user)).json()
        assert body["tier"] == "high" and body["tier_expires_at"] is not None
        assert body["usage"]["monthly_limit"] is None and body["usage"]["max_pages"] is None and body["usage"]["max_active"] is None

    def test_an_expired_subscription_is_shown_as_standard(self, client, auth, make_user):
        user = make_user("middle", expires_at=past())
        body = client.get("/billing/overview", headers=auth(user)).json()
        assert body["tier"] == "free" and body["paid_tier"] == "free" and body["tier_expires_at"] is None

    def test_developer_unlock_shows_the_difference(self, client, auth, make_user, monkeypatch):
        monkeypatch.setattr(settings, "dev_unlock_all_tiers", True)
        body = client.get("/billing/overview", headers=auth(make_user("free"))).json()
        assert body["tier"] == "high" and body["paid_tier"] == "free"

    def test_it_requires_login(self, client):
        assert client.get("/billing/overview").status_code == 401


class TestCheckout:
    def test_an_upgrade_creates_a_pending_virtual_account(self, client, auth, make_user):
        user = make_user("free")
        res = checkout(client, auth, user)
        assert res.status_code == 201
        body = res.json()
        assert re.fullmatch(rf"NAR-{user.id}-[0-9a-f]{{10}}", body["order_id"])
        assert (body["kind"], body["plan"], body["quantity"], body["amount"]) == ("upgrade", "middle", 1, 29000)
        assert (body["bank"], body["provider"], body["status"], body["paid_at"]) == ("bca", "simulated", "pending", None)
        assert re.fullmatch(r"\d{16}", body["va_number"])
        lifetime = datetime.fromisoformat(body["expires_at"]) - datetime.fromisoformat(body["created_at"])
        assert timedelta(hours=23, minutes=59) < lifetime < timedelta(hours=24, minutes=1)

    @pytest.mark.parametrize("bank, prefix", [("bca", "39358"), ("bni", "8810"), ("bri", "26215"), ("permata", "8528")])
    def test_each_bank_has_its_own_number_prefix(self, client, auth, make_user, bank, prefix):
        body = checkout(client, auth, make_user("free"), bank=bank).json()
        assert body["bank"] == bank and body["va_number"].startswith(prefix) and len(body["va_number"]) == 16

    def test_the_price_depends_on_the_plan(self, client, auth, make_user):
        user = make_user("free")
        assert checkout(client, auth, user, plan="middle").json()["amount"] == 29000
        assert checkout(client, auth, user, plan="high").json()["amount"] == 59000

    def test_extra_analyses_cost_5000_each(self, client, auth, make_user):
        body = checkout(client, auth, make_user("free"), kind="pay_per_check", quantity=3).json()
        assert (body["kind"], body["plan"], body["quantity"], body["amount"]) == ("pay_per_check", None, 3, 15000)

    def test_a_plan_sent_with_extra_analyses_is_ignored(self, client, auth, make_user):
        body = checkout(client, auth, make_user("free"), kind="pay_per_check", plan="high", quantity=2).json()
        assert body["plan"] is None and body["amount"] == 10000

    def test_a_quantity_sent_with_an_upgrade_is_ignored(self, client, auth, make_user):
        body = checkout(client, auth, make_user("free"), quantity=5).json()
        assert body["quantity"] == 1 and body["amount"] == 29000

    def test_nothing_changes_for_the_user_until_payment(self, client, db, auth, make_user):
        user = make_user("free")
        checkout(client, auth, user)
        checkout(client, auth, user, kind="pay_per_check", quantity=2)
        fresh = fresh_user(db, user)
        assert fresh.tier == "free" and fresh.extra_checks == 0

    @pytest.mark.parametrize(
        "body",
        [
            {"kind": "hadiah", "bank": "bca"},
            {"kind": "upgrade", "bank": "bca"},
            {"kind": "upgrade", "plan": "free", "bank": "bca"},
            {"kind": "upgrade", "plan": "middle", "bank": "mandiri"},
            {"kind": "pay_per_check", "quantity": 0, "bank": "bca"},
            {"kind": "pay_per_check", "quantity": 11, "bank": "bca"},
            {"kind": "pay_per_check", "bank": "cimb"},
        ],
    )
    def test_invalid_orders_are_rejected(self, client, auth, make_user, body):
        assert client.post("/billing/checkout", json=body, headers=auth(make_user("free"))).status_code == 422

    def test_ten_extra_analyses_are_the_maximum(self, client, auth, make_user):
        assert checkout(client, auth, make_user("free"), kind="pay_per_check", quantity=10).json()["amount"] == 50000

    def test_checkout_requires_login(self, client):
        assert client.post("/billing/checkout", json={"kind": "upgrade", "plan": "middle", "bank": "bca"}).status_code == 401

    def test_a_user_cannot_buy_a_lower_plan_than_the_one_in_force(self, client, auth, make_user):
        user = make_user("high", expires_at=future())
        res = checkout(client, auth, user, plan="middle")
        assert res.status_code == 400
        assert res.json()["detail"] == "Kamu sudah memakai paket yang lebih tinggi."

    def test_renewing_the_same_plan_and_upgrading_are_allowed(self, client, auth, make_user):
        middle = make_user("middle", expires_at=future())
        assert checkout(client, auth, middle, plan="middle").status_code == 201
        assert checkout(client, auth, middle, plan="high").status_code == 201
        high = make_user("high", expires_at=future())
        assert checkout(client, auth, high, plan="high").status_code == 201

    def test_an_expired_subscription_can_buy_any_plan_again(self, client, auth, make_user):
        user = make_user("high", expires_at=past())
        assert checkout(client, auth, user, plan="middle").status_code == 201

    def test_high_cannot_buy_extra_analyses(self, client, auth, make_user):
        user = make_user("high", expires_at=future())
        res = checkout(client, auth, user, kind="pay_per_check", quantity=1)
        assert res.status_code == 400
        assert res.json()["detail"] == "Paket High tanpa batas analisis, tidak perlu membeli analisis tambahan."

    def test_other_tiers_can_buy_extra_analyses(self, client, auth, make_user):
        for tier in ("free", "middle"):
            user = make_user(tier, expires_at=future() if tier != "free" else None)
            assert checkout(client, auth, user, kind="pay_per_check", quantity=1).status_code == 201


class TestPaying:
    def test_paying_an_upgrade_activates_the_plan_for_thirty_days(self, client, db, auth, make_user, outbox):
        user = make_user("free")
        order = checkout(client, auth, user).json()["order_id"]
        res = pay(client, auth, user, order)
        assert res.status_code == 200 and res.json()["status"] == "paid" and res.json()["paid_at"] is not None
        fresh = fresh_user(db, user)
        assert fresh.tier == "middle"
        assert timedelta(days=29, hours=23) < fresh.tier_expires_at - datetime.utcnow() < timedelta(days=30, minutes=1)

    def test_the_account_shows_the_new_tier_everywhere(self, client, auth, make_user, outbox):
        user = make_user("free")
        pay(client, auth, user, checkout(client, auth, user).json()["order_id"])
        assert client.get("/auth/me", headers=auth(user)).json()["tier"] == "middle"
        overview = client.get("/billing/overview", headers=auth(user)).json()
        assert overview["tier"] == "middle" and overview["usage"]["monthly_limit"] == 15 and overview["usage"]["max_pages"] == 300

    def test_renewing_while_active_adds_thirty_days_to_the_end_date(self, client, db, auth, make_user, outbox):
        end = future(10)
        user = make_user("middle", expires_at=end)
        pay(client, auth, user, checkout(client, auth, user, plan="middle").json()["order_id"])
        assert fresh_user(db, user).tier_expires_at == end + timedelta(days=30)

    def test_renewing_after_it_ended_starts_from_now(self, client, db, auth, make_user, outbox):
        user = make_user("middle", expires_at=past(5))
        pay(client, auth, user, checkout(client, auth, user, plan="middle").json()["order_id"])
        left = fresh_user(db, user).tier_expires_at - datetime.utcnow()
        assert timedelta(days=29, hours=23) < left < timedelta(days=30, minutes=1)

    def test_upgrading_to_a_higher_plan_keeps_the_remaining_days(self, client, db, auth, make_user, outbox):
        end = future(20)
        user = make_user("middle", expires_at=end)
        pay(client, auth, user, checkout(client, auth, user, plan="high").json()["order_id"])
        fresh = fresh_user(db, user)
        assert fresh.tier == "high" and fresh.tier_expires_at == end + timedelta(days=30)

    def test_upgrading_after_the_old_plan_ended_starts_from_now(self, client, db, auth, make_user, outbox):
        user = make_user("middle", expires_at=past(3))
        pay(client, auth, user, checkout(client, auth, user, plan="high").json()["order_id"])
        left = fresh_user(db, user).tier_expires_at - datetime.utcnow()
        assert timedelta(days=29, hours=23) < left < timedelta(days=30, minutes=1)

    def test_paying_for_extra_analyses_adds_them_without_changing_the_tier(self, client, db, auth, make_user, outbox):
        user = make_user("free", extra_checks=1)
        pay(client, auth, user, checkout(client, auth, user, kind="pay_per_check", quantity=3).json()["order_id"])
        fresh = fresh_user(db, user)
        assert fresh.extra_checks == 4 and fresh.tier == "free" and fresh.tier_expires_at is None

    def test_the_invoice_is_emailed_with_the_order_details(self, client, auth, make_user, outbox):
        user = make_user("free")
        order = checkout(client, auth, user, bank="bni").json()
        pay(client, auth, user, order["order_id"])
        [mail] = outbox
        assert mail["to"] == user.email and mail["subject"] == f"Invoice NARAtive {order['order_id']}"
        for fragment in (order["order_id"], "Paket Middle (30 hari)", "Rp 29.000", f"BNI {order['va_number']}", "Aktif sampai"):
            assert fragment in mail["body"]

    def test_the_invoice_for_extra_analyses_has_no_end_date(self, client, auth, make_user, outbox):
        user = make_user("free")
        pay(client, auth, user, checkout(client, auth, user, kind="pay_per_check", quantity=3).json()["order_id"])
        body = outbox[0]["body"]
        assert "3 analisis tambahan (pay-per-check)" in body and "Rp 15.000" in body and "Aktif sampai" not in body

    def test_a_paid_order_cannot_be_paid_again(self, client, db, auth, make_user, outbox):
        user = make_user("free")
        order = checkout(client, auth, user, kind="pay_per_check", quantity=2).json()["order_id"]
        pay(client, auth, user, order)
        res = pay(client, auth, user, order)
        assert res.status_code == 409 and res.json()["detail"] == "Pembayaran ini sudah tidak menunggu."
        assert fresh_user(db, user).extra_checks == 2 and len(outbox) == 1

    def test_settling_twice_in_the_service_applies_it_only_once(self, db, make_user, outbox):
        user = make_user("free")
        tx = make_tx(db, user, kind="pay_per_check", quantity=2)
        billing.settle(db, tx)
        billing.settle(db, tx)
        assert fresh_user(db, user).extra_checks == 2 and len(outbox) == 1

    def test_another_users_order_cannot_be_paid(self, client, db, auth, make_user, outbox):
        owner, stranger = make_user("free"), make_user("free")
        order = checkout(client, auth, owner).json()["order_id"]
        res = pay(client, auth, stranger, order)
        assert res.status_code == 404 and res.json()["detail"] == "Transaksi tidak ditemukan."
        assert fresh_user(db, owner).tier == "free"

    def test_unknown_orders_are_not_found(self, client, auth, make_user):
        assert pay(client, auth, make_user("free"), "NAR-0-tidakada").status_code == 404

    def test_simulation_is_refused_when_midtrans_is_configured(self, client, db, auth, make_user, monkeypatch, outbox):
        user = make_user("free")
        order = checkout(client, auth, user).json()["order_id"]
        monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)
        res = pay(client, auth, user, order)
        assert res.status_code == 403 and res.json()["detail"] == "Simulasi pembayaran tidak tersedia."
        assert fresh_user(db, user).tier == "free"

    def test_midtrans_orders_cannot_be_simulated(self, client, db, auth, make_user, outbox):
        user = make_user("free")
        tx = make_tx(db, user, provider="midtrans")
        assert pay(client, auth, user, tx.order_id).status_code == 403

    def test_an_order_past_its_deadline_expires_and_cannot_be_paid(self, client, db, auth, make_user, outbox):
        user = make_user("free")
        tx = make_tx(db, user, expires_at=past())
        res = pay(client, auth, user, tx.order_id)
        assert res.status_code == 409
        assert client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user)).json()["status"] == "expired"
        assert fresh_user(db, user).tier == "free"


class TestHistory:
    def test_orders_are_listed_newest_first_and_only_the_users_own(self, client, db, auth, make_user):
        mine, other = make_user("free"), make_user("free")
        first = checkout(client, auth, mine).json()["order_id"]
        second = checkout(client, auth, mine, plan="high").json()["order_id"]
        checkout(client, auth, other)
        listed = client.get("/billing/transactions", headers=auth(mine)).json()
        assert [t["order_id"] for t in listed] == [second, first]

    def test_an_empty_history_is_an_empty_list(self, client, auth, make_user):
        assert client.get("/billing/transactions", headers=auth(make_user("free"))).json() == []

    def test_overdue_orders_show_as_expired_in_the_list(self, client, db, auth, make_user):
        user = make_user("free")
        make_tx(db, user, expires_at=past())
        assert client.get("/billing/transactions", headers=auth(user)).json()[0]["status"] == "expired"

    def test_one_order_can_be_read_by_its_owner_only(self, client, auth, make_user):
        owner, stranger = make_user("free"), make_user("free")
        order = checkout(client, auth, owner).json()["order_id"]
        assert client.get(f"/billing/transactions/{order}", headers=auth(owner)).status_code == 200
        res = client.get(f"/billing/transactions/{order}", headers=auth(stranger))
        assert res.status_code == 404 and res.json()["detail"] == "Transaksi tidak ditemukan."

    def test_history_requires_login(self, client):
        assert client.get("/billing/transactions").status_code == 401


class TestCancelling:
    def test_a_waiting_order_can_be_cancelled(self, client, db, auth, make_user, outbox):
        user = make_user("free")
        order = checkout(client, auth, user).json()["order_id"]
        res = client.post(f"/billing/transactions/{order}/cancel", headers=auth(user))
        assert res.status_code == 200 and res.json()["status"] == "cancelled"
        assert pay(client, auth, user, order).status_code == 409
        assert fresh_user(db, user).tier == "free"

    def test_only_waiting_orders_can_be_cancelled(self, client, auth, make_user, outbox):
        user = make_user("free")
        order = checkout(client, auth, user).json()["order_id"]
        pay(client, auth, user, order)
        res = client.post(f"/billing/transactions/{order}/cancel", headers=auth(user))
        assert res.status_code == 409
        assert res.json()["detail"] == "Hanya pembayaran yang masih menunggu yang bisa dibatalkan."

    def test_cancelling_twice_is_refused(self, client, auth, make_user):
        user = make_user("free")
        order = checkout(client, auth, user).json()["order_id"]
        client.post(f"/billing/transactions/{order}/cancel", headers=auth(user))
        assert client.post(f"/billing/transactions/{order}/cancel", headers=auth(user)).status_code == 409

    def test_another_users_order_cannot_be_cancelled(self, client, auth, make_user):
        owner, stranger = make_user("free"), make_user("free")
        order = checkout(client, auth, owner).json()["order_id"]
        assert client.post(f"/billing/transactions/{order}/cancel", headers=auth(stranger)).status_code == 404

    def test_cancelling_a_midtrans_order_cancels_it_at_the_gateway_too(self, client, db, auth, make_user, monkeypatch):
        user = make_user("free")
        tx = make_tx(db, user, provider="midtrans")
        monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)
        calls = []
        monkeypatch.setattr(payments, "_call", lambda path, body=None: calls.append(path) or {})
        res = client.post(f"/billing/transactions/{tx.order_id}/cancel", headers=auth(user))
        assert res.status_code == 200 and calls == [f"/v2/{tx.order_id}/cancel"]

    def test_a_gateway_failure_does_not_stop_the_cancellation(self, client, db, auth, make_user, monkeypatch):
        user = make_user("free")
        tx = make_tx(db, user, provider="midtrans")
        monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)

        def broken(path, body=None):
            raise payments.PaymentError("mati")

        monkeypatch.setattr(payments, "_call", broken)
        res = client.post(f"/billing/transactions/{tx.order_id}/cancel", headers=auth(user))
        assert res.status_code == 200 and res.json()["status"] == "cancelled"


class TestMidtransCheckout:
    @pytest.fixture(autouse=True)
    def configured(self, monkeypatch):
        monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)
        self.sent = []

    def gateway(self, monkeypatch, response):
        def fake(path, body=None):
            self.sent.append((path, body))
            if isinstance(response, Exception):
                raise response
            return response

        monkeypatch.setattr(payments, "_call", fake)

    def test_the_provider_becomes_midtrans(self, client, auth, make_user):
        assert client.get("/billing/overview", headers=auth(make_user("free"))).json()["provider"] == "midtrans"

    def test_the_virtual_account_is_requested_from_the_gateway(self, client, auth, make_user, monkeypatch):
        self.gateway(monkeypatch, {"status_code": "201", "va_numbers": [{"bank": "bca", "va_number": "123456789012"}]})
        body = checkout(client, auth, make_user("free"), plan="high").json()
        assert body["va_number"] == "123456789012" and body["provider"] == "midtrans"
        [(path, sent)] = self.sent
        assert path == "/v2/charge"
        assert sent["payment_type"] == "bank_transfer" and sent["bank_transfer"] == {"bank": "bca"}
        assert sent["transaction_details"] == {"order_id": body["order_id"], "gross_amount": 59000}
        assert sent["custom_expiry"] == {"expiry_duration": 24, "unit": "hour"}

    def test_permata_uses_its_own_field(self, client, auth, make_user, monkeypatch):
        self.gateway(monkeypatch, {"status_code": "201", "permata_va_number": "8528000011112222"})
        body = checkout(client, auth, make_user("free"), bank="permata").json()
        assert body["va_number"] == "8528000011112222"

    def test_a_refusal_from_the_gateway_is_reported_and_nothing_is_saved(self, client, db, auth, make_user, monkeypatch):
        self.gateway(monkeypatch, {"status_code": "400", "status_message": "Bank sedang gangguan"})
        res = checkout(client, auth, make_user("free"))
        assert res.status_code == 502 and res.json()["detail"] == "Gagal membuat Virtual Account. Bank sedang gangguan"
        assert db.query(models.Transaction).count() == 0

    def test_a_missing_number_is_reported(self, client, auth, make_user, monkeypatch):
        self.gateway(monkeypatch, {"status_code": "201", "va_numbers": []})
        res = checkout(client, auth, make_user("free"))
        assert res.status_code == 502 and "Nomor Virtual Account tidak diterima" in res.json()["detail"]

    def test_an_unreachable_gateway_is_reported(self, client, db, auth, make_user, monkeypatch):
        self.gateway(monkeypatch, payments.PaymentError("Layanan pembayaran tidak merespons."))
        res = checkout(client, auth, make_user("free"))
        assert res.status_code == 502 and "Layanan pembayaran tidak merespons." in res.json()["detail"]
        assert db.query(models.Transaction).count() == 0


class TestGatewayClient:
    @pytest.fixture(autouse=True)
    def configured(self, monkeypatch):
        monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)
        self.requests = []

    def serve(self, monkeypatch, payload=None, error=None):
        def fake(req, timeout=None):
            self.requests.append(req)
            if error:
                raise error
            return io.BytesIO(json.dumps(payload or {}).encode())

        monkeypatch.setattr(urllib.request, "urlopen", fake)

    def test_requests_go_to_the_sandbox_by_default_with_basic_authentication(self, monkeypatch):
        self.serve(monkeypatch, {"status_code": "200"})
        payments._call("/v2/charge", {"a": 1})
        [req] = self.requests
        assert req.full_url == "https://api.sandbox.midtrans.com/v2/charge"
        import base64
        assert req.get_header("Authorization") == "Basic " + base64.b64encode(f"{SERVER_KEY}:".encode()).decode()
        assert req.get_header("Content-type") == "application/json" and json.loads(req.data) == {"a": 1}

    def test_production_mode_uses_the_production_host(self, monkeypatch):
        monkeypatch.setattr(settings, "midtrans_is_production", True)
        self.serve(monkeypatch, {})
        payments._call("/v2/x")
        assert self.requests[0].full_url == "https://api.midtrans.com/v2/x"

    def test_network_failures_become_payment_errors(self, monkeypatch):
        self.serve(monkeypatch, error=urllib.error.URLError("putus"))
        with pytest.raises(payments.PaymentError) as err:
            payments._call("/v2/charge", {})
        assert str(err.value) == "Layanan pembayaran tidak merespons."

    def test_the_server_key_is_never_part_of_the_error(self, monkeypatch):
        self.serve(monkeypatch, error=urllib.error.URLError(f"gagal {SERVER_KEY}"))
        with pytest.raises(payments.PaymentError) as err:
            payments._call("/v2/charge", {})
        assert SERVER_KEY not in str(err.value)

    def test_without_a_key_the_virtual_account_is_generated_locally(self, monkeypatch):
        monkeypatch.setattr(settings, "midtrans_server_key", "")
        self.serve(monkeypatch, error=AssertionError("tidak boleh ada permintaan keluar"))
        va = payments.create_va("NAR-1-abc", 29000, "bri")
        assert va.startswith("26215") and len(va) == 16 and va.isdigit() and self.requests == []

    def test_status_names_from_midtrans_are_mapped(self):
        assert [payments.map_status(s) for s in ("settlement", "capture", "pending", "expire", "cancel", "deny", "failure")] == [
            "paid", "paid", "pending", "expired", "cancelled", "failed", "failed",
        ]
        assert payments.map_status("aneh") is None


def notification(order_id, status, gross="29000.00", code="200", key=SERVER_KEY, **extra):
    raw = f"{order_id}{code}{gross}{key}"
    return {
        "order_id": order_id, "status_code": code, "gross_amount": gross, "transaction_status": status,
        "signature_key": hashlib.sha512(raw.encode()).hexdigest(), **extra,
    }


class TestWebhook:
    @pytest.fixture(autouse=True)
    def configured(self, monkeypatch, outbox):
        monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)

    def post(self, client, payload):
        return client.post("/billing/midtrans/notification", json=payload)

    def test_it_is_hidden_when_midtrans_is_not_configured(self, client, monkeypatch):
        monkeypatch.setattr(settings, "midtrans_server_key", "")
        res = self.post(client, notification("NAR-1-x", "settlement", key=""))
        assert res.status_code == 404 and res.json()["detail"] == "Tidak tersedia."

    def test_a_wrong_signature_is_rejected(self, client, db, make_user):
        tx = make_tx(db, make_user("free"), provider="midtrans")
        payload = notification(tx.order_id, "settlement")
        payload["signature_key"] = "0" * 128
        res = self.post(client, payload)
        assert res.status_code == 403 and res.json()["detail"] == "Signature tidak valid."

    def test_a_signature_made_with_another_key_is_rejected(self, client, db, make_user):
        tx = make_tx(db, make_user("free"), provider="midtrans")
        assert self.post(client, notification(tx.order_id, "settlement", key="kunci-lain")).status_code == 403

    def test_a_missing_signature_is_rejected(self, client, db, make_user):
        tx = make_tx(db, make_user("free"), provider="midtrans")
        payload = notification(tx.order_id, "settlement")
        del payload["signature_key"]
        assert self.post(client, payload).status_code == 403

    def test_settlement_pays_the_order_and_applies_it(self, client, db, make_user, outbox):
        user = make_user("free")
        tx = make_tx(db, user, provider="midtrans")
        res = self.post(client, notification(tx.order_id, "settlement"))
        assert res.status_code == 200 and res.json() == {"ok": True}
        db.expire_all()
        assert db.get(models.Transaction, tx.id).status == "paid"
        assert fresh_user(db, user).tier == "middle" and len(outbox) == 1

    def test_capture_also_counts_as_paid(self, client, db, make_user):
        user = make_user("free")
        tx = make_tx(db, user, provider="midtrans")
        self.post(client, notification(tx.order_id, "capture"))
        assert fresh_user(db, user).tier == "middle"

    def test_a_repeated_notification_is_applied_once(self, client, db, make_user, outbox):
        user = make_user("free")
        tx = make_tx(db, user, kind="pay_per_check", quantity=2, provider="midtrans", amount=10000)
        for _ in range(3):
            assert self.post(client, notification(tx.order_id, "settlement", gross="10000.00")).status_code == 200
        assert fresh_user(db, user).extra_checks == 2 and len(outbox) == 1

    def test_an_amount_that_does_not_match_is_rejected(self, client, db, make_user):
        user = make_user("free")
        tx = make_tx(db, user, provider="midtrans")
        res = self.post(client, notification(tx.order_id, "settlement", gross="1000.00"))
        assert res.status_code == 400 and res.json()["detail"] == "Nominal tidak cocok."
        db.expire_all()
        assert db.get(models.Transaction, tx.id).status == "pending" and fresh_user(db, user).tier == "free"

    def test_an_unreadable_amount_is_rejected(self, client, db, make_user):
        tx = make_tx(db, make_user("free"), provider="midtrans")
        assert self.post(client, notification(tx.order_id, "settlement", gross="banyak")).status_code == 400

    def test_a_plain_integer_amount_is_accepted(self, client, db, make_user):
        user = make_user("free")
        tx = make_tx(db, user, provider="midtrans")
        assert self.post(client, notification(tx.order_id, "settlement", gross="29000")).status_code == 200
        assert fresh_user(db, user).tier == "middle"

    def test_unknown_orders_are_not_found(self, client):
        res = self.post(client, notification("NAR-9-tidakada", "settlement"))
        assert res.status_code == 404 and res.json()["detail"] == "Transaksi tidak ditemukan."

    def test_simulated_orders_cannot_be_settled_by_webhook(self, client, db, make_user):
        user = make_user("free")
        tx = make_tx(db, user, provider="simulated")
        assert self.post(client, notification(tx.order_id, "settlement")).status_code == 404
        assert fresh_user(db, user).tier == "free"

    @pytest.mark.parametrize("incoming, stored", [("expire", "expired"), ("cancel", "cancelled"), ("deny", "failed"), ("failure", "failed")])
    def test_other_final_statuses_are_recorded_without_applying_anything(self, client, db, make_user, incoming, stored):
        user = make_user("free")
        tx = make_tx(db, user, provider="midtrans")
        assert self.post(client, notification(tx.order_id, incoming)).status_code == 200
        db.expire_all()
        assert db.get(models.Transaction, tx.id).status == stored and fresh_user(db, user).tier == "free"

    def test_a_pending_notification_changes_nothing(self, client, db, make_user):
        tx = make_tx(db, make_user("free"), provider="midtrans")
        self.post(client, notification(tx.order_id, "pending"))
        db.expire_all()
        assert db.get(models.Transaction, tx.id).status == "pending"

    def test_an_unknown_status_is_ignored(self, client, db, make_user):
        tx = make_tx(db, make_user("free"), provider="midtrans")
        assert self.post(client, notification(tx.order_id, "aneh")).status_code == 200
        db.expire_all()
        assert db.get(models.Transaction, tx.id).status == "pending"

    def test_a_late_expiry_notice_does_not_undo_a_payment(self, client, db, make_user):
        user = make_user("free")
        tx = make_tx(db, user, provider="midtrans")
        self.post(client, notification(tx.order_id, "settlement"))
        self.post(client, notification(tx.order_id, "expire"))
        db.expire_all()
        assert db.get(models.Transaction, tx.id).status == "paid" and fresh_user(db, user).tier == "middle"

    def test_no_login_is_needed_for_the_gateway_to_call(self, client, db, make_user):
        tx = make_tx(db, make_user("free"), provider="midtrans")
        assert self.post(client, notification(tx.order_id, "pending")).status_code == 200


class TestQuotaCalendar:
    def test_the_period_is_the_calendar_month(self):
        assert billing.current_period(datetime(2026, 3, 9)) == "2026-03"
        assert billing.current_period(datetime(2026, 12, 31, 23, 59)) == "2026-12"

    def test_the_quota_resets_on_the_first_of_next_month(self):
        assert billing.next_reset(datetime(2026, 3, 9)) == datetime(2026, 4, 1)
        assert billing.next_reset(datetime(2026, 1, 31)) == datetime(2026, 2, 1)

    def test_the_reset_rolls_over_the_year(self):
        assert billing.next_reset(datetime(2026, 12, 15)) == datetime(2027, 1, 1)

    def test_a_new_month_starts_with_a_fresh_count(self, db, make_user):
        user = make_user("free")
        db.add(models.UsageQuota(user_id=user.id, period="2000-01", used=3))
        db.commit()
        assert billing.used_this_month(db, user) == 0
        billing.ensure_can_upload(db, user, 10)

    def test_the_reset_date_is_named_in_the_limit_message(self, db, make_user):
        from fastapi import HTTPException
        user = make_user("free")
        db.add(models.UsageQuota(user_id=user.id, period=billing.current_period(), used=3))
        db.commit()
        with pytest.raises(HTTPException) as err:
            billing.ensure_can_upload(db, user, 10)
        reset = billing.next_reset()
        assert err.value.status_code == 402
        assert f"1 {billing.MONTHS_ID[reset.month - 1]} {reset.year}" in err.value.detail


class TestSimulationOnlyOnLocalhost:
    @pytest.mark.parametrize("origins", [
        "http://localhost:5173", "http://127.0.0.1:5173", "http://[::1]:5173", "http://localhost:5173, http://127.0.0.1:3000",
    ])
    def test_local_origins_keep_the_simulation(self, client, auth, make_user, monkeypatch, origins):
        monkeypatch.setattr(settings, "cors_origins", origins)
        assert client.get("/billing/overview", headers=auth(make_user("free"))).json()["provider"] == "simulated"

    @pytest.mark.parametrize("origins", [
        "https://narative.example.com", "http://localhost:5173,https://narative.example.com", "http://localhost.evil.com",
    ])
    def test_a_public_origin_disables_the_simulation(self, client, auth, make_user, monkeypatch, origins):
        monkeypatch.setattr(settings, "cors_origins", origins)
        assert client.get("/billing/overview", headers=auth(make_user("free"))).json()["provider"] == "unavailable"

    def test_checkout_is_refused_and_nothing_is_stored(self, client, db, auth, make_user, monkeypatch):
        monkeypatch.setattr(settings, "cors_origins", "https://narative.example.com")
        res = checkout(client, auth, make_user("free"))
        assert res.status_code == 503 and res.json()["detail"] == "Pembayaran belum tersedia."
        db.expire_all()
        assert db.query(models.Transaction).count() == 0

    def test_an_old_simulated_order_cannot_be_paid_on_a_public_server(self, client, db, auth, make_user, monkeypatch, outbox):
        user = make_user("free")
        order = checkout(client, auth, user).json()["order_id"]
        monkeypatch.setattr(settings, "cors_origins", "https://narative.example.com")
        res = pay(client, auth, user, order)
        assert res.status_code == 403 and fresh_user(db, user).tier == "free"

    def test_a_midtrans_key_works_on_a_public_origin(self, client, auth, make_user, monkeypatch):
        monkeypatch.setattr(settings, "cors_origins", "https://narative.example.com")
        monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)
        assert client.get("/billing/overview", headers=auth(make_user("free"))).json()["provider"] == "midtrans"


class TestLateSettlement:
    def notify(self, client, tx):
        raw = f"{tx.order_id}200{tx.amount}.00{SERVER_KEY}"
        body = {"order_id": tx.order_id, "status_code": "200", "gross_amount": f"{tx.amount}.00", "transaction_status": "settlement",
                "signature_key": hashlib.sha512(raw.encode()).hexdigest()}
        return client.post("/billing/midtrans/notification", json=body)

    @pytest.mark.parametrize("state", ["expired", "cancelled"])
    def test_a_late_settlement_is_still_applied(self, client, db, auth, make_user, monkeypatch, outbox, state):
        monkeypatch.setattr(settings, "midtrans_server_key", SERVER_KEY)
        user = make_user("free")
        tx = make_tx(db, user, provider="midtrans", status=state)
        assert self.notify(client, tx).status_code == 200
        assert fresh_user(db, user).tier == "middle" and len(outbox) == 1
