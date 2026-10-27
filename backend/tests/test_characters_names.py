from collections import Counter

import pytest

from app.services import characters


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Rana", "Rana"),
        ("Dede Dering", "Dede Dering"),
        ("  Rana  ", "Rana"),
        ('"Rana"', "Rana"),
        ("(Rana)", "Rana"),
        ("Rana's", "Rana"),
        ("Rana’s", "Rana"),
        ("Rana.", "Rana"),
        ("Rana   Afifah", "Rana Afifah"),
        ("I Wayan", "Wayan"),
        ("Ludwig van Beethoven", "Ludwig van Beethoven"),
        ("Siti binti Ahmad", "Siti binti Ahmad"),
    ],
)
def test_clean_surface_accepts_and_tidies_names(raw, expected):
    assert characters.clean_surface(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "rana",
        "R",
        "",
        "Rana2",
        "Apollo 13",
        "Anna Bella Cinta Dewi Eka",
        "Dede dan Rana",
        "Rana pergi ke pasar",
        "1234",
        "...",
    ],
)
def test_clean_surface_rejects_things_that_are_not_names(raw):
    assert characters.clean_surface(raw) is None


def test_clean_surface_keeps_the_longest_piece_around_quotes():
    assert characters.clean_surface('"Rana Afifah" (X)') == "Rana Afifah"


@pytest.mark.parametrize(
    "surface, expected",
    [
        ("Rana", ("rana",)),
        ("Rana Afifah", ("rana", "afifah")),
        ("Dr. Budi", ("budi",)),
        ("Mr Smith", ("smith",)),
        ("Prof Dr Budi", ("budi",)),
        ("Pak Budi", ("budi",)),
        ("Pak", None),
        ("Dr.", None),
    ],
)
def test_canonical_drops_titles_and_case(surface, expected):
    assert characters.canonical(surface) == expected


def entity(text, name, score=0.99, group="PER", key="entity_group"):
    start = text.index(name)
    return {key: group, "score": score, "start": start, "end": start + len(name), "word": name}


def test_surfaces_come_from_character_offsets():
    text = "Kemarin Rana bertemu Dede di pasar."
    found = characters.surfaces_from([entity(text, "Rana"), entity(text, "Dede")], text)
    assert found == ["Rana", "Dede"]


def test_only_person_entities_are_kept():
    text = "Rana pergi ke Jakarta."
    found = characters.surfaces_from([entity(text, "Rana"), entity(text, "Jakarta", group="LOC")], text)
    assert found == ["Rana"]


@pytest.mark.parametrize("group", ["PER", "PERSON", "PERS", "per"])
def test_person_group_spellings_are_accepted(group):
    text = "Rana pergi."
    assert characters.surfaces_from([entity(text, "Rana", group=group)], text) == ["Rana"]


def test_token_style_labels_are_accepted():
    text = "Rana pergi."
    assert characters.surfaces_from([entity(text, "Rana", group="B-PER", key="entity")], text) == ["Rana"]


def test_the_confidence_threshold_is_0_85_inclusive():
    text = "Rana dan Dede."
    entities = [entity(text, "Rana", score=0.85), entity(text, "Dede", score=0.8499)]
    assert characters.surfaces_from(entities, text) == ["Rana"]


def test_entities_that_do_not_clean_into_names_are_dropped():
    text = "kemarin rana pergi."
    assert characters.surfaces_from([entity(text, "rana")], text) == []


def test_a_short_name_that_is_part_of_one_longer_name_is_merged():
    counts = Counter({("rana",): 3, ("rana", "afifah"): 5})
    root = characters.unify(counts)
    assert root[("rana",)] == ("rana", "afifah")
    assert root[("rana", "afifah")] == ("rana", "afifah")


def test_an_ambiguous_short_name_stays_separate_when_the_candidates_are_close():
    counts = Counter({("rana",): 3, ("rana", "afifah"): 5, ("rana", "dzikro"): 4})
    root = characters.unify(counts)
    assert root[("rana",)] == ("rana",)


def test_an_ambiguous_short_name_goes_to_a_candidate_twice_as_frequent():
    counts = Counter({("rana",): 3, ("rana", "afifah"): 8, ("rana", "dzikro"): 4})
    root = characters.unify(counts)
    assert root[("rana",)] == ("rana", "afifah")


def test_unrelated_names_never_merge():
    counts = Counter({("rana",): 3, ("dede", "dering"): 5})
    root = characters.unify(counts)
    assert root[("rana",)] == ("rana",)
