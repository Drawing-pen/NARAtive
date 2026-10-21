import logging
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Character, CharacterRelation, Document

log = logging.getLogger("narative.characters")

MIN_SCORE = 0.85
MIN_MENTIONS = 3
MAX_CHARACTERS = 25
MIN_PAIR_WEIGHT = 2
CONFLICT_SHARE = 0.4
CONFLICT_EMOTION_PROB = 0.6
CONFLICT_VIOLENCE = 0.5
CONFLICT_PROFANITY = 0.5
MAX_NAME_TOKENS = 4
MAX_TEXT_CHARS = 1500
BATCH_SIZE = 16
LEAD_RANK = 2
LEAD_RATIO = 0.5
SUPPORT_RATIO = 0.05
COMMON_WORD_GUARD = 15

PERSON_GROUPS = {"PER", "PERSON", "PERS"}

TITLES = {
    "mr", "mrs", "ms", "miss", "mister", "madam", "madame", "dr", "prof", "sir", "lord", "lady", "earl", "duke",
    "duchess", "count", "countess", "baron", "baroness", "king", "queen", "prince", "princess", "captain",
    "pak", "bapak", "bu", "ibu", "kak", "mas", "mbak", "om", "tante", "nona", "tuan", "nyonya", "raja", "ratu",
    "pangeran", "putri", "kapten", "bang", "abang", "dik", "adik",
}

PARTICLES = {"de", "da", "del", "della", "di", "van", "von", "der", "den", "bin", "binti", "bint", "al", "el", "la", "le", "du", "dos", "das", "ibn"}

INTERJECTIONS = {"jeez", "crap", "jesus", "christ", "gosh", "damn", "goddamn", "dammit", "omg"}

EMOTION_ID = {"sad": "sedih", "angry": "marah", "fear": "takut", "happy": "senang"}


class CharacterError(Exception):
    pass


@dataclass
class CharInfo:
    key: tuple
    name: str
    count: int
    role: str = ""
    biodata: str = ""
    chapters: set = field(default_factory=set)
    emotions: Counter = field(default_factory=Counter)
    aliases: list = field(default_factory=list)


@dataclass
class Result:
    characters: list
    relations: list


_ner = None
_lock = threading.Lock()


def _load_ner():
    global _ner
    if _ner is None:
        try:
            import torch
            from transformers import pipeline

            device = 0 if torch.cuda.is_available() else -1
            _ner = pipeline(
                "token-classification", model=settings.ner_model, aggregation_strategy="simple", device=device
            )
        except Exception as e:
            raise CharacterError(f"Model NER '{settings.ner_model}' tidak dapat dimuat: {e}")
    return _ner


def detect(texts: list[str]) -> list[list[dict]]:
    if not texts:
        return []
    ner = _load_ner()
    return ner([t[:MAX_TEXT_CHARS] for t in texts], batch_size=BATCH_SIZE)


def clean_surface(raw: str) -> str | None:
    chunks = re.split(r"[\"“”()\[\]{}…,;:!?]+", raw)
    s = max(chunks, key=lambda c: sum(ch.isalpha() for ch in c)).strip()
    s = re.sub(r"^I\.?\s+", "", s)
    s = re.sub(r"[’']s$", "", s)
    s = s.strip(" \t\r\n\"'“”‘’.,;:!?()[]{}-—–_")
    s = re.sub(r"\s+", " ", s)
    if len(s) < 2 or any(ch.isdigit() for ch in s) or not s[0].isalpha() or not s[0].isupper():
        return None
    tokens = s.split(" ")
    if len(tokens) > MAX_NAME_TOKENS:
        return None
    if any(t[0].islower() and t not in PARTICLES for t in tokens[1:]):
        return None
    return s


def canonical(surface: str) -> tuple | None:
    tokens = [t.rstrip(".").casefold() for t in surface.split(" ")]
    while tokens and tokens[0] in TITLES:
        tokens.pop(0)
    tokens = [t for t in tokens if t]
    return tuple(tokens) if tokens else None


