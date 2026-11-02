from datetime import datetime, timedelta

import pytest

from app.db import models
from app.services import email_templates
from tests.conftest import code_from

OLD = "sandi-uji-123"
NEW = "sandi-baru-456"
GENERIC = "Kode salah atau sudah kedaluwarsa. Minta kode baru."


@pytest.fixture
def user(make_user):
    return make_user(email="rana@example.com")


def forgot(client, email="rana@example.com"):
    return client.post("/auth/password/forgot", json={"email": email})


def reset(client, code, password=NEW, email="rana@example.com"):
    return client.post("/auth/password/reset", json={"email": email, "code": code, "new_password": password})


def record(db, email="rana@example.com"):
    db.expire_all()
    return db.query(models.PasswordReset).filter_by(email=email).first()


def login(client, password, email="rana@example.com"):
    return client.post("/auth/login", json={"email": email, "password": password})


class TestForgot:
    def test_a_registered_email_gets_a_code_by_mail(self, client, user, outbox):
        res = forgot(client)
        assert res.status_code == 202
        assert res.json() == {"email": "rana@example.com", "expires_in": 600, "resend_after": 60}
        [mail] = outbox
        assert mail["to"] == "rana@example.com" and mail["subject"] == "Atur ulang kata sandi NARAtive"
        assert len(code_from(mail)) == 6 and mail["html"]

    def test_an_unknown_email_gets_the_same_answer_but_no_mail(self, client, db, outbox):
        res = forgot(client, "tidakada@example.com")
        assert res.status_code == 202
        assert res.json() == {"email": "tidakada@example.com", "expires_in": 600, "resend_after": 60}
        assert outbox == [] and db.query(models.PasswordReset).count() == 0

    def test_the_email_is_case_insensitive(self, client, user, outbox):
        assert forgot(client, "RANA@Example.COM").status_code == 202
        assert len(outbox) == 1 and outbox[0]["to"] == "rana@example.com"

    def test_an_inactive_account_gets_no_mail(self, client, db, user, outbox):
        user.is_active = False
        db.commit()
        assert forgot(client).status_code == 202
        assert outbox == [] and db.query(models.PasswordReset).count() == 0

    def test_a_malformed_email_is_rejected(self, client):
        assert client.post("/auth/password/forgot", json={"email": "bukan-email"}).status_code == 422

    def test_the_code_is_stored_only_as_a_hash(self, client, db, user, outbox):
        forgot(client)
        code = code_from(outbox[0])
        row = record(db)
        assert code not in row.code_hash and len(row.code_hash) == 64
        assert row.attempts == 0 and row.expires_at > datetime.utcnow() + timedelta(minutes=9)

    def test_asking_again_inside_the_cooldown_sends_nothing_and_keeps_the_code(self, client, user, outbox):
        forgot(client)
        code = code_from(outbox[0])
        assert forgot(client).status_code == 202
        assert len(outbox) == 1
        assert reset(client, code).status_code == 200

    def test_asking_again_after_the_cooldown_replaces_the_code(self, client, db, user, outbox):
        forgot(client)
        first = code_from(outbox[0])
        row = record(db)
        row.last_sent_at = datetime.utcnow() - timedelta(seconds=61)
        row.attempts = 3
        db.commit()
        assert forgot(client).status_code == 202 and len(outbox) == 2
        second = code_from(outbox[1])
        assert record(db).attempts == 0 and db.query(models.PasswordReset).count() == 1
        if first != second:
            assert reset(client, first).status_code == 400
        assert reset(client, second).status_code == 200

    def test_each_account_has_its_own_record(self, client, make_user, outbox):
        make_user(email="rana@example.com")
        make_user(email="dede@example.com")
        forgot(client)
        forgot(client, "dede@example.com")
        assert {m["to"] for m in outbox} == {"rana@example.com", "dede@example.com"}


