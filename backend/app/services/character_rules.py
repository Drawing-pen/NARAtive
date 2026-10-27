"""Biodata tokoh tanpa layanan eksternal: jenis kelamin, usia, dan pekerjaan dari pola teks di sekitar nama.

Hasilnya sengaja konservatif: lebih baik kosong (None) daripada menebak.
"""
import re
from collections import Counter

MAX_MENTIONS = 400
AFTER_CHARS = 140
BEFORE_CHARS = 50
MIN_GENDER_VOTES = 3
MIN_STAGE_VOTES = 2
MIN_ROLE_SCORE = 3

MALE_WORDS = {"he", "himself"}
FEMALE_WORDS = {"she", "herself"}
MALE_TITLES = {"mr", "sir", "lord", "pak", "bapak", "mas", "abang", "bang", "om", "tuan", "raja", "pangeran", "king", "prince", "duke", "earl", "baron", "count"}
FEMALE_TITLES = {"mrs", "ms", "miss", "madam", "madame", "lady", "bu", "ibu", "mbak", "tante", "nona", "nyonya", "ratu", "putri", "queen", "princess", "duchess", "countess", "baroness"}
OLD_TITLES = {"kakek", "nenek", "grandfather", "grandmother", "grandpa", "grandma", "granny"}

TITLE_ROLES = {
    "dr": "Dokter", "dokter": "Dokter", "doctor": "Dokter", "prof": "Profesor", "professor": "Profesor", "profesor": "Profesor",
    "captain": "Kapten", "kapten": "Kapten", "raja": "Raja", "king": "Raja", "ratu": "Ratu", "queen": "Ratu",
    "pangeran": "Pangeran", "prince": "Pangeran", "putri": "Putri", "princess": "Putri",
}

ROLES = {
    "guru": "Guru", "teacher": "Guru", "dosen": "Dosen", "lecturer": "Dosen", "mahasiswa": "Mahasiswa", "mahasiswi": "Mahasiswa",
    "siswa": "Pelajar", "siswi": "Pelajar", "murid": "Pelajar", "student": "Pelajar", "pelajar": "Pelajar",
    "dokter": "Dokter", "doctor": "Dokter", "perawat": "Perawat", "nurse": "Perawat",
    "polisi": "Polisi", "police": "Polisi", "detektif": "Detektif", "detective": "Detektif", "inspector": "Detektif",
    "prajurit": "Prajurit", "soldier": "Prajurit", "tentara": "Tentara", "jenderal": "Jenderal", "general": "Jenderal",
    "pengacara": "Pengacara", "lawyer": "Pengacara", "hakim": "Hakim", "judge": "Hakim",
    "penulis": "Penulis", "writer": "Penulis", "author": "Penulis", "novelist": "Penulis", "wartawan": "Wartawan", "journalist": "Wartawan",
    "petani": "Petani", "farmer": "Petani", "nelayan": "Nelayan", "fisherman": "Nelayan",
    "pedagang": "Pedagang", "merchant": "Pedagang", "penjual": "Pedagang", "shopkeeper": "Pedagang",
    "pelayan": "Pelayan", "waiter": "Pelayan", "waitress": "Pelayan", "servant": "Pelayan", "maid": "Pelayan",
    "koki": "Juru masak", "chef": "Juru masak", "cook": "Juru masak", "supir": "Sopir", "sopir": "Sopir", "driver": "Sopir",
    "penyihir": "Penyihir", "wizard": "Penyihir", "witch": "Penyihir", "pendeta": "Pendeta", "priest": "Pendeta",
    "pilot": "Pilot", "insinyur": "Insinyur", "engineer": "Insinyur", "ilmuwan": "Ilmuwan", "scientist": "Ilmuwan",
    "pelukis": "Pelukis", "painter": "Pelukis", "artist": "Seniman", "musisi": "Musisi", "musician": "Musisi",
    "bajak": "Bajak laut", "pirate": "Bajak laut", "pemburu": "Pemburu", "hunter": "Pemburu",
}

