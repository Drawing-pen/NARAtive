import logging
import queue
import threading
from datetime import datetime

from sqlalchemy import select

from app.db.database import SessionLocal
from app.ml.analyzer import summarize
from app.core.security import has_tier
from app.db.models import Document, User
from app.services import heaviness
from app.services import character_ai, characters, llm_analyzer
from app.services.llm_analyzer import AnalysisError
from app.services.summarizer import SummaryError, configured

log = logging.getLogger("uvicorn.error")

_queue: "queue.Queue[int]" = queue.Queue()
_worker: threading.Thread | None = None


def enqueue(doc_id: int) -> None:
    _queue.put(doc_id)


def process(doc_id: int) -> None:
    db = SessionLocal()
    try:
        doc = db.get(Document, doc_id)
        if doc is None:
            return
        doc.status, doc.analysis_progress = "analyzing", 0
        db.commit()
        paras = list(doc.paragraphs)

        def on_progress(done: int, total: int) -> None:
            doc.analysis_progress = 90 * done // total
            db.commit()

        results = llm_analyzer.analyze([(p.chapter_no, p.text) for p in paras], on_progress=on_progress)
        for p, r in zip(paras, results):
            p.profanity, p.sexual, p.violence = r["profanity"], r["sexual"], r["violence"]
            p.emotion = p.emotion_score = None
        if configured():
            doc.analysis_progress = 95
            db.commit()
            try:
                doc.heaviness_ai, doc.heaviness_note = heaviness.rate_document(doc)
            except SummaryError as e:
                log.warning("Penilaian bobot cerita oleh Gemini dilewati untuk dokumen %s: %s", doc_id, e)
        s = summarize(results, ai=doc.heaviness_ai)
        doc.pct_profanity, doc.pct_sexual, doc.pct_violence = s["pct"]["profanity"], s["pct"]["sexual"], s["pct"]["violence"]
        doc.rating, doc.dominant_emotion = s["rating"], None
        doc.pct_adult, doc.heaviness = s["adult"], s["heaviness"]
        doc.status, doc.analyzed_at, doc.analysis_progress = "done", datetime.utcnow(), 100
        db.commit()
        owner = db.get(User, doc.user_id)
        if owner is not None and has_tier(owner, "middle") and character_ai.available():
            characters.run(doc_id)
    except Exception as e:
        log.exception("Analisis dokumen %s gagal", doc_id)
        db.rollback()
        doc = db.get(Document, doc_id)
        if doc is not None:
            doc.status = "failed"
            if isinstance(e, AnalysisError):
                doc.failure_reason = str(e)
            db.commit()
    finally:
        db.close()


def _loop() -> None:
    while True:
        doc_id = _queue.get()
        try:
            process(doc_id)
        except Exception:
            log.exception("Worker analisis: dokumen %s dilewati", doc_id)
        finally:
            _queue.task_done()


def start_worker() -> None:
    global _worker
    if _worker is not None:
        return
    with SessionLocal() as db:
        pending = db.scalars(
            select(Document.id).where(Document.status.in_(("queued", "analyzing"))).order_by(Document.id)
        ).all()
    for doc_id in pending:
        enqueue(doc_id)
    if pending:
        log.info("%d dokumen belum selesai dimasukkan kembali ke antrean.", len(pending))
    _worker = threading.Thread(target=_loop, name="analysis-worker", daemon=True)
    _worker.start()