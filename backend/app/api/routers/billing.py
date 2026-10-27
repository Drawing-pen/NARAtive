import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import BillingOverview, CheckoutIn, TransactionOut, UsageOut
from app.core.config import settings
from app.core.plans import BANKS, LIMITS, PAY_PER_CHECK_MAX, PAY_PER_CHECK_PRICE, PERIOD_DAYS, UPGRADE_PRICE, VA_TTL_HOURS
from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import Transaction, User
from app.services import billing, payments

router = APIRouter(prefix="/billing", tags=["billing"])
log = logging.getLogger("uvicorn.error")


def _own_transaction(db: Session, user: User, order_id: str) -> Transaction:
    tx = db.scalar(select(Transaction).where(Transaction.order_id == order_id, Transaction.user_id == user.id))
    if tx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaksi tidak ditemukan.")
    return billing.refresh(db, tx)


@router.get("/overview", response_model=BillingOverview)
def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    limits = LIMITS[user.access_tier]
    return BillingOverview(
        tier=user.access_tier,
        paid_tier=user.paid_tier,
        tier_expires_at=user.tier_expires_at if user.paid_tier != "free" else None,
        usage=UsageOut(
            used=billing.used_this_month(db, user),
            monthly_limit=limits.monthly,
            extra_checks=user.extra_checks,
            active_books=billing.active_books(db, user),
            max_active=limits.max_active,
            max_pages=limits.max_pages,
            resets_at=billing.next_reset(),
        ),
        upgrade_prices=UPGRADE_PRICE,
        period_days=PERIOD_DAYS,
        pay_per_check_price=PAY_PER_CHECK_PRICE,
        pay_per_check_max=PAY_PER_CHECK_MAX,
        banks=list(BANKS),
        provider=payments.provider(),
    )


@router.post("/checkout", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def checkout(body: CheckoutIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.kind == "upgrade":
        if billing.TIER_RANK[body.plan] < billing.TIER_RANK[user.paid_tier]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kamu sudah memakai paket yang lebih tinggi.")
    elif user.paid_tier == "high":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Paket High tanpa batas analisis, tidak perlu membeli analisis tambahan.")

    quantity = body.quantity if body.kind == "pay_per_check" else 1
    order_id = f"NAR-{user.id}-{uuid.uuid4().hex[:10]}"
    amount = billing.price_for(body.kind, body.plan, quantity)
    try:
        va = payments.create_va(order_id, amount, body.bank)
    except payments.PaymentUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))
    except payments.PaymentError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Gagal membuat Virtual Account. {e}")

    now = datetime.utcnow()
    tx = Transaction(
        user_id=user.id, order_id=order_id, kind=body.kind, plan=body.plan if body.kind == "upgrade" else None,
        quantity=quantity, amount=amount, bank=body.bank, va_number=va, provider=payments.provider(),
        status="pending", created_at=now, expires_at=now + timedelta(hours=VA_TTL_HOURS),
    )
    db.add(tx)
    db.commit()
    return tx


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    txs = db.scalars(select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.created_at.desc(), Transaction.id.desc())).all()
    return [billing.refresh(db, tx) for tx in txs]


@router.get("/transactions/{order_id}", response_model=TransactionOut)
def get_transaction(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _own_transaction(db, user, order_id)


@router.post("/transactions/{order_id}/cancel", response_model=TransactionOut)
def cancel_transaction(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tx = _own_transaction(db, user, order_id)
    if tx.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Hanya pembayaran yang masih menunggu yang bisa dibatalkan.")
    if tx.provider == "midtrans":
        payments.cancel_va(tx.order_id)
    tx.status = "cancelled"
    db.commit()
    return tx


@router.post("/transactions/{order_id}/simulate-pay", response_model=TransactionOut)
def simulate_payment(order_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Hanya untuk mode simulasi (tanpa kunci Midtrans): menandai VA simulasi sebagai sudah dibayar."""
    tx = _own_transaction(db, user, order_id)
    if tx.provider != "simulated" or payments.provider() != "simulated":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Simulasi pembayaran tidak tersedia.")
    if tx.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Pembayaran ini sudah tidak menunggu.")
    billing.settle(db, tx)
    return tx


@router.post("/midtrans/notification")
def midtrans_notification(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Webhook status pembayaran dari Midtrans. Keaslian diperiksa lewat signature_key."""
    if not settings.midtrans_server_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tidak tersedia.")
    if not payments.valid_signature(payload):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Signature tidak valid.")
    tx = db.scalar(select(Transaction).where(Transaction.order_id == str(payload.get("order_id", ""))))
    if tx is None or tx.provider != "midtrans":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaksi tidak ditemukan.")
    try:
        if int(float(payload.get("gross_amount", 0))) != tx.amount:
            raise ValueError
    except (TypeError, ValueError):
        log.warning("Notifikasi %s ditolak: nominal tidak cocok", tx.order_id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Nominal tidak cocok.")

    new_status = payments.map_status(str(payload.get("transaction_status", "")))
    if new_status == "paid":
        billing.settle(db, tx)
    elif new_status and tx.status == "pending":
        tx.status = new_status
        db.commit()
    return {"ok": True}
