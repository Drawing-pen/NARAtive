import logging
from dataclasses import dataclass

from app.core.config import settings
from app.extraction import markdown_utils as mdu
from app.extraction.epub_markdown import read_epub_markdown
from app.extraction.epub_utils import EpubError, read_epub
from app.extraction.pdf_markdown import read_pdf_markdown
from app.extraction.pdf_utils import read_pdf

log = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class ParsedDocument:
    page_count: int
    titles: list[str]
    blocks: list[tuple[int, mdu.Block]]
    parser: str


def parse_legacy(path: str, ext: str) -> ParsedDocument:
    page_count, titles, paragraphs = read_epub(path) if ext == ".epub" else read_pdf(path)
    return ParsedDocument(page_count, titles, [(n, mdu.Block("p", None, text)) for n, text in paragraphs], "legacy")


def parse_markdown(path: str, ext: str) -> ParsedDocument:
    page_count, titles, blocks = read_epub_markdown(path) if ext == ".epub" else read_pdf_markdown(path)
    return ParsedDocument(page_count, titles, blocks, "markdown")


def read_document(path: str, ext: str) -> ParsedDocument:
    mode = settings.document_parser
    if mode == "auto":
        mode = "markdown" if ext == ".epub" else "legacy"
    if mode != "markdown":
        return parse_legacy(path, ext)
    try:
        parsed = parse_markdown(path, ext)
        if parsed.blocks:
            return parsed
        log.warning("Parser markdown tidak menemukan teks, memakai parser lama.")
    except EpubError:
        raise
    except Exception as error:
        log.warning("Parser markdown gagal (%s), memakai parser lama.", error)
    return parse_legacy(path, ext)
