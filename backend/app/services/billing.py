import logging
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.plans import LIMITS, PAY_PER_CHECK_PRICE, PERIOD_DAYS, PLAN_LABEL, UPGRADE_PRICE
from app.db.models import Document, Transaction, UsageQuota, User
from app.services import email_templates, mailer, payments

log = logging.getLogger("uvicorn.error")

RECHECK_DAYS = 7
FINAL_STATUSES = ("expired", "cancelled", "failed")
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
    return db.scalar(select(func.count()).select_from(Document).where(Document.user_id == user.id, Document.status.notin_(("failed", "not_novel")))) or 0


def books_being_read(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).select_from(Document).where(Document.user_id == user.id, Document.status == "reading")) or 0


def remaining_analyses(db: Session, user: User) -> int | None:
    monthly = LIMITS[user.access_tier].monthly
    if monthly is None:
        return None
    return max(0, monthly - used_this_month(db, user)) + user.extra_checks


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
    if limits.monthly is not None and remaining_analyses(db, user) <= books_being_read(db, user):
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


def _gateway_amount(data: dict) -> int | None:
    if data.get("gross_amount") is None:
        return None
    try:
        return int(float(data["gross_amount"]))
    except (TypeError, ValueError):
        return None


def _reconcile(db: Session, tx: Transaction, only_paid: bool = False) -> None:
    try:
        data = payments.fetch_status(tx.order_id)
    except payments.PaymentError:
        return
    new_status = payments.map_status(str(data.get("transaction_status", "")))
    if new_status == "paid":
        amount = _gateway_amount(data)
        if amount != tx.amount:
            log.warning("Penelusuran %s ditolak: nominal Midtrans %s berbeda dari pesanan %s", tx.order_id, amount, tx.amount)
            return
        settle(db, tx, data)
    elif new_status and not only_paid:
        tx.status = new_status
        db.commit()


def _midtrans_live(tx: Transaction) -> bool:
    return tx.provider == "midtrans" and payments.provider() == "midtrans"


def refresh(db: Session, tx: Transaction) -> Transaction:
    """Transaksi Midtrans yang menunggu ditanyakan ke Midtrans (notifikasi bisa terlewat); status akhir yang baru juga dicek ulang
    untuk pembayaran yang terlambat (R32); VA yang lewat batas waktunya dianggap kedaluwarsa."""
    if _midtrans_live(tx):
        if tx.status == "pending":
            _reconcile(db, tx)
        elif tx.status in FINAL_STATUSES and tx.created_at >= datetime.utcnow() - timedelta(days=RECHECK_DAYS):
            _reconcile(db, tx, only_paid=True)
    if tx.status == "pending" and tx.expires_at <= datetime.utcnow():
        tx.status = "expired"
        db.commit()
    return tx


def recheck(db: Session, tx: Transaction) -> Transaction:
    """Pemeriksaan atas permintaan pengguna (R32): tanpa batas umur pesanan."""
    if tx.status != "paid" and _midtrans_live(tx):
        _reconcile(db, tx, only_paid=tx.status != "pending")
    if tx.status == "pending" and tx.expires_at <= datetime.utcnow():
        tx.status = "expired"
        db.commit()
    return tx


def _described(tx: Transaction, gateway: dict, message: str, can_sync: bool, applied: bool) -> dict:
    return {
        "order_id": tx.order_id, "provider": tx.provider, "kind": tx.kind, "plan": tx.plan, "quantity": tx.quantity,
        "local_status": tx.status, "local_amount": tx.amount, "local_method": tx.payment_method,
        "created_at": tx.created_at, "expires_at": tx.expires_at, "paid_at": tx.paid_at,
        "gateway": gateway, "can_sync": can_sync, "applied": applied, "message": message,
    }


def _inspect(tx: Transaction) -> tuple[dict, dict | None]:
    gateway = {"checked": False, "status": None, "raw_status": None, "amount": None, "method": None}
    data = None
    if tx.provider != "midtrans":
        return _described(tx, gateway, "Pesanan ini berasal dari mode simulasi; tidak ada data di Midtrans.", False, False), None
    if payments.provider() != "midtrans":
        return _described(tx, gateway, "Kunci Midtrans belum diatur di server; pesanan tidak bisa diperiksa.", False, False), None
    try:
        data = payments.fetch_status(tx.order_id)
    except payments.PaymentError:
        return _described(tx, gateway, "Midtrans tidak merespons. Coba lagi sebentar lagi.", False, False), None
    raw = str(data.get("transaction_status") or "") or None
    gateway = {
        "checked": True, "status": payments.map_status(raw or ""), "raw_status": raw,
        "amount": _gateway_amount(data), "method": payments.method_label(data),
    }
    if gateway["status"] == "paid":
        if tx.status == "paid":
            return _described(tx, gateway, "Sudah tercatat berhasil dan sesuai dengan Midtrans.", False, False), data
        if gateway["amount"] == tx.amount:
            message = "Midtrans mencatat pembayaran ini lunas, tetapi di NARAtive belum berhasil. Tekan Sinkronkan untuk mencatatnya."
            return _described(tx, gateway, message, True, False), data
        message = "Midtrans mencatat lunas tetapi nominalnya berbeda dari pesanan. Periksa manual di dashboard Midtrans."
        return _described(tx, gateway, message, False, False), data
    if tx.status == "paid":
        message = "Tercatat berhasil di NARAtive tetapi Midtrans tidak melaporkan lunas. Periksa di dashboard Midtrans."
        return _described(tx, gateway, message, False, False), data
    return _described(tx, gateway, "Midtrans belum mencatat pembayaran lunas untuk pesanan ini.", False, False), data


def inspect(tx: Transaction) -> dict:
    return _inspect(tx)[0]


def sync(db: Session, tx: Transaction) -> dict:
    result, data = _inspect(tx)
    if not result["can_sync"]:
        return result
    settle(db, tx, data)
    message = "Pembayaran dicatat berhasil; paket atau analisis pengguna sudah diterapkan dan invoice dikirim."
    return _described(tx, result["gateway"], message, False, True)


def settle(db: Session, tx: Transaction, gateway: dict | None = None) -> None:
    """Pembayaran terkonfirmasi: terapkan hasil pembelian lalu kirim invoice. Aman dipanggil berulang (notifikasi ganda)."""
    if tx.status == "paid":
        return
    user = db.get(User, tx.user_id)
    now = datetime.utcnow()
    tx.status, tx.paid_at = "paid", now
    if gateway:
        tx.payment_method = payments.method_label(gateway) or tx.payment_method
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