def surfaces_from(entities: list[dict], text: str) -> list[str]:
    out = []
    for e in entities:
        group = str(e.get("entity_group") or e.get("entity") or "").upper().replace("B-", "").replace("I-", "")
        if group not in PERSON_GROUPS or float(e.get("score", 0.0)) < MIN_SCORE:
            continue
        surface = clean_surface(text[int(e["start"]):int(e["end"])])
        if surface:
            out.append(surface)
    return out


def unify(counts: Counter) -> dict:
    keys = sorted(counts, key=lambda k: (-len(k), -counts[k]))
    root: dict = {}
    for k in keys:
        longer = {root[c] for c in keys if c in root and len(c) > len(k) and set(k) <= set(c)}
        if len(longer) == 1:
            root[k] = next(iter(longer))
        elif len(longer) > 1:
            ranked = sorted(longer, key=lambda c: -counts[c])
            root[k] = ranked[0] if counts[ranked[0]] >= 2 * counts[ranked[1]] else k
        else:
            root[k] = k
    return root


def _is_conflict(p: dict) -> bool:
    return (
        (p.get("emotion") == "angry" and (p.get("emotion_score") or 0.0) >= CONFLICT_EMOTION_PROB)
        or (p.get("violence") or 0.0) >= CONFLICT_VIOLENCE
        or (p.get("profanity") or 0.0) >= CONFLICT_PROFANITY
    )


def _role(rank: int, ratio: float) -> str:
    if rank < LEAD_RANK or ratio >= LEAD_RATIO:
        return "Tokoh utama"
    if ratio >= SUPPORT_RATIO:
        return "Tokoh pendukung"
    return "Tokoh figuran"


def build(paragraphs: list[dict], mentions: list[list[str]]) -> Result:
    key_counts: Counter = Counter()
    surface_counts: dict = defaultdict(Counter)
    para_keys: list[list[tuple]] = []
    for names in mentions:
        keys = []
        for surface in names:
            k = canonical(surface)
            if k is None:
                continue
            key_counts[k] += 1
            surface_counts[k][surface] += 1
            keys.append(k)
        para_keys.append(keys)

    root = unify(key_counts)
    totals: Counter = Counter()
    for k, n in key_counts.items():
        totals[root[k]] += n
    for k in [k for k in totals if any(t in INTERJECTIONS for t in k)]:
        del totals[k]

    common = {k for k in totals if len(k) == 1 and totals[k] < COMMON_WORD_GUARD}
    if common:
        lowered: Counter = Counter()
        for p in paragraphs:
            for w in re.findall(r"[^\W\d_]+", p.get("text", "")):
                if w.islower() and (w,) in common:
                    lowered[(w,)] += 1
        for k in common:
            if lowered[k] >= MIN_MENTIONS and lowered[k] >= totals[k]:
                del totals[k]

    chosen = [k for k, n in totals.most_common(MAX_CHARACTERS) if n >= MIN_MENTIONS]
    chosen_set = set(chosen)
    top = totals[chosen[0]] if chosen else 1

    infos = {}
    for rank, k in enumerate(chosen):
        forms = surface_counts[k]
        name = (forms.most_common(1)[0][0] if forms else " ".join(k).title())[:100]
        others = Counter()
        for member, r in root.items():
            if r == k and member != k:
                others.update(surface_counts[member])
        infos[k] = CharInfo(
            key=k, name=name, count=totals[k], role=_role(rank, totals[k] / top),
            aliases=[s for s, _ in others.most_common(3) if s != name],
        )

    para_chars: list[set] = []
    for p, keys in zip(paragraphs, para_keys):
        present = {root[k] for k in keys if root[k] in chosen_set}
        para_chars.append(present)
        for k in present:
            infos[k].chapters.add(p["chapter_no"])
            if p.get("emotion"):
                infos[k].emotions[p["emotion"]] += 1

    by_chapter: dict = defaultdict(list)
    for i, p in enumerate(paragraphs):
        by_chapter[p["chapter_no"]].append(i)
    conflict = [_is_conflict(p) for p in paragraphs]

    weights: Counter = Counter()
    hits: Counter = Counter()
    for chapter_no, idx in by_chapter.items():
        for pos, i in enumerate(idx):
            window = [i] + ([idx[pos + 1]] if pos + 1 < len(idx) else [])
            union = set().union(*(para_chars[j] for j in window))
            flagged = any(conflict[j] for j in window)
            for a, b in combinations(sorted(union), 2):
                if a in para_chars[i] or b in para_chars[i]:
                    weights[(chapter_no, a, b)] += 1
                    if flagged:
                        hits[(chapter_no, a, b)] += 1

    relations = []
    partner_weight: dict = defaultdict(Counter)
    for (chapter_no, a, b), w in sorted(weights.items()):
        if w < MIN_PAIR_WEIGHT:
            continue
        kind = "konflik" if hits[(chapter_no, a, b)] / w >= CONFLICT_SHARE else "akrab"
        relations.append((chapter_no, a, b, kind, w))
        partner_weight[a][b] += w
        partner_weight[b][a] += w

    total_chapters = len(by_chapter)
    for k, info in infos.items():
        first = min(info.chapters) if info.chapters else None
        parts = [f"{info.name} disebut {info.count} kali"]
        if first is not None:
            parts[0] += f", muncul di {len(info.chapters)} dari {total_chapters} bab (pertama kali pada bab {first})."
        else:
            parts[0] += "."
        if info.emotions:
            parts.append(f"Suasana yang paling sering menyertainya: {EMOTION_ID.get(info.emotions.most_common(1)[0][0], 'netral')}.")
        top = [infos[o].name for o, _ in partner_weight[k].most_common(2)]
        if top:
            parts.append("Paling sering bersama " + " dan ".join(top) + ".")
        if info.aliases:
            parts.append("Disebut juga: " + ", ".join(info.aliases) + ".")
        info.biodata = " ".join(parts)

    return Result(characters=[infos[k] for k in chosen], relations=relations)


