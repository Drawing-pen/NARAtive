import logging
import re
import zipfile
from html.parser import HTMLParser

from app.extraction import markdown_utils as mdu
from app.extraction.epub_utils import (
    CHARS_PER_PAGE,
    MAX_UNCOMPRESSED,
    MIN_PARAGRAPH_CHARS,
    MIN_UNTITLED_CHARS,
    EpubError,
    _BLOCK,
    _HEADINGS,
    _SKIP,
    _TOC_NAMES,
    _check_drm,
    _decode,
    _package,
    _squash,
    _toc,
)
from app.extraction.pdf_utils import MAX_PARAGRAPH_CHARS

log = logging.getLogger("narative.epub")

B_OPEN, B_CLOSE, I_OPEN, I_CLOSE = "", "", "", ""
_MARK_TAGS = {"strong": (B_OPEN, B_CLOSE), "b": (B_OPEN, B_CLOSE), "em": (I_OPEN, I_CLOSE), "i": (I_OPEN, I_CLOSE)}
_SENTINEL_MARKS = {B_OPEN: "**", B_CLOSE: "**", I_OPEN: "*", I_CLOSE: "*"}
_HAS_LETTER = re.compile(r"[^\W\d_]")
_NEEDS_ESCAPE = re.compile(r"([\\`*_\[\]<>])")


def _escape(text: str) -> str:
    return _NEEDS_ESCAPE.sub(lambda m: "\\" + m.group(1), text)


def _guard_start(markdown: str) -> str:
    if markdown.startswith("#") or re.match(r"[-+]\s", markdown):
        return "\\" + markdown
    return re.sub(r"^(\d+)([.)])(\s)", lambda m: f"{m.group(1)}\\{m.group(2)}{m.group(3)}", markdown)


def _tidy_marks(raw: str) -> str:
    for opener, closer in ((B_OPEN, B_CLOSE), (I_OPEN, I_CLOSE)):
        for _ in range(3):
            raw = re.sub(f"({opener})(\\s+)", lambda m: m.group(2) + m.group(1), raw)
            raw = re.sub(f"(\\s+)({closer})", lambda m: m.group(2) + m.group(1), raw)
        raw = re.sub(f"{opener}\\s*{closer}", " ", raw)
    return raw


