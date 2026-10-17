import logging
import re
import string
import unicodedata
from collections import Counter
from functools import lru_cache

import pymupdf

log = logging.getLogger("uvicorn.error")

_DICT_FLAGS = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES


NUMBER_WORDS = (
    "satu|dua|tiga|empat|lima|enam|tujuh|delapan|sembilan|sepuluh|"
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
)
HEADING = re.compile(
    rf"^(bab|chapter|episode|bagian|part)\s+([0-9]+|[ivxlcdm]+|{NUMBER_WORDS})\b[\s.:\-\u2013\u2014]*(.*)$",
    re.IGNORECASE,
)

STANDALONE = re.compile(
    r"^(prolog|prologue|epilog|epilogue|pendahuluan|penutup|interlude|intermezzo|kata pengantar|contents|table of contents|daftar isi|about the author|tentang penulis|acknowledg(?:e)?ments?|ucapan terima kasih|also by\b|books by\b|if you enjoyed)\b.{0,40}$",
    re.IGNORECASE,
)

URLISH = re.compile(
    r"(?:https?://)?(?:www\.)?[\w-]+(?:\.[\w-]+)*\.(?:blogspot\.com|wordpress\.com|com|net|org|co\.id)\b\S*",
    re.IGNORECASE,
)

PAGE_NUMBER = re.compile(
    r"^(?:halaman|hal\.?|hlm\.?|page|p\.)?\s*[-\u2013\u2014\[(]?\s*(?:\d{1,4}|[ivxlcdm]{1,7})\s*[-\u2013\u2014\])]?(?:\s*/\s*\d{1,4})?$",
    re.IGNORECASE,
)
PAGES_PER_SECTION = 20   