def extract(db: Session, doc: Document, ner=None) -> tuple[int, int]:
    paragraphs = list(doc.paragraphs)
    texts = [p.text for p in paragraphs]
    found = (ner or detect)(texts)
    mentions = [surfaces_from(ents, t[:MAX_TEXT_CHARS]) for ents, t in zip(found, texts)]
    meta = [
        {
            "chapter_no": p.chapter_no, "emotion": p.emotion, "emotion_score": p.emotion_score,
            "violence": p.violence, "profanity": p.profanity, "text": p.text,
        }
        for p in paragraphs
    ]
    result = build(meta, mentions)

    old_ids = list(db.scalars(select(Character.id).where(Character.document_id == doc.id)))
    if old_ids:
        db.execute(delete(CharacterRelation).where(
            or_(CharacterRelation.character_a_id.in_(old_ids), CharacterRelation.character_b_id.in_(old_ids))
        ))
        db.execute(delete(Character).where(Character.id.in_(old_ids)))
    db.flush()

    rows = {}
    for info in result.characters:
        row = Character(document_id=doc.id, name=info.name, role=info.role, biodata=info.biodata, mention_count=info.count)
        db.add(row)
        rows[info.key] = row
    db.flush()

    chapter_ids = {c.number: c.id for c in doc.chapters}
    made = 0
    for chapter_no, a, b, kind, weight in result.relations:
        if chapter_no not in chapter_ids:
            continue
        low, high = sorted((rows[a].id, rows[b].id))
        db.add(CharacterRelation(
            character_a_id=low, character_b_id=high, chapter_id=chapter_ids[chapter_no], relation_type=kind, weight=weight
        ))
        made += 1
    db.commit()
    db.expire_all()
    return len(result.characters), made


def run(doc_id: int) -> None:
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        if doc is None:
            return
        doc.characters_status = "running"
        db.commit()
        try:
            with _lock:
                extract(db, doc)
            status = "done"
        except Exception:
            log.exception("Deteksi tokoh dokumen %s gagal", doc_id)
            db.rollback()
            status = "failed"
        doc = db.get(Document, doc_id)
        if doc is not None:
            doc.characters_status = status
            db.commit()


def start(doc_id: int) -> None:
    threading.Thread(target=run, args=(doc_id,), name=f"characters-{doc_id}", daemon=True).start()


def reset_stale() -> None:
    with SessionLocal() as db:
        for doc in db.query(Document).filter(Document.characters_status == "running"):
            doc.characters_status = "failed"
        db.commit()