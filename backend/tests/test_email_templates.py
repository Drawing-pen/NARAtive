import re
import smtplib
from datetime import datetime, timedelta
from html.parser import HTMLParser

import pytest

from app.core.config import settings
from app.db import models
from app.services import billing, email_templates as templates, mailer

CODE = "482913"


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.links, self.images = [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag == "a":
            self.links.append(dict(attrs).get("href"))
        if tag == "img":
            self.images.append(dict(attrs).get("src"))


def parse(html):
    parser = Collector()
    parser.feed(html)
    return parser


def visible_text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


@pytest.fixture(autouse=True)
def site(monkeypatch):
    monkeypatch.setattr(settings, "frontend_url", "https://narative.example.com/")


@pytest.fixture
def user(make_user):
    return make_user("free")


def transaction(db, user, **kw):
    values = dict(
        user_id=user.id, order_id="NAR-1-abc123", kind="upgrade", plan="middle", quantity=1, amount=29000, bank="bni",
        va_number="8810123456789012", provider="midtrans", status="pending",
        created_at=datetime(2026, 10, 28, 3, 0), expires_at=datetime(2026, 10, 29, 3, 0),
    )
    values.update(kw)
    tx = models.Transaction(**values)
    db.add(tx)
    db.commit()
    return tx


class TestLayout:
    @pytest.fixture
    def mail(self):
        return templates.verification_email("Rana", CODE, 10)

    def test_it_is_a_complete_html_document(self, mail):
        assert mail.html.lstrip().lower().startswith("<!doctype html>")
        tags = parse(mail.html).tags
        assert "html" in tags and "body" in tags and "table" in tags

    def test_it_carries_the_brand(self, mail):
        assert "NARAtive" in visible_text(mail.html)
        assert "#24365f" in mail.html and "#efb54d" in mail.html

    def test_it_has_a_preheader_and_a_footer(self, mail):
        assert "display:none" in mail.html.replace(" ", "")
        assert "dikirim otomatis" in visible_text(mail.html)

    def test_it_loads_nothing_from_outside(self, mail):
        parsed = parse(mail.html)
        assert parsed.images == ["cid:narative-logo"]
        assert "script" not in parsed.tags and "form" not in parsed.tags and "iframe" not in parsed.tags

    def test_it_declares_the_language_and_encoding(self, mail):
        assert 'lang="id"' in mail.html and "utf-8" in mail.html.lower()

    def test_it_is_responsive_with_a_maximum_width(self, mail):
        assert "max-width:560px" in mail.html.replace(" ", "")


class TestLogo:
    LOGO = mailer.LOGO_PATH

    @pytest.fixture(params=["code", "instructions", "invoice"])
    def html(self, request, db, user):
        if request.param == "code":
            return templates.verification_email("Rana", CODE, 10).html
        tx = transaction(db, user, status="paid", paid_at=datetime(2026, 10, 28, 3, 30))
        user.tier_expires_at = datetime(2026, 11, 27)
        mail = templates.payment_instructions(user, tx) if request.param == "instructions" else templates.invoice(user, tx)
        return mail.html

    def test_every_email_shows_the_logo_inline(self, html):
        assert parse(html).images == ["cid:narative-logo"]

    def test_the_logo_has_alt_text_and_a_fixed_size(self, html):
        tag = re.search(r"<img[^>]*>", html).group(0)
        assert 'alt="NARAtive"' in tag and 'width="240"' in tag and 'height="75"' in tag and "display:block" in tag.replace(" ", "")

    def test_the_logo_sits_inside_the_card(self, html):
        assert html.index("<img") > html.index("border-top:4px")

    def test_the_text_version_has_no_image(self):
        assert "cid:" not in templates.verification_email("Rana", CODE, 10).text

    def test_the_logo_file_is_a_small_png(self):
        data = self.LOGO.read_bytes()
        assert data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) < 60 * 1024
        assert int.from_bytes(data[16:20], "big") == 520 and int.from_bytes(data[20:24], "big") == 163


