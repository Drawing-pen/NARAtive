from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.db import models

PASSWORD = "sandi-uji-123"
NEW_PASSWORD = "sandi-baru-456"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def user(make_user):
    return make_user("free")


def me(client, auth, user):
    return client.get("/auth/me", headers=auth(user))


def rename(client, auth, user, name):
    return client.patch("/auth/me", json={"name": name}, headers=auth(user))


def change(client, auth, user, current=PASSWORD, new=NEW_PASSWORD):
    return client.put("/auth/me/password", json={"current_password": current, "new_password": new}, headers=auth(user))


def remove(client, auth, user, password=PASSWORD):
    return client.request("DELETE", "/auth/me", json={"password": password}, headers=auth(user))


def login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


class TestReading:
    def test_the_account_shows_when_it_was_created(self, client, auth, user):
        body = me(client, auth, user).json()
        assert body["email"] == user.email and body["name"] == user.name
        assert datetime.fromisoformat(body["created_at"]) <= datetime.utcnow()

    def test_the_token_response_carries_it_too(self, client, user):
        body = login(client, user.email, PASSWORD).json()
        assert "created_at" in body["user"]


class TestRename:
    def test_the_name_is_changed(self, client, db, auth, user):
        res = rename(client, auth, user, "Nama Baru")
        assert res.status_code == 200 and res.json()["name"] == "Nama Baru"
        db.expire_all()
        assert db.get(models.User, user.id).name == "Nama Baru"
        assert me(client, auth, user).json()["name"] == "Nama Baru"

    def test_the_name_is_tidied(self, client, auth, user):
        assert rename(client, auth, user, "  Rana    Afifah  ").json()["name"] == "Rana Afifah"

    @pytest.mark.parametrize("name", ["", "   ", "x" * 101])
    def test_a_bad_name_is_rejected(self, client, db, auth, user, name):
        before = user.name
        assert rename(client, auth, user, name).status_code == 422
        db.expire_all()
        assert db.get(models.User, user.id).name == before

    def test_the_longest_allowed_name_is_accepted(self, client, auth, user):
        assert rename(client, auth, user, "x" * 100).status_code == 200

    def test_only_the_own_account_changes(self, client, db, auth, user, make_user):
        other = make_user("free")
        other_name = other.name
        rename(client, auth, user, "Berubah")
        db.expire_all()
        assert db.get(models.User, other.id).name == other_name

    def test_it_requires_login(self, client):
        assert client.patch("/auth/me", json={"name": "X"}).status_code == 401


