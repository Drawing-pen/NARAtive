import sys

from .database import SessionLocal
from .ml.analyzer import summarize
from .ml.lexicon import sexual_lexicon_score
from .models import Document


def main() -> None:
    ids = [int(a) for a in sys.argv[1:]]
    with SessionLocal() as db:
        docs = [d for d in db.query(Document).order_by(Document.id) if d.status == "done" and (not ids or d.id in ids)]
        for doc in docs:
            before = (doc.rating, doc.pct_sexual, doc.pct_adult)
            results = []
            for p in doc.paragraphs:
                p.sexual = max(p.sexual or 0.0, sexual_lexicon_score(p.text))
                results.append({"profanity": p.profanity or 0.0, "sexual": p.sexual, "violence": p.violence or 0.0, "emotion": p.emotion or "happy"})
            s = summarize(results)
            doc.pct_profanity, doc.pct_sexual, doc.pct_violence = s["pct"]["profanity"], s["pct"]["sexual"], s["pct"]["violence"]
            doc.rating, doc.dominant_emotion = s["rating"], s["emotion"]
            doc.pct_adult, doc.heaviness = s["adult"], s["heaviness"]
            db.commit()
            print(f"[{doc.id}] {doc.title[:40]}: rating {before[0]} -> {doc.rating} | seksual {before[1]}% -> {doc.pct_sexual}% | konten dewasa {before[2]}% -> {doc.pct_adult}%")
        if not docs:
            print("Tidak ada dokumen yang diproses.")


if __name__ == "__main__":
    main()