class TestVerificationEmail:
    def test_the_subject_is_unchanged(self):
        assert templates.verification_email("Rana", CODE, 10).subject == "Kode verifikasi NARAtive"

    def test_the_code_is_prominent_in_both_versions(self):
        mail = templates.verification_email("Rana", CODE, 10)
        assert CODE in mail.text and CODE in mail.html
        assert re.findall(r"(?<!\d)\d{6}(?!\d)", mail.text) == [CODE]

    def test_it_states_the_lifetime_and_the_warning(self):
        mail = templates.verification_email("Rana", CODE, 10)
        for body in (mail.text, visible_text(mail.html)):
            assert "10 menit" in body and "abaikan" in body.lower()

    def test_it_greets_by_name(self):
        mail = templates.verification_email("Rana", CODE, 10)
        assert "Halo Rana" in mail.text and "Halo Rana" in visible_text(mail.html)

    def test_the_name_is_escaped_in_the_html_only(self):
        mail = templates.verification_email('<b>"x"</b> & <script>alert(1)</script>', CODE, 10)
        assert "<script>" not in mail.html and "&lt;script&gt;" in mail.html and "<b>" not in mail.html
        assert "<script>" in mail.text

    def test_the_plain_text_has_no_markup(self):
        assert "<" not in templates.verification_email("Rana", CODE, 10).text


class TestPaymentInstructions:
    def test_the_subject_names_the_order(self, db, user):
        tx = transaction(db, user)
        assert templates.payment_instructions(user, tx).subject == "Selesaikan pembayaran NARAtive NAR-1-abc123"

    def test_it_lists_what_to_pay_and_where(self, db, user):
        mail = templates.payment_instructions(user, transaction(db, user))
        for body in (mail.text, visible_text(mail.html)):
            for fragment in ("Paket Middle (30 hari)", "Rp 29.000", "BNI", "8810123456789012", "NAR-1-abc123"):
                assert fragment in body, fragment

    def test_the_deadline_is_in_wib(self, db, user):
        mail = templates.payment_instructions(user, transaction(db, user))
        for body in (mail.text, visible_text(mail.html)):
            assert "29-10-2026 10:00 WIB" in body

    def test_it_explains_how_to_pay(self, db, user):
        mail = templates.payment_instructions(user, transaction(db, user))
        assert "Virtual Account" in mail.text and "Virtual Account" in visible_text(mail.html)

    def test_extra_analyses_are_described(self, db, user):
        mail = templates.payment_instructions(user, transaction(db, user, kind="pay_per_check", plan=None, quantity=3, amount=15000))
        assert "3 analisis tambahan" in mail.text and "Rp 15.000" in mail.text

    def test_the_simulation_is_called_out(self, db, user):
        simulated = templates.payment_instructions(user, transaction(db, user, provider="simulated"))
        real = templates.payment_instructions(user, transaction(db, user, provider="midtrans", order_id="NAR-1-real"))
        assert "simulasi" in simulated.text.lower() and "simulasi" in visible_text(simulated.html).lower()
        assert "simulasi" not in real.text.lower()

    def test_the_button_opens_the_payment_history(self, db, user):
        mail = templates.payment_instructions(user, transaction(db, user))
        assert "https://narative.example.com/profil#riwayat" in parse(mail.html).links
        assert "https://narative.example.com/profil#riwayat" in mail.text


class TestInvoice:
    def paid(self, db, user, **kw):
        user.tier, user.tier_expires_at = "middle", datetime(2026, 11, 27, 3, 0)
        db.commit()
        return transaction(db, user, status="paid", paid_at=datetime(2026, 10, 28, 3, 30), **kw)

    def test_the_subject_is_unchanged(self, db, user):
        assert templates.invoice(user, self.paid(db, user)).subject == "Invoice NARAtive NAR-1-abc123"

    def test_it_lists_the_order_details(self, db, user):
        mail = templates.invoice(user, self.paid(db, user))
        for body in (mail.text, visible_text(mail.html)):
            for fragment in ("NAR-1-abc123", "Paket Middle (30 hari)", "Rp 29.000", "BNI 8810123456789012", "28-10-2026 10:30 WIB", "27-11-2026"):
                assert fragment in body, fragment

    def test_extra_analyses_have_no_end_date(self, db, user):
        mail = templates.invoice(user, self.paid(db, user, kind="pay_per_check", plan=None, quantity=3, amount=15000))
        assert "Aktif sampai" not in mail.text and "Aktif sampai" not in visible_text(mail.html)
        assert "3 analisis tambahan" in mail.text

    def test_it_links_to_the_history(self, db, user):
        mail = templates.invoice(user, self.paid(db, user))
        assert "https://narative.example.com/profil#riwayat" in parse(mail.html).links

    def test_the_user_name_is_escaped(self, db, user):
        user.name = "<i>Rana</i>"
        mail = templates.invoice(user, self.paid(db, user))
        assert "<i>" not in mail.html and "&lt;i&gt;Rana&lt;/i&gt;" in mail.html


