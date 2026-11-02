import re
from dataclasses import dataclass

from app.extraction.pdf_utils import MAX_PARAGRAPH_CHARS, clean_text

_ESCAPABLE = "\\`*_{}[]()#+-.!|><"
_ESCAPE = re.compile(r"\\([" + re.escape(_ESCAPABLE) + r"])")
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_TAG = re.compile(r"<[^>\n]{1,200}>")
_CODE = re.compile(r"`([^`]*)`")
_BOLD_ITALIC = re.compile(r"\*\*\*(.+?)\*\*\*")
_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_ITALIC_STAR = re.compile(r"(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])")
_ITALIC_UNDERSCORE = re.compile(r"(?<!\w)_(?![\s_])(.+?)(?<![\s_])_(?!\w)")
_LINE_PREFIX = re.compile(r"^\s*(?:#{1,6}\s+|>\s?|[-*+]\s+|\d+[.)]\s+)")
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_LIST_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_QUOTE = re.compile(r"^\s*>\s?(.*)$")
_RULE = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
_IMAGE_LINE = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_RULE = re.compile(r"^\s*\|?[\s:|-]*-[\s:|-]*\|?\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")
_HAS_LETTER = re.compile(r"[^\W\d_]")
_BOUNDARY = re.compile(r"[.!?][\"'”’)*_]*\s+")
_MARKER = re.compile(r"\*\*|__|(?<![\w*_])[*_](?=[^\s*_])|(?<=[^\s*_])[*_](?![\w*_])")


@dataclass(frozen=True)
class Block:
    kind: str
    markdown: str | None
    text: str
    level: int = 0


def _inline_plain(text: str) -> str:
    keep = {chr(0xE000 + i): c for i, c in enumerate(_ESCAPABLE)}
    back = {c: k for k, c in keep.items()}
    text = _ESCAPE.sub(lambda m: back[m.group(1)], text)
    text = _IMAGE.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = _TAG.sub("", text)
    text = _CODE.sub(r"\1", text)
    text = _BOLD_ITALIC.sub(r"\1", text)
    text = _BOLD.sub(r"\2", text)
    text = _ITALIC_STAR.sub(r"\1", text)
    text = _ITALIC_UNDERSCORE.sub(r"\1", text)
    text = "".join(keep.get(c, c) for c in text)
    return re.sub(r"\s+", " ", text).strip()


def plain_text(markdown: str) -> str:
    paragraphs = []
    for part in re.split(r"\n\s*\n", markdown.strip()):
        lines = [_LINE_PREFIX.sub("", line, count=1) for line in part.split("\n")]
        text = _inline_plain(" ".join(line.strip() for line in lines if line.strip()))
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _sentences(markdown: str) -> list[str]:
    pieces, start = [], 0
    for match in _BOUNDARY.finditer(markdown):
        pieces.append(markdown[start:match.end()].strip())
        start = match.end()
    tail = markdown[start:].strip()
    if tail:
        pieces.append(tail)
    return pieces


def _scan(chunk: str, opened: list[str]) -> list[str]:
    state = list(opened)
    for match in _MARKER.finditer(chunk):
        token = match.group(0)
        if token in state:
            state.remove(token)
        else:
            state.append(token)
    return state


def _rebalance(chunks: list[str]) -> list[str]:
    out, opened = [], []
    for chunk in chunks:
        prefix = "".join(opened)
        opened = _scan(chunk, opened)
        out.append(prefix + chunk + "".join(reversed(opened)))
    return out


def split_block(markdown: str, limit: int = MAX_PARAGRAPH_CHARS) -> list[str]:
    if len(plain_text(markdown)) <= limit:
        return [markdown]
    chunks, current = [], ""
    for sentence in _sentences(markdown):
        if current and len(plain_text(f"{current} {sentence}")) > limit:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return _rebalance(chunks)


_TIDY = re.compile(r"\*\*|(?<!\w)_|_(?!\w)")


