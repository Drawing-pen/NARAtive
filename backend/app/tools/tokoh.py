import sys
from collections import defaultdict

from app.db.database import SessionLocal
from app.db.models import Document
from app.services import characters


def report(doc: Document) -> None:
    print(f"\n[{doc.id}] {doc.title[:60]}")
    if not doc.characters:
        print("  Tokoh tidak terdeteksi.")
        return
    print(f"  {len(doc.characters)} tokoh:")
    for c in doc.characters:
        print(f"    {c.mention_count:>4}x  {c.name:<28} {c.role}")
    by_pair = defaultdict(lambda: {"akrab": 0, "konflik": 0, "weight": 0})
    for ch in doc.chapters:
        for r in ch.relations:
            pair = (r.character_a.name, r.character_b.name)
            by_pair[pair][r.relation_type] += 1
            by_pair[pair]["weight"] += r.weight
    ranked = sorted(by_pair.items(), key=lambda kv: -kv[1]["weight"])[:12]
    print(f"  Relasi terkuat ({len(by_pair)} pasangan, {sum(len(c.relations) for c in doc.chapters)} relasi per bab):")
    for (a, b), v in ranked:
        print(f"    {a} - {b}: {v['weight']} kemunculan bersama, akrab di {v['akrab']} bab, konflik di {v['konflik']} bab")
    print("  Contoh biodata:")
    for c in doc.characters[:3]:
        print(f"    {c.biodata}")


def main() -> None:
    ids = [int(a) for a in sys.argv[1:]]
    with SessionLocal() as db:
        docs = [d for d in db.query(Document).order_by(Document.id) if d.status == "done" and (not ids or d.id in ids)]
        if not docs:
            print("Tidak ada dokumen yang diproses.")
            return
        for doc in docs:
            try:
                n_char, n_rel = characters.extract(db, doc)
            except characters.CharacterError as e:
                print(f"[{doc.id}] {doc.title[:40]}: gagal ({e})")
                return
            db.refresh(doc)
            report(doc)


if __name__ == "__main__":
    main()