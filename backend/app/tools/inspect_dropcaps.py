"""Alat bantu diagnosa huruf hias (drop cap): python -m app.tools.inspect_dropcaps berkas.pdf

Mencari huruf hias di awal baris (karakter sampah, font/ukuran beda, atau lebih besar), lalu menampilkan: halaman, font, kode karakter yang terbaca,
lanjutan teksnya, dan tebakan sistem. Ringkasan di akhir mengelompokkan per (font, kode) supaya
terlihat apakah satu kode selalu berarti satu huruf yang sama.
"""
import sys
import unicodedata
from collections import Counter, defaultdict
from statistics import median

import pymupdf

from app.extraction.pdf_utils import restore_dropcap

_BAD = {"Cc", "Cf", "Co", "Cs", "Cn"}


def main() -> None:
    path = sys.argv[1]
    rows = []
    with pymupdf.open(path) as pdf:
        sizes = []
        for page in pdf:
            for b in page.get_text("dict")["blocks"]:
                for ln in b.get("lines", []):
                    sizes += [sp["size"] for sp in ln["spans"] if len(sp["text"].strip()) > 3]
        body = median(sizes) if sizes else 10
        small_imgs = []
        for page in pdf:
            for im in page.get_image_info():
                x0, y0, x1, y1 = im["bbox"]
                if 0 < x1 - x0 < body * 8 and 0 < y1 - y0 < body * 8:
                    small_imgs.append((page.number + 1, round(x1 - x0), round(y1 - y0), round(x0), round(y0)))
            for b in page.get_text("dict")["blocks"]:
                lines = b.get("lines", [])
                for i, ln in enumerate(lines):
                    spans = ln["spans"]
                    first = spans[0]
                    ft = first["text"].strip()
                    if not ft or len(ft) > 2:
                        continue
                    bad = any(unicodedata.category(c) in _BAD or c == "\ufffd" for c in ft)
                    other = len(spans) > 1 and (spans[1]["font"] != first["font"] or abs(spans[1]["size"] - first["size"]) > 0.5)
                    big = first["size"] >= body * 1.3
                    # huruf hias: karakter sampah, ATAU font/ukurannya beda dari kata berikutnya, ATAU lebih besar dari teks isi
                    if not (bad or other or big):
                        continue
                    rest = "".join(sp["text"] for sp in spans[1:])
                    if not rest.strip() and i + 1 < len(lines):   # sisa kata ada di baris berikutnya
                        rest = "".join(sp["text"] for sp in lines[i + 1]["spans"])
                    rest = rest[:25]
                    shown = first["text"]
                    guess = restore_dropcap(shown + rest)
                    rows.append((page.number + 1, first["font"], round(first["size"], 1), shown, rest, guess[:1]))
    print(f"Ukuran huruf isi: {body:.1f} | huruf hias ditemukan: {len(rows)}\n")
    for r in rows[:60]:
        pg, font, size, shown, rest, g = r
        print(f"hal {pg:>3} | {font[:22]:22} | {size:>5} | terbaca={shown!r} ord={[ord(c) for c in shown]} | lanjut={rest!r} | tebakan={g!r}")
    if len(rows) > 60:
        print(f"... {len(rows) - 60} baris lain tidak ditampilkan")
    print(f"\nGambar kecil (mungkin huruf hias berupa GAMBAR): {len(small_imgs)}")
    for pg, w, h, x, y in small_imgs[:15]:
        print(f"  hal {pg:>3} | {w}x{h} pt | posisi x={x} y={y}")
    print("\n--- detail untuk karakter sampah (kata di kanan dan di bawah huruf, + gambar potongan) ---")
    seen = set()
    with pymupdf.open(path) as pdf:
        for pg, font, size, shown, rest, g in rows:
            if not any(unicodedata.category(c) in _BAD for c in shown) or (font, shown) in seen or size < 9:
                continue
            seen.add((font, shown))
            page = pdf[pg - 1]
            for b in page.get_text("dict")["blocks"]:
                for ln in b.get("lines", []):
                    if ln["spans"][0]["text"] == shown and ln["spans"][0]["font"] == font:
                        x0, y0, x1, y1 = ln["bbox"]
                        words = page.get_text("words")
                        same = [w for w in words if w[0] >= x1 - 1 and y0 - 2 <= (w[1] + w[3]) / 2 <= y1 + 2]
                        below = [w for w in words if y1 < (w[1] + w[3]) / 2 <= y1 + 22 and abs(w[0] - x0) < 120]
                        print(f"hal {pg} kode={[ord(c) for c in shown]} bbox=({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f})")
                        print("   kata di kanan  :", " ".join(w[4] for w in sorted(same, key=lambda w: w[0]))[:60])
                        print("   kata di bawah  :", " ".join(w[4] for w in sorted(below, key=lambda w: (w[1], w[0])))[:60])
                        clip = pymupdf.Rect(x0 - 10, y0 - 10, min(page.rect.x1, x1 + 200), y1 + 30)
                        name = f"dropcap_hal{pg}_kode{ord(shown[0])}.png"
                        page.get_pixmap(matrix=pymupdf.Matrix(3, 3), clip=clip).save(name)
                        print("   gambar potongan:", name)
                        break
                else:
                    continue
                break
    print("\n--- ringkasan per (font, kode) ---")
    group = defaultdict(Counter)
    for _, font, _, shown, rest, g in rows:
        group[(font, tuple(ord(c) for c in shown))][g] += 1
    for (font, code), c in sorted(group.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"{font[:22]:22} kode={list(code)} muncul={sum(c.values())}x tebakan={dict(c)}")


if __name__ == "__main__":
    main()