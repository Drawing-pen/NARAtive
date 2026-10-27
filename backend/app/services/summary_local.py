import re

UNAVAILABLE = "Rangkuman bab ini tidak dapat dibuat."
ALL_FILTERED = "Bab ini sebagian besar berisi adegan yang dilewati dalam rangkuman (kekerasan, bahasa kasar, atau konten dewasa)."
ALL_FILTERED_BOOK = "Buku ini sebagian besar berisi adegan yang dilewati dalam rangkuman (kekerasan, bahasa kasar, atau konten dewasa)."

MAX_SENTENCES = 4
MAX_SENTENCE_CHARS = 220
MAX_OVERALL_CHAPTERS = 6

_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _sentences(texts: list[str]) -> list[str]:
    out = []
    for text in texts:
        for part in _SPLIT.split(text.strip()):
            part = " ".join(part.split())
            if part:
                out.append(part)
    return out


def _clip(sentence: str) -> str:
    if len(sentence) <= MAX_SENTENCE_CHARS:
        return sentence
    return sentence[: MAX_SENTENCE_CHARS - 1].rstrip() + "…"


def chapter_summary(texts: list[str]) -> str:
    sentences = _sentences(texts)
    if not sentences:
        return ALL_FILTERED
    if len(sentences) > MAX_SENTENCES:
        picks = {0, 1, len(sentences) // 2, len(sentences) - 1}
    else:
        picks = set(range(len(sentences)))
    return " ".join(_clip(sentences[i]) for i in sorted(picks))


def overall_summary(chapter_summaries: list[str]) -> str:
    firsts = []
    for summary in chapter_summaries:
        if not summary or summary in (ALL_FILTERED, UNAVAILABLE):
            continue
        sentences = _sentences([summary])
        if sentences:
            firsts.append(_clip(sentences[0]))
    if not firsts:
        return ALL_FILTERED_BOOK
    if len(firsts) > MAX_OVERALL_CHAPTERS:
        last = len(firsts) - 1
        firsts = [firsts[round(i * last / (MAX_OVERALL_CHAPTERS - 1))] for i in range(MAX_OVERALL_CHAPTERS)]
    return " ".join(firsts)
