"""UC-13: susun PDF hasil analisis (ringkasan rating + teks bersih per bab dengan paragraf sensitif disorot)."""
import io
from html import escape

import pymupdf

DIMENSIONS = (("profanity", "Bahasa kasar"), ("sexual", "Seksual"), ("violence", "Kekerasan"))
EMOTION_NEGATIVE_NOTE = "Bobot cerita = persentase paragraf beremosi sedih, marah, atau takut (skala 0-100)."

CSS = """
body { font-family: serif; font-size: 10.5pt; line-height: 1.45; color: #1b2440; }
h1 { font-size: 22pt; margin: 0 0 4pt 0; color: #24365F; }
h2 { font-size: 15pt; margin: 18pt 0 6pt 0; color: #24365F; }
.sub { color: #5b6480; font-size: 9.5pt; margin: 0 0 12pt 0; }
table.sum { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt 0; }
table.sum td { border: 1pt solid #d9d4c7; padding: 6pt 8pt; vertical-align: top; }
.k { font-size: 8.5pt; color: #5b6480; }
.v { font-size: 16pt; font-weight: bold; color: #24365F; }
p { margin: 0 0 6pt 0; text-align: justify; }
p.hl { background-color: #FBE3A8; padding: 2pt 3pt; }
span.tag { font-family: sans-serif; font-size: 7.5pt; color: #8a4b00; font-weight: bold; }
.note { font-size: 8.5pt; color: #5b6480; }
"""


def _flags(par, thresholds: dict) -> list[str]:
    return [label for key, label in DIMENSIONS if (getattr(par, key) or 0) >= thresholds[key]]


def build_pdf(doc, chapters, paragraphs, thresholds: dict) -> bytes:
    by_chapter: dict[int, list] = {}
    for p in paragraphs:
        by_chapter.setdefault(p.chapter_no, []).append(p)
    flagged = sum(1 for p in paragraphs if _flags(p, thresholds))

    h = [f"<h1>{escape(doc.title)}</h1>",
         f"<p class='sub'>Hasil analisis konten NARAtive &middot; {doc.page_count} halaman &middot; {len(paragraphs)} paragraf</p>",
         "<table class='sum'><tr>"
         f"<td><span class='k'>Rating konten</span><br><span class='v'>{escape(doc.rating or '-')}</span></td>"
         f"<td><span class='k'>Rentang usia</span><br><span class='v'>{escape(doc.age_range or '-')}</span></td>"
         f"<td><span class='k'>Konten dewasa</span><br><span class='v'>{doc.pct_adult if doc.pct_adult is not None else '-'}%</span></td>"
         f"<td><span class='k'>Bobot cerita</span><br><span class='v'>{doc.heaviness if doc.heaviness is not None else '-'}</span></td>"
         "</tr></table>",
         "<table class='sum'><tr>"
         f"<td><span class='k'>Bahasa kasar</span><br>{doc.pct_profanity}% paragraf</td>"
         f"<td><span class='k'>Seksual</span><br>{doc.pct_sexual}% paragraf</td>"
         f"<td><span class='k'>Kekerasan</span><br>{doc.pct_violence}% paragraf</td>"
         "</tr></table>",
         f"<p class='note'>{EMOTION_NEGATIVE_NOTE} Paragraf yang melewati ambang deteksi disorot kuning "
         f"dan diberi label dimensinya ({flagged} paragraf). Teks di bawah adalah hasil ekstraksi dan pembersihan "
         "sistem, sehingga dapat dibandingkan dengan buku aslinya.</p>"]
    titles = {c.number: c.title for c in chapters}
    for no in sorted(by_chapter):
        h.append(f"<h2>{escape(titles.get(no, f'Bab {no}'))}</h2>")
        for p in by_chapter[no]:
            fl = _flags(p, thresholds)
            if fl:
                h.append(f"<p class='hl'><span class='tag'>[{escape(', '.join(fl))}]</span> {escape(p.text)}</p>")
            else:
                h.append(f"<p>{escape(p.text)}</p>")

    story = pymupdf.Story(html="<body>" + "".join(h) + "</body>", user_css=CSS)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    media = pymupdf.paper_rect("a4")
    where = media + (50, 50, -50, -60)
    more = 1
    while more:
        dev = writer.begin_page(media)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()

    pdf = pymupdf.open("pdf", buf.getvalue())
    total = len(pdf)
    for i, page in enumerate(pdf, 1):
        page.insert_text((media.width / 2 - 20, media.height - 30), f"{i} / {total}", fontsize=8, color=(0.4, 0.4, 0.5))
    out = pdf.tobytes(garbage=3, deflate=True)
    pdf.close()
    return out