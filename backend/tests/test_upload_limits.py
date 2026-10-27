from datetime import datetime, timedelta

from fastapi import HTTPException

from app.db.models import UsageQuota
from app.services import billing


def attempt(db, user, pages):
    try:
        billing.ensure_can_upload(db, user, pages)
    except HTTPException as e:
        return e
    return None


def record_usage(db, user, used):
    db.add(UsageQuota(user_id=user.id, period=billing.current_period(), used=used))
    db.commit()


def test_standard_page_limit_is_50(db, make_user):
    user = make_user("free")
    assert attempt(db, user, 50) is None
    err = attempt(db, user, 51)
    assert err.status_code == 402 and "Batas halaman" in err.detail


def test_middle_page_limit_is_300(db, make_user):
    user = make_user("middle")
    assert attempt(db, user, 300) is None
    assert attempt(db, user, 301).status_code == 402


def test_high_has_no_page_limit(db, make_user):
    user = make_user("high")
    assert attempt(db, user, 5000) is None


def test_standard_monthly_quota_is_3(db, make_user):
    user = make_user("free")
    record_usage(db, user, 2)
    assert attempt(db, user, 10) is None
    db.query(UsageQuota).update({"used": 3})
    db.commit()
    err = attempt(db, user, 10)
    assert err.status_code == 402 and "Kuota analisis" in err.detail


def test_middle_monthly_quota_is_15(db, make_user):
    user = make_user("middle")
    record_usage(db, user, 14)
    assert attempt(db, user, 10) is None
    db.query(UsageQuota).update({"used": 15})
    db.commit()
    assert attempt(db, user, 10).status_code == 402


def test_extra_checks_allow_upload_after_quota_is_used(db, make_user):
    user = make_user("free", extra_checks=1)
    record_usage(db, user, 3)
    assert attempt(db, user, 10) is None


def test_monthly_quota_is_used_before_extra_checks(db, make_user):
    user = make_user("free", extra_checks=2)
    billing.consume_analysis(db, user)
    db.commit()
    assert billing.used_this_month(db, user) == 1 and user.extra_checks == 2


def test_extra_checks_are_consumed_when_quota_is_full(db, make_user):
    user = make_user("free", extra_checks=2)
    record_usage(db, user, 3)
    billing.consume_analysis(db, user)
    db.commit()
    assert billing.used_this_month(db, user) == 3 and user.extra_checks == 1


def test_standard_active_book_limit_is_3(db, make_user, make_doc):
    user = make_user("free")
    for n in range(2):
        make_doc(user, title=f"Buku {n}")
    assert attempt(db, user, 10) is None
    make_doc(user, title="Buku 3")
    err = attempt(db, user, 10)
    assert err.status_code == 402 and "Koleksi aktif penuh" in err.detail


def test_high_has_no_limits_on_books_or_quota(db, make_user, make_doc):
    user = make_user("high")
    for n in range(5):
        make_doc(user, title=f"Buku {n}")
    record_usage(db, user, 999)
    assert attempt(db, user, 10) is None


def test_expired_middle_gets_standard_limits(db, make_user):
    user = make_user("middle", expires_at=datetime.utcnow() - timedelta(days=1))
    assert attempt(db, user, 100).status_code == 402
