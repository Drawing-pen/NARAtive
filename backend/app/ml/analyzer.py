"""Aturan rating konten: ambang per paragraf, kategori usia, dan ringkasan hasil analisis (R24: skor paragraf berasal dari LLM)."""


THRESHOLDS = {"profanity": 0.5, "sexual": 0.5, "violence": 0.8}


ADULT_DIMENSIONS = ("sexual", "violence")   


DIMENSION_LABEL = {"violence": "Kekerasan", "sexual": "Konten seksual", "profanity": "Bahasa kasar"}
RATING_RULES = (
    ("Explicit", (("sexual", 3, 3),)),
    ("Mature", (("violence", 15, 3), ("sexual", 1, 2))),
    ("Teen", (("violence", 3, 2), ("sexual", 0.5, 2))),
)


def rate(pct: dict, counts: dict | None = None) -> str:
    c = counts or {"sexual": 99, "violence": 99}
    for level, conditions in RATING_RULES:
        if any(pct[d] >= share and c[d] >= paragraphs for d, share, paragraphs in conditions):
            return level
    return "General"


def _decimal(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _limit(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def explain(pct: dict, hits: dict) -> list[str]:
    level = rate(pct, hits)
    if level == "General":
        teen = dict(RATING_RULES)["Teen"]
        limits = ", atau ".join(f"{DIMENSION_LABEL[d].lower()} minimal {_limit(share)}% dan {paragraphs} paragraf" for d, share, paragraphs in teen)
        actual = ", ".join(f"{DIMENSION_LABEL[d].lower()} {_decimal(pct[d])}% ({hits[d]} paragraf)" for d, _, _ in teen)
        return [f"Tidak ada dimensi yang mencapai batas Teen ({limits}): {actual}."]
    return [
        f"{DIMENSION_LABEL[d]} {_decimal(pct[d])}% paragraf ({hits[d]} paragraf) mencapai batas {level}: minimal {_limit(share)}% dan {paragraphs} paragraf."
        for d, share, paragraphs in dict(RATING_RULES)[level]
        if pct[d] >= share and hits[d] >= paragraphs
    ]


AGE_RANGES = {"General": "Semua umur", "Teen": "13+", "Mature": "17+", "Explicit": "21+"}


def summarize(results: list[dict], ai: float | None = None) -> dict:
    n = max(len(results), 1)
    pct = {d: round(100 * sum(1 for r in results if r[d] >= t) / n, 1)
           for d, t in THRESHOLDS.items()}
    hit = {d: sum(1 for r in results if r[d] >= t) for d, t in THRESHOLDS.items()}
    adult = round(100 * sum(1 for r in results if any(r[d] >= THRESHOLDS[d] for d in ADULT_DIMENSIONS)) / n, 1)
    heaviness = ai if ai is not None else pct["violence"]
    return {"pct": pct, "adult": adult, "heaviness": heaviness, "rating": rate(pct, hit)}