class _MdBlocks(HTMLParser):
    """Ubah XHTML menjadi blok: ("h", level, teks polos) dan (jenis, markdown) dengan jenis p, li, atau quote."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple] = []
        self.buf: list[str] = []
        self.skip = 0
        self.heading = 0
        self.quote = 0
        self.item = 0
        self.in_a = 0
        self.a_chars = 0
        self.all_chars = 0

    def _flush(self):
        raw = _tidy_marks("".join(self.buf))
        self.buf = []
        text = _squash(raw)
        if not text:
            return
        if self.heading:
            plain = "".join(c for c in text if c not in _SENTINEL_MARKS)
            self.blocks.append(("h", self.heading, mdu.plain_text(plain)))
            return
        content = _guard_start("".join(_SENTINEL_MARKS.get(c, c) for c in text))
        if self.quote:
            self.blocks.append(("quote", "> " + content))
        elif self.item:
            self.blocks.append(("li", "- " + content))
        else:
            self.blocks.append(("p", content))

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "br":
            self.buf.append(" ")
            return
        if tag in _MARK_TAGS:
            self.buf.append(_MARK_TAGS[tag][0])
            return
        if tag == "a":
            self.in_a += 1
        if tag in _BLOCK:
            self._flush()
            if tag in _HEADINGS:
                self.heading = int(tag[1])
            elif tag == "blockquote":
                self.quote += 1
            elif tag == "li":
                self.item += 1

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in _MARK_TAGS:
            self.buf.append(_MARK_TAGS[tag][1])
            return
        if tag == "a":
            self.in_a = max(0, self.in_a - 1)
        if tag in _BLOCK:
            self._flush()
            if tag in _HEADINGS:
                self.heading = 0
            elif tag == "blockquote":
                self.quote = max(0, self.quote - 1)
            elif tag == "li":
                self.item = max(0, self.item - 1)

    def handle_data(self, data):
        if self.skip:
            return
        self.buf.append(_escape(data))
        n = len(data.strip())
        self.all_chars += n
        if self.in_a:
            self.a_chars += n

    def close(self):
        super().close()
        self._flush()


def _pack_blocks(items: list[tuple]) -> list[mdu.Block]:
    """items: (jenis, markdown, teks polos, level). Paragraf pendek berurutan dikemas seperti `epub_utils._pack`."""
    out: list[mdu.Block] = []
    mds: list[str] = []
    plains: list[str] = []

    def flush():
        if mds:
            text = "\n".join(plains)
            if len(text) >= MIN_PARAGRAPH_CHARS:
                out.append(mdu.Block("p", "\n\n".join(mds), text))
        mds.clear()
        plains.clear()

    for kind, markdown, plain, level in items:
        if kind == "p":
            if not _HAS_LETTER.search(plain):
                flush()
                continue
            for piece in mdu.split_block(markdown):
                piece_plain = mdu.plain_text(piece)
                if plains and len("\n".join(plains)) + 1 + len(piece_plain) > MAX_PARAGRAPH_CHARS:
                    flush()
                mds.append(piece)
                plains.append(piece_plain)
            continue
        flush()
        if not _HAS_LETTER.search(plain):
            continue
        if kind == "h":
            out.append(mdu.Block("h", markdown, plain, level))
            continue
        prefix = "> " if kind == "quote" else "- "
        for piece in mdu.split_block(markdown[len(prefix):]):
            out.append(mdu.Block(kind, prefix + piece, mdu.plain_text(piece)))
    flush()
    return out


def read_epub_markdown(path: str) -> tuple[int, list[str], list[tuple[int, mdu.Block]]]:
    """Return (perkiraan halaman, judul bab, [(nomor bab, Block)]). Aturan bab sama dengan `read_epub`."""
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        raise EpubError("File EPUB rusak atau bukan EPUB yang valid.")
    with z:
        if sum(i.file_size for i in z.infolist()) > MAX_UNCOMPRESSED:
            raise EpubError("Isi EPUB terlalu besar untuk diproses.")
        _check_drm(z)
        _, manifest, spine, ncx_id = _package(z)
        toc = _toc(z, manifest, ncx_id)

        chapters: list[dict] = []
        for idref in spine:
            if idref not in manifest:
                continue
            fpath, media, props = manifest[idref]
            if "html" not in media and "xml" not in media or "nav" in props.split():
                continue
            try:
                parser = _MdBlocks()
                parser.feed(_decode(z.read(fpath)))
                parser.close()
            except KeyError:
                continue
            if parser.all_chars and parser.a_chars / parser.all_chars > 0.6:
                continue
            blocks = parser.blocks
            if not any(b[0] != "h" for b in blocks):
                continue
            cur = {"title": toc.get(fpath), "items": []}
            chapters.append(cur)
            for b in blocks:
                if b[0] != "h":
                    cur["items"].append((b[0], b[1], mdu.plain_text(b[1]), 0))
                    continue
                level, text = b[1], b[2]
                if _TOC_NAMES.match(text):
                    continue
                if not cur["items"]:
                    if cur["title"] is None:
                        cur["title"] = text
                elif level <= 2 and len(text) <= 120:
                    cur = {"title": text, "items": []}
                    chapters.append(cur)
                else:
                    cur["items"].append(("h", f"{'#' * min(level, 6)} {_escape(text)}", text, min(level, 6)))

        merged: list[dict] = []
        for ch in chapters:
            if ch["title"] is None and merged and sum(len(i[2]) for i in ch["items"]) < MIN_UNTITLED_CHARS:
                merged[-1]["items"].extend(ch["items"])
            else:
                merged.append(ch)

        titles: list[str] = []
        blocks_out: list[tuple[int, mdu.Block]] = []
        for ch in merged:
            packed = _pack_blocks(ch["items"])
            if not packed:
                continue
            titles.append((ch["title"] or ("Pembuka" if not titles else f"Bagian {len(titles) + 1}"))[:255])
            blocks_out.extend((len(titles), b) for b in packed)

    if not blocks_out:
        raise EpubError("EPUB tidak berisi teks yang dapat dianalisis.")
    chars = sum(len(b.text) for _, b in blocks_out)
    pages = max(1, round(chars / CHARS_PER_PAGE))
    log.info("EPUB (markdown): %d bab, %d blok, perkiraan %d halaman", len(titles), len(blocks_out), pages)
    return pages, titles, blocks_out