NUMBER_WORDS = {
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}
STAGES = {
    "Lansia": {"lansia", "grandfather", "grandmother", "grandpa", "grandma", "granny", "kakek", "nenek"},
    "Remaja": {"remaja", "teenager", "teenage", "teen"},
    "Anak-anak": {"bocah", "balita", "toddler"},
}

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_AGE = re.compile(
    r"(?:\b(\d{1,2})[\s-]*(?:tahun|th\b|years?[\s-]*old|yo\b)|\b(?:berusia|aged|usia)\s+(\d{1,2})\b|\b([a-z]+)[\s-]year[\s-]old)",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"[.!?]+[\"”’']?\s")


def _words(text: str) -> list[str]:
    return [w.casefold() for w in _WORD.findall(text)]


def _after(text: str, end: int) -> str:
    chunk = text[end:end + AFTER_CHARS]
    m = _SENTENCE_END.search(chunk)
    return chunk[:m.start()] if m else chunk


def facts(paragraphs: list[dict], locs: list[tuple], surfaces: Counter) -> dict:
    """Kembalikan {"gender", "age", "occupation"}; bidang yang tidak jelas bernilai None."""
    male = female = 0
    ages: Counter = Counter()
    stages: Counter = Counter()
    roles: Counter = Counter()
    title_roles: Counter = Counter()

    for surface, n in surfaces.items():
        first = _words(surface)[:1]
        if first and first[0] in MALE_TITLES:
            male += 3 * n
        elif first and first[0] in FEMALE_TITLES:
            female += 3 * n
        if first and first[0] in OLD_TITLES:
            stages["Lansia"] += MIN_STAGE_VOTES
        if first and first[0] in TITLE_ROLES:
            title_roles[TITLE_ROLES[first[0]]] += n

    seen = 0
    for i, surface in dict.fromkeys(locs):
        text = paragraphs[i]["text"]
        for m in re.finditer(re.escape(surface), text):
            if seen >= MAX_MENTIONS:
                break
            seen += 1
            after, before = _after(text, m.end()), text[max(0, m.start() - BEFORE_CHARS):m.start()]
            a_words, b_words = _words(after), _words(before)
            male += sum(w in MALE_WORDS for w in a_words)
            female += sum(w in FEMALE_WORDS for w in a_words)
            if b_words and b_words[-1] in MALE_TITLES:
                male += 3
            elif b_words and b_words[-1] in FEMALE_TITLES:
                female += 3
            window = text[max(0, m.start() - BEFORE_CHARS):m.end() + AFTER_CHARS]
            for g in _AGE.finditer(window):
                digits, digits2, word = g.groups()
                value = int(digits or digits2) if (digits or digits2) else NUMBER_WORDS.get((word or "").casefold())
                if value and 3 <= value <= 99:
                    ages[value] += 1
            for stage, vocab in STAGES.items():
                stages[stage] += sum(w in vocab for w in a_words + b_words[-3:])
            for w in a_words[:12]:
                if w in ROLES:
                    roles[ROLES[w]] += 1
            for w in b_words[-2:]:
                if w in ROLES:
                    roles[ROLES[w]] += 2

    gender = None
    if male >= MIN_GENDER_VOTES and male >= 2 * female:
        gender = "Laki-laki"
    elif female >= MIN_GENDER_VOTES and female >= 2 * male:
        gender = "Perempuan"

    age = None
    if ages:
        age = f"{ages.most_common(1)[0][0]} tahun"
    else:
        stage, votes = max(stages.items(), key=lambda kv: kv[1], default=(None, 0))
        if votes >= MIN_STAGE_VOTES:
            age = stage

    occupation = title_roles.most_common(1)[0][0] if title_roles else None
    if occupation is None and roles:
        role, score = roles.most_common(1)[0]
        if score >= MIN_ROLE_SCORE:
            occupation = role
    return {"gender": gender, "age": age, "occupation": occupation}


