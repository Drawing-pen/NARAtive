import json
from datetime import datetime, timedelta

import pytest

from app.db import models
from tests.test_admin import URL, admin  # noqa: F401

COUNTER = [0]


def user_at(make_user, db, when, tier="free", **kw):
    user = make_user(tier, **kw)
    user.created_at = when
    db.commit()
    return user


def tx_at(db, user, created, *, paid=None, status="paid", kind="upgrade", plan="middle", amount=29_000):
    COUNTER[0] += 1
    row = models.Transaction(
        user_id=user.id, order_id=f"NAR-P-{COUNTER[0]:05d}", kind=kind, plan=plan if kind == "upgrade" else None, amount=amount,
        bank="bca", va_number=f"7700{COUNTER[0]:08d}", provider="simulated", status=status,
        created_at=created, expires_at=created + timedelta(hours=24), paid_at=paid if paid is not None else (created if status == "paid" else None),
    )
    db.add(row)
    db.commit()
    return row


def doc_at(db, make_doc, user, created, **kw):
    reason = kw.pop("reason", None)
    doc = make_doc(user, **kw)
    doc.created_at = created
    if reason:
        doc.failure_reason = reason
    db.commit()
    return doc


def get(client, auth, admin, **params):
    return client.get(URL, params=params, headers=auth(admin))


def body(client, auth, admin, **params):
    res = get(client, auth, admin, **params)
    assert res.status_code == 200, res.text
    return res.json()


class TestParameters:
    @pytest.mark.parametrize("params", [{"month": 5}, {"month": 0, "year": 2026}, {"month": 13, "year": 2026}, {"year": 1999}, {"year": 2101}, {"year": "dua"}, {"year": 2026, "month": "mei"}])
    def test_invalid_parameters_are_refused(self, client, auth, admin, params):
        assert get(client, auth, admin, **params).status_code == 422

    def test_a_month_without_a_year_explains_why(self, client, auth, admin):
        res = get(client, auth, admin, month=5)
        assert res.status_code == 422 and "Pilih tahun" in json.dumps(res.json())

    @pytest.mark.parametrize("params", [{}, {"year": 2026}, {"year": 2026, "month": 10}])
    def test_a_token_is_still_required(self, client, params):
        assert client.get(URL, params=params).status_code == 401

    @pytest.mark.parametrize("params", [{"year": 2026}, {"year": 2026, "month": 10}])
    def test_only_an_admin_may_filter(self, client, auth, make_user, params):
        assert client.get(URL, params=params, headers=auth(make_user())).status_code == 403

    def test_a_future_period_is_allowed_and_empty(self, client, auth, admin, make_user, db):
        user_at(make_user, db, datetime(2026, 10, 5))
        data = body(client, auth, admin, year=2090, month=2)
        assert data["users"]["registered"] == 0 and data["revenue"]["paid_in_period"] == 0 and data["documents"]["total"] == 0
        assert len(data["users"]["signups"]) == 28


class TestDefaultMode:
    def test_the_period_object_describes_the_last_thirty_days(self, client, auth, admin):
        period = body(client, auth, admin)["period"]
        assert period["mode"] == "last30" and period["year"] is None and period["month"] is None
        assert period["label"] == "30 hari terakhir" and period["granularity"] == "day" and period["tables_label"] == "Seluruh waktu"
        assert datetime.utcnow().year in period["available_years"]

    def test_series_are_still_thirty_days(self, client, auth, admin):
        data = body(client, auth, admin)
        assert [len(data["users"]["signups"]), len(data["revenue"]["per_day"]), len(data["documents"]["uploads"])] == [30, 30, 30]

    def test_the_new_totals_equal_the_thirty_day_series(self, client, auth, admin, make_user, db):
        user = make_user()
        tx_at(db, user, datetime.utcnow() - timedelta(days=2), amount=29_000)
        tx_at(db, user, datetime.utcnow() - timedelta(days=100), amount=59_000, plan="high")
        data = body(client, auth, admin)
        assert data["revenue"]["paid_in_period"] == 29_000 == sum(r["amount"] for r in data["revenue"]["per_day"])
        assert data["revenue"]["paid_total"] == 88_000
        assert data["users"]["registered"] == sum(r["count"] for r in data["users"]["signups"])

    def test_the_tables_stay_all_time(self, client, auth, admin, make_user, db):
        user = make_user()
        tx_at(db, user, datetime.utcnow() - timedelta(days=100))
        data = body(client, auth, admin)
        assert data["revenue"]["by_status"]["paid"] == 1


