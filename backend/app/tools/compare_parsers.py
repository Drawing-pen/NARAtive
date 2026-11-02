"""Bandingkan parser lama dan parser Markdown pada berkas yang diberikan.

Pemakaian (dari folder backend): python -m app.tools.compare_parsers buku1.pdf buku2.epub
"""
import os
import sys
import time
from collections import Counter

from app.extraction import reader

SUPPORTED = (".pdf", ".epub")
SHOW_TITLES = 12


def _report(parse, path: str, ext: str) -> dict:
    started = time.time()
    try:
        parsed = parse(path, ext)
    except Exception as error:
        return {"error": str(error)}
    blocks = [block for _, block in parsed.blocks]
    texts = Counter(line for block in blocks for line in block.text.split("\n") if len(line) <= 100)
    return {
        "pages": parsed.page_count,
        "chapters": parsed.titles,
        "blocks": len(blocks),
        "chars": sum(len(block.text) for block in blocks),
        "kinds": dict(Counter(block.kind for block in blocks)),
        "formatted": sum(1 for block in blocks if block.markdown and ("*" in block.markdown or "_" in block.markdown)),
        "numeric": sum(1 for block in blocks if block.text.strip().isdigit()),
        "repeated": [(text, count) for text, count in texts.most_common(3) if count >= 3],
        "seconds": round(time.time() - started, 1),
    }


def compare(path: str) -> dict:
    ext = os.path.splitext(path)[1].lower()
    return {"legacy": _report(reader.parse_legacy, path, ext), "markdown": _report(reader.parse_markdown, path, ext)}


def _print(name: str, result: dict) -> None:
    print(f"\n=== {name}")
    for parser, report in result.items():
        if "error" in report:
            print(f"[{parser}] GAGAL: {report['error']}")
            continue
        titles = report["chapters"]
        shown = ", ".join(titles[:SHOW_TITLES]) + (f", ... (+{len(titles) - SHOW_TITLES})" if len(titles) > SHOW_TITLES else "")
        print(f"[{parser}] {report['pages']} halaman | {len(titles)} bab | {report['blocks']} blok | {report['chars']} karakter | {report['seconds']} dtk")
        print(f"    bab: {shown}")
        print(f"    jenis blok: {report['kinds']} | berformat: {report['formatted']} | blok hanya angka: {report['numeric']}")
        if report["repeated"]:
            print("    teks pendek berulang (kemungkinan header bocor): " + "; ".join(f"{text[:40]!r} x{count}" for text, count in report["repeated"]))


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not argv:
        print("Pemakaian: python -m app.tools.compare_parsers berkas1.pdf [berkas2.epub ...]")
        return 2
    status = 0
    for path in argv:
        name = os.path.basename(path)
        if not os.path.exists(path):
            print(f"\n=== {name}\nBerkas tidak ditemukan.")
            status = 1
        elif os.path.splitext(path)[1].lower() not in SUPPORTED:
            print(f"\n=== {name}\nFormat tidak didukung (hanya PDF dan EPUB).")
            status = 1
        else:
            _print(name, compare(path))
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
