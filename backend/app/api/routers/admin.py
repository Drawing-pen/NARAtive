from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import AdminOverviewOut, PaymentCheckOut
from app.core.security import require_admin
from app.db.database import get_db
from app.db.models import Transaction, User
from app.services import admin_stats, billing

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverviewOut)
def overview(
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if month is not None and year is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Pilih tahun untuk bulan yang dipilih.")
    return admin_stats.overview(db, year, month)


def _transaction(db: Session, order_id: str) -> Transaction:
    tx = db.scalar(select(Transaction).where(Transaction.order_id == order_id))
    if tx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaksi tidak ditemukan.")
    return tx


@router.get("/payments/{order_id}", response_model=PaymentCheckOut)
def inspect_payment(order_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return billing.inspect(_transaction(db, order_id))


@router.post("/payments/{order_id}/sync", response_model=PaymentCheckOut)
def sync_payment(order_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return billing.sync(db, _transaction(db, order_id))
