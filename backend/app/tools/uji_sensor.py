"""Uji manual analyzer LLM pada berkas .txt, .epub, atau .pdf: python -m app.tools.uji_sensor buku.epub [maks_paragraf] [mulai]."""
import os
import re
import sys
import time

from app.extraction.reader import read_document
from app.ml.analyzer import THRESHOLDS, summarize
from app.services import llm_analyzer

CHAPTER = re.compile(r"^\s*(chapter|bab|book|part)\b", re.IGNORECASE)


def paragraphs(path: str) -> list[tuple[int, str]]:
    ext = os.path.splitext(path.lower())[1]
    if ext in (".epub", ".pdf"):
        parsed = read_document(path, ext)
        return [(chapter, " ".join(block.text.split())) for chapter, block in parsed.blocks if block.text.strip()]
    with open(path, encoding="utf-8", errors="replace") as f:
        blocks = [" ".join(b.split()) for b in re.split(r"\n\s*\n", f.read())]
    chapter, items = 1, []
    for block in blocks:
        if not block:
            continue
        if CHAPTER.match(block) and len(block) < 80:
            chapter += 1
            continue
        items.append((chapter, block))
    return items


def main() -> None:
    if len(sys.argv) < 2:
        print("Pemakaian: python -m app.tools.uji_sensor buku.epub [maks_paragraf] [mulai]")
        return
    if not llm_analyzer.available():
        print("9router atau Gemini belum dikonfigurasi di backend/.env.")
        return
    items = paragraphs(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else len(items)
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    items = items[start:start + limit]
    print(f"{len(items)} paragraf (mulai dari {start}).")
    began = time.time()
    scores = llm_analyzer.analyze(items)
    s = summarize(scores)
    print(f"Selesai dalam {time.time() - began:.0f} detik.")
    print(f"Rating {s['rating']} | profanity {s['pct']['profanity']}% | seksual {s['pct']['sexual']}% | kekerasan {s['pct']['violence']}% | konten dewasa {s['adult']}%")
    for dim, cut in THRESHOLDS.items():
        marked = [start + i for i, r in enumerate(scores) if r[dim] >= cut]
        print(f"  {dim}: {len(marked)} paragraf, nomor: {marked[:40]}{' ...' if len(marked) > 40 else ''}")


if __name__ == "__main__":
    main()