_DESCRIBED = re.compile(
    r"^[,\s]*(?:(?:adalah|merupakan|is|was)\s+)?((?:an?|the|seorang)\s+[^.!?;\n]{4,100}?)(?=[.,;!?]|\s+(?:and|but|yang|dan|tetapi)\s|$)",
    re.IGNORECASE,
)


def describe(paragraphs: list[dict], locs: list[tuple], max_sexual: float = 0.2) -> str | None:
    """Frasa pengenal pertama tepat setelah nama, mis. 'Budi, seorang guru matematika' atau 'Anna was a quiet girl'."""
    for i, surface in sorted(dict.fromkeys(locs)):
        p = paragraphs[i]
        if (p.get("sexual") or 0.0) >= max_sexual:
            continue
        text = p["text"]
        for m in re.finditer(re.escape(surface), text):
            found = _DESCRIBED.match(text[m.end():m.end() + 140])
            if found:
                return " ".join(found.group(1).split())
    return None


def prefix_alias(a: tuple, b: tuple) -> bool:
    """True bila `a` (satu kata pendek) tampak sebagai panggilan awalan dari `b`, mis. ("de",) dan ("dede", "dering")."""
    if len(a) != 1 or a == b or not 2 <= len(a[0]) <= 5:
        return False
    first = b[0]
    return first.startswith(a[0]) and 0 < len(first) - len(a[0]) <= 4


RELATION_KINDS = ("pasangan", "sahabat", "musuh", "teman", "keluarga")
MIN_RELATION_VOTES = 2
CONFLICT_VOTES = 2

_RELATION_LEXICON = {
    "pasangan": (
        {"kekasih", "pacar", "istri", "isteri", "suami", "tunangan", "menikah", "pernikahan", "mencintai", "cinta", "mencium", "ciuman",
         "girlfriend", "boyfriend", "wife", "husband", "fiance", "fiancee", "married", "marry", "wedding", "kiss", "kissed", "lover", "darling"},
        ("jatuh cinta", "in love", "my love", "love you"),
    ),
    "sahabat": ({"sahabat", "bestie", "bff"}, ("best friend", "teman baik", "teman dekat", "sahabat karib")),
    "musuh": (
        {"musuh", "benci", "membenci", "dendam", "lawan", "saingan", "rival", "enemy", "enemies", "hate", "hated", "betray", "betrayed",
         "khianat", "mengkhianati", "membunuh", "bunuh", "kill", "killed", "murder"},
        ("mortal enemy",),
    ),
    "teman": ({"teman", "kawan", "rekan", "friend", "friends", "buddy", "mate", "classmate", "temannya", "kawannya"}, ("teman sekelas",)),
    "keluarga": (
        {"ibu", "ayah", "bapak", "kakak", "adik", "saudara", "kakek", "nenek", "paman", "bibi", "sepupu", "anak", "ibunya", "ayahnya",
         "mother", "father", "brother", "sister", "uncle", "aunt", "cousin", "mom", "dad", "mum", "grandmother", "grandfather",
         "son", "daughter", "parents", "family"},
        (),
    ),
}


def relation_votes(text: str) -> Counter:
    """Hitung petunjuk jenis hubungan (pasangan, sahabat, dst.) dari satu paragraf."""
    lowered = text.casefold()
    words = set(_WORD.findall(lowered))
    votes: Counter = Counter()
    for kind, (singles, phrases) in _RELATION_LEXICON.items():
        n = len(words & singles) + sum(p in lowered for p in phrases)
        if n:
            votes[kind] = n
    return votes


def pick_relation(votes: Counter, conflict: bool = False) -> str | None:
    """Jenis hubungan dengan suara terbanyak (minimal MIN_RELATION_VOTES); seri dimenangkan urutan RELATION_KINDS."""
    tally = Counter(votes)
    if conflict:
        tally["musuh"] += CONFLICT_VOTES
    best = max(RELATION_KINDS, key=lambda kind: (tally[kind], -RELATION_KINDS.index(kind)))
    return best if tally[best] >= MIN_RELATION_VOTES else None