class TestMonthMode:
    @pytest.fixture
    def world(self, client, auth, admin, make_user, make_doc, db):
        """Oktober 2026 berisi data; November dan September berisi data pembanding."""
        user = user_at(make_user, db, datetime(2026, 10, 5, 8))
        user_at(make_user, db, datetime(2026, 10, 31, 23, 59, 59))
        user_at(make_user, db, datetime(2026, 11, 1, 0, 0, 0))
        user_at(make_user, db, datetime(2026, 9, 30, 23, 59, 59))
        tx_at(db, user, datetime(2026, 10, 3), amount=29_000)
        tx_at(db, user, datetime(2026, 10, 20), amount=59_000, plan="high")
        tx_at(db, user, datetime(2026, 10, 31, 23, 59, 59), amount=5_000, kind="pay_per_check")
        tx_at(db, user, datetime(2026, 11, 1), amount=29_000)
        tx_at(db, user, datetime(2026, 10, 12), status="pending", amount=29_000)
        tx_at(db, user, datetime(2026, 10, 13), status="expired", amount=29_000)
        tx_at(db, user, datetime(2026, 9, 25), paid=datetime(2026, 10, 2), amount=29_000)
        doc_at(db, make_doc, user, datetime(2026, 10, 4), status="done", summary="Ringkas.", characters=["Rana"])
        doc_at(db, make_doc, user, datetime(2026, 10, 6), status="failed", reason="PDF terenkripsi")
        doc_at(db, make_doc, user, datetime(2026, 10, 7), status="failed", reason="PDF terenkripsi")
        doc_at(db, make_doc, user, datetime(2026, 11, 2), status="failed", reason="Teks tidak terbaca")
        doc_at(db, make_doc, user, datetime(2026, 9, 2), status="done")
        return body(client, auth, admin, year=2026, month=10)

    def test_the_period_object(self, world):
        period = world["period"]
        assert (period["mode"], period["year"], period["month"]) == ("month", 2026, 10)
        assert period["label"] == "Oktober 2026" and period["tables_label"] == "Oktober 2026" and period["granularity"] == "day"
        assert 2026 in period["available_years"]

    def test_every_series_has_one_point_per_day_of_the_month(self, world):
        for series in (world["users"]["signups"], world["revenue"]["per_day"], world["documents"]["uploads"]):
            assert len(series) == 31 and series[0]["date"] == "2026-10-01" and series[-1]["date"] == "2026-10-31"

    @pytest.mark.parametrize("year,month,days", [(2026, 2, 28), (2028, 2, 29), (2026, 4, 30), (2026, 12, 31)])
    def test_the_length_follows_the_calendar(self, client, auth, admin, year, month, days):
        assert len(body(client, auth, admin, year=year, month=month)["users"]["signups"]) == days

    def test_signups_include_the_last_second_and_exclude_the_next_midnight(self, world):
        by_date = {r["date"]: r["count"] for r in world["users"]["signups"]}
        assert by_date["2026-10-05"] == 1 and by_date["2026-10-31"] == 1 and sum(by_date.values()) == 2
        assert world["users"]["registered"] == 2

    def test_revenue_is_grouped_by_the_day_it_was_paid(self, world):
        by_date = {r["date"]: r["amount"] for r in world["revenue"]["per_day"]}
        assert by_date["2026-10-02"] == 29_000 and by_date["2026-10-03"] == 29_000 and by_date["2026-10-31"] == 5_000
        assert world["revenue"]["paid_in_period"] == 29_000 + 29_000 + 59_000 + 5_000

    def test_all_time_totals_are_unchanged(self, world):
        assert world["revenue"]["paid_total"] == 29_000 * 3 + 59_000 + 5_000

    def test_plans_count_only_what_was_paid_in_the_month(self, world):
        plans = world["revenue"]["by_plan"]
        assert plans["middle"] == {"count": 2, "amount": 58_000}
        assert plans["high"] == {"count": 1, "amount": 59_000}
        assert plans["pay_per_check"] == {"count": 1, "amount": 5_000}

    def test_statuses_count_the_transactions_created_in_the_month(self, world):
        status = world["revenue"]["by_status"]
        assert status["pending"] == 1 and status["expired"] == 1 and status["paid"] == 3 and status["failed"] == 0

    def test_documents_are_the_ones_created_in_the_month(self, world):
        docs = world["documents"]
        assert docs["total"] == 3 and docs["by_status"]["done"] == 1 and docs["by_status"]["failed"] == 2
        assert docs["failure_reasons"] == [{"reason": "PDF terenkripsi", "count": 2}]
        assert docs["summary"]["done"] == 1 and docs["characters"]["done"] == 1
        assert {r["date"]: r["count"] for r in docs["uploads"]}["2026-10-06"] == 1

    def test_the_account_numbers_are_the_current_snapshot(self, world):
        assert world["users"]["total"] == 4


