from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Document, Paragraph
from app.ml.analyzer import AGE_RANGES, DIMENSION_LABEL, THRESHOLDS, explain, rate

NOTE = "Bahasa kasar ditampilkan sebagai informasi dan tidak dihitung dalam rating maupun persentase konten dewasa."
ORDER = ("violence", "sexual", "profanity")


def breakdown(db: Session, doc: Document) -> dict:
    base = select(func.count()).select_from(Paragraph).where(Paragraph.document_id == doc.id)
    total = db.scalar(base) or 0
    hits = {d: db.scalar(base.where(getattr(Paragraph, d) >= THRESHOLDS[d])) or 0 for d in ORDER}
    pct = {d: round(100 * hits[d] / max(total, 1), 1) for d in ORDER}
    rating = rate(pct, hits)
    return {
        "rating": rating,
        "age_range": AGE_RANGES[rating],
        "dimensions": [
            {"key": d, "label": DIMENSION_LABEL[d], "percent": pct[d], "paragraphs": hits[d], "threshold": THRESHOLDS[d]} for d in ORDER
        ],
        "reasons": explain(pct, hits),
        "note": NOTE,
    }
