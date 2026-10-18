import re

_TERMS: list[tuple[str, float]] = [
    # eksplisit
    (r"nipples?", 0.6), (r"erections?|erect manhood|manhood", 0.6), (r"orgasms?|orgasmic", 0.6),
    (r"(?:buried|plunged|slid|sank|surged|pushed|thrust)\w*\s+(?:himself\s+)?(?:deep\s+)?inside\s+(?:her|me)", 0.6),
    (r"inside\s+(?:her|me)", 0.3), (r"(?:cradle|apex)\s+of\s+her\s+thighs|between\s+her\s+(?:thighs|legs)", 0.5),
    (r"slickness|wetness\s+between|aroused|arousal|swollen\s+(?:with\s+desire|flesh)", 0.4),
    (r"naked|nude|unclothed|bare\s+skin|bare\s+breasts?", 0.35), (r"breasts?|bosom", 0.3),
    (r"lovemaking|make\s+love|made\s+love|making\s+love", 0.4), (r"moans?|moaned|moaning|groaned\s+softly", 0.2),
    (r"thrusts?|thrusting|thrust\s+of", 0.2), (r"hips?\s+(?:rose|arched|bucked|rocked)|arched\s+(?:against|into)", 0.25),
    (r"undress(?:ed|ing)?|unlaced|unbuttoned|stripped\s+off|chemise", 0.1), (r"thighs?", 0.1),
    (r"intimate\s+(?:caress|touch)|caress(?:ed|ing)?\s+her\s+(?:breast|thigh|skin)", 0.3), (r"climax(?:ed)?|ecstasy", 0.1),
    (r"tongue\s+(?:trailed|flicked|swirled|teased)|suckled|nuzzled\s+her\s+(?:breast|neck)", 0.35),
    (r"lust|desire|passion(?:ate)?", 0.05), (r"bed(?:ded)?", 0.03),
    # Indonesia
    (r"puting|payudara|dada\s+telanjang", 0.5), (r"telanjang|bugil", 0.4), (r"bersetubuh|bersenggama|persetubuhan", 0.7),
    (r"bercinta|bermesraan|bercumbu|bercumbuan", 0.45), (r"ereksi|alat\s+kelamin|kemaluan", 0.6), (r"orgasme|klimaks", 0.5),
    (r"birahi|gairah|nafsu", 0.25), (r"mendesah|melenguh|merintih\s+nikmat", 0.25), (r"paha", 0.15), (r"ranjang", 0.1),
]
_COMPILED = [(re.compile(rf"\b(?:{p})\b", re.IGNORECASE), w) for p, w in _TERMS]


def sexual_lexicon_score(text: str) -> float:
    miss = 1.0
    for rx, w in _COMPILED:
        hits = len(rx.findall(text))
        if hits:
            miss *= (1 - w) * (1 - 0.2 * w * min(hits - 1, 3))   
    return round(min(0.99, 1 - miss), 4)