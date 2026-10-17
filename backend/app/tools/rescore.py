"""Hitung ulang dimensi seksual untuk e-book yang sudah dianalisis, tanpa upload ulang dan tanpa menjalankan model.

    python -m app.tools.rescore            # semua dokumen berstatus done
    python -m app.tools.rescore 12 15      # hanya dokumen tertentu

Skor seksual paragraf diganti menjadi maksimum(skor model yang tersimpan, skor kamus), lalu rating dan
persentase dokumen dihitung ulang. Aman dijalankan berulang kali (hasilnya sama).
"""
import sys

from app.db.database import SessionLocal
from app.ml.analyzer import summarize
from app.ml.lexicon import sexual_lexicon_score
from app.db.models import Document


def recompute(doc) -> None:
    results = []
    for p in doc.paragraphs:
        p.sexual = max(p.sexual or 0.0, sexual_lexicon_score(p.text))
        results.append({"profanity": p.profanity or 0.0, "sexual": p.sexual, "violence": p.violence or 0.0, "emotion": p.emotion or "happy", "emotion_prob": p.emotion_score})
    s = summarize(results, ai=doc.heaviness_ai)
    doc.pct_profanity, doc.pct_sexual, doc.pct_violence = s["pct"]["profanity"], s["pct"]["sexual"], s["pct"]["violence"]
    doc.rating, doc.dominant_emotion = s["rating"], s["emotion"]
    doc.pct_adult, doc.heaviness = s["adult"], s["heaviness"]


def main() -> None:
    ids = [int(a) for a in sys.argv[1:]]
    with SessionLocal() as db:
        docs = [d for d in db.query(Document).order_by(Document.id) if d.status == "done" and (not ids or d.id in ids)]
        for doc in docs:
            before = (doc.rating, doc.pct_sexual, doc.pct_adult, doc.heaviness)
            recompute(doc)
            db.commit()
            print(f"[{doc.id}] {doc.title[:40]}: rating {before[0]} -> {doc.rating} | seksual {before[1]}% -> {doc.pct_sexual}% | konten dewasa {before[2]}% -> {doc.pct_adult}% | bobot cerita {before[3]} -> {doc.heaviness}")
        if not docs:
            print("Tidak ada dokumen yang diproses.")


if __name__ == "__main__":
    main()