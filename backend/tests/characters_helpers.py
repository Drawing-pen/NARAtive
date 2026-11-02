from app.services import character_ai, characters


def para(text, chapter=1, sexual=0.0):
    return {"chapter_no": chapter, "text": text, "sexual": sexual}


def person(name, aliases=(), role=""):
    return {"name": name, "aliases": list(aliases), "role": role}


def relation(a, b, kind="teman", evidence=""):
    return {"a": a, "b": b, "type": kind, "evidence": evidence}


def chunk_result(people=(), relations=(), narrator="", pronouns=(), pov="ketiga"):
    return {"pov": pov, "narrator": narrator, "pronouns": list(pronouns), "people": list(people), "relations": list(relations)}


def build(paragraphs, people=(), relations=(), narrator="", pronouns=(), pov=None, limit=character_ai.CHUNK_CHARS, merge=None, results=None):
    """Satu hasil yang sama dipakai untuk setiap potongan, kecuali `results` diberikan."""
    chunks = character_ai.make_chunks(paragraphs, limit=limit)
    if results is None:
        pov = pov or ("pertama" if pronouns else "ketiga")
        results = [chunk_result(people, relations, narrator, pronouns, pov) for _ in chunks]
    return characters.build(paragraphs, chunks, results, merge_fn=merge or (lambda entries: None))


def by_name(result):
    return {c.name: c for c in result.characters}


def repeat(text, n, chapter=1):
    return [para(text, chapter) for _ in range(n)]
