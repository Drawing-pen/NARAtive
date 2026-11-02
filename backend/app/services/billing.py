from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.plans import LIMITS, PAY_PER_CHECK_PRICE, PERIOD_DAYS, PLAN_LABEL, UPGRADE_PRICE
from app.db.models import Document, Transaction, UsageQuota, User
from app.services import email_templates, mailer

TIER_RANK = {"free": 0, "middle": 1, "high": 2}
MONTHS_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def _limit_reached(message: str) -> HTTPException:
    return HTTPException(status.HTTP_402_PAYMENT_REQUIRED, message)    # 402: UI menawarkan tautan ke halaman paket


# --- kuota dan batas tingkatan -------------------------------------------------

def current_period(now: datetime | None = None) -> str:
    return (now or datetime.utcnow()).strftime("%Y-%m")


def next_reset(now: datetime | None = None) -> datetime:
    now = now or datetime.utcnow()
    return datetime(now.year + (now.month == 12), now.month % 12 + 1, 1)


def used_this_month(db: Session, user: User) -> int:
    row = db.scalar(select(UsageQuota).where(UsageQuota.user_id == user.id, UsageQuota.period == current_period()))
    return row.used if row else 0


def active_books(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).select_from(Document).where(Document.user_id == user.id)) or 0


def ensure_can_upload(db: Session, user: User, page_count: int) -> None:
    """Periksa batas halaman, kapasitas koleksi, dan kuota bulanan (UC-01 langkah 3)."""
    limits = LIMITS[user.access_tier]
    label = PLAN_LABEL[user.access_tier]
    if limits.max_pages is not None and page_count > limits.max_pages:
        raise _limit_reached(
            f"Batas halaman tercapai: file ini {page_count} halaman, paket {label} maksimal {limits.max_pages} halaman per unggahan. "
            "Naikkan paketmu untuk mengunggah file yang lebih panjang."
        )
    if limits.max_active is not None and active_books(db, user) >= limits.max_active:
        raise _limit_reached(
            f"Koleksi aktif penuh: paket {label} maksimal {limits.max_active} e-book. Hapus e-book yang tidak dipakai atau naikkan paketmu."
        )
    if limits.monthly is not None and used_this_month(db, user) >= limits.monthly and user.extra_checks <= 0:
        reset = next_reset()
        raise _limit_reached(
            f"Kuota analisis bulan ini habis ({limits.monthly} per bulan). Beli analisis tambahan, "
            f"atau tunggu kuota direset pada 1 {MONTHS_ID[reset.month - 1]} {reset.year}."
        )


def consume_analysis(db: Session, user: User) -> None:
    """Catat satu analisis (UC-01 pasca-kondisi). Kuota bulanan dipakai dulu, lalu analisis tambahan hasil pay-per-check."""
    period = current_period()
    row = db.scalar(select(UsageQuota).where(UsageQuota.user_id == user.id, UsageQuota.period == period))
    if row is None:
        row = UsageQuota(user_id=user.id, period=period, used=0)
        db.add(row)
    monthly = LIMITS[user.access_tier].monthly
    if monthly is not None and row.used >= monthly:
        user.extra_checks = max(0, user.extra_checks - 1)
    else:
        row.used += 1


# --- transaksi -----------------------------------------------------------------

def price_for(kind: str, plan: str | None, quantity: int) -> int:
    return UPGRADE_PRICE[plan] if kind == "upgrade" else PAY_PER_CHECK_PRICE * quantity


def refresh(db: Session, tx: Transaction) -> Transaction:
    """VA yang lewat batas waktunya dianggap kedaluwarsa."""
    if tx.status == "pending" and tx.expires_at <= datetime.utcnow():
        tx.status = "expired"
        db.commit()
    return tx


def settle(db: Session, tx: Transaction) -> None:
    """Pembayaran terkonfirmasi: terapkan hasil pembelian lalu kirim invoice. Aman dipanggil berulang (notifikasi ganda)."""
    if tx.status == "paid":
        return
    user = db.get(User, tx.user_id)
    now = datetime.utcnow()
    tx.status, tx.paid_at = "paid", now
    if tx.kind == "upgrade":
        active = user.paid_tier != "free" and user.tier_expires_at and user.tier_expires_at > now
        start = user.tier_expires_at if active else now
        user.tier, user.tier_expires_at = tx.plan, start + timedelta(days=PERIOD_DAYS)
    else:
        user.extra_checks += tx.quantity
    db.commit()
    send_invoice(user, tx)


def send_invoice(user: User, tx: Transaction) -> None:
    mail = email_templates.invoice(user, tx)
    mailer.send(user.email, mail.subject, mail.text, mail.html)


def send_instructions(user: User, tx: Transaction) -> None:
    mail = email_templates.payment_instructions(user, tx)
    mailer.send(user.email, mail.subject, mail.text, mail.html)
