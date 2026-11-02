import pytest

from app.services import character_ai, characters
from tests.characters_helpers import build, by_name, chunk_result, para, person, repeat


def two_chunks(paragraphs):
    chunks = character_ai.make_chunks(paragraphs, limit=60)
    assert len(chunks) > 1
    return chunks


class TestDescriptions:
    def test_the_basic_sentence_counts_mentions_and_chapters(self):
        paragraphs = repeat("Rana pulang.", 2, chapter=1) + repeat("Rana pergi.", 2, chapter=2)
        result = build(paragraphs, [person("Rana")])
        assert result.characters[0].biodata == "Rana disebut 4 kali di 2 bab."

    def test_the_role_sentence_replaces_the_basic_one(self):
        result = build(repeat("Rana pulang.", 3), [person("Rana", role="Seorang mahasiswa pendiam.")])
        assert result.characters[0].biodata == "Seorang mahasiswa pendiam."

    def test_the_description_from_the_merge_comes_first(self):
        paragraphs = repeat("Rana pulang.", 5) + repeat("Dede pulang.", 5)
        chunks = two_chunks(paragraphs)
        results = [chunk_result([person("Rana", role="peran bab")]) for _ in chunks]
        merge = lambda entries: [{"ids": [0], "name": "Rana", "description": "Rana adalah pusat cerita."}]
        result = characters.build(paragraphs, chunks, results, merge_fn=merge)
        assert by_name(result)["Rana"].biodata == "Rana adalah pusat cerita."

    def test_characters_carry_no_role_label_or_profile(self):
        result = build(repeat("Rana pulang.", 3), [person("Rana")])
        assert not any(hasattr(c, "role") or hasattr(c, "profile") for c in result.characters)


class TestAliasesShown:
    def test_up_to_three_name_like_nicknames_most_frequent_first(self):
        paragraphs = repeat("Raib dan Ra dan Rai.", 4) + repeat("Putri dan Princess.", 2) + [para("Raib lagi.")] * 3
        people = [person("Raib", ["Ra", "Rai", "Putri", "Princess", "sang Pengintai"])]
        card = by_name(build(paragraphs, people))["Raib"]
        assert card.aliases == ["Ra", "Rai", "Putri"]

    def test_the_main_name_and_unused_nicknames_are_not_listed(self):
        card = by_name(build(repeat("Raib pulang.", 3), [person("Raib", ["Ra"])]))["Raib"]
        assert "Raib" not in card.aliases and card.aliases == []


