import pytest

from app.services import character_ai, characters
from tests.characters_helpers import build, chunk_result, para, person, relation


def pair_book(extra=()):
    return [
        para("Rana dan Dede adalah sahabat karib.", 1),
        para("Rana pulang sendirian.", 1),
        para("Rana pulang lagi.", 1),
        para("Dede menunggu di rumah.", 1),
        para("Dede menunggu lagi.", 1),
        *extra,
    ]


PEOPLE = [person("Rana"), person("Dede")]
GOOD = relation("Rana", "Dede", "sahabat", "Rana dan Dede adalah sahabat karib")


def edges(result):
    names = {i: c.name for i, c in enumerate(result.characters)}
    return [(chapter, names[a], names[b], kind, weight) for chapter, a, b, kind, weight in result.relations]


def test_a_verified_relation_becomes_an_edge_with_its_kind_and_weight():
    paragraphs = pair_book() + [para("Rana dan Dede berjalan.", 1), para("Rana dan Dede duduk.", 1)]
    result = build(paragraphs, PEOPLE, [GOOD])
    [(chapter, a, b, kind, weight)] = edges(result)
    assert (chapter, {a, b}, kind) == (1, {"Rana", "Dede"}, "sahabat") and weight >= 2


def test_edge_ids_are_ordered_and_refer_to_the_cards():
    paragraphs = pair_book() + [para("Rana dan Dede berjalan.", 1)]
    result = build(paragraphs, PEOPLE, [GOOD])
    [(_, a, b, _, _)] = result.relations
    assert a < b and 0 <= a < len(result.characters) and 0 <= b < len(result.characters)


def test_evidence_that_is_not_in_the_text_is_dropped():
    bad = relation("Rana", "Dede", "musuh", "Rana membenci Dede sejak lama sekali")
    assert build(pair_book(), PEOPLE, [bad]).relations == []


def test_evidence_matching_ignores_case_spacing_and_edge_punctuation():
    loose = relation("Rana", "Dede", "sahabat", "  “RANA   dan Dede adalah sahabat karib.” ")
    assert len(build(pair_book() + [para("Rana dan Dede berjalan.", 1)], PEOPLE, [loose]).relations) == 1


def test_the_paragraph_of_the_evidence_must_contain_both_characters():
    paragraphs = pair_book([para("Mereka tertawa bersama di halaman sekolah.", 1)])
    weak = relation("Rana", "Dede", "sahabat", "Mereka tertawa bersama di halaman sekolah")
    assert build(paragraphs, PEOPLE, [weak]).relations == []


def test_the_narrator_counts_as_present_in_the_chapters_they_narrate():
    paragraphs = [para("Mama selalu menjagaku sejak kecil.", 1)] + [para("Mama masak di dapur.", 1)] * 3 + [para("Aku makan.", 1)] * 3
    rel = relation("Raib", "Mama", "keluarga", "Mama selalu menjagaku sejak kecil")
    result = build(paragraphs, [person("Raib"), person("Mama")], [rel], narrator="Raib", pronouns=["aku"])
    assert [(k) for _, _, _, k, _ in result.relations] == ["keluarga"]


def test_unknown_names_and_self_relations_are_dropped():
    rels = [
        relation("Rana", "Budi", "teman", "Rana dan Dede adalah sahabat karib"),
        relation("Rana", "Rana", "teman", "Rana pulang sendirian"),
        relation("Rana", "Ra", "teman", "Rana pulang sendirian"),
    ]
    assert build(pair_book(), [person("Rana", ["Ra"]), person("Dede")], rels).relations == []


def test_nicknames_resolve_to_the_right_character():
    rel = relation("Ra", "De", "sahabat", "Rana dan Dede adalah sahabat karib")
    result = build(pair_book() + [para("Rana dan Dede berjalan.", 1)], [person("Rana", ["Ra"]), person("Dede", ["De"])], [rel])
    assert len(result.relations) == 1


def test_a_name_shared_by_two_characters_does_not_resolve():
    rel = relation("Sel", "Dede", "sahabat", "Rana dan Dede adalah sahabat karib")
    assert build(pair_book(), [person("Rana", ["Sel"]), person("Dede", ["Sel"])], [rel]).relations == []


def test_an_unknown_relation_kind_becomes_acquaintance():
    rel = relation("Rana", "Dede", "rekan bisnis", "Rana dan Dede adalah sahabat karib")
    assert edges(build(pair_book(), PEOPLE, [rel]))[0][3] == "kenalan"


def test_each_chapter_takes_the_vote_of_its_own_evidence():
    paragraphs = (
        [para("Rana dan Dede adalah sahabat karib.", 1), para("Rana dan Dede bermain.", 1)]
        + [para("Rana dan Dede saling membenci.", 2), para("Rana dan Dede bertengkar.", 2)]
    )
    rels = [
        relation("Rana", "Dede", "sahabat", "Rana dan Dede adalah sahabat karib"),
        relation("Rana", "Dede", "musuh", "Rana dan Dede saling membenci"),
    ]
    assert [(c, k) for c, _, _, k, _ in edges(build(paragraphs, PEOPLE, rels))] == [(1, "sahabat"), (2, "musuh")]


