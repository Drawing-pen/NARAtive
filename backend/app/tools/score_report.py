"""Diagnosa skor model pada satu e-book: python -m app.tools.score_report <id_dokumen> [dimensi]

Menampilkan sebaran skor, jumlah paragraf yang lolos ambang, paragraf dengan skor tertinggi, dan
paragraf yang memuat kata kunci eksplisit tetapi skornya rendah (indikasi model melewatkan konten).
"""
import re
import sys

from app.db.database import SessionLocal
from app.db.models import Document, Paragraph

THRESHOLDS = {"profanity": 0.5, "sexual": 0.5, "violence": 0.8}
EXPLICIT = re.compile(r"\b(nipples?|thrust(?:ed|ing)?|inside her|inside me|moan(?:ed|ing)?|naked|breasts?|erection|climax|orgasm|plunged inside|buried himself)\b", re.I)


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)[:150]


def main() -> None:
    doc_id = int(sys.argv[1])
    dim = sys.argv[2] if len(sys.argv) > 2 else "sexual"
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        rows = db.query(Paragraph).filter(Paragraph.document_id == doc_id).order_by(Paragraph.idx).all()
        print(f"{doc.title} | {len(rows)} paragraf | rating={doc.rating} | pct sexual={doc.pct_sexual} violence={doc.pct_violence} profanity={doc.pct_profanity}")
        scores = [(getattr(r, dim) or 0.0, r) for r in rows]
        print(f"\nSebaran skor '{dim}' (jumlah paragraf dengan skor >= batas):")
        for t in (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 0.9):
            print(f"  >= {t:<4}: {sum(1 for s, _ in scores if s >= t)}")
        print(f"\nAmbang saat ini: {THRESHOLDS[dim]}")
        print(f"\n--- 15 paragraf skor tertinggi ---")
        for s, r in sorted(scores, key=lambda x: -x[0])[:15]:
            print(f"{s:.3f} | idx {r.idx} | {flat(r.text)}")
        kw = [(s, r, len(EXPLICIT.findall(r.text))) for s, r in scores]
        kw = [x for x in kw if x[2] >= 2]
        print(f"\n--- paragraf dengan >=2 kata kunci eksplisit: {len(kw)} (skor di bawah ambang: {sum(1 for s, _, _ in kw if s < THRESHOLDS[dim])}) ---")
        for s, r, n in sorted(kw, key=lambda x: x[0])[:15]:
            print(f"{s:.3f} | kata kunci={n} | idx {r.idx} | {flat(r.text)}")


if __name__ == "__main__":
    main()