class TestSiteLink:
    @pytest.mark.parametrize("base", ["https://a.example.com", "https://a.example.com/", "https://a.example.com///"])
    def test_trailing_slashes_are_ignored(self, monkeypatch, base):
        monkeypatch.setattr(settings, "frontend_url", base)
        assert templates.site_url("/profil") == "https://a.example.com/profil"

    def test_the_default_points_at_localhost(self):
        from app.core.config import Settings
        assert Settings(_env_file=None).frontend_url == "http://localhost:5173"


class FakeSMTP:
    sent = []

    def __init__(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, *a):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


class TestSending:
    @pytest.fixture(autouse=True)
    def smtp(self, monkeypatch):
        FakeSMTP.sent = []
        monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
        monkeypatch.setattr(settings, "smtp_host", "smtp.contoh.com")
        monkeypatch.setattr(settings, "smtp_user", "")

        class Now:
            def __init__(self, target, args=(), daemon=None, **kw):
                self.target, self.args = target, args

            def start(self):
                self.target(*self.args)

        monkeypatch.setattr(mailer.threading, "Thread", Now)

    def test_it_is_sent_as_text_and_html(self):
        mail = templates.verification_email("Rana", CODE, 10)
        mailer.send("rana@example.com", mail.subject, mail.text, mail.html)
        [msg] = FakeSMTP.sent
        assert msg.is_multipart()
        assert msg.get_body(("plain",)).get_content().strip() == mail.text.strip()
        assert CODE in msg.get_body(("html",)).get_content()

    def test_the_logo_is_attached_inline_to_the_html(self):
        mail = templates.verification_email("Rana", CODE, 10)
        mailer.send("rana@example.com", mail.subject, mail.text, mail.html)
        [msg] = FakeSMTP.sent
        [image] = [p for p in msg.walk() if p.get_content_type() == "image/png"]
        assert image["Content-ID"] == "<narative-logo>" and image.get_content_disposition() == "inline"
        assert image.get_payload(decode=True) == mailer.LOGO_PATH.read_bytes()
        assert msg.get_body(("html",)).get_content_type() == "text/html"

    def test_the_html_and_its_logo_travel_together(self):
        mail = templates.verification_email("Rana", CODE, 10)
        mailer.send("rana@example.com", mail.subject, mail.text, mail.html)
        [msg] = FakeSMTP.sent
        related = [p for p in msg.walk() if p.get_content_type() == "multipart/related"]
        assert len(related) == 1 and [p.get_content_type() for p in related[0].iter_parts()] == ["text/html", "image/png"]

    def test_html_without_a_logo_reference_gets_no_image(self):
        mailer.send("rana@example.com", "Judul", "Isi", "<p>Halo</p>")
        [msg] = FakeSMTP.sent
        assert [p for p in msg.walk() if p.get_content_type().startswith("image/")] == []

    def test_a_missing_logo_file_does_not_stop_the_email(self, monkeypatch, tmp_path, caplog):
        monkeypatch.setattr(mailer, "LOGO_PATH", tmp_path / "tidak-ada.png")
        mail = templates.verification_email("Rana", CODE, 10)
        mailer.send("rana@example.com", mail.subject, mail.text, mail.html)
        [msg] = FakeSMTP.sent
        assert CODE in msg.get_body(("html",)).get_content()
        assert [p for p in msg.walk() if p.get_content_type().startswith("image/")] == []
        assert "tidak-ada.png" in caplog.text

    def test_without_html_it_stays_plain(self):
        mailer.send("rana@example.com", "Judul", "Isi saja")
        [msg] = FakeSMTP.sent
        assert not msg.is_multipart() and msg.get_content().strip() == "Isi saja"

    def test_non_ascii_text_survives(self):
        mail = templates.verification_email("Ráná Ünï", CODE, 10)
        mailer.send("rana@example.com", mail.subject, mail.text, mail.html)
        [msg] = FakeSMTP.sent
        assert "Ráná Ünï" in msg.get_body(("html",)).get_content()

    def test_without_smtp_only_the_text_is_logged(self, monkeypatch, caplog):
        import logging
        monkeypatch.setattr(settings, "smtp_host", "")
        caplog.set_level(logging.INFO, logger="uvicorn.error")
        mail = templates.verification_email("Rana", CODE, 10)
        mailer.send("rana@example.com", mail.subject, mail.text, mail.html)
        assert FakeSMTP.sent == []
        logged = " ".join(r.getMessage() for r in caplog.records)
        assert CODE in logged and "<table" not in logged


