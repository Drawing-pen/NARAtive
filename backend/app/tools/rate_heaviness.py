import sys

from app.db.database import SessionLocal
from app.db.models import Document
from app.services import heaviness
from app.services.summarizer import SummaryError, configured, visible_texts
from app.tools.rescore import recompute


def main() -> None:
    if not configured():
        print("GEMINI_API_KEY belum diisi di backend/.env.")
        return
    ids = [int(a) for a in sys.argv[1:]]
    with SessionLocal() as db:
        docs = [d for d in db.query(Document).order_by(Document.id) if d.status == "done" and (not ids or d.id in ids)]
        for doc in docs:
            before = doc.heaviness
            try:
                texts = visible_texts(doc.paragraphs)
                doc.heaviness_ai, doc.heaviness_note = heaviness.rate(doc.title, [c.title for c in doc.chapters], texts)
            except SummaryError as e:
                print(f"[{doc.id}] {doc.title[:40]}: gagal ({e})")
                continue
            recompute(doc)
            db.commit()
            print(f"[{doc.id}] {doc.title[:40]}: Gemini {doc.heaviness_ai} | bobot cerita {before} -> {doc.heaviness}")
            print(f"      {doc.heaviness_note}")
        if not docs:
            print("Tidak ada dokumen yang diproses.")


if __name__ == "__main__":
    main()