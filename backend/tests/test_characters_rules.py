from collections import Counter

import pytest

from app.services import character_rules as rules


def para(text, sexual=0.0):
    return {"text": text, "sexual": sexual}


def facts_for(name, texts, surfaces=None):
    paragraphs = [para(t) for t in texts]
    locs = [(i, name) for i, t in enumerate(texts) if name in t]
    return rules.facts(paragraphs, locs, Counter(surfaces or {name: len(locs)}))


def test_gender_needs_three_pronoun_votes():
    male = facts_for("Budi", ["Budi said that he was tired."] * 3)
    two = facts_for("Budi", ["Budi said that he was tired."] * 2)
    assert male["gender"] == "Laki-laki"
    assert two["gender"] is None


def test_gender_from_female_pronouns():
    assert facts_for("Siti", ["Siti knew that she had won."] * 3)["gender"] == "Perempuan"


def test_mixed_pronouns_without_a_two_to_one_majority_stay_unknown():
    texts = ["Alex said he was ill."] * 3 + ["Alex said she was ill."] * 2
    assert facts_for("Alex", texts)["gender"] is None


def test_a_title_before_the_name_counts_as_three_votes():
    assert facts_for("Smith", ["Mr Smith arrived."])["gender"] == "Laki-laki"
    assert facts_for("Smith", ["Mrs Smith arrived."])["gender"] == "Perempuan"


def test_a_title_inside_the_surface_form_counts_too():
    result = rules.facts([para("Pak Budi datang.")], [(0, "Pak Budi")], Counter({"Pak Budi": 1}))
    assert result["gender"] == "Laki-laki"


def test_age_from_a_number_of_years():
    assert facts_for("Budi", ["Budi berusia 17 tahun.", "Budi, 17 tahun, tertawa."])["age"] == "17 tahun"
    assert facts_for("Anna", ["Anna was a sixteen-year-old girl."])["age"] == "16 tahun"
    assert facts_for("Anna", ["Anna, who was 12 years old, sang."])["age"] == "12 tahun"


def test_ages_outside_the_plausible_range_are_ignored():
    assert facts_for("Budi", ["Budi berusia 150 tahun."])["age"] is None


def test_life_stage_needs_two_votes():
    assert facts_for("Kakek", ["Kakek, seorang kakek tua, berjalan."])["age"] == "Lansia"
    assert facts_for("Budi", ["Budi seorang remaja yang pemalu."])["age"] is None


def test_an_old_age_title_counts_as_a_life_stage():
    result = rules.facts([para("Kakek Budi datang.")], [(0, "Kakek Budi")], Counter({"Kakek Budi": 1}))
    assert result["age"] == "Lansia"


def test_occupation_from_a_title():
    result = rules.facts([para("Dr. Budi datang.")], [(0, "Dr. Budi")], Counter({"Dr. Budi": 1}))
    assert result["occupation"] == "Dokter"


def test_occupation_from_words_after_the_name_needs_enough_evidence():
    strong = facts_for("Budi", ["Budi adalah guru di sekolah."] * 3)
    weak = facts_for("Budi", ["Budi adalah guru di sekolah."])
    assert strong["occupation"] == "Guru"
    assert weak["occupation"] is None


def test_nothing_is_guessed_without_evidence():
    result = facts_for("Rana", ["Rana pergi ke pasar.", "Rana pulang."])
    assert result == {"gender": None, "age": None, "occupation": None}


def test_describe_finds_the_first_identifying_phrase():
    paragraphs = [para("Budi, seorang guru matematika, datang.")]
    assert rules.describe(paragraphs, [(0, "Budi")]) == "seorang guru matematika"


def test_describe_works_for_english_phrases():
    paragraphs = [para("Anna was a quiet girl who loved books.")]
    assert rules.describe(paragraphs, [(0, "Anna")]) == "a quiet girl who loved books"


def test_describe_returns_nothing_when_there_is_no_phrase():
    assert rules.describe([para("Rana pergi ke pasar.")], [(0, "Rana")]) is None


def test_describe_skips_sexual_paragraphs():
    paragraphs = [para("Budi, seorang kekasih rahasia, datang.", sexual=0.5), para("Budi, seorang guru, datang.")]
    assert rules.describe(paragraphs, [(0, "Budi"), (1, "Budi")]) == "seorang guru"


@pytest.mark.parametrize(
    "short, long, expected",
    [
        (("de",), ("dede", "dering"), True),
        (("ran",), ("rana", "afifah"), True),
        (("de",), ("de",), False),
        (("rana", "a"), ("rana", "afifah"), False),
        (("d",), ("dede",), False),
        (("dedekiah",), ("dedekiah", "x"), False),
        (("budi",), ("andi", "budi"), False),
        (("de",), ("dedeksekali", "x"), False),
    ],
)
def test_nickname_prefix_rule(short, long, expected):
    assert rules.prefix_alias(short, long) is expected


def test_relationship_votes_count_cue_words_and_phrases():
    votes = rules.relation_votes("Mereka sahabat karib dan teman baik, sering bertemu.")
    assert votes["sahabat"] >= 2
    assert rules.relation_votes("Rana dan Dede berjalan.") == Counter()


def test_relationship_votes_are_case_insensitive():
    assert rules.relation_votes("SAHABAT")["sahabat"] == 1


def test_the_most_voted_kind_wins_with_at_least_two_votes():
    assert rules.pick_relation(Counter({"sahabat": 3, "teman": 2})) == "sahabat"
    assert rules.pick_relation(Counter({"sahabat": 1})) is None
    assert rules.pick_relation(Counter()) is None


def test_ties_are_resolved_by_the_fixed_order_of_kinds():
    assert rules.pick_relation(Counter({"keluarga": 2, "pasangan": 2})) == "pasangan"
    assert rules.pick_relation(Counter({"teman": 2, "sahabat": 2})) == "sahabat"


def test_conflict_adds_two_votes_for_enemies():
    assert rules.pick_relation(Counter(), conflict=True) == "musuh"
    assert rules.pick_relation(Counter({"sahabat": 3}), conflict=True) == "sahabat"
    assert rules.pick_relation(Counter({"sahabat": 2}), conflict=True) == "sahabat"
    assert rules.pick_relation(Counter({"musuh": 1, "teman": 2}), conflict=True) == "musuh"