def test_a_chapter_without_its_own_vote_takes_the_overall_kind():
    paragraphs = (
        [para("Rana dan Dede adalah sahabat karib.", 1), para("Rana dan Dede bermain.", 1)]
        + [para("Rana dan Dede berjalan.", 2), para("Rana dan Dede duduk.", 2)]
    )
    result = build(paragraphs, PEOPLE, [relation("Rana", "Dede", "sahabat", "Rana dan Dede adalah sahabat karib")])
    assert [(c, k) for c, _, _, k, _ in edges(result)] == [(1, "sahabat"), (2, "sahabat")]


def test_the_most_voted_kind_wins_and_ties_follow_the_priority_order():
    paragraphs = [para("Rana dan Dede adalah sahabat karib.", 1), para("Rana dan Dede dekat sekali.", 1), para("Rana dan Dede lagi.", 1)]
    rels = [
        relation("Rana", "Dede", "teman", "Rana dan Dede adalah sahabat karib"),
        relation("Rana", "Dede", "pasangan", "Rana dan Dede dekat sekali"),
    ]
    assert edges(build(paragraphs, PEOPLE, rels))[0][3] == "pasangan"
    rels = [
        relation("Rana", "Dede", "teman", "Rana dan Dede adalah sahabat karib"),
        relation("Rana", "Dede", "teman", "Rana dan Dede dekat sekali"),
        relation("Rana", "Dede", "musuh", "Rana dan Dede lagi"),
    ]
    assert edges(build(paragraphs, PEOPLE, rels))[0][3] == "teman"


def test_acquaintance_loses_a_tie_against_any_other_kind():
    paragraphs = [para("Rana dan Dede adalah sahabat karib.", 1), para("Rana dan Dede dekat sekali.", 1), para("Rana dan Dede lagi.", 1)]
    rels = [
        relation("Rana", "Dede", "kenalan", "Rana dan Dede adalah sahabat karib"),
        relation("Rana", "Dede", "teman", "Rana dan Dede dekat sekali"),
    ]
    assert edges(build(paragraphs, PEOPLE, rels))[0][3] == "teman"


def test_a_pair_the_llm_never_stated_gets_no_edge():
    paragraphs = [para("Rana dan Dede berjalan.", 1)] * 5
    assert build(paragraphs, PEOPLE, []).relations == []


def test_the_relation_belongs_to_the_chapter_of_its_evidence():
    paragraphs = [para("Rana pulang.", 1)] * 2 + [para("Dede pulang.", 1)] * 2 + [para("Rana dan Dede adalah sahabat karib.", 2)] * 2
    result = build(paragraphs, PEOPLE, [relation("Rana", "Dede", "sahabat", "Rana dan Dede adalah sahabat karib")])
    assert [c for c, _, _, _, _ in result.relations] == [2]


def test_a_weak_chapter_is_kept_only_when_it_has_its_own_evidence():
    paragraphs = (
        [para("Rana dan Dede adalah sahabat karib.", 1)]
        + [para("Rana dan Dede berjalan.", 2), para("Rana pulang.", 2)]
        + [para("Rana dan Dede bertemu.", 3), para("Dede pulang.", 3), para("Rana pergi.", 3)] * 2
    )
    rels = [relation("Rana", "Dede", "sahabat", "Rana dan Dede adalah sahabat karib")]
    chapters = {c: w for c, _, _, _, w in build(paragraphs, PEOPLE, rels).relations}
    assert 1 in chapters and chapters[1] >= 1
    assert 3 in chapters and chapters[3] >= characters.MIN_PAIR_WEIGHT


def test_weight_counts_paragraphs_where_both_are_in_the_window():
    paragraphs = [para("Rana berjalan.", 1), para("Dede menyusul.", 1), para("Rana dan Dede tiba.", 1), para("Sepi.", 1)]
    result = build(paragraphs * 2, PEOPLE, [relation("Rana", "Dede", "teman", "Rana dan Dede tiba")])
    assert edges(result)[0][4] >= 2


def test_relations_from_a_failed_chunk_are_simply_absent():
    paragraphs = pair_book() + [para("Rana dan Dede berjalan.", 1)]
    chunks = character_ai.make_chunks(paragraphs, limit=60)
    results = [chunk_result(PEOPLE, [GOOD])] + [None] * (len(chunks) - 1)
    result = characters.build(paragraphs, chunks, results, merge_fn=lambda entries: None)
    assert result.complete is False


@pytest.mark.parametrize("kind", ["pasangan", "sahabat", "teman", "keluarga", "musuh", "kenalan"])
def test_every_known_kind_is_accepted(kind):
    rel = relation("Rana", "Dede", kind, "Rana dan Dede adalah sahabat karib")
    assert edges(build(pair_book(), PEOPLE, [rel]))[0][3] == kind
