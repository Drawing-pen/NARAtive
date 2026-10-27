from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import CollectionIn, CollectionOut
from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import Collection, Document, User
from app.services import collections as service

router = APIRouter(prefix="/collections", tags=["collections"])


def _own_collection(db: Session, user: User, collection_id: int) -> Collection:
    col = db.get(Collection, collection_id)
    if not col or col.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Koleksi tidak ditemukan.")
    return col


def _out(db: Session, col: Collection) -> CollectionOut:
    return CollectionOut(id=col.id, name=col.name, document_ids=service.member_ids(db, col.id))


def _set_members(db: Session, user: User, col: Collection, ids: list[int]) -> None:
    if len(set(ids)) != len(ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Satu e-book tidak bisa dimasukkan dua kali.")
    docs = {d.id: d for d in db.scalars(select(Document).where(Document.id.in_(ids), Document.user_id == user.id))}
    if len(docs) != len(ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ada e-book yang tidak ditemukan.")
    for old in db.scalars(select(Document).where(Document.collection_id == col.id)):
        if old.id not in docs:
            old.collection_id = None
    for position, doc_id in enumerate(ids):
        docs[doc_id].collection_id = col.id
        docs[doc_id].position = position


@router.get("", response_model=list[CollectionOut])
def list_collections(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cols = db.scalars(
        select(Collection).where(Collection.user_id == user.id).order_by(Collection.created_at.desc(), Collection.id.desc())
    ).all()
    return [_out(db, c) for c in cols]


@router.post("", response_model=CollectionOut, status_code=status.HTTP_201_CREATED)
def create_collection(body: CollectionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    col = Collection(user_id=user.id, name=body.name)
    db.add(col)
    db.flush()
    _set_members(db, user, col, body.document_ids)
    db.flush()
    service.prune_empty(db, user.id)    # buku yang dipindah dari koleksi lain bisa membuatnya kosong
    db.commit()
    return _out(db, col)


@router.put("/{collection_id}", response_model=CollectionOut)
def update_collection(collection_id: int, body: CollectionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    col = _own_collection(db, user, collection_id)
    col.name = body.name
    _set_members(db, user, col, body.document_ids)
    db.flush()
    service.prune_empty(db, user.id)
    db.commit()
    return _out(db, col)


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(collection_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Bubarkan koleksi; e-book di dalamnya tetap ada."""
    col = _own_collection(db, user, collection_id)
    for doc in db.scalars(select(Document).where(Document.collection_id == col.id)):
        doc.collection_id = None
    db.flush()
    db.delete(col)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