class TestMerge:
    def setup_method(self):
        self.paragraphs = repeat("Rana dan Ra dan Dede pergi.", 6) + repeat("Rana pulang. Dede menunggu.", 6)
        self.chunks = two_chunks(self.paragraphs)
        self.people = [person("Rana", ["Ra"], "Tokoh pertama."), person("Ra", role="Panggilan."), person("Dede", role="Tokoh kedua.")]
        self.results = [chunk_result(self.people) for _ in self.chunks]

    def run(self, merge):
        return characters.build(self.paragraphs, self.chunks, self.results, merge_fn=merge)

    def test_the_merge_receives_numbered_candidates_with_counts_and_at_most_two_roles(self):
        seen = {}
        self.run(lambda entries: seen.setdefault("entries", entries) and None)
        entries = seen["entries"]
        assert [e["id"] for e in entries] == list(range(len(entries)))
        assert {"id", "name", "aliases", "count", "roles"} == set(entries[0])
        assert all(len(e["roles"]) <= 2 and e["count"] >= characters.MIN_MENTIONS for e in entries)
        assert entries == sorted(entries, key=lambda e: -e["count"])

    def test_the_merge_is_skipped_for_a_single_chunk(self):
        paragraphs = repeat("Rana pulang.", 3)
        result = build(paragraphs, [person("Rana")], merge=lambda entries: pytest.fail("tidak boleh dipanggil"))
        assert result.complete is True

    def test_groups_unify_names_and_nicknames(self):
        def merge(entries):
            ids = {e["name"]: e["id"] for e in entries}
            return [{"ids": [ids["Rana"]], "name": "Rana", "description": "Rana adalah tokoh utama."}]

        result = self.run(merge)
        assert set(by_name(result)) == {"Rana", "Dede"}
        assert by_name(result)["Rana"].biodata == "Rana adalah tokoh utama."
        assert result.complete is True

    def test_two_candidates_in_one_group_become_one_card_with_the_sum_of_mentions(self):
        paragraphs = repeat("Raib pergi.", 3) + repeat("Hana lewat.", 3) + repeat("Dede lewat.", 3) + repeat("Dede pulang.", 3)
        chunks = two_chunks(paragraphs)
        results = [chunk_result([person("Raib"), person("Hana"), person("Dede")]) for _ in chunks]

        def merge(entries):
            ids = {e["name"]: e["id"] for e in entries}
            return [{"ids": [ids["Raib"], ids["Hana"]], "name": "Raib", "description": "Satu orang."}]

        result = characters.build(paragraphs, chunks, results, merge_fn=merge)
        assert "Hana" not in by_name(result)
        assert by_name(result)["Raib"].count == 6 and by_name(result)["Raib"].aliases == ["Hana"]

    def test_a_name_the_llm_invented_falls_back_to_the_biggest_member(self):
        def merge(entries):
            return [{"ids": [entries[0]["id"]], "name": "Nama Karangan", "description": "x"}]

        result = self.run(merge)
        assert "Nama Karangan" not in by_name(result)

    def test_unknown_ids_are_ignored_and_uncovered_candidates_stay(self):
        result = self.run(lambda entries: [{"ids": [99], "name": "Hantu", "description": "x"}])
        assert {"Rana", "Dede"} <= set(by_name(result))

    def test_a_failed_merge_keeps_the_candidates_and_marks_the_result_incomplete(self):
        result = self.run(lambda entries: None)
        assert result.complete is False and {"Rana", "Dede"} <= set(by_name(result))
        assert by_name(result)["Rana"].biodata == "Tokoh pertama."

    def test_a_candidate_named_like_anothers_nickname_is_merged_by_code(self):
        paragraphs = repeat("Colin dan Lord Greystone bicara.", 4)
        people = [person("Lord Greystone", ["Colin"]), person("Colin")]
        result = build(paragraphs, people)
        assert list(by_name(result)) == ["Lord Greystone"]

    def test_candidates_below_the_threshold_are_not_sent_to_the_merge(self):
        paragraphs = repeat("Rana pulang.", 6) + repeat("Budi lewat.", 1)
        chunks = two_chunks(paragraphs)
        results = [chunk_result([person("Rana"), person("Budi")]) for _ in chunks]
        seen = {}
        characters.build(paragraphs, chunks, results, merge_fn=lambda entries: seen.setdefault("n", [e["name"] for e in entries]) and None)
        assert seen["n"] == ["Rana"]

    def test_at_most_sixty_candidates_are_sent(self):
        paragraphs = [para(f"Tokoh{chr(65 + i % 26)}{i} lewat.") for i in range(70) for _ in range(3)]
        chunks = two_chunks(paragraphs)
        people = [person(f"Tokoh{chr(65 + i % 26)}{i}") for i in range(70)]
        results = [chunk_result(people) for _ in chunks]
        seen = {}
        characters.build(paragraphs, chunks, results, merge_fn=lambda entries: seen.setdefault("n", len(entries)) and None)
        assert seen["n"] == 60


class TestIncompleteRuns:
    def test_all_chunks_failing_is_an_error(self):
        paragraphs = repeat("Rana pulang.", 3)
        chunks = character_ai.make_chunks(paragraphs)
        with pytest.raises(characters.CharacterError):
            characters.build(paragraphs, chunks, [None], merge_fn=lambda entries: None)

    def test_a_failed_chunk_makes_the_result_incomplete_but_keeps_the_rest(self):
        paragraphs = repeat("Rana dan Dede pergi. Rana pulang.", 8)
        chunks = two_chunks(paragraphs)
        results = [chunk_result([person("Rana"), person("Dede")])] + [None] * (len(chunks) - 1)
        result = characters.build(paragraphs, chunks, results, merge_fn=lambda entries: [])
        assert result.complete is False and "Rana" in by_name(result)

    def test_no_paragraphs_means_no_characters(self):
        result = characters.build([], [], [], merge_fn=lambda entries: None)
        assert result.characters == [] and result.relations == []
