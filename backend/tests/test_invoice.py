import json
from datetime import datetime

import pymupdf
import pytest

from app.db import models
from app.services import invoice
from tests.test_billing import make_tx

VA = "3935800000000001"
CREATED = datetime(2026, 10, 29, 3, 3)
DUE = datetime(2026, 10, 30, 3, 3)
PAID = datetime(2026, 10, 29, 10, 3)


@pytest.fixture
def user(make_user):
    return make_user("free")


def paid(db, user, **kw):
    tx = make_tx(db, user, status="paid", **kw)
    tx.created_at, tx.expires_at, tx.paid_at = CREATED, DUE, PAID
    db.commit()
    return tx


class TestBuild:
    def test_an_upgrade_has_one_item_priced_from_the_stored_amount(self, db, user):
        data = invoice.build(user, paid(db, user))
        assert data["number"].startswith("NAR-") and data["status"] == "paid"
        assert data["customer_name"] == user.name and data["customer_email"] == user.email
        assert data["items"] == [{"no": 1, "name": "Paket Middle (30 hari)", "unit_price": 29000, "quantity": 1, "total": 29000}]
        assert data["subtotal"] == 29000 and data["total"] == 29000

    def test_extra_analyses_use_the_quantity_and_a_unit_price(self, db, user):
        data = invoice.build(user, paid(db, user, kind="pay_per_check", quantity=3, amount=15000))
        assert data["items"] == [{"no": 1, "name": "Analisis tambahan (pay-per-check)", "unit_price": 5000, "quantity": 3, "total": 15000}]
        assert data["total"] == 15000

    def test_the_unit_price_comes_from_what_was_paid_not_from_todays_price_list(self, db, user):
        data = invoice.build(user, paid(db, user, amount=20000))
        assert data["items"][0]["unit_price"] == 20000 and data["total"] == 20000

    def test_the_three_dates_come_from_the_transaction(self, db, user):
        data = invoice.build(user, paid(db, user))
        assert (data["issued_at"], data["due_at"], data["paid_at"]) == (CREATED, DUE, PAID)

    @pytest.mark.parametrize("bank,label", [("bca", "Virtual Account BCA"), ("bni", "Virtual Account BNI"), ("permata", "Virtual Account PERMATA")])
    def test_the_method_is_the_bank_name_only(self, db, user, bank, label):
        tx = paid(db, user)
        tx.bank = bank
        assert invoice.build(user, tx)["method"] == label

    def test_no_payment_code_is_included_anywhere(self, db, user):
        data = invoice.build(user, paid(db, user))
        assert VA not in json.dumps(data, default=str)

    def test_the_total_has_no_invented_fees(self, db, user):
        data = invoice.build(user, paid(db, user))
        assert data["subtotal"] == data["total"] == sum(i["total"] for i in data["items"])


class TestFormatting:
    def test_money_has_a_space_and_dots(self):
        assert invoice.money(29000) == "Rp 29.000" and invoice.money(1500000) == "Rp 1.500.000"

    def test_the_time_is_wib_with_a_short_month(self):
        assert invoice.stamp(datetime(2026, 10, 29, 10, 3)) == "29 Okt 2026 17:03"
        assert invoice.stamp(datetime(2026, 5, 1, 20, 0)) == "2 Mei 2026 03:00"


