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
from app.services import character_ai, character_rules, images

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
MIN_CANDIDATE_MENTIONS = 2
AI_CANDIDATES = 12
SNIPPET_SEXUAL_MAX = 0.2
AI_SNIPPETS, AI_WIDTH = 3, 200

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
    profile: dict = field(default_factory=dict)


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


def _snippets(paragraphs: list[dict], locs: list[tuple], limit: int, width: int) -> list[str]:
    seen: dict = {}
    for i, surface in locs:
        if i not in seen and (paragraphs[i].get("sexual") or 0.0) < SNIPPET_SEXUAL_MAX:
            seen[i] = surface
    usable = sorted(seen.items())
    if not usable:
        return []
    step = len(usable) / limit if len(usable) > limit else 1
    out = []
    for j in range(min(limit, len(usable))):
        i, surface = usable[int(j * step)]
        text = paragraphs[i]["text"]
        start = max(0, max(text.find(surface), 0) - width // 2)
        out.append(("..." if start else "") + " ".join(text[start:start + width].split()))
    return out


def build(paragraphs: list[dict], mentions: list[list[str]], ai_fn=None) -> Result:
    key_counts: Counter = Counter()
    surface_counts: dict = defaultdict(Counter)
    locations: dict = defaultdict(list)
    para_keys: list[list[tuple]] = []
    for i, names in enumerate(mentions):
        keys = []
        for surface in names:
            k = canonical(surface)
            if k is None:
                continue
            key_counts[k] += 1
            surface_counts[k][surface] += 1
            locations[k].append((i, surface))
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

    def members(k):
        return [m for m, r in root.items() if r == k]

    def locs_of(k):
        return [loc for m in members(k) for loc in locations[m]]

    para_sets = [{root[k] for k in keys} for keys in para_keys]
    pool = [k for k, n in totals.items() if n >= MIN_CANDIDATE_MENTIONS]
    for a in sorted(pool, key=lambda k: totals[k]):
        if a not in totals:
            continue
        targets = [
            b for b in pool
            if b in totals and b != a and character_rules.prefix_alias(a, b) and not any(a in s and b in s for s in para_sets)
        ]
        if len(targets) == 1:
            for m in members(a):
                root[m] = targets[0]
            totals[targets[0]] += totals.pop(a)

    profiles: dict = {}
    if ai_fn:
        cands = [k for k, n in totals.most_common(AI_CANDIDATES) if n >= MIN_CANDIDATE_MENTIONS]
        items = []
        for idx, k in enumerate(cands):
            forms = Counter()
            for m in members(k):
                forms.update(surface_counts[m])
            items.append({
                "id": idx, "name": forms.most_common(1)[0][0] if forms else " ".join(k).title(),
                "snippets": _snippets(paragraphs, locs_of(k), AI_SNIPPETS, AI_WIDTH),
            })
        people = ai_fn(items) or []
        parent = list(range(len(cands)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for person in people:
            for other in person["ids"][1:]:
                parent[find(other)] = find(person["ids"][0])
        by_root: dict = {}
        for person in people:
            by_root.setdefault(find(person["ids"][0]), person)
        clusters: dict = defaultdict(list)
        for idx in range(len(cands)):
            clusters[find(idx)].append(cands[idx])
        for r, keys in clusters.items():
            primary = max(keys, key=lambda k: totals[k])
            for other in keys:
                if other == primary:
                    continue
                for m in members(other):
                    root[m] = primary
                totals[primary] += totals.pop(other)
            if r in by_root:
                profiles[primary] = by_root[r]

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
    para_votes = [character_rules.relation_votes(p["text"]) if para_chars[i] else Counter() for i, p in enumerate(paragraphs)]

    weights: Counter = Counter()
    hits: Counter = Counter()
    votes: dict = defaultdict(Counter)
    for chapter_no, idx in by_chapter.items():
        for pos, i in enumerate(idx):
            window = [i] + ([idx[pos + 1]] if pos + 1 < len(idx) else [])
            union = set().union(*(para_chars[j] for j in window))
            flagged = any(conflict[j] for j in window)
            for a, b in combinations(sorted(union), 2):
                if a in para_chars[i] or b in para_chars[i]:
                    weights[(chapter_no, a, b)] += 1
                    for j in window:
                        if a in para_chars[j] and b in para_chars[j]:
                            votes[(chapter_no, a, b)].update(para_votes[j])
                    if flagged:
                        hits[(chapter_no, a, b)] += 1

    overall: dict = defaultdict(Counter)
    overall_hits: Counter = Counter()
    overall_weight: Counter = Counter()
    for (chapter_no, a, b), w in weights.items():
        overall[(a, b)].update(votes[(chapter_no, a, b)])
        overall_hits[(a, b)] += hits[(chapter_no, a, b)]
        overall_weight[(a, b)] += w
    overall_kind = {
        pair: character_rules.pick_relation(v, overall_hits[pair] / overall_weight[pair] >= CONFLICT_SHARE)
        for pair, v in overall.items()
    }

    relations = []
    partner_weight: dict = defaultdict(Counter)
    for (chapter_no, a, b), w in sorted(weights.items()):
        if w < MIN_PAIR_WEIGHT:
            continue
        kind = (
            character_rules.pick_relation(votes[(chapter_no, a, b)], hits[(chapter_no, a, b)] / w >= CONFLICT_SHARE)
            or overall_kind[(a, b)]
            or "kenalan"
        )
        relations.append((chapter_no, a, b, kind, w))
        partner_weight[a][b] += w
        partner_weight[b][a] += w

    for k, info in infos.items():
        surfaces: Counter = Counter()
        for m in members(k):
            surfaces.update(surface_counts[m])
        info.profile = {
            **character_rules.facts(paragraphs, locs_of(k), surfaces),
            "personality": None, "background": None, "summary": "",
        }
        bits = [v.lower() for v in (info.profile["gender"], info.profile["age"], info.profile["occupation"]) if v]
        parts = [f"{info.name} adalah {info.role.lower()}" + (f" ({', '.join(bits)})" if bits else "") + "."]
        described = character_rules.describe(paragraphs, locs_of(k))
        if described:
            parts.append(f"Dalam teks digambarkan sebagai “{described}”.")
        info.biodata = " ".join(parts)

    for k, ai_p in profiles.items():
        info = infos.get(k)
        if info is None:
            continue
        for f in ("gender", "age", "occupation"):
            info.profile[f] = info.profile.get(f) or ai_p.get(f)
        for f in ("personality", "background"):
            info.profile[f] = ai_p.get(f)
        if ai_p.get("summary"):
            info.biodata = ai_p["summary"]

    return Result(characters=[infos[k] for k in chosen], relations=relations)


def extract(db: Session, doc: Document, ner=None, ai: bool = False) -> tuple[int, int, bool]:
    paragraphs = list(doc.paragraphs)
    texts = [p.text for p in paragraphs]
    found = (ner or detect)(texts)
    mentions = [surfaces_from(ents, t[:MAX_TEXT_CHARS]) for ents, t in zip(found, texts)]
    meta = [
        {
            "chapter_no": p.chapter_no, "emotion": p.emotion, "emotion_score": p.emotion_score,
            "violence": p.violence, "profanity": p.profanity, "sexual": p.sexual, "text": p.text,
        }
        for p in paragraphs
    ]
    ai_ok = True

    def ask(items):
        nonlocal ai_ok
        people = character_ai.safe(items)
        ai_ok = people is not None
        return people

    result = build(meta, mentions, ai_fn=ask if ai else None)

    old_ids = list(db.scalars(select(Character.id).where(Character.document_id == doc.id)))
    if old_ids:
        images.remove(*db.scalars(select(Character.photo_path).where(Character.id.in_(old_ids))))
        db.execute(delete(CharacterRelation).where(
            or_(CharacterRelation.character_a_id.in_(old_ids), CharacterRelation.character_b_id.in_(old_ids))
        ))
        db.execute(delete(Character).where(Character.id.in_(old_ids)))
    db.flush()

    rows = {}
    for info in result.characters:
        pf = info.profile
        row = Character(
            document_id=doc.id, name=info.name, role=info.role, biodata=info.biodata, mention_count=info.count,
            aliases=", ".join(info.aliases) or None, gender=pf.get("gender"), age=pf.get("age"),
            occupation=pf.get("occupation"), personality=pf.get("personality"), background=pf.get("background"),
        )
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
    return len(result.characters), made, ai_ok


def run(doc_id: int, ai: bool = False) -> None:
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        if doc is None:
            return
        doc.characters_status = "running"
        db.commit()
        try:
            with _lock:
                _, _, ai_ok = extract(db, doc, ai=ai)
            status = "done" if ai_ok else "partial"
        except Exception:
            log.exception("Deteksi tokoh dokumen %s gagal", doc_id)
            db.rollback()
            status = "failed"
        doc = db.get(Document, doc_id)
        if doc is not None:
            doc.characters_status = status
            db.commit()


def start(doc_id: int, ai: bool = False) -> None:
    threading.Thread(target=run, args=(doc_id, ai), name=f"characters-{doc_id}", daemon=True).start()


def reset_stale() -> None:
    with SessionLocal() as db:
        for doc in db.query(Document).filter(Document.characters_status == "running"):
            doc.characters_status = "failed"
        db.commit()