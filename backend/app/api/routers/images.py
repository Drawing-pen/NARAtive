from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.routers.documents import _own_document
from app.api.schemas import CharacterOut, DocumentOut
from app.core.security import get_current_user, require_tier
from app.db.database import get_db
from app.db.models import Character, Document, User
from app.services import images

router = APIRouter(prefix="/documents", tags=["images"])

NO_STORE = {"Cache-Control": "private, no-cache"}


def _own_character(db: Session, doc: Document, character_id: int) -> Character:
    char = db.get(Character, character_id)
    if char is None or char.document_id != doc.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tokoh tidak ditemukan.")
    return char


def _picture(path: str | None) -> Response:
    data, media_type = images.load(path)
    return Response(data, media_type=media_type, headers=NO_STORE)


@router.put("/{doc_id}/cover", response_model=DocumentOut)
def set_cover(doc_id: int, file: UploadFile = File(...), user: User = Depends(require_tier("high")), db: Session = Depends(get_db)):
    doc = _own_document(db, user, doc_id)
    data, ext = images.read_upload(file)
    old, doc.cover_path = doc.cover_path, images.save(data, ext)
    db.commit()
    images.remove(old)
    return doc


@router.get("/{doc_id}/cover")
def get_cover(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _picture(_own_document(db, user, doc_id).cover_path)


@router.delete("/{doc_id}/cover", status_code=status.HTTP_204_NO_CONTENT)
def reset_cover(doc_id: int, user: User = Depends(require_tier("high")), db: Session = Depends(get_db)):
    doc = _own_document(db, user, doc_id)
    old, doc.cover_path = doc.cover_path, None
    db.commit()
    images.remove(old)


@router.put("/{doc_id}/characters/{character_id}/photo", response_model=CharacterOut)
def set_photo(doc_id: int, character_id: int, file: UploadFile = File(...), user: User = Depends(require_tier("high")), db: Session = Depends(get_db)):
    char = _own_character(db, _own_document(db, user, doc_id), character_id)
    data, ext = images.read_upload(file)
    old, char.photo_path = char.photo_path, images.save(data, ext)
    db.commit()
    images.remove(old)
    return char


@router.get("/{doc_id}/characters/{character_id}/photo")
def get_photo(doc_id: int, character_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _picture(_own_character(db, _own_document(db, user, doc_id), character_id).photo_path)


@router.delete("/{doc_id}/characters/{character_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
def reset_photo(doc_id: int, character_id: int, user: User = Depends(require_tier("high")), db: Session = Depends(get_db)):
    char = _own_character(db, _own_document(db, user, doc_id), character_id)
    old, char.photo_path = char.photo_path, None
    db.commit()
    images.remove(old)
