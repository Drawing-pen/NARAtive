import logging
import re
from dataclasses import dataclass

import pymupdf4llm

from app.extraction import markdown_utils as mdu
from app.extraction.epub_markdown import _pack_blocks
from app.extraction.pdf_utils import HEADING, PAGE_NUMBER, PAGES_PER_SECTION, STANDALONE, _norm_edge, _open, _plain, clean_text

log = logging.getLogger("uvicorn.error")

MIN_CHARS = 20
SENTENCE_END = ".!?\"”'’:;)"
QUOTES = "\"“”'‘’"
_HAS_LETTER = re.compile(r"[^\W\d_]")
_SPLIT_WORD = re.compile(r"[^\W\d_]-$")
_LIST_PREFIX = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s")


@dataclass
class Item:
    page: int
    block: mdu.Block
    boundary: bool = False
    title: str | None = None
    drop: bool = False


def _page_blocks(markdown: str) -> list[mdu.Block]:
    out = []
    for block in mdu.parse_blocks(markdown):
        cleaned = mdu.clean_markdown(block.markdown)
        text = mdu.plain_text(cleaned)
        if text and _HAS_LETTER.search(text):
            out.append(mdu.Block(block.kind, cleaned, text, block.level))
    return out


def _edges(blocks: list[mdu.Block]) -> list[mdu.Block]:
    return blocks[:2] + blocks[-2:]


def _running_edges(pages: list[list[mdu.Block]]) -> set[str]:
    if len(pages) < 8:
        return set()
    counts: dict[str, int] = {}
    for blocks in pages:
        seen = {_norm_edge(b.text) for b in _edges(blocks) if len(b.text) <= 100 and not HEADING.match(b.text)}
        for key in seen:
            counts[key] = counts.get(key, 0) + 1
    need = max(4, int(0.3 * len(pages)))
    return {key for key, count in counts.items() if count >= need}


def _strip_edges(blocks: list[mdu.Block], drop: set[str]) -> list[mdu.Block]:
    edges = {id(b) for b in _edges(blocks)}
    return [
        b for b in blocks
        if not (id(b) in edges and b.kind != "h" and (PAGE_NUMBER.match(b.text) or _norm_edge(b.text) in drop))
    ]


def _continues(previous: mdu.Block, following: mdu.Block) -> bool:
    return previous.kind == "p" and following.kind == "p" and previous.text[-1:] not in SENTENCE_END and following.text[:1].islower()


def _glue(first: str, second: str) -> str:
    if _SPLIT_WORD.search(first) and second[:1].islower():
        return first[:-1] + second
    return f"{first} {second}"


def _join_pages(pages: list[list[mdu.Block]]) -> list[Item]:
    items: list[Item] = []
    for number, blocks in enumerate(pages):
        for position, block in enumerate(blocks):
            if position == 0 and items and _continues(items[-1].block, block):
                last = items[-1]
                joined = mdu.Block("p", _glue(last.block.markdown, block.markdown), _glue(last.block.text, block.text))
                items[-1] = Item(last.page, joined)
                continue
            items.append(Item(number, block))
    return items


def _body(block: mdu.Block) -> str:
    return block.markdown if block.kind == "p" else _LIST_PREFIX.sub("", block.markdown, count=1)


def _rejoin_broken(items: list[Item]) -> list[Item]:
    out: list[Item] = []
    for item in items:
        if out and _continues(out[-1].block, item.block):
            last = out[-1]
            block = mdu.Block("p", _glue(last.block.markdown, item.block.markdown), _glue(last.block.text, item.block.text))
            out[-1] = Item(last.page, block)
            continue
        out.append(item)
    return out


def _unbullet_dialogue(items: list[Item]) -> None:
    index = 0
    while index < len(items):
        if items[index].block.kind != "li":
            index += 1
            continue
        end = index
        while end < len(items) and items[end].block.kind == "li":
            end += 1
        run = items[index:end]
        numbered = any(_NUMBERED.match(item.block.markdown) for item in run)
        if not numbered and any(item.block.text[:1] in QUOTES for item in run):
            for item in run:
                item.block = mdu.Block("p", _body(item.block), item.block.text)
        index = end


