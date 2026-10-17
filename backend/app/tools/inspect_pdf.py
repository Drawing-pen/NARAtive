"""Alat bantu diagnosa: python -m app.tools.inspect_pdf berkas.pdf [halaman]

Menampilkan teks mentah satu halaman (repr, agar karakter aneh terlihat) dan hasil deteksi bab.
"""
import sys

import pymupdf

from app.extraction.pdf_utils import clean_text, read_pdf


def main() -> None:
    path = sys.argv[1]
    page_no = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    with pymupdf.open(path) as pdf:
        print(f"Halaman: {len(pdf)} | daftar isi PDF: {len(pdf.get_toc())} entri")
        page = pdf[page_no - 1]
        print(f"\n--- teks mentah halaman {page_no} (12 baris pertama) ---")
        for ln in page.get_text("text").split("\n")[:12]:
            print(repr(ln))
        print("\n--- baris miring (watermark?) ---")
        for block in page.get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                if abs(ln["dir"][1]) > 0.2:
                    print(repr("".join(sp["text"] for sp in ln["spans"])))
        print("\n--- ukuran huruf per baris (6 pertama) ---")
        n = 0
        for block in page.get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                if n < 6:
                    print(round(min(sp["size"] for sp in ln["spans"]), 1), repr("".join(sp["text"] for sp in ln["spans"])[:60]))
                    n += 1
    pages, titles, paras = read_pdf(path)
    print(f"\n--- hasil: {len(titles)} bab, {len(paras)} paragraf ---")
    for t in titles[:15]:
        print(" -", t)
    print("\nContoh paragraf 1:", clean_text(paras[0][1])[:200] if paras else "-")


main()