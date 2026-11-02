import logging
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import Character, CharacterRelation, Document
from app.services import character_ai, images

log = logging.getLogger("narative.characters")

MIN_MENTIONS = 3
MAX_CHARACTERS = 25
MAX_MERGE_ENTRIES = 60
MAX_ALIASES_SHOWN = 3
MAX_ROLES_SENT = 2
MIN_PAIR_WEIGHT = 2
MIN_EVIDENCE_CHARS = 8
QUOTE_SPAN = 500
RELATION_PRIORITY = ("pasangan", "keluarga", "sahabat", "musuh", "teman", "kenalan")

_QUOTED = re.compile(rf"[“”\"«][^“”\"«»]{{0,{QUOTE_SPAN}}}[”\"»]")
_WORD = re.compile(r"\w+")
_EVIDENCE_EDGES = " .,;:!?\"'“”‘’«»…-—"


class CharacterError(Exception):
    pass


@dataclass
class CharInfo:
    key: int
    name: str
    count: int
    biodata: str = ""
    chapters: set = field(default_factory=set)
    aliases: list = field(default_factory=list)


@dataclass
class Result:
    characters: list
    relations: list
    complete: bool = True


@dataclass
class _Group:
    primary: str
    aliases: list = field(default_factory=list)
    roles: list = field(default_factory=list)
    narrations: list = field(default_factory=list)
    description: str = ""

    def names(self) -> list[str]:
        return [self.primary, *self.aliases]


_lock = threading.Lock()


def _cased(text: str) -> bool:
    return any(c.isupper() or c.islower() for c in text)


def name_like(alias: str) -> bool:
    alias = alias.strip()
    if len(alias) < 2:
        return False
    return alias[0].isupper() if _cased(alias) else True


def strip_quotes(text: str) -> str:
    return _QUOTED.sub("", text)


def _pattern(word: str) -> str:
    escaped = re.escape(word)
    return rf"(?<!\w){escaped}(?!\w)" if _cased(word) else escaped


def _normalize(text: str) -> str:
    return " ".join(text.split()).casefold().strip(_EVIDENCE_EDGES)


def _merge_into(target: _Group, other: _Group) -> None:
    known = {n.casefold() for n in target.names()}
    for name in other.names():
        if name.casefold() not in known:
            known.add(name.casefold())
            target.aliases.append(name)
    target.roles.extend(r for r in other.roles if r not in target.roles)
    target.narrations.extend(other.narrations)


def _find(groups: dict[str, _Group], name: str) -> _Group | None:
    key = name.casefold()
    if key in groups:
        return groups[key]
    return next((g for g in groups.values() if any(a.casefold() == key for a in g.aliases)), None)


def _candidates(chunks: list, results: list) -> list[_Group]:
    groups: dict[str, _Group] = {}
    for chunk, result in zip(chunks, results):
        if result is None:
            continue
        pronouns = {p.casefold() for p in result["pronouns"]}
        for person in result["people"]:
            if person["name"].casefold() in pronouns:
                continue
            aliases = [a for a in person["aliases"] if a.casefold() not in pronouns]
            group = groups.setdefault(person["name"].casefold(), _Group(person["name"]))
            _merge_into(group, _Group(person["name"], aliases, [person["role"]] if person["role"] else []))
        if result["narrator"] and result["pronouns"]:
            group = _find(groups, result["narrator"]) or groups.setdefault(result["narrator"].casefold(), _Group(result["narrator"]))
            group.narrations.append((frozenset(chunk.chapters), list(result["pronouns"])))
    return _dedupe(list(groups.values()))


