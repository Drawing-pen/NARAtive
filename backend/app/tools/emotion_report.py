import sys
from collections import Counter

from app.db.database import SessionLocal
from app.db.models import Document, Paragraph
from app.ml.analyzer import EMOTION_MIN_CONF, NEGATIVE_EMOTIONS

CUTOFFS = (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99)


def main() -> None:
    if len(sys.argv) < 2:
        print("Pemakaian: python -m app.tools.emotion_report <id_dokumen>")
        return
    with SessionLocal() as db:
        doc = db.get(Document, int(sys.argv[1]))
        if doc is None:
            print("Dokumen tidak ditemukan.")
            return
        rows = db.query(Paragraph).filter(Paragraph.document_id == doc.id).all()
    scored = [p for p in rows if p.emotion_score is not None]
    print(f"[{doc.id}] {doc.title} | {len(rows)} paragraf | bobot cerita tersimpan: {doc.heaviness}")
    if not scored:
        print("Buku ini dianalisis sebelum skor keyakinan emosi disimpan. Hapus lalu unggah ulang untuk mendapat skornya.")
        return
    print("\nEmosi dominan per paragraf (tanpa ambang):")
    for emo, c in Counter(p.emotion for p in scored).most_common():
        print(f"  {emo:6} {c:4}  {100 * c / len(scored):5.1f}%")
    neg = [p for p in scored if p.emotion in NEGATIVE_EMOTIONS]
    print(f"\nSebaran keyakinan model pada {len(neg)} paragraf bernada negatif:")
    for lo in (0.3, 0.5, 0.7, 0.8, 0.9, 0.95):
        hi = {0.3: 0.5, 0.5: 0.7, 0.7: 0.8, 0.8: 0.9, 0.9: 0.95, 0.95: 1.01}[lo]
        c = sum(1 for p in neg if lo <= p.emotion_score < hi)
        print(f"  {lo:.2f} - {min(hi, 1.0):.2f}  {c:4}")
    print(f"\nBobot cerita bila ambang keyakinan = x (ambang sekarang {EMOTION_MIN_CONF}):")
    for cut in CUTOFFS:
        heavy = sum(1 for p in neg if p.emotion_score >= cut)
        print(f"  {cut:.2f}  ->  {100 * heavy / len(scored):5.1f}")
    print("\nParagraf negatif dengan keyakinan tertinggi:")
    for p in sorted(neg, key=lambda p: -p.emotion_score)[:8]:
        print(f"  {p.emotion_score:.2f} {p.emotion:5} {' '.join(p.text.split())[:140]}")
    print("\nParagraf negatif dengan keyakinan terendah:")
    for p in sorted(neg, key=lambda p: p.emotion_score)[:8]:
        print(f"  {p.emotion_score:.2f} {p.emotion:5} {' '.join(p.text.split())[:140]}")


if __name__ == "__main__":
    main()