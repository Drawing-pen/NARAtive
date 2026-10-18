import logging
import posixpath
import re
import unicodedata
import zipfile
from html.parser import HTMLParser
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from .pdf_utils import MAX_PARAGRAPH_CHARS, _chunk_long

log = logging.getLogger("narative.epub")

CHARS_PER_PAGE = 1800        
MIN_PARAGRAPH_CHARS = 20
MIN_UNTITLED_CHARS = 300     
MAX_UNCOMPRESSED = 300 * 1024 * 1024

_FONT_ONLY = ("http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC")
_BLOCK = {"p", "div", "li", "blockquote", "pre", "dt", "dd", "tr", "section", "article", "aside",
          "figcaption", "caption", "ul", "ol", "table", "body", "hr", "h1", "h2", "h3", "h4", "h5", "h6"}
_SKIP = {"head", "script", "style", "svg", "nav", "title", "math"}
_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_TOC_NAMES = re.compile(r"^(contents|table of contents|daftar isi|toc)$", re.IGNORECASE)


class EpubError(Exception):
    """Pesan sudah berbahasa Indonesia dan aman ditampilkan ke pengguna."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _squash(text: str) -> str:
    text = unicodedata.normalize("NFC", text.replace("­", "").replace("​", ""))
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


class _Blocks(HTMLParser):

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple] = []
        self.buf: list[str] = []
        self.skip = 0
        self.heading = 0          
        self.in_a = 0
        self.a_chars = 0
        self.all_chars = 0

    def _flush(self):
        text = _squash("".join(self.buf))
        self.buf = []
        if not text:
            return
        self.blocks.append(("h", self.heading, text) if self.heading else ("p", text))

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
        if tag == "a":
            self.in_a += 1
        if tag in _BLOCK:
            self._flush()
            if tag in _HEADINGS:
                self.heading = int(tag[1])

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "a":
            self.in_a = max(0, self.in_a - 1)
        if tag in _BLOCK:
            self._flush()
            if tag in _HEADINGS:
                self.heading = 0

    def handle_data(self, data):
        if self.skip:
            return
        self.buf.append(data)
        n = len(data.strip())
        self.all_chars += n
        if self.in_a:
            self.a_chars += n

    def close(self):
        super().close()
        self._flush()


def _decode(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace")
    m = re.match(rb'\s*<\?xml[^>]*encoding=["\']([\w.-]+)["\']', raw)
    for enc in ([m.group(1).decode("ascii")] if m else []) + ["utf-8"]:
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def _xml(raw: bytes) -> ET.Element:
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", _decode(raw))   
    return ET.fromstring(text)


def _resolve(base_dir: str, href: str) -> str:
    return posixpath.normpath(posixpath.join(base_dir, unquote(href.split("#", 1)[0]))) if href else ""


def _check_drm(z: zipfile.ZipFile) -> None:
    if "META-INF/encryption.xml" not in z.namelist():
        return
    try:
        root = _xml(z.read("META-INF/encryption.xml"))
    except ET.ParseError:
        return
    for el in root.iter():
        if _local(el.tag) == "encryptionmethod" and not any(el.get("Algorithm", "").startswith(a) for a in _FONT_ONLY):
            raise EpubError("EPUB ini dilindungi DRM sehingga isinya tidak bisa dibaca. Gunakan EPUB tanpa DRM.")


def _package(z: zipfile.ZipFile):
    """Return (folder OPF, manifest {id: (path, media, props)}, urutan spine [id], id NCX, judul dari metadata)."""
    try:
        container = _xml(z.read("META-INF/container.xml"))
        opf_path = next(el.get("full-path") for el in container.iter() if _local(el.tag) == "rootfile")
        opf = _xml(z.read(opf_path))
    except (KeyError, StopIteration, ET.ParseError):
        raise EpubError("Struktur EPUB tidak valid atau rusak.")
    base = posixpath.dirname(opf_path)
    manifest, spine, ncx = {}, [], None
    for el in opf.iter():
        tag = _local(el.tag)
        if tag == "item":
            manifest[el.get("id")] = (_resolve(base, el.get("href", "")), el.get("media-type", ""), el.get("properties", ""))
        elif tag == "itemref" and el.get("linear", "yes") != "no":
            spine.append(el.get("idref"))
        elif tag == "spine":
            ncx = el.get("toc")
    return base, manifest, spine, ncx


def _toc(z: zipfile.ZipFile, manifest: dict, ncx_id: str | None) -> dict[str, str]:
    """{berkas: judul bab} dari nav EPUB3, atau NCX EPUB2. Bila satu berkas punya banyak entri, yang pertama dipakai."""
    out: dict[str, str] = {}

    def add(path: str, title: str):
        title = _squash(title)
        if path and title and path not in out:
            out[path] = title

    try:
        nav = next((p for p, _, props in manifest.values() if "nav" in props.split()), None)
        if nav:
            class Nav(HTMLParser):
                href, text, depth = None, [], 0
                def handle_starttag(s, tag, attrs):
                    if tag == "a":
                        s.href, s.text = dict(attrs).get("href"), []
                def handle_data(s, data):
                    if s.href is not None:
                        s.text.append(data)
                def handle_endtag(s, tag):
                    if tag == "a" and s.href is not None:
                        add(_resolve(posixpath.dirname(nav), s.href), "".join(s.text))
                        s.href = None
            p = Nav(convert_charrefs=True)
            p.feed(_decode(z.read(nav)))
        elif ncx_id and ncx_id in manifest:
            ncx = manifest[ncx_id][0]
            for point in _xml(z.read(ncx)).iter():
                if _local(point.tag) == "navpoint":
                    label = next((t.text or "" for t in point.iter() if _local(t.tag) == "text"), "")
                    src = next((c.get("src") for c in point.iter() if _local(c.tag) == "content"), "")
                    add(_resolve(posixpath.dirname(ncx), src or ""), label)
    except (KeyError, ET.ParseError):
        log.warning("Daftar isi EPUB tidak terbaca; judul bab diambil dari isi.")
    return out


def _pack(paragraphs: list[str]) -> list[str]:
    out, cur = [], ""

    def flush():
        nonlocal cur
        if cur:
            out.append(cur)
        cur = ""

    for text in paragraphs:
        if not re.search(r"[^\W\d_]", text):   
            flush()
            continue
        for piece in _chunk_long(text):
            if cur and len(cur) + 1 + len(piece) > MAX_PARAGRAPH_CHARS:
                flush()
            cur = f"{cur}\n{piece}" if cur else piece
    flush()
    return out


def read_epub(path: str) -> tuple[int, list[str], list[tuple[int, str]]]:
    """Return (perkiraan halaman, judul bab, [(nomor bab, paragraf)])."""
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
                parser = _Blocks()
                parser.feed(_decode(z.read(fpath)))
                parser.close()
            except KeyError:
                continue
            if parser.all_chars and parser.a_chars / parser.all_chars > 0.6:
                continue   
            blocks = parser.blocks
            if not any(b[0] == "p" for b in blocks):
                continue
            title = toc.get(fpath)
            cur = {"title": title, "paras": [], "from_toc": bool(title)}
            chapters.append(cur)
            for b in blocks:
                if b[0] == "p":
                    cur["paras"].append(b[1])
                    continue
                level, text = b[1], b[2]
                if _TOC_NAMES.match(text):
                    continue
                if not cur["paras"]:
                    if cur["title"] is None:
                        cur["title"] = text
                elif level <= 2 and len(text) <= 120:
                    cur = {"title": text, "paras": [], "from_toc": False}  
                    chapters.append(cur)

        merged: list[dict] = []
        for ch in chapters:
            if ch["title"] is None and merged and sum(len(p) for p in ch["paras"]) < MIN_UNTITLED_CHARS:
                merged[-1]["paras"].extend(ch["paras"])
            else:
                merged.append(ch)

        titles: list[str] = []
        paras: list[tuple[int, str]] = []
        for ch in merged:
            texts = [t for t in _pack(ch["paras"]) if len(t) >= MIN_PARAGRAPH_CHARS]
            if not texts:
                continue
            titles.append((ch["title"] or ("Pembuka" if not titles else f"Bagian {len(titles) + 1}"))[:255])
            paras.extend((len(titles), t) for t in texts)

    if not paras:
        raise EpubError("EPUB tidak berisi teks yang dapat dianalisis.")
    chars = sum(len(t) for _, t in paras)
    pages = max(1, round(chars / CHARS_PER_PAGE))
    log.info("EPUB: %d bab, %d paragraf, perkiraan %d halaman", len(titles), len(paras), pages)
    return pages, titles, paras