def _dedupe(groups: list[_Group]) -> list[_Group]:
    parent = list(range(len(groups)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(groups):
        for j, b in enumerate(groups):
            if i != j and a.primary.casefold() in {n.casefold() for n in b.aliases}:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj
    merged: dict[int, _Group] = {}
    for i, group in enumerate(groups):
        root = find(i)
        if root not in merged:
            merged[root] = _Group(groups[root].primary)
            _merge_into(merged[root], groups[root])
        if i != root:
            _merge_into(merged[root], group)
    return list(merged.values())


def _alias_table(groups: list[_Group], texts: list[str]) -> dict[str, int]:
    words = Counter(_WORD.findall("\n".join(texts)))
    table = {g.primary: i for i, g in enumerate(groups)}
    owners: dict[str, set] = defaultdict(set)
    for i, group in enumerate(groups):
        for alias in group.aliases:
            if alias in table or not name_like(alias):
                continue
            lowered = alias.lower()
            if _WORD.fullmatch(alias) and lowered != alias and words[lowered] >= words[alias]:
                continue
            owners[alias].add(i)
    table.update({alias: next(iter(o)) for alias, o in owners.items() if len(o) == 1})
    return table


def _mentions(texts: list[str], chapters: list[int], groups: list[_Group]):
    table = _alias_table(groups, texts)
    rx = re.compile("(?:" + "|".join(_pattern(k) for k in sorted(table, key=len, reverse=True)) + ")") if table else None
    counts: list[Counter] = [Counter() for _ in texts]
    alias_counts: Counter = Counter()
    if rx:
        for i, text in enumerate(texts):
            for match in rx.finditer(text):
                counts[i][table[match.group(0)]] += 1
                alias_counts[(table[match.group(0)], match.group(0))] += 1
    narrated: dict[int, set] = defaultdict(set)
    for g, group in enumerate(groups):
        for narrated_chapters, pronouns in group.narrations:
            narrated[g] |= narrated_chapters
            prx = re.compile("(?:" + "|".join(_pattern(p) for p in sorted(pronouns, key=len, reverse=True)) + ")", re.IGNORECASE)
            for i, text in enumerate(texts):
                if chapters[i] in narrated_chapters:
                    counts[i][g] += len(prx.findall(strip_quotes(text)))
    return counts, alias_counts, narrated


def _apply_merge(entry_groups: list[_Group], answer: list[dict]) -> list[_Group]:
    used: set[int] = set()
    out: list[_Group] = []
    for item in answer:
        ids = sorted(i for i in item["ids"] if 0 <= i < len(entry_groups) and i not in used)
        if not ids:
            continue
        used.update(ids)
        members = [entry_groups[i] for i in ids]
        names = {n.casefold(): n for m in members for n in m.names()}
        group = _Group(names.get(item["name"].casefold(), members[0].primary), description=item["description"])
        for member in members:
            _merge_into(group, member)
        out.append(group)
    out.extend(g for i, g in enumerate(entry_groups) if i not in used)
    return out


def _top(votes: Counter) -> str:
    return min(votes, key=lambda kind: (-votes[kind], RELATION_PRIORITY.index(kind)))


def _relations(chosen: list[_Group], present: list[set], chapters: list[int], chunks: list, results: list) -> list[tuple]:
    resolve: dict[str, int | None] = {}
    for pos, group in enumerate(chosen):
        resolve[group.primary.casefold()] = pos
    for pos, group in enumerate(chosen):
        for alias in group.aliases:
            key = alias.casefold()
            if key not in resolve or resolve[key] == pos:
                resolve[key] = pos
            elif resolve[key] is not None and chosen[resolve[key]].primary.casefold() != key:
                resolve[key] = None

    votes_chapter: dict[tuple, Counter] = defaultdict(Counter)
    votes_all: dict[tuple, Counter] = defaultdict(Counter)
    for chunk, result in zip(chunks, results):
        if result is None:
            continue
        for relation in result["relations"]:
            a, b = resolve.get(relation["a"].casefold()), resolve.get(relation["b"].casefold())
            evidence = _normalize(relation["evidence"])
            if a is None or b is None or a == b or len(evidence) < MIN_EVIDENCE_CHARS:
                continue
            low, high = sorted((a, b))
            for index, chapter, text in chunk.paragraphs:
                if evidence in _normalize(text) and {low, high} <= present[index]:
                    kind = relation["type"] if relation["type"] in RELATION_PRIORITY else "kenalan"
                    votes_chapter[(chapter, low, high)][kind] += 1
                    votes_all[(low, high)][kind] += 1
                    break
    if not votes_all:
        return []

    by_chapter: dict[int, list[int]] = defaultdict(list)
    for index, chapter in enumerate(chapters):
        by_chapter[chapter].append(index)
    weights: Counter = Counter()
    for chapter, indexes in by_chapter.items():
        for pos, i in enumerate(indexes):
            window = [i] + ([indexes[pos + 1]] if pos + 1 < len(indexes) else [])
            union = set().union(*(present[j] for j in window))
            for a, b in combinations(sorted(union), 2):
                if (a, b) in votes_all and (a in present[i] or b in present[i]):
                    weights[(chapter, a, b)] += 1

    edges = []
    for chapter, a, b in sorted(set(weights) | set(votes_chapter)):
        own = votes_chapter.get((chapter, a, b))
        weight = weights[(chapter, a, b)]
        if own or weight >= MIN_PAIR_WEIGHT:
            edges.append((chapter, a, b, _top(own or votes_all[(a, b)]), max(weight, 1)))
    return edges


def build(paragraphs: list[dict], chunks: list, results: list, merge_fn=None) -> Result:
    if chunks and all(r is None for r in results):
        raise CharacterError("Layanan AI tidak berhasil membaca satu pun bagian buku ini.")
    if not chunks:
        return Result([], [])
    complete = all(r is not None for r in results)
    texts = [p["text"] for p in paragraphs]
    chapters = [p["chapter_no"] for p in paragraphs]

    groups = _candidates(chunks, results)
    counts, alias_counts, narrated = _mentions(texts, chapters, groups)
    totals = [sum(c[g] for c in counts) for g in range(len(groups))]
    ranked = sorted((g for g in range(len(groups)) if totals[g] >= MIN_MENTIONS), key=lambda g: -totals[g])[:MAX_MERGE_ENTRIES]

    if len(chunks) > 1 and ranked:
        entries = [
            {"id": n, "name": groups[g].primary, "aliases": groups[g].aliases, "count": totals[g], "roles": groups[g].roles[:MAX_ROLES_SENT]}
            for n, g in enumerate(ranked)
        ]
        answer = (merge_fn or character_ai.merge_safe)(entries)
        if answer is None:
            complete = False
        else:
            groups = _apply_merge([groups[g] for g in ranked], answer)
            counts, alias_counts, narrated = _mentions(texts, chapters, groups)
            totals = [sum(c[g] for c in counts) for g in range(len(groups))]

    order = sorted((g for g in range(len(groups)) if totals[g] >= MIN_MENTIONS), key=lambda g: -totals[g])[:MAX_CHARACTERS]
    chosen = [groups[g] for g in order]
    position = {g: pos for pos, g in enumerate(order)}

    present: list[set] = []
    for i, counter in enumerate(counts):
        here = {position[g] for g, n in counter.items() if n > 0 and g in position}
        here |= {position[g] for g in order if chapters[i] in narrated.get(g, ())}
        present.append(here)

    infos = []
    for pos, g in enumerate(order):
        group = groups[g]
        seen = [i for i, counter in enumerate(counts) if counter[g] > 0]
        shown = sorted((a for a in group.aliases if name_like(a) and alias_counts[(g, a)] > 0), key=lambda a: -alias_counts[(g, a)])
        chapter_set = {chapters[i] for i in seen}
        basic = f"{group.primary} disebut {totals[g]} kali di {len(chapter_set)} bab."
        infos.append(CharInfo(
            key=pos, name=group.primary[:100], count=totals[g], chapters=chapter_set, aliases=shown[:MAX_ALIASES_SHOWN],
            biodata=group.description or (group.roles[0] if group.roles else "") or basic,
        ))
    return Result(infos, _relations(chosen, present, chapters, chunks, results), complete)


def extract(db: Session, doc: Document) -> tuple[int, int, bool]:
    if not character_ai.available():
        raise CharacterError("Deteksi tokoh butuh layanan AI (9router atau Gemini) di server.")
    paragraphs = [{"chapter_no": p.chapter_no, "text": p.text, "sexual": p.sexual or 0.0} for p in doc.paragraphs]
    chunks = character_ai.make_chunks(paragraphs)
    result = build(paragraphs, chunks, character_ai.read_chunks(chunks))

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
        row = Character(
            document_id=doc.id, name=info.name, biodata=info.biodata, mention_count=info.count,
            aliases=", ".join(info.aliases) or None,
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
    return len(result.characters), made, result.complete


def run(doc_id: int) -> None:
    with SessionLocal() as db:
        doc = db.get(Document, doc_id)
        if doc is None:
            return
        doc.characters_status = "running"
        db.commit()
        try:
            with _lock:
                _, _, complete = extract(db, doc)
            status = "done" if complete else "partial"
            if not complete:
                log.warning("Deteksi tokoh dokumen %s selesai sebagian: ada bagian buku atau penggabungan yang gagal diproses LLM", doc_id)
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
