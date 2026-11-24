import calendar
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.plans import LIMITS
from app.db.models import Document, Transaction, UsageQuota, User

DAYS = 30
TX_STATUSES = ("pending", "paid", "failed", "expired", "cancelled")
DOC_STATUSES = ("uploaded", "queued", "analyzing", "done", "failed", "not_novel")
JOB_STATUSES = ("done", "partial", "failed")
TOP_REASONS = 5
MONTH_NAMES = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


@dataclass(frozen=True)
class Period:
    mode: str
    year: int | None
    month: int | None
    start: datetime
    end: datetime
    label: str
    granularity: str
    buckets: list[date]

    def bucket(self, moment: datetime) -> date:
        return date(moment.year, moment.month, 1) if self.granularity == "month" else moment.date()

    def contains(self, moment: datetime | None) -> bool:
        return moment is not None and self.start <= moment < self.end

    @property
    def tables_label(self) -> str:
        return "Seluruh waktu" if self.mode == "last30" else self.label

    @property
    def filters_tables(self) -> bool:
        return self.mode != "last30"


def make_period(today: date, year: int | None = None, month: int | None = None) -> Period:
    if year is None:
        days = [today - timedelta(days=DAYS - 1 - i) for i in range(DAYS)]
        return Period("last30", None, None, datetime.combine(days[0], datetime.min.time()), datetime.combine(today + timedelta(days=1), datetime.min.time()),
                      "30 hari terakhir", "day", days)
    if month is None:
        return Period("year", year, None, datetime(year, 1, 1), datetime(year + 1, 1, 1), f"Tahun {year}", "month", [date(year, m, 1) for m in range(1, 13)])
    last = calendar.monthrange(year, month)[1]
    end = datetime(year + (month == 12), month % 12 + 1, 1)
    return Period("month", year, month, datetime(year, month, 1), end, f"{MONTH_NAMES[month - 1]} {year}", "day", [date(year, month, d) for d in range(1, last + 1)])


def _series(buckets: list[date], values: dict[date, int], key: str) -> list[dict]:
    return [{"date": d.isoformat(), key: values.get(d, 0)} for d in buckets]


def _jobs(statuses) -> dict:
    count = Counter(statuses)
    return {s: count.get(s, 0) for s in JOB_STATUSES}


def _years(users, transactions, documents, now: datetime, selected: int | None) -> list[int]:
    found = [m.year for m in [*users, *transactions, *documents] if m is not None]
    first = min([*found, now.year, *([selected] if selected else [])])
    last = max(now.year, selected or now.year)
    return list(range(first, last + 1))


def overview(db: Session, year: int | None = None, month: int | None = None) -> dict:
    now = datetime.utcnow()
    today = now.date()
    period = make_period(today, year, month)
    current_month = now.strftime("%Y-%m")

    users = list(db.scalars(select(User).where(User.role != "admin")))
    active = [u for u in users if u.is_active]
    per_tier = Counter(u.paid_tier for u in active)
    signups = Counter(period.bucket(u.created_at) for u in users if period.contains(u.created_at))

    rows = list(db.execute(
        select(Transaction.kind, Transaction.plan, Transaction.amount, Transaction.status, Transaction.paid_at, Transaction.created_at)
        .join(User, User.id == Transaction.user_id)
        .where(User.role != "admin")
    ))
    shown_rows = [r for r in rows if period.contains(r.created_at)] if period.filters_tables else rows
    status_count = Counter(r.status for r in shown_rows)
    paid = [r for r in rows if r.status == "paid"]
    paid_in_period = [r for r in paid if period.contains(r.paid_at)]
    plan_scope = paid_in_period if period.filters_tables else paid
    by_plan = {}
    for name in ("middle", "high", "pay_per_check"):
        matching = [r for r in plan_scope if (r.kind == "pay_per_check" and name == "pay_per_check") or (r.kind == "upgrade" and r.plan == name)]
        by_plan[name] = {"count": len(matching), "amount": sum(r.amount for r in matching)}
    per_bucket = Counter()
    for r in paid_in_period:
        per_bucket[period.bucket(r.paid_at)] += r.amount

    docs = list(db.execute(
        select(Document.status, Document.created_at, Document.failure_reason, Document.summary_status, Document.characters_status)
        .join(User, User.id == Document.user_id)
        .where(User.role != "admin")
    ))
    shown_docs = [d for d in docs if period.contains(d.created_at)] if period.filters_tables else docs
    doc_count = Counter(d.status for d in shown_docs)
    reasons = Counter(d.failure_reason for d in shown_docs if d.status == "failed" and d.failure_reason)
    uploads = Counter(period.bucket(d.created_at) for d in docs if period.contains(d.created_at))

    quota_period = {"last30": current_month, "month": f"{year}-{month:02d}" if month else None, "year": None}[period.mode]
    at_limit = None
    if quota_period is not None:
        used = {q.user_id: q.used for q in db.scalars(select(UsageQuota).where(UsageQuota.period == quota_period))}
        at_limit = 0
        for u in active:
            monthly = LIMITS[u.paid_tier].monthly
            if monthly is not None and used.get(u.id, 0) >= monthly:
                at_limit += 1

    return {
        "users": {
            "total": len(users),
            "inactive": len(users) - len(active),
            "per_tier": {t: per_tier.get(t, 0) for t in ("free", "middle", "high")},
            "registered": sum(signups.values()),
            "signups": _series(period.buckets, signups, "count"),
        },
        "revenue": {
            "paid_total": sum(r.amount for r in paid),
            "paid_this_month": sum(r.amount for r in paid if r.paid_at and r.paid_at.strftime("%Y-%m") == current_month),
            "paid_in_period": sum(r.amount for r in paid_in_period),
            "by_status": {s: status_count.get(s, 0) for s in TX_STATUSES},
            "by_plan": by_plan,
            "per_day": _series(period.buckets, per_bucket, "amount"),
        },
        "documents": {
            "total": len(shown_docs),
            "by_status": {s: doc_count.get(s, 0) for s in DOC_STATUSES},
            "uploads": _series(period.buckets, uploads, "count"),
            "failure_reasons": [{"reason": r, "count": c} for r, c in reasons.most_common(TOP_REASONS)],
            "summary": _jobs(d.summary_status for d in shown_docs),
            "characters": _jobs(d.characters_status for d in shown_docs),
        },
        "quota": {"at_limit": at_limit},
        "period": {
            "mode": period.mode,
            "year": period.year,
            "month": period.month,
            "label": period.label,
            "granularity": period.granularity,
            "tables_label": period.tables_label,
            "available_years": _years(
                [u.created_at for u in users], [r.created_at for r in rows], [d.created_at for d in docs], now, period.year,
            ),
        },
        "generated_at": now,
    }
