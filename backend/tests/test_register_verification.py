from datetime import datetime, timedelta

import bcrypt

from tests.conftest import code_from

NAME = "Rana Afifah"
EMAIL = "rana@example.com"
PASSWORD = "kata-sandi-aman"


def start(client, email=EMAIL, name=NAME, password=PASSWORD):
    return client.post("/auth/register", json={"name": name, "email": email, "password": password})


def verify(client, code, email=EMAIL):
    return client.post("/auth/register/verify", json={"email": email, "code": code})


def resend(client, email=EMAIL):
    return client.post("/auth/register/resend", json={"email": email})


def login(client, password, email=EMAIL):
    return client.post("/auth/login", json={"email": email, "password": password})


def user_row(db, email=EMAIL):
    from app.db.models import User
    db.expire_all()
    return db.query(User).filter(User.email == email).first()


def pending_row(db, email=EMAIL):
    from app.db.models import EmailVerification
    db.expire_all()
    return db.query(EmailVerification).filter(EmailVerification.email == email).first()


def pending_count(db):
    from app.db.models import EmailVerification
    db.expire_all()
    return db.query(EmailVerification).count()


def age_pending(db, seconds, email=EMAIL):
    row = pending_row(db, email)
    row.last_sent_at = row.last_sent_at - timedelta(seconds=seconds)
    db.commit()


def wrong_code(real):
    return "000000" if real != "000000" else "111111"


def test_register_sends_code_and_does_not_create_account(client, db, outbox):
    res = start(client)
    assert res.status_code == 202
    assert "access_token" not in res.json()
    assert user_row(db) is None
    assert len(outbox) == 1
    assert outbox[0]["to"] == EMAIL
    assert len(code_from(outbox[0])) == 6


def test_correct_code_creates_free_account_and_signs_in(client, db, outbox):
    start(client)
    res = verify(client, code_from(outbox[0]))
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == EMAIL
    assert body["user"]["name"] == NAME
    assert body["user"]["tier"] == "free"
    assert body["user"]["role"] == "user"
    user = user_row(db)
    assert user is not None and user.tier == "free" and user.role == "user" and user.is_active
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == EMAIL


def test_account_can_log_in_after_verification(client, outbox):
    start(client)
    verify(client, code_from(outbox[0]))
    assert login(client, PASSWORD).status_code == 200


def test_pending_registration_is_removed_after_success(client, db, outbox):
    start(client)
    verify(client, code_from(outbox[0]))
    assert pending_row(db) is None


def test_wrong_code_is_rejected_and_creates_no_account(client, db, outbox):
    start(client)
    res = verify(client, wrong_code(code_from(outbox[0])))
    assert res.status_code == 400
    assert res.json()["detail"] == "Kode verifikasi salah."
    assert user_row(db) is None
    assert pending_row(db) is not None


def test_correct_code_still_works_after_a_few_wrong_attempts(client, outbox):
    start(client)
    code = code_from(outbox[0])
    for _ in range(4):
        assert verify(client, wrong_code(code)).status_code == 400
    assert verify(client, code).status_code == 201


def test_fifth_wrong_attempt_voids_the_registration(client, db, outbox):
    start(client)
    code = code_from(outbox[0])
    for _ in range(4):
        assert verify(client, wrong_code(code)).status_code == 400
    res = verify(client, wrong_code(code))
    assert res.status_code == 429
    assert res.json()["detail"] == "Terlalu banyak percobaan. Mulai pendaftaran lagi."
    assert pending_row(db) is None
    assert verify(client, code).status_code == 404
    assert user_row(db) is None


def test_expired_code_is_rejected(client, db, outbox):
    start(client)
    row = pending_row(db)
    row.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    res = verify(client, code_from(outbox[0]))
    assert res.status_code == 400
    assert res.json()["detail"] == "Kode verifikasi sudah kedaluwarsa. Kirim ulang kode."
    assert user_row(db) is None


def test_code_lifetime_is_ten_minutes(client, db, outbox):
    before = datetime.utcnow()
    start(client)
    row = pending_row(db)
    assert timedelta(minutes=9, seconds=30) < row.expires_at - before <= timedelta(minutes=10, seconds=30)


def test_verify_without_pending_registration(client):
    res = verify(client, "123456")
    assert res.status_code == 404
    assert res.json()["detail"] == "Pendaftaran tidak ditemukan. Mulai pendaftaran lagi."


