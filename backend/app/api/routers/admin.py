from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import AdminOverviewOut
from app.core.security import require_admin
from app.db.database import get_db
from app.db.models import User
from app.services import admin_stats

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverviewOut)
def overview(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return admin_stats.overview(db)