class TestPdf:
    def text(self, data):
        with pymupdf.open("pdf", data) as pdf:
            assert len(pdf) == 1
            return " ".join(pdf[0].get_text("text").split())

    def test_it_is_a_one_page_pdf_with_the_invoice_data(self, db, user):
        tx = paid(db, user)
        data = invoice.pdf(user, tx)
        assert data.startswith(b"%PDF")
        text = self.text(data)
        for fragment in ("INVOICE", "TERBAYAR", tx.order_id, user.name, user.email, "Virtual Account BCA", "Paket Middle (30 hari)", "Rp 29.000", "29 Okt 2026 10:03", "30 Okt 2026 10:03", "29 Okt 2026 17:03", "NARAtive"):
            assert fragment in text, fragment

    def test_it_never_shows_the_payment_code(self, db, user):
        assert VA not in self.text(invoice.pdf(user, paid(db, user)))

    def test_the_logo_is_on_the_page_in_place_of_the_brand_text(self, db, user):
        data = invoice.pdf(user, paid(db, user))
        with pymupdf.open("pdf", data) as pdf:
            assert len(pdf) == 1 and len(pdf[0].get_images()) == 1
            rect = pdf[0].get_image_rects(pdf[0].get_images()[0][0])[0]
            assert rect.x0 < 100 and rect.y0 < 100 and 100 < rect.width < 170 and abs(rect.width / rect.height - 520 / 163) < 0.05
        text = self.text(data)
        assert text.count("NARAtive") == 1 and "Analisis rating konten e-book" in text

    def test_without_the_logo_file_the_header_falls_back_to_the_brand_text(self, db, user, monkeypatch, tmp_path):
        monkeypatch.setattr(invoice, "LOGO_PATH", tmp_path / "tidak-ada.png")
        data = invoice.pdf(user, paid(db, user))
        with pymupdf.open("pdf", data) as pdf:
            assert len(pdf[0].get_images()) == 0
        assert self.text(data).count("NARAtive") == 2

    def test_the_logo_file_exists_and_is_a_png(self):
        assert invoice.LOGO_PATH.read_bytes().startswith(b"\x89PNG")

    def test_extra_analyses_show_the_quantity(self, db, user):
        text = self.text(invoice.pdf(user, paid(db, user, kind="pay_per_check", quantity=3, amount=15000)))
        assert "Analisis tambahan (pay-per-check)" in text and "Rp 5.000" in text and "Rp 15.000" in text

    def test_markup_in_the_name_is_shown_as_text(self, db, user):
        user.name = "<b>Rana</b>"
        assert "<b>Rana</b>" in self.text(invoice.pdf(user, paid(db, user)))


class TestEndpoints:
    def url(self, tx, suffix="invoice"):
        return f"/billing/transactions/{tx.order_id}/{suffix}"

    def test_a_paid_transaction_returns_the_invoice_json(self, db, client, auth, user):
        tx = paid(db, user)
        body = client.get(self.url(tx), headers=auth(user)).json()
        assert body["number"] == tx.order_id and body["status"] == "paid" and body["method"] == "Virtual Account BCA"
        assert body["customer_name"] == user.name and body["customer_email"] == user.email
        assert body["items"][0]["name"] == "Paket Middle (30 hari)" and body["total"] == 29000 and body["subtotal"] == 29000
        assert body["issued_at"].startswith("2026-10-29") and body["paid_at"].startswith("2026-10-29")
        assert VA not in json.dumps(body)

    def test_the_pdf_is_an_attachment_named_after_the_order(self, db, client, auth, user):
        tx = paid(db, user)
        res = client.get(self.url(tx, "invoice.pdf"), headers=auth(user))
        assert res.status_code == 200 and res.headers["content-type"] == "application/pdf"
        assert res.headers["content-disposition"] == f'attachment; filename="Invoice NARAtive {tx.order_id}.pdf"'
        assert res.content.startswith(b"%PDF")

    @pytest.mark.parametrize("status", ["pending", "expired", "cancelled", "failed"])
    @pytest.mark.parametrize("suffix", ["invoice", "invoice.pdf"])
    def test_only_a_paid_transaction_has_an_invoice(self, db, client, auth, user, status, suffix):
        tx = make_tx(db, user, status=status)
        res = client.get(self.url(tx, suffix), headers=auth(user))
        assert res.status_code == 409 and res.json()["detail"] == "Invoice hanya tersedia untuk pembayaran yang berhasil."

    @pytest.mark.parametrize("suffix", ["invoice", "invoice.pdf"])
    def test_someone_elses_transaction_is_not_found(self, db, client, auth, make_user, user, suffix):
        tx = paid(db, user)
        other = make_user("free")
        assert client.get(self.url(tx, suffix), headers=auth(other)).status_code == 404

    @pytest.mark.parametrize("suffix", ["invoice", "invoice.pdf"])
    def test_an_unknown_order_is_not_found(self, client, auth, user, suffix):
        assert client.get(f"/billing/transactions/NAR-0-tidakada/{suffix}", headers=auth(user)).status_code == 404

    @pytest.mark.parametrize("suffix", ["invoice", "invoice.pdf"])
    def test_a_token_is_required(self, db, client, user, suffix):
        tx = paid(db, user)
        assert client.get(self.url(tx, suffix)).status_code == 401

    def test_the_other_transaction_routes_still_work(self, db, client, auth, user):
        tx = paid(db, user)
        assert client.get(f"/billing/transactions/{tx.order_id}", headers=auth(user)).json()["order_id"] == tx.order_id
        assert isinstance(db.query(models.Transaction).count(), int)
