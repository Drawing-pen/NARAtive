from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Collection, Document


def member_ids(db: Session, collection_id: int) -> list[int]:
    return list(db.scalars(
        select(Document.id).where(Document.collection_id == collection_id).order_by(Document.position, Document.id)
    ))


def prune_empty(db: Session, user_id: int) -> None:
    """Hapus koleksi milik pengguna yang sudah tidak punya buku (mis. setelah buku terakhirnya dihapus atau dipindah)."""
    used = select(Document.collection_id).where(Document.collection_id.is_not(None))
    db.execute(delete(Collection).where(Collection.user_id == user_id, Collection.id.not_in(used)))