class TestYearMode:
    @pytest.fixture
    def world(self, client, auth, admin, make_user, make_doc, db):
        user = user_at(make_user, db, datetime(2026, 1, 1, 0, 0, 0))
        user_at(make_user, db, datetime(2026, 12, 31, 23, 59, 59))
        user_at(make_user, db, datetime(2027, 1, 1, 0, 0, 0))
        user_at(make_user, db, datetime(2025, 12, 31, 23, 59, 59))
        tx_at(db, user, datetime(2026, 3, 10), amount=29_000)
        tx_at(db, user, datetime(2026, 3, 11), amount=59_000, plan="high")
        tx_at(db, user, datetime(2026, 12, 31, 23, 59, 59), amount=5_000, kind="pay_per_check")
        tx_at(db, user, datetime(2027, 1, 1), amount=29_000)
        doc_at(db, make_doc, user, datetime(2026, 7, 1), status="done")
        doc_at(db, make_doc, user, datetime(2025, 7, 1), status="done")
        return body(client, auth, admin, year=2026)

    def test_the_period_object(self, world):
        period = world["period"]
        assert (period["mode"], period["year"], period["month"]) == ("year", 2026, None)
        assert period["label"] == "Tahun 2026" and period["tables_label"] == "Tahun 2026" and period["granularity"] == "month"
        assert 2025 in period["available_years"] and 2026 in period["available_years"]

    def test_every_series_has_twelve_monthly_points(self, world):
        for series in (world["users"]["signups"], world["revenue"]["per_day"], world["documents"]["uploads"]):
            assert [r["date"] for r in series] == [f"2026-{m:02d}-01" for m in range(1, 13)]

    def test_signups_are_grouped_by_month_with_year_boundaries(self, world):
        by_date = {r["date"]: r["count"] for r in world["users"]["signups"]}
        assert by_date["2026-01-01"] == 1 and by_date["2026-12-01"] == 1 and sum(by_date.values()) == 2
        assert world["users"]["registered"] == 2

    def test_revenue_is_grouped_by_month(self, world):
        by_date = {r["date"]: r["amount"] for r in world["revenue"]["per_day"]}
        assert by_date["2026-03-01"] == 88_000 and by_date["2026-12-01"] == 5_000 and sum(by_date.values()) == 93_000
        assert world["revenue"]["paid_in_period"] == 93_000

    def test_documents_of_the_year_only(self, world):
        assert world["documents"]["total"] == 1

    def test_the_quota_card_has_no_number_for_a_whole_year(self, world):
        assert world["quota"]["at_limit"] is None