class TestChangePassword:
    def test_the_new_password_works_and_the_old_one_does_not(self, client, auth, user):
        assert change(client, auth, user).status_code == 204
        assert login(client, user.email, NEW_PASSWORD).status_code == 200
        assert login(client, user.email, PASSWORD).status_code == 401

    def test_a_wrong_current_password_is_refused(self, client, auth, user):
        res = change(client, auth, user, current="bukan-sandiku")
        assert res.status_code == 400 and res.json()["detail"] == "Kata sandi lama salah."
        assert login(client, user.email, PASSWORD).status_code == 200

    def test_the_new_password_must_differ(self, client, auth, user):
        res = change(client, auth, user, new=PASSWORD)
        assert res.status_code == 400 and res.json()["detail"] == "Kata sandi baru harus berbeda dari yang lama."

    @pytest.mark.parametrize("new", ["pendek", "x" * 73, "é" * 37])
    def test_the_new_password_follows_the_registration_rules(self, client, auth, user, new):
        assert change(client, auth, user, new=new).status_code == 422
        assert login(client, user.email, PASSWORD).status_code == 200

    def test_eight_and_seventy_two_characters_are_allowed(self, client, auth, user):
        assert change(client, auth, user, new="x" * 8).status_code == 204
        assert change(client, auth, user, current="x" * 8, new="y" * 72).status_code == 204

    def test_the_stored_password_is_hashed(self, client, db, auth, user):
        change(client, auth, user)
        db.expire_all()
        stored = db.get(models.User, user.id).password_hash
        assert NEW_PASSWORD not in stored and stored.startswith("$2")

    def test_it_requires_login(self, client):
        res = client.put("/auth/me/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
        assert res.status_code == 401


class TestDeleteAccount:
    def test_the_account_and_everything_it_owns_are_removed(self, client, db, auth, make_user, make_doc, user):
        user.tier = "high"
        db.commit()
        make_doc(user, characters=["Budi"])
        series_docs = [make_doc(user, title="A"), make_doc(user, title="B")]
        client.post("/collections", json={"name": "Seri", "document_ids": [d.id for d in series_docs]}, headers=auth(user))
        client.post("/billing/checkout", json={"kind": "pay_per_check", "quantity": 1, "bank": "bca"}, headers=auth(user))
        owner_id = user.id
        assert remove(client, auth, user).status_code == 204
        db.expire_all()
        assert db.get(models.User, owner_id) is None
        for model in (models.Document, models.Chapter, models.Paragraph, models.Character, models.Collection, models.Transaction):
            assert db.query(model).count() == 0, model.__name__

    def test_a_wrong_password_deletes_nothing(self, client, db, auth, make_doc, user):
        make_doc(user)
        res = remove(client, auth, user, password="bukan-sandiku")
        assert res.status_code == 400 and res.json()["detail"] == "Kata sandi salah."
        db.expire_all()
        assert db.get(models.User, user.id) is not None and db.query(models.Document).count() == 1

    def test_the_password_is_required(self, client, auth, user):
        assert client.request("DELETE", "/auth/me", headers=auth(user)).status_code == 422

    def test_other_accounts_are_untouched(self, client, db, auth, make_user, make_doc, user):
        other = make_user("free")
        make_doc(other, title="Milik lain")
        make_doc(user)
        remove(client, auth, user)
        db.expire_all()
        assert db.get(models.User, other.id) is not None
        assert [d.title for d in db.query(models.Document).all()] == ["Milik lain"]

    def test_the_old_token_stops_working(self, client, auth, user):
        headers = auth(user)
        remove(client, auth, user)
        assert client.get("/auth/me", headers=headers).status_code == 401

    def test_login_fails_afterwards(self, client, auth, user):
        email = user.email
        remove(client, auth, user)
        assert login(client, email, PASSWORD).status_code == 401

    def test_leftover_verification_codes_for_the_email_are_removed(self, client, db, auth, user):
        db.add(models.EmailVerification(
            email=user.email, name="X", password_hash="x", code_hash="x" * 64,
            expires_at=datetime.utcnow() + timedelta(minutes=5), last_sent_at=datetime.utcnow(),
        ))
        db.commit()
        remove(client, auth, user)
        db.expire_all()
        assert db.query(models.EmailVerification).count() == 0

    def test_the_picture_files_are_removed_from_disk(self, client, db, auth, make_user, make_doc, upload_dir):
        owner = make_user("high")
        doc = make_doc(owner, characters=["Budi"])
        char = db.query(models.Character).filter_by(document_id=doc.id).one()
        for url in (f"/documents/{doc.id}/cover", f"/documents/{doc.id}/characters/{char.id}/photo"):
            client.put(url, files={"file": ("a.jpg", JPEG, "image/jpeg")}, headers=auth(owner))
        assert len(list((upload_dir / "images").iterdir())) == 2
        remove(client, auth, owner)
        assert list((upload_dir / "images").iterdir()) == []

    def test_the_same_email_can_register_again(self, client, outbox, auth, user):
        email = user.email
        remove(client, auth, user)
        res = client.post("/auth/register", json={"name": "Baru", "email": email, "password": "kata-sandi-aman"})
        assert res.status_code == 202

    def test_it_requires_login(self, client):
        assert client.request("DELETE", "/auth/me", json={"password": PASSWORD}).status_code == 401

    def test_an_active_paid_plan_does_not_block_deletion(self, client, db, auth, make_user):
        paying = make_user("high", expires_at=datetime.utcnow() + timedelta(days=20))
        assert remove(client, auth, paying).status_code == 204