def tidy_marks(markdown: str) -> str:
    result: list[str] = []
    openers: dict[str, int] = {}
    pending: int | None = None
    last = 0
    for match in _TIDY.finditer(markdown):
        token = match.group(0)
        chunk = markdown[last:match.start()]
        last = match.end()
        if pending is not None and chunk[:1].isspace():
            stripped = chunk.lstrip()
            result.insert(pending, chunk[:len(chunk) - len(stripped)])
            chunk = stripped
            openers = {t: i + 1 if i >= pending else i for t, i in openers.items()}
        pending = None
        if token in openers:
            body = chunk.rstrip()
            result.extend([body, token, chunk[len(body):]])
            del openers[token]
        else:
            result.extend([chunk, token])
            openers[token] = len(result) - 1
            pending = len(result) - 1
    tail = markdown[last:]
    if pending is not None and tail[:1].isspace():
        stripped = tail.lstrip()
        result.insert(pending, tail[:len(tail) - len(stripped)])
        openers = {t: i + 1 if i >= pending else i for t, i in openers.items()}
        tail = stripped
    result.append(tail)
    for index in openers.values():
        result[index] = ""
    joined = re.sub(r"\*\*\s*\*\*", " ", "".join(result))
    return re.sub(r"[ \t]{2,}", " ", joined).strip()


def clean_markdown(markdown: str) -> str:
    match = _LINE_PREFIX.match(markdown)
    prefix = match.group(0) if match else ""
    body = _LINK.sub(r"\1", _IMAGE.sub("", markdown[len(prefix):]))
    return prefix + tidy_marks(clean_text(body))


def _block(kind: str, markdown: str, level: int = 0) -> Block | None:
    markdown = markdown.strip()
    text = plain_text(markdown)
    if not text or not _HAS_LETTER.search(text):
        return None
    return Block(kind, markdown, text, level)


def _flatten_table(rows: list[str]) -> str:
    lines = []
    for row in rows:
        if _TABLE_RULE.match(row):
            continue
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        line = "  ".join(cell for cell in cells if cell)
        if line:
            lines.append(line)
    return "\n\n".join(lines)


def parse_blocks(markdown: str) -> list[Block]:
    blocks: list[Block] = []
    paragraph: list[str] = []
    quote: list[str] = []
    table: list[str] = []
    item: list[str] = []
    item_marker = "-"
    fenced = False

    def add(block: Block | None):
        if block:
            blocks.append(block)

    def flush():
        nonlocal item_marker
        if paragraph:
            add(_block("p", " ".join(s.strip() for s in paragraph)))
            paragraph.clear()
        if quote:
            add(_block("quote", "> " + " ".join(quote)))
            quote.clear()
        if table:
            add(_block("p", _flatten_table(table)))
            table.clear()
        if item:
            add(_block("li", f"{item_marker} " + " ".join(item)))
            item.clear()

    for raw in markdown.replace("\r\n", "\n").split("\n"):
        if _FENCE.match(raw):
            flush()
            fenced = not fenced
            continue
        line = raw.rstrip()
        if fenced:
            if line.strip():
                paragraph.append(line)
            else:
                flush()
            continue
        if not line.strip():
            flush()
            continue
        if _RULE.match(line) or _IMAGE_LINE.match(line):
            flush()
            continue
        heading = _HEADING.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            add(_block("h", f"{'#' * level} {heading.group(2)}", level))
            continue
        if _TABLE_ROW.match(line):
            if not table:
                flush()
            table.append(line)
            continue
        entry = _LIST_ITEM.match(line)
        if entry:
            flush()
            item_marker = entry.group(2) if entry.group(2)[0].isdigit() else "-"
            item.append(entry.group(3).strip())
            continue
        if item and line[:1].isspace():
            item.append(line.strip())
            continue
        quoted = _QUOTE.match(line)
        if quoted:
            if not quote:
                flush()
            quote.append(quoted.group(1).strip())
            continue
        if item or quote or table:
            flush()
        paragraph.append(line)
    flush()
    return blocks