class TestQuotaPerMonth:
    def test_the_selected_month_decides_who_is_at_the_limit(self, client, auth, admin, make_user, db):
        penuh = make_user("free")
        masih = make_user("free")
        db.add(models.UsageQuota(user_id=penuh.id, period="2026-09", used=3))
        db.add(models.UsageQuota(user_id=masih.id, period="2026-09", used=1))
        db.add(models.UsageQuota(user_id=penuh.id, period="2026-10", used=0))
        db.commit()
        assert body(client, auth, admin, year=2026, month=9)["quota"]["at_limit"] == 1
        assert body(client, auth, admin, year=2026, month=10)["quota"]["at_limit"] == 0

    def test_the_default_mode_still_uses_the_running_month(self, client, auth, admin, make_user, db):
        user = make_user("free")
        db.add(models.UsageQuota(user_id=user.id, period=datetime.utcnow().strftime("%Y-%m"), used=3))
        db.commit()
        assert body(client, auth, admin)["quota"]["at_limit"] == 1


class TestAvailableYears:
    def test_it_runs_from_the_earliest_data_to_the_current_year(self, client, auth, admin, make_user, make_doc, db):
        user_at(make_user, db, datetime(2024, 6, 1))
        years = body(client, auth, admin)["period"]["available_years"]
        assert years == list(range(2024, datetime.utcnow().year + 1))

    def test_transactions_and_documents_count_too(self, client, auth, admin, make_user, make_doc, db):
        user = user_at(make_user, db, datetime(2026, 6, 1))
        tx_at(db, user, datetime(2023, 2, 1))
        doc_at(db, make_doc, user, datetime(2022, 2, 1))
        assert body(client, auth, admin)["period"]["available_years"][0] == 2022

    def test_the_selected_year_is_always_offered(self, client, auth, admin):
        assert 2090 in body(client, auth, admin, year=2090)["period"]["available_years"]

    def test_the_admin_account_does_not_extend_the_range(self, client, auth, admin, db):
        admin.created_at = datetime(2001, 1, 1)
        db.commit()
        assert body(client, auth, admin)["period"]["available_years"] == [datetime.utcnow().year]


class TestAdminDataIsExcluded:
    def test_the_admin_transactions_and_documents_are_not_counted_in_a_period(self, client, auth, admin, make_doc, db):
        tx_at(db, admin, datetime(2026, 10, 3))
        doc_at(db, make_doc, admin, datetime(2026, 10, 3))
        data = body(client, auth, admin, year=2026, month=10)
        assert data["revenue"]["paid_in_period"] == 0 and data["documents"]["total"] == 0 and data["users"]["registered"] == 0


class TestPrivacy:
    @pytest.mark.parametrize("params", [{}, {"year": 2026}, {"year": 2026, "month": 10}])
    def test_no_identity_keys_or_values(self, client, auth, admin, make_user, make_doc, db, params):
        user = make_user(email="rahasia.sekali@example.com")
        user.name = "Nama Rahasia Banget"
        user.created_at = datetime(2026, 10, 5)
        db.commit()
        doc_at(db, make_doc, user, datetime(2026, 10, 6), title="Judul Rahasia Banget", reason="PDF terenkripsi", status="failed")
        row = tx_at(db, user, datetime(2026, 10, 3))
        raw = json.dumps(client.get(URL, params=params, headers=auth(admin)).json())
        for secret in ("rahasia.sekali", "Nama Rahasia", "Judul Rahasia", ".pdf", row.order_id, row.va_number, "pemilik@example.com"):
            assert secret not in raw
        for key in ('"email"', '"name"', '"title"', '"filename"', '"user_id"', '"order_id"', '"va_number"', '"id"'):
            assert key not in raw