class TestWiring:
    def test_registration_sends_the_branded_code_email(self, client, outbox):
        client.post("/auth/register", json={"name": "Rana", "email": "rana@example.com", "password": "kata-sandi-aman"})
        [mail] = outbox
        assert mail["subject"] == "Kode verifikasi NARAtive" and mail["html"] and "<table" in mail["html"]
        assert re.search(r"(?<!\d)\d{6}(?!\d)", mail["body"])

    def checkout(self, client, auth, user, **body):
        body.setdefault("kind", "upgrade")
        body.setdefault("plan", "middle")
        body.setdefault("bank", "bca")
        return client.post("/billing/checkout", json=body, headers=auth(user))

    def test_checkout_sends_the_instructions_once(self, client, auth, user, outbox):
        order = self.checkout(client, auth, user).json()
        [mail] = outbox
        assert mail["to"] == user.email and mail["subject"] == f"Selesaikan pembayaran NARAtive {order['order_id']}"
        assert order["va_number"] in mail["body"] and order["va_number"] in mail["html"]

    def test_opening_or_listing_the_order_does_not_resend(self, client, auth, user, outbox):
        order = self.checkout(client, auth, user).json()
        client.get(f"/billing/transactions/{order['order_id']}", headers=auth(user))
        client.get("/billing/transactions", headers=auth(user))
        assert len(outbox) == 1

    def test_each_order_gets_its_own_email(self, client, auth, user, outbox):
        self.checkout(client, auth, user)
        self.checkout(client, auth, user, kind="pay_per_check", quantity=2)
        assert len(outbox) == 2 and outbox[0]["subject"] != outbox[1]["subject"]

    def test_a_failed_checkout_sends_nothing(self, client, auth, user, outbox, monkeypatch):
        monkeypatch.setattr(settings, "cors_origins", "https://narative.example.com")
        assert self.checkout(client, auth, user).status_code == 503
        assert outbox == []

    def test_a_rejected_order_sends_nothing(self, client, auth, make_user, outbox):
        assert self.checkout(client, auth, make_user("high"), kind="pay_per_check", quantity=1).status_code == 400
        assert outbox == []

    def test_paying_sends_the_invoice_after_the_instructions(self, client, auth, user, outbox):
        order = self.checkout(client, auth, user).json()
        client.post(f"/billing/transactions/{order['order_id']}/simulate-pay", headers=auth(user))
        assert [m["subject"].split()[0] for m in outbox] == ["Selesaikan", "Invoice"]
        assert outbox[1]["html"] and "<table" in outbox[1]["html"]

    def test_paying_twice_still_sends_one_invoice(self, client, auth, user, outbox):
        order = self.checkout(client, auth, user).json()
        for _ in range(2):
            client.post(f"/billing/transactions/{order['order_id']}/simulate-pay", headers=auth(user))
        assert len([m for m in outbox if m["subject"].startswith("Invoice")]) == 1

    def test_the_service_helper_sends_an_invoice_directly(self, db, user, outbox):
        tx = transaction(db, user, status="paid", paid_at=datetime.utcnow())
        billing.send_invoice(user, tx)
        assert outbox[0]["subject"].startswith("Invoice") and outbox[0]["html"]