class TestReset:
    def start(self, client, outbox):
        forgot(client)
        return code_from(outbox[-1])

    def test_the_right_code_sets_the_new_password_and_logs_the_user_in(self, client, user, outbox):
        code = self.start(client, outbox)
        res = reset(client, code)
        assert res.status_code == 200
        body = res.json()
        assert body["access_token"] and body["user"]["email"] == "rana@example.com"
        assert login(client, OLD).status_code == 401
        assert login(client, NEW).status_code == 200

    def test_the_token_works(self, client, user, outbox):
        token = reset(client, self.start(client, outbox)).json()["access_token"]
        assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["email"] == "rana@example.com"

    def test_a_code_works_only_once(self, client, db, user, outbox):
        code = self.start(client, outbox)
        assert reset(client, code).status_code == 200
        assert record(db) is None
        res = reset(client, code, "lain-lagi-789")
        assert res.status_code == 400 and res.json()["detail"] == GENERIC
        assert login(client, NEW).status_code == 200

    def test_the_email_is_case_insensitive(self, client, user, outbox):
        code = self.start(client, outbox)
        assert reset(client, code, email="RANA@example.com").status_code == 200

    def test_a_wrong_code_is_refused_and_counted(self, client, db, user, outbox):
        code = self.start(client, outbox)
        wrong = "000000" if code != "000000" else "111111"
        res = reset(client, wrong)
        assert res.status_code == 400 and res.json()["detail"] == GENERIC
        assert record(db).attempts == 1
        assert login(client, OLD).status_code == 200

    def test_the_fifth_wrong_code_deletes_the_record(self, client, db, user, outbox):
        code = self.start(client, outbox)
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(4):
            assert reset(client, wrong).status_code == 400
        res = reset(client, wrong)
        assert res.status_code == 429 and res.json()["detail"] == "Terlalu banyak percobaan. Minta kode baru."
        assert record(db) is None
        late = reset(client, code)
        assert late.status_code == 400 and late.json()["detail"] == GENERIC
        assert login(client, OLD).status_code == 200

    def test_an_expired_code_is_refused(self, client, db, user, outbox):
        code = self.start(client, outbox)
        row = record(db)
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
        res = reset(client, code)
        assert res.status_code == 400 and res.json()["detail"] == GENERIC
        assert login(client, OLD).status_code == 200

    def test_an_email_that_never_asked_gets_the_same_refusal(self, client, user):
        res = reset(client, "123456")
        assert res.status_code == 400 and res.json()["detail"] == GENERIC

    def test_an_unknown_email_gets_the_same_refusal(self, client):
        res = reset(client, "123456", email="tidakada@example.com")
        assert res.status_code == 400 and res.json()["detail"] == GENERIC

    def test_a_deactivated_account_cannot_be_reset(self, client, db, user, outbox):
        code = self.start(client, outbox)
        user.is_active = False
        db.commit()
        res = reset(client, code)
        assert res.status_code == 400 and res.json()["detail"] == GENERIC
        assert login(client, OLD).status_code == 403

    def test_a_short_password_is_refused_without_burning_the_code(self, client, db, user, outbox):
        code = self.start(client, outbox)
        assert reset(client, code, "pendek").status_code == 422
        assert record(db).attempts == 0
        assert reset(client, code).status_code == 200

    def test_a_password_over_72_bytes_is_refused(self, client, user, outbox):
        code = self.start(client, outbox)
        assert reset(client, code, "é" * 40).status_code == 422
        assert reset(client, code, "a" * 73).status_code == 422

    @pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", "12 456", ""])
    def test_a_badly_shaped_code_is_refused_by_the_schema(self, client, db, user, outbox, code):
        self.start(client, outbox)
        assert reset(client, code).status_code == 422
        assert record(db).attempts == 0

    def test_only_the_requesting_account_changes(self, client, make_user, outbox):
        make_user(email="rana@example.com")
        make_user(email="dede@example.com")
        reset(client, self.start(client, outbox))
        assert login(client, OLD, "dede@example.com").status_code == 200
        assert login(client, NEW, "dede@example.com").status_code == 401

    def test_the_new_password_may_equal_the_old_one(self, client, user, outbox):
        assert reset(client, self.start(client, outbox), OLD).status_code == 200
        assert login(client, OLD).status_code == 200


class TestEmail:
    def test_the_mail_carries_the_code_the_lifetime_and_the_safety_note(self):
        mail = email_templates.password_reset_email("Rana", "123456", 10)
        assert mail.subject == "Atur ulang kata sandi NARAtive"
        for part in (mail.text, mail.html):
            assert "123456" in part and "10 menit" in part and "Rana" in part
        assert "abaikan email ini" in mail.text and "kata sandimu tidak berubah" in mail.text

    def test_the_html_escapes_the_name(self):
        mail = email_templates.password_reset_email("<b>Rana</b>", "123456", 10)
        assert "<b>Rana</b>" not in mail.html and "&lt;b&gt;" in mail.html


def test_deleting_the_account_removes_a_pending_reset(client, db, user, outbox, auth):
    forgot(client)
    assert record(db) is not None
    res = client.request("DELETE", "/auth/me", json={"password": OLD}, headers=auth(user))
    assert res.status_code == 204
    assert record(db) is None
