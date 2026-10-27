import logging
import os
import uuid

from fastapi.responses import Response
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.services.export import build_pdf
from app.services.jobs import enqueue
from app.ml.analyzer import model_ready
from app.db.models import Chapter, Character, CharacterRelation, Document, Paragraph, User
from app.extraction.epub_utils import EpubError, read_epub
from app.extraction.pdf_utils import read_pdf
from app.services import billing, images
from app.services import characters as character_service
from app.services import collections as collection_service
from app.services import summarizer
from app.api.schemas import ChapterOut, CharactersOut, DocumentOut, DocumentRename, ParagraphOut, RelationOut, SummaryOut
from app.core.security import ensure_tier, get_current_user, require_tier

router = APIRouter(prefix="/documents", tags=["documents"])
log = logging.getLogger("uvicorn.error")


def _own_document(db: Session, user: User, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dokumen tidak ditemukan.")
    return doc


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not model_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Model analisis belum terpasang di server. Hubungi pengelola sistem.")

    ext = os.path.splitext((file.filename or "").lower())[1]
    allowed = {
        ".pdf": ("application/pdf", "application/octet-stream"),
        ".epub": ("application/epub+zip", "application/octet-stream", "application/zip"),
    }
    if ext not in allowed or file.content_type not in allowed[ext]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Format file tidak didukung. Unggah file berformat PDF atau EPUB.")

    os.makedirs(settings.upload_dir, exist_ok=True)
    stored = os.path.join(settings.upload_dir, f"{uuid.uuid4().hex}{ext}")
    try:
        with open(stored, "wb") as f:
            f.write(file.file.read())
        page_count, chapter_titles, paragraphs = read_epub(stored) if ext == ".epub" else read_pdf(stored)
        if not paragraphs:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "File tidak berisi teks yang dapat dianalisis.")
        billing.ensure_can_upload(db, user, page_count)

        doc = Document(
            user_id=user.id,
            title=os.path.splitext(file.filename)[0][:255],
            filename=os.path.basename(file.filename)[:255],
            page_count=page_count,
            paragraph_count=len(paragraphs),
            status="queued",
        )
        doc.chapters = [Chapter(number=i + 1, title=t[:255]) for i, t in enumerate(chapter_titles)]
        doc.paragraphs = [Paragraph(idx=i, chapter_no=n, text=t) for i, (n, t) in enumerate(paragraphs)]
        db.add(doc)
        billing.consume_analysis(db, user)    # satu transaksi dengan penyimpanan dokumen
        db.commit()
    except HTTPException:
        raise
    except EpubError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception:
        log.exception("Unggahan gagal diproses")  #
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File tidak dapat dibaca atau gagal disimpan. Coba unggah lagi.")
    finally:
        if os.path.exists(stored):
            os.remove(stored)

    enqueue(doc.id)
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())
    ).all()


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _own_document(db, user, doc_id)
    pictures = [doc.cover_path, *(c.photo_path for c in doc.characters)]
    db.delete(doc)
    db.flush()
    collection_service.prune_empty(db, user.id)
    db.commit()
    images.remove(*pictures)


@router.patch("/{doc_id}", response_model=DocumentOut)
def rename_document(doc_id: int, body: DocumentRename, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _own_document(db, user, doc_id)
    doc.title = body.title
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/{doc_id}/export")
def export_document(doc_id: int, user: User = Depends(require_tier("high")), db: Session = Depends(get_db)):
    from app.ml.analyzer import THRESHOLDS

    doc = _own_document(db, user, doc_id)
    if doc.status != "done":
        raise HTTPException(status.HTTP_409_CONFLICT, "Analisis belum selesai.")
    try:
        pdf = build_pdf(doc, doc.chapters, doc.paragraphs, THRESHOLDS)
    except Exception:
        log.exception("Gagal menyusun PDF hasil analisis dokumen %s", doc_id)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Gagal menyusun PDF. Coba lagi.")
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in doc.title).strip()[:80] or "hasil"
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="NARAtive - {safe}.pdf"'})


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _own_document(db, user, doc_id)


@router.get("/{doc_id}/chapters", response_model=list[ChapterOut])
def get_chapters(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _own_document(db, user, doc_id).chapters


@router.get("/{doc_id}/paragraphs", response_model=list[ParagraphOut])
def get_paragraphs(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _own_document(db, user, doc_id).paragraphs


def _summary_out(doc: Document) -> SummaryOut:
    return SummaryOut(
        status=doc.summary_status,
        done_chapters=sum(1 for c in doc.chapters if c.summary),
        total_chapters=len(doc.chapters),
        overall=doc.summary,
        chapters=doc.chapters,
    )


@router.get("/{doc_id}/summary", response_model=SummaryOut)
def get_summary(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _own_document(db, user, doc_id)
    if doc.summary_status is None:
        ensure_tier(user, "middle")
    return _summary_out(doc)


@router.post("/{doc_id}/summary", response_model=SummaryOut, status_code=status.HTTP_202_ACCEPTED)
def create_summary(doc_id: int, user: User = Depends(require_tier("middle")), db: Session = Depends(get_db)):
    doc = _own_document(db, user, doc_id)
    if doc.status != "done":
        raise HTTPException(status.HTTP_409_CONFLICT, "Rangkuman bisa dibuat setelah analisis selesai.")
    if not summarizer.configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Layanan rangkuman belum diatur di server (GEMINI_API_KEY kosong).")
    if doc.summary_status != "running":
        resume = doc.summary_status in ("failed", "partial")
        doc.summary_status, doc.summary = "running", None
        if not resume:
            for c in doc.chapters:
                c.summary, c.summary_source = None, None
        db.commit()
        summarizer.start(doc.id)
    return _summary_out(doc)


def _characters_out(db: Session, doc: Document) -> CharactersOut:
    chars = db.scalars(
        select(Character).where(Character.document_id == doc.id).order_by(Character.mention_count.desc(), Character.id)
    ).all()
    rows = db.execute(
        select(CharacterRelation, Chapter.number)
        .join(Chapter, Chapter.id == CharacterRelation.chapter_id)
        .where(Chapter.document_id == doc.id)
        .order_by(Chapter.number, CharacterRelation.id)
    ).all()
    relations = [
        RelationOut(chapter=number, a=r.character_a_id, b=r.character_b_id, type=r.relation_type, weight=r.weight)
        for r, number in rows
    ]
    return CharactersOut(status=doc.characters_status, characters=chars, relations=relations)


@router.get("/{doc_id}/characters", response_model=CharactersOut)
def get_characters(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = _own_document(db, user, doc_id)
    if doc.characters_status is None:
        ensure_tier(user, "middle")
    return _characters_out(db, doc)


@router.post("/{doc_id}/characters", response_model=CharactersOut, status_code=status.HTTP_202_ACCEPTED)
def detect_characters(doc_id: int, ai: bool = False, user: User = Depends(require_tier("middle")), db: Session = Depends(get_db)):
    doc = _own_document(db, user, doc_id)
    if doc.status != "done":
        raise HTTPException(status.HTTP_409_CONFLICT, "Tokoh bisa dideteksi setelah analisis selesai.")
    if ai and not character_service.character_ai.available():
        raise HTTPException(status.HTTP_409_CONFLICT, "Biodata AI butuh GEMINI_API_KEY di server.")
    if doc.characters_status != "running":
        doc.characters_status = "running"
        db.commit()
        character_service.start(doc.id, ai)
    return _characters_out(db, doc)