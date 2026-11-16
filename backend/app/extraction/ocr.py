import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from wordfreq import zipf_frequency

from app.core.config import settings

log = logging.getLogger("uvicorn.error")

MIN_LETTERS = 25
MIN_LETTER_SHARE = 0.5
MAX_REPLACEMENT_SHARE = 0.1
REPLACEMENT = "\ufffd"
NOT_LANGUAGES = {"osd", "equ"}
STANDARD_DIRS = [
    r"C:\Program Files\Tesseract-OCR\tessdata",
    r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
    "/usr/share/tesseract-ocr/5/tessdata",
    "/usr/share/tesseract-ocr/4.00/tessdata",
    "/usr/share/tessdata",
    "/usr/local/share/tessdata",
]
_WORD = re.compile(r"[^\W\d_]{3,}")
_warned: set[str] = set()


def page_needs_ocr(text: str) -> bool:
    compact = "".join(text.split())
    letters = sum(c.isalpha() for c in compact)
    if letters < MIN_LETTERS or letters / len(compact) < MIN_LETTER_SHARE:
        return True
    return compact.count(REPLACEMENT) / len(compact) > MAX_REPLACEMENT_SHARE


def _has_languages(folder: str) -> bool:
    return os.path.isdir(folder) and any(Path(folder).glob("*.traineddata"))


def tessdata_dir() -> str | None:
    prefix = os.environ.get("TESSDATA_PREFIX", "")
    candidates = [settings.tessdata_dir, prefix, os.path.join(prefix, "tessdata") if prefix else "", *STANDARD_DIRS]
    return next((c for c in candidates if c and _has_languages(c)), None)


def installed_languages() -> set[str]:
    folder = tessdata_dir()
    if folder is None:
        return set()
    return {p.stem for p in Path(folder).glob("*.traineddata")} - NOT_LANGUAGES


def usable_languages() -> str:
    requested = [lang for lang in settings.ocr_languages.split("+") if lang]
    installed = installed_languages()
    missing = [lang for lang in requested if lang not in installed]
    if missing and "+".join(missing) not in _warned:
        _warned.add("+".join(missing))
        log.warning("Paket bahasa OCR tidak terpasang: %s", ", ".join(missing))
    return "+".join(lang for lang in requested if lang in installed)


def ocr_ready() -> bool:
    return settings.ocr_enabled and bool(usable_languages())


def recognize(page) -> bytes:
    pixmap = page.get_pixmap(dpi=settings.ocr_dpi, alpha=False)
    return pixmap.pdfocr_tobytes(language=usable_languages(), tessdata=tessdata_dir())


def _words_known(text: str) -> tuple[int, int]:
    words = _WORD.findall(text.lower())
    known = sum(1 for w in words if zipf_frequency(w, "id") > 0 or zipf_frequency(w, "en") > 0)
    return known, len(words)


def text_quality(texts: list[str]) -> float:
    known = total = 0
    for text in texts:
        k, t = _words_known(text)
        known, total = known + k, total + t
    return known / total if total else 0.0


@dataclass
class Prepared:
    path: str
    pages: int
    ocr_pages: int = 0
    skipped: int = 0
    known_words: int = 0
    total_words: int = 0
    stopped: bool = False

    @property
    def quality(self) -> float | None:
        if not self.ocr_pages:
            return None
        return self.known_words / self.total_words if self.total_words else 0.0


def prepare_pdf(source: str, destination: str, on_page=None, should_stop=None) -> Prepared:
    ready = ocr_ready()
    with pymupdf.open(source) as src:
        result = Prepared(path=source, pages=len(src))
        replacements: dict[int, bytes] = {}
        for index in range(result.pages):
            if should_stop is not None and should_stop():
                result.stopped = True
                return result
            page = src[index]
            if page_needs_ocr(page.get_text("text")):
                if not ready:
                    result.skipped += 1
                else:
                    try:
                        data = recognize(page)
                        with pymupdf.open("pdf", data) as recognised:
                            known, total = _words_known(recognised[0].get_text("text"))
                        replacements[index] = data
                        result.ocr_pages += 1
                        result.known_words += known
                        result.total_words += total
                    except Exception as error:
                        log.warning("OCR halaman %d dilewati: %s", index + 1, error)
                        result.skipped += 1
            if on_page is not None:
                on_page(index + 1)
        if not replacements:
            return result
        with pymupdf.open() as out:
            for index in range(result.pages):
                if index in replacements:
                    with pymupdf.open("pdf", replacements[index]) as recognised:
                        out.insert_pdf(recognised)
                else:
                    out.insert_pdf(src, from_page=index, to_page=index)
            try:
                out.set_toc(src.get_toc())
            except Exception:
                log.warning("Daftar isi PDF tidak ikut disalin ke berkas kerja.")
            out.save(destination, garbage=3, deflate=True)
        result.path = destination
    return result