def test_code_must_be_six_digits(client, outbox):
    start(client)
    assert verify(client, "12345").status_code == 422
    assert verify(client, "abcdef").status_code == 422
    assert verify(client, "1234567").status_code == 422


def test_existing_email_is_rejected_without_sending_mail(client, outbox):
    start(client)
    verify(client, code_from(outbox[0]))
    outbox.clear()
    res = start(client)
    assert res.status_code == 409
    assert res.json()["detail"] == "Email sudah terdaftar. Silakan masuk."
    assert outbox == []


def test_email_is_case_insensitive(client, db, outbox):
    start(client, email="Rana@Example.COM")
    assert outbox[0]["to"] == EMAIL
    res = verify(client, code_from(outbox[0]), email="RANA@example.com")
    assert res.status_code == 201
    assert user_row(db) is not None


def test_password_and_code_are_not_stored_in_plain_text(client, db, outbox):
    start(client)
    code = code_from(outbox[0])
    row = pending_row(db)
    stored = [str(getattr(row, col.name)) for col in row.__table__.columns]
    assert PASSWORD not in stored
    assert code not in stored
    assert bcrypt.checkpw(PASSWORD.encode(), row.password_hash.encode())
    assert row.code_hash != code


def test_password_chosen_at_registration_is_the_one_used_to_sign_in(client, outbox):
    start(client, password="sandi-pertama-123")
    verify(client, code_from(outbox[0]))
    assert login(client, "sandi-pertama-123").status_code == 200
    assert login(client, PASSWORD).status_code == 401


def test_resend_issues_a_new_working_code(client, db, outbox):
    start(client)
    first = code_from(outbox[0])
    age_pending(db, 61)
    res = resend(client)
    assert res.status_code == 202
    assert len(outbox) == 2
    second = code_from(outbox[1])
    if second != first:
        assert verify(client, first).status_code == 400
    assert verify(client, second).status_code == 201


def test_resend_resets_failed_attempts(client, db, outbox):
    start(client)
    code = code_from(outbox[0])
    for _ in range(3):
        verify(client, wrong_code(code))
    age_pending(db, 61)
    resend(client)
    assert pending_row(db).attempts == 0


def test_resend_too_soon_is_rejected(client, outbox):
    start(client)
    res = resend(client)
    assert res.status_code == 429
    assert res.json()["detail"] == "Tunggu sebentar sebelum meminta kode baru."
    assert len(outbox) == 1


def test_resend_without_pending_registration(client, outbox):
    res = resend(client)
    assert res.status_code == 404
    assert res.json()["detail"] == "Pendaftaran tidak ditemukan. Mulai pendaftaran lagi."
    assert outbox == []


def test_registering_again_replaces_pending_data_after_cooldown(client, db, outbox):
    start(client, name="Nama Lama", password="sandi-lama-123")
    age_pending(db, 61)
    start(client, name="Nama Baru", password="sandi-baru-123")
    assert pending_count(db) == 1
    res = verify(client, code_from(outbox[1]))
    assert res.status_code == 201
    assert res.json()["user"]["name"] == "Nama Baru"
    assert login(client, "sandi-baru-123").status_code == 200


def test_registering_again_too_soon_is_rejected(client, outbox):
    start(client)
    res = start(client)
    assert res.status_code == 429
    assert len(outbox) == 1


def test_email_taken_between_start_and_verify(client, db, outbox):
    from app.core.security import hash_password
    from app.db.models import User
    start(client)
    db.add(User(name="Orang Lain", email=EMAIL, password_hash=hash_password("sandi-lain-123"), tier="free", role="user"))
    db.commit()
    assert verify(client, code_from(outbox[0])).status_code == 409


def test_invalid_input_is_still_rejected(client, outbox):
    assert start(client, password="pendek").status_code == 422
    assert start(client, name="   ").status_code == 422
    assert start(client, email="bukan-email").status_code == 422
    assert outbox == []


def test_accounts_created_before_verification_existed_can_still_log_in(client, db):
    from app.core.security import hash_password
    from app.db.models import User
    db.add(User(name="Lama", email="lama@example.com", password_hash=hash_password("sandi-lama-123"), tier="free", role="user"))
    db.commit()
    assert login(client, "sandi-lama-123", email="lama@example.com").status_code == 200
