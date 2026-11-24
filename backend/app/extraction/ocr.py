import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from wordfreq import zipf_frequency

from app.core.config import settings
from app.extraction import vision

log = logging.getLogger("uvicorn.error")

CONFIDENCE = 75.0
MIN_WORDS = 10
STANDARD_BINARIES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
]
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


def engine_mode() -> str:
    return vision.mode()


def tesseract_binary() -> str | None:
    found = shutil.which("tesseract")
    if found:
        return found
    return next((path for path in STANDARD_BINARIES if os.path.isfile(path)), None)


def parse_tsv(text: str) -> tuple[float | None, int]:
    values = []
    for line in text.splitlines()[1:]:
        columns = line.split("\t")
        if len(columns) < 12 or columns[0] != "5" or not columns[11].strip():
            continue
        try:
            confidence = float(columns[10])
        except ValueError:
            continue
        if confidence >= 0:
            values.append(confidence)
    return (sum(values) / len(values), len(values)) if values else (None, 0)


def measure(page) -> tuple[float | None, int]:
    binary = tesseract_binary()
    languages = usable_languages()
    if binary is None or not languages:
        return None, 0
    command = [binary, "stdin", "stdout", "-l", languages]
    folder = tessdata_dir()
    if folder:
        command += ["--tessdata-dir", folder]
    command.append("tsv")
    png = page.get_pixmap(dpi=settings.ocr_dpi, alpha=False).tobytes("png")
    done = subprocess.run(command, input=png, capture_output=True, timeout=settings.ocr_timeout)
    if done.returncode != 0:
        return None, 0
    return parse_tsv(done.stdout.decode("utf-8", "replace"))


@dataclass
class PageRead:
    pdf: bytes
    confidence: float | None = None
    words: int = 0

    @property
    def low(self) -> bool:
        return self.confidence is not None and self.words >= MIN_WORDS and self.confidence < CONFIDENCE


def read_tesseract(page) -> PageRead:
    data = recognize(page)
    confidence, words = measure(page)
    return PageRead(data, confidence, words)


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
    vision_pages: int = 0
    low_confidence_pages: int = 0

    @property
    def quality(self) -> float | None:
        if not self.ocr_pages:
            return None
        return self.known_words / self.total_words if self.total_words else 0.0


def prepare_pdf(source: str, destination: str, on_page=None, should_stop=None) -> Prepared:
    ready = ocr_ready()
    mode = engine_mode()
    use_vision = vision.available()
    with pymupdf.open(source) as src:
        result = Prepared(path=source, pages=len(src))
        replacements: dict[int, bytes] = {}
        waiting: list[tuple[int, PageRead | None]] = []
        finished = 0

        def finish() -> None:
            nonlocal finished
            finished += 1
            if on_page is not None:
                on_page(finished)

        def keep(index: int, data: bytes) -> None:
            with pymupdf.open("pdf", data) as recognised:
                known, total = _words_known(recognised[0].get_text("text"))
            replacements[index] = data
            result.ocr_pages += 1
            result.known_words += known
            result.total_words += total

        def use_tesseract(index: int, read: PageRead | None) -> None:
            try:
                if read is None:
                    if not ready:
                        result.skipped += 1
                        return
                    read = read_tesseract(src[index])
                keep(index, read.pdf)
                result.low_confidence_pages += int(read.low)
            except Exception as error:
                log.warning("OCR halaman %d dilewati: %s", index + 1, error)
                result.skipped += 1

        for index in range(result.pages):
            if should_stop is not None and should_stop():
                result.stopped = True
                return result
            if page_needs_ocr(src[index].get_text("text")):
                rescuable = use_vision and len(waiting) < settings.vision_max_pages
                if rescuable and (mode == "router" or not ready):
                    waiting.append((index, None))
                    continue
                read = None
                if ready:
                    try:
                        read = read_tesseract(src[index])
                    except Exception as error:
                        log.warning("OCR halaman %d dilewati: %s", index + 1, error)
                if read is not None and rescuable and read.low:
                    waiting.append((index, read))
                    continue
                if read is not None:
                    use_tesseract(index, read)
                else:
                    result.skipped += 1
            finish()
        if waiting:
            try:
                images = [vision.render(src[index]) for index, _ in waiting]
            except Exception as error:
                log.warning("Halaman tidak bisa dijadikan gambar untuk dibaca ulang: %s", error)
                images = None
            for group in vision.groups([len(i) for i in images]) if images is not None else [list(range(len(waiting)))]:
                if should_stop is not None and should_stop():
                    result.stopped = True
                    return result
                texts = vision.transcribe_group([images[k] for k in group]) if images is not None else [None] * len(group)
                for k, text in zip(group, texts):
                    index, fallback = waiting[k]
                    if text:
                        try:
                            page = src[index]
                            keep(index, vision.text_page(page.rect.width, page.rect.height, text))
                            result.vision_pages += 1
                            finish()
                            continue
                        except Exception as error:
                            log.warning("Hasil pembacaan gambar halaman %d tidak bisa dipakai: %s", index + 1, error)
                    use_tesseract(index, fallback)
                    finish()
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
