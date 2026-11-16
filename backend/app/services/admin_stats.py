"""Statistik agregat untuk panel admin (R22). Tidak pernah mengembalikan data pribadi pengguna."""
from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.plans import LIMITS
from app.db.models import Document, Transaction, UsageQuota, User

DAYS = 30
TX_STATUSES = ("pending", "paid", "failed", "expired", "cancelled")
DOC_STATUSES = ("uploaded", "queued", "analyzing", "done", "failed")
JOB_STATUSES = ("done", "partial", "failed")
TOP_REASONS = 5


def _days(today: date) -> list[date]:
    return [today - timedelta(days=DAYS - 1 - i) for i in range(DAYS)]


def _series(days: list[date], values: dict[date, int], key: str) -> list[dict]:
    return [{"date": d.isoformat(), key: values.get(d, 0)} for d in days]


def _jobs(statuses) -> dict:
    count = Counter(statuses)
    return {s: count.get(s, 0) for s in JOB_STATUSES}


def overview(db: Session) -> dict:
    now = datetime.utcnow()
    today = now.date()
    days = _days(today)
    first = set(days)
    month = now.strftime("%Y-%m")

    users = list(db.scalars(select(User).where(User.role != "admin")))
    active = [u for u in users if u.is_active]
    per_tier = Counter(u.paid_tier for u in active)
    signups = Counter(u.created_at.date() for u in users if u.created_at.date() in first)

    rows = list(db.execute(
        select(Transaction.kind, Transaction.plan, Transaction.amount, Transaction.status, Transaction.paid_at)
        .join(User, User.id == Transaction.user_id)
        .where(User.role != "admin")
    ))
    status_count = Counter(r.status for r in rows)
    paid = [r for r in rows if r.status == "paid"]
    by_plan = {}
    for name in ("middle", "high", "pay_per_check"):
        matching = [r for r in paid if (r.kind == "pay_per_check" and name == "pay_per_check") or (r.kind == "upgrade" and r.plan == name)]
        by_plan[name] = {"count": len(matching), "amount": sum(r.amount for r in matching)}
    per_day = Counter()
    for r in paid:
        if r.paid_at and r.paid_at.date() in first:
            per_day[r.paid_at.date()] += r.amount

    docs = list(db.execute(
        select(Document.status, Document.created_at, Document.failure_reason, Document.summary_status, Document.characters_status)
        .join(User, User.id == Document.user_id)
        .where(User.role != "admin")
    ))
    doc_count = Counter(d.status for d in docs)
    reasons = Counter(d.failure_reason for d in docs if d.status == "failed" and d.failure_reason)
    uploads = Counter(d.created_at.date() for d in docs if d.created_at.date() in first)

    used = {
        (q.user_id): q.used
        for q in db.scalars(select(UsageQuota).where(UsageQuota.period == month))
    }
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
            "signups": _series(days, signups, "count"),
        },
        "revenue": {
            "paid_total": sum(r.amount for r in paid),
            "paid_this_month": sum(r.amount for r in paid if r.paid_at and r.paid_at.strftime("%Y-%m") == month),
            "by_status": {s: status_count.get(s, 0) for s in TX_STATUSES},
            "by_plan": by_plan,
            "per_day": _series(days, per_day, "amount"),
        },
        "documents": {
            "total": len(docs),
            "by_status": {s: doc_count.get(s, 0) for s in DOC_STATUSES},
            "uploads": _series(days, uploads, "count"),
            "failure_reasons": [{"reason": r, "count": c} for r, c in reasons.most_common(TOP_REASONS)],
            "summary": _jobs(d.summary_status for d in docs),
            "characters": _jobs(d.characters_status for d in docs),
        },
        "quota": {"at_limit": at_limit},
        "generated_at": now,
    }