def _outline(toc: list, page_count: int) -> list[tuple[str, int]]:
    entries = [(level, title.strip(), page - 1) for level, title, page in toc if title.strip() and 1 <= page <= page_count]
    by_level: dict[int, list] = {}
    for entry in entries:
        by_level.setdefault(entry[0], []).append(entry)
    limit = max(40, page_count // 6)
    levels = [level for level, found in sorted(by_level.items()) if 2 <= len(found) <= limit]
    return [(title, page) for _, title, page in by_level[levels[-1]]] if levels else []


def _insert(items: list[Item], inserts: dict[int, list[Item]]) -> list[Item]:
    out: list[Item] = []
    for index, item in enumerate(items):
        out.extend(inserts.get(index, []))
        out.append(item)
    out.extend(inserts.get(len(items), []))
    return out


def _apply_outline(items: list[Item], outline: list[tuple[str, int]]) -> list[Item]:
    by_page: dict[int, list[int]] = {}
    for index, item in enumerate(items):
        by_page.setdefault(item.page, []).append(index)
    inserts: dict[int, list[Item]] = {}
    for title, page in outline:
        target = _plain(title)
        candidates = by_page.get(page, [])[:15]
        hit = next(
            (i for i in candidates if _plain(items[i].block.text) == target or (len(target) >= 4 and _plain(items[i].block.text).startswith(target))),
            None,
        )
        if hit is not None:
            items[hit].boundary = True
            continue
        at = candidates[0] if candidates else next((i for i, it in enumerate(items) if it.page >= page), len(items))
        inserts.setdefault(at, []).append(Item(page, mdu.Block("h", f"# {title}", title, 1), boundary=True, title=title))
    return _insert(items, inserts)


def _headingish(block: mdu.Block) -> bool:
    return len(block.text) <= 80 and bool(HEADING.match(block.text) or STANDALONE.match(block.text))


def _mark_regex_headings(items: list[Item]) -> None:
    index = 0
    while index < len(items):
        if items[index].boundary or not _headingish(items[index].block):
            index += 1
            continue
        run = 0
        page = items[index].page
        while index + run < len(items) and items[index + run].page == page and not items[index + run].boundary and _headingish(items[index + run].block):
            run += 1
        for item in items[index:index + run]:
            if run >= 3:
                item.drop = True
            else:
                item.boundary = True
        index += run


def _mark_markdown_headings(items: list[Item], page_count: int) -> None:
    candidates = [i for i in items if not i.drop and not i.boundary and i.block.kind == "h" and i.block.level <= 2 and len(i.block.text) <= 120]
    if 2 <= len(candidates) <= max(3, page_count):
        for item in candidates:
            item.boundary = True


def _add_sections(items: list[Item], page_count: int) -> list[Item]:
    inserts: dict[int, list[Item]] = {}
    for start in range(0, page_count, PAGES_PER_SECTION):
        label = f"Halaman {start + 1}–{min(start + PAGES_PER_SECTION, page_count)}"
        at = next((i for i, it in enumerate(items) if it.page >= start), None)
        if at is not None:
            inserts.setdefault(at, []).append(Item(start, mdu.Block("h", f"# {label}", label, 1), boundary=True, title=label))
    return _insert(items, inserts)


def _boundaries(items: list[Item]) -> int:
    return sum(1 for i in items if i.boundary and not i.drop)


def _subtitle(items: list[Item], index: int, title: str) -> bool:
    match = HEADING.match(title)
    if not match or match.group(3).strip() or index + 1 >= len(items):
        return False
    following = items[index + 1]
    block = following.block
    return (
        not following.boundary and not following.drop and block.kind in ("h", "p")
        and len(block.text) <= 60 and len(block.text.split()) <= 6 and not block.text.endswith((".", ",", ";"))
        and not HEADING.match(block.text) and not STANDALONE.match(block.text)
    )


def _chapters(items: list[Item]) -> tuple[list[str], list[tuple[int, mdu.Block]]]:
    titles: list[str] = []
    out: list[tuple[int, mdu.Block]] = []
    content_since_title = True
    index = 0
    while index < len(items):
        item = items[index]
        index += 1
        if item.drop:
            continue
        if not item.boundary:
            out.append((len(titles), item.block))
            content_since_title = True
            continue
        title = item.title or item.block.text
        if _subtitle(items, index - 1, title):
            title = f"{title} — {items[index].block.text}"
            index += 1
        title = clean_text(title) or f"Bab {len(titles) + 1}"
        if titles and titles[-1] == title and not content_since_title:
            continue
        titles.append(title)
        content_since_title = False
    if not titles:
        return ["Isi naskah"], [(1, b) for _, b in out]
    if any(n == 0 for n, _ in out):
        return ["Pembuka"] + titles, [(n + 1, b) for n, b in out]
    return titles, out


def _finish(blocks: list[tuple[int, mdu.Block]]) -> list[tuple[int, mdu.Block]]:
    final = []
    run: list[mdu.Block] = []
    run_chapter = 0

    def flush():
        packed = _pack_blocks([("p", b.markdown, b.text, 0) for b in run])
        final.extend((run_chapter, block) for block in packed if len(block.text) >= MIN_CHARS)
        run.clear()

    for number, block in blocks:
        if block.kind == "p":
            if run and number != run_chapter:
                flush()
            run_chapter = number
            run.append(block)
            continue
        flush()
        final.append((number, block))
    flush()
    return final


def assemble(pages: list[str], toc: list, page_count: int) -> tuple[list[str], list[tuple[int, mdu.Block]]]:
    per_page = [_page_blocks(markdown) for markdown in pages]
    drop = _running_edges(per_page)
    items = _join_pages([_strip_edges(blocks, drop) for blocks in per_page])
    _unbullet_dialogue(items)
    items = _rejoin_broken(items)

    outline = _outline(toc, page_count)
    if outline:
        items = _apply_outline(items, outline)
    _mark_regex_headings(items)
    if _boundaries(items) < 2:
        _mark_markdown_headings(items, page_count)
    if _boundaries(items) < 2 and page_count > PAGES_PER_SECTION + 10:
        items = _add_sections(items, page_count)

    titles, blocks = _chapters(items)
    return titles, _finish(blocks)


def read_pdf_markdown(path: str) -> tuple[int, list[str], list[tuple[int, mdu.Block]]]:
    with _open(path) as doc:
        page_count = len(doc)
        chunks = pymupdf4llm.to_markdown(doc, page_chunks=True, show_progress=False, use_ocr=False)
        pages = [chunk["text"] for chunk in chunks]
        toc = doc.get_toc()
    titles, blocks = assemble(pages, toc, page_count)
    log.info("PDF (markdown): %d bab, %d blok, %d halaman", len(titles), len(blocks), page_count)
    return page_count, titles, blocks