def _norm_edge(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", line.strip().lower()))


_BAD_CATEGORIES = {"Cc", "Cf", "Co", "Cs", "Cn"}


_LIGATURES = str.maketrans({"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl", "\ufb05": "st", "\ufb06": "st"})


_FUNC = "a|of|in|on|to|at|by|or|an|as|if|it|is|he|we|me|my|so|up|us|do|go|and|the|for|but|off|out|from|with"
_GLUED_CAMEL = re.compile(rf"\b((?:{_FUNC})|(?:{_FUNC.title().replace('|', '|')}))(?=[A-Z][a-z]+)")
_WORD6 = re.compile(r"[A-Za-z]{6,}")
_SHORT_OK = set("of in on to at by or an as if it is he we me my so up us do go no be am".split())


def _unglue_word(m: re.Match) -> str:
    w = m.group(0)
    try:
        if _zipf(w) >= 1.0:
            return w
        best = None
        for i in range(2, len(w) - 1):
            a, b = w[:i].lower(), w[i:].lower()
            if (len(a) < 3 and a not in _SHORT_OK) or (len(b) < 3 and b not in _SHORT_OK):
                continue
            za, zb = _zipf(a), _zipf(b)
            if min(za, zb) >= 3.5 and (best is None or min(za, zb) > best[0]):
                best = (min(za, zb), i)
        return w[:best[1]] + " " + w[best[1]:] if best else w
    except Exception:   
        return w


def clean_text(text: str) -> str:
    text = text.translate(_LIGATURES)                    
    text = re.sub(r"\u00ad\s*", "", text)                
    text = "".join(c for c in text if c in "\n\t " or unicodedata.category(c) not in _BAD_CATEGORIES)
    text = URLISH.sub(" ", text)
    text = re.sub(r"(?<=[a-z])-\s+(?=[a-z])", "-", text)  
    text = _GLUED_CAMEL.sub(lambda m: m.group(1) + " ", text)   
    text = _WORD6.sub(_unglue_word, text)
    return re.sub(r"\s+", " ", text).strip()

_DROPCAP = re.compile(r"^[\x00-\x08\x0b\x0c\x0e-\x1f\ue000-\uf8ff]+\s*([A-Za-z]{2,})\b")


@lru_cache(maxsize=200_000)
def _zipf(word: str) -> float:
    from wordfreq import zipf_frequency   

    w = word.lower()
    return max(zipf_frequency(w, "id"), zipf_frequency(w, "en"))


def restore_dropcap(raw: str) -> str:
    m = _DROPCAP.match(raw)
    if not m:
        return raw
    try:
        frag = m.group(1)
        base = _zipf(frag)
        scored = sorted(((_zipf(c + frag), c) for c in string.ascii_uppercase), reverse=True)
    except Exception:   
        return raw
    (best, letter), second = scored[0], scored[1][0]
    if best >= 3.0 and best >= base + 1.0 and best >= second + 0.7:
        return letter + raw[m.start(1):]
    return raw


def guess_dropcap_letter(fragment: str) -> str | None:
    try:
        frag = fragment.lower()
        scored = sorted(((_zipf(c + frag), c) for c in string.ascii_uppercase), reverse=True)
    except Exception:  
        return None
    (best, letter), second = scored[0], scored[1][0]
    return letter if best >= 2.5 and best >= second + 0.3 else None


def _vector_dropcaps(page, d=None) -> dict[str, str]:
    try:
        shapes = [d["rect"] for d in page.get_drawings() if d.get("fill") is not None and 0 < d["rect"].width < 60 and 0 < d["rect"].height < 80]
    except Exception:
        return {}
    if not shapes:
        return {}
    found = {}
    for block in (d or page.get_text("dict", flags=_DICT_FLAGS))["blocks"]:
        for ln in block.get("lines", []):
            text = "".join(sp["text"] for sp in ln["spans"]).strip()
            m = re.match(r"^([A-Z]{2,})\b", text)
            if not m:
                continue
            x0, y0, x1, y1 = ln["bbox"]
            lh = y1 - y0
            near = [r for r in shapes if x0 - 45 <= r.x1 <= x0 + 4 and r.y0 <= y1 and r.y1 >= y0 and r.height >= 0.5 * lh]
            if not near:
                continue
            height = max(r.y1 for r in near) - min(r.y0 for r in near)
            if height < 0.9 * lh:
                continue
            letter = guess_dropcap_letter(m.group(1))
            if letter:
                found[text] = letter
    return found


def _rotated_lines(page, d=None) -> set[str]:
    out = set()
    for block in (d or page.get_text("dict", flags=_DICT_FLAGS))["blocks"]:
        for ln in block.get("lines", []):
            if abs(ln["dir"][1]) > 0.2:
                out.add("".join(sp["text"] for sp in ln["spans"]).strip())
    return out


def _margin_numbers(page, d=None) -> set[str]:
    h = page.rect.height
    out = set()
    for block in (d or page.get_text("dict", flags=_DICT_FLAGS))["blocks"]:
        for ln in block.get("lines", []):
            y0, y1 = ln["bbox"][1], ln["bbox"][3]
            if y0 > 0.88 * h or y1 < 0.10 * h:
                raw = "".join(sp["text"] for sp in ln["spans"]).strip()
                text = clean_text(raw)
                if raw and (not text or PAGE_NUMBER.match(text)):
                    out.add(raw)
    return out


def _merge_letter_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        cur = lines[i].strip()
        if len(cur) == 1 and cur.isupper() and cur.isalpha():
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            nxt = lines[j].strip() if j < len(lines) else ""
            if nxt[:1].islower():
                first = re.match(r"[A-Za-z]+", nxt)
                ok = cur not in "AIO"
                if not ok and first:
                    try:
                        ok = _zipf(cur + first.group(0)) >= 2.5 > _zipf(first.group(0))
                    except Exception:
                        ok = False
                if ok:
                    if out and out[-1].strip():
                        out.append("")   
                    out.append(cur + nxt)
                    i = j + 1
                    continue
        out.append(lines[i])
        i += 1
    return out


def _page_text(page, drop: set[str]) -> str:
    d = page.get_text("dict", flags=_DICT_FLAGS)   
    rotated = _rotated_lines(page, d) | _margin_numbers(page, d)
    lines = [ln for ln in page.get_text("text").split("\n") if ln.strip() not in rotated]
    lines = _merge_letter_lines(lines)
    caps = _vector_dropcaps(page, d)
    if caps:
        lines = [(caps.pop(ln.strip()) + ln.lstrip()) if ln.strip() in caps else ln for ln in lines]
    edges = _edges(lines)
    return "\n".join(ln for ln in lines if not (ln.strip() in edges and _norm_edge(ln) in drop))


def _edges(lines: list[str]) -> set[str]:
    filled = [ln.strip() for ln in lines if ln.strip()]
    return set(filled[:2] + filled[-2:])


def _running_edges(pdf) -> set[str]:
    if len(pdf) < 8:
        return set()
    counts: dict[str, int] = {}
    for page in pdf:
        seen = {_norm_edge(ln) for ln in _edges(page.get_text("text").split("\n")) if len(ln) <= 100 and not HEADING.match(ln)}
        for key in seen:
            counts[key] = counts.get(key, 0) + 1
    need = max(4, int(0.3 * len(pdf)))
    return {k for k, c in counts.items() if c >= need}


def _plain(text: str) -> str:
    return re.sub(r"[^\w ]", "", re.sub(r"\s+", " ", text.lower())).strip()


def _toc_headings(pdf, pages: list[str], extra: set[str]) -> int:
    toc = [(lvl, title.strip(), pg - 1) for lvl, title, pg in pdf.get_toc() if title.strip() and 1 <= pg <= len(pages)]
    by_level: dict[int, list] = {}
    for item in toc:
        by_level.setdefault(item[0], []).append(item)
    limit = max(40, len(pages) // 6)
    levels = [lv for lv, items in sorted(by_level.items()) if 2 <= len(items) <= limit]
    if not levels:
        return 0
    chosen = by_level[levels[-1]]   
    for _, title, pg in chosen:
        target = _plain(title)
        lines = [ln.strip() for ln in pages[pg].split("\n") if ln.strip()]
        hit = next((ln for ln in lines[:15] if _plain(ln) == target or (len(target) >= 4 and _plain(ln).startswith(target))), None)
        if hit:
            extra.add(hit)
        else:
            pages[pg] = title + "\n\n" + pages[pg]
            extra.add(title)
    return len(chosen)


def _big_lines(pdf) -> set[str]:
    sizes: Counter = Counter()
    lines: list[tuple[str, float]] = []
    for page in pdf:
        for block in page.get_text("dict", flags=_DICT_FLAGS)["blocks"]:
            for ln in block.get("lines", []):
                text = "".join(sp["text"] for sp in ln["spans"]).strip()
                if text:
                    size = min(sp["size"] for sp in ln["spans"])
                    sizes[round(size)] += len(text)
                    lines.append((text, size))
    if not sizes:
        return set()
    body = sizes.most_common(1)[0][0]
    found = {t for t, sz in lines if sz >= body * 1.25 and 3 <= len(t) <= 80 and len(t.split()) <= 10}
    return found if len(found) <= max(3, len(pdf)) else set()   # terlalu banyak = bukan judul bab


def read_pdf(path: str) -> tuple[int, list[str], list[tuple[int, str]]]:
    with pymupdf.open(path) as pdf:
        page_count = len(pdf)
        drop = _running_edges(pdf)
        pages = [_page_text(page, drop) for page in pdf]
        extra: set[str] = set()

        method = "daftar isi PDF" if _toc_headings(pdf, pages, extra) else None
        if method:
            titles, paras = split_chapters(_join_pages(pages), extra=extra)
        else:
            titles, paras = split_chapters(_join_pages(pages))
            method = "judul di teks"
            if len(titles) < 2:
                big = _big_lines(pdf)
                if big:
                    titles, paras = split_chapters(_join_pages(pages), extra=big)
                    method = "ukuran huruf"
            if len(titles) < 2 and page_count > PAGES_PER_SECTION + 10:
                sections: set[str] = set()
                for start in range(0, page_count, PAGES_PER_SECTION):
                    label = f"Halaman {start + 1}\u2013{min(start + PAGES_PER_SECTION, page_count)}"
                    pages[start] = label + "\n\n" + pages[start]
                    sections.add(label)
                titles, paras = split_chapters(_join_pages(pages), extra=sections)
                method = "dipecah per halaman"
        if any("glyphless" in f[3].lower() for pg in list(pdf)[:15] for f in pg.get_fonts()):
            log.warning("PDF ini hasil OCR (teks tak kasat mata): mutu teks mengikuti hasil OCR-nya, awal bab bisa berantakan.")
        log.info("Bab: %d terdeteksi lewat %s (%d halaman, %d paragraf)", len(titles), method, page_count, len(paras))
    return page_count, titles, paras


def split_chapters(text: str, min_chars: int = 20, extra: set[str] | None = None) -> tuple[list[str], list[tuple[int, str]]]:
    titles: list[str] = []
    found: list[tuple[int, str]] = []   
    last_heading_at = -1 

    def flush(buf: list[str]):
        merged = clean_text(restore_dropcap(" ".join(buf).lstrip()))
        if len(merged) >= min_chars:
            for chunk in _chunk_long(merged):
                found.append((len(titles), chunk))
        buf.clear()

    for block in re.split(r"\n\s*\n", text):
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        buf: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            m = (HEADING.match(line) or STANDALONE.match(line)) if len(line) <= 80 else None
            if not m and not (extra and line in extra):
                buf.append(lines[i])
                i += 1
                continue
            run = 0   
            while i + run < len(lines) and len(lines[i + run]) <= 80 and (HEADING.match(lines[i + run]) or STANDALONE.match(lines[i + run])):
                run += 1
            if run >= 3:
                i += run
                continue
            flush(buf)
            title = lines[i]
            i += 1
            nxt_is_heading = i < len(lines) and (HEADING.match(lines[i]) or STANDALONE.match(lines[i]))
            after = lines[i + 1] if i + 1 < len(lines) else ""
            nxt_is_body = i < len(lines) and (after[:1].islower() or len(lines[i].split()) > 6)
            if m and HEADING.match(title) and not m.group(3).strip() and i < len(lines) and not nxt_is_heading and not nxt_is_body and len(lines[i]) <= 60 and not lines[i].endswith((".", ",", ";")):
                title += " \u2014 " + lines[i]
                i += 1
            title = clean_text(title) or f"Bab {len(titles) + 1}"   
            if not titles or titles[-1] != title or len(found) != last_heading_at:
                titles.append(title)
            last_heading_at = len(found)
        flush(buf)

    if not titles:
        return ["Isi naskah"], [(1, t) for _, t in found]
    if any(n == 0 for n, _ in found):
        titles.insert(0, "Pembuka")
        return titles, [(n + 1, t) for n, t in found]
    return titles, found


def count_pages(path: str) -> int:
    with pymupdf.open(path) as pdf:
        return len(pdf)


MAX_PARAGRAPH_CHARS = 900


def _join_pages(pages: list[str]) -> str:
    out = ""
    for text in pages:
        if out:
            out = out.rstrip()
            text = text.lstrip()
            tail = out[-1:]
            head = text[:1]
            out += ("\n" if head.islower() and tail not in ".!?\"\u201d'\u2019:;)" else "\n\n")
        out += text
    return out


def _chunk_long(paragraph: str) -> list[str]:
    if len(paragraph) <= MAX_PARAGRAPH_CHARS:
        return [paragraph]
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    chunks, current = [], ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > MAX_PARAGRAPH_CHARS:
            chunks.append(current.strip())
            current = ""
        current += sentence + " "
    if current.strip():
        chunks.append(current.strip())
    return chunks