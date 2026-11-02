import pytest

from app.services import character_ai, characters
from tests.characters_helpers import build, by_name, para, person, repeat


class TestNameLike:
    @pytest.mark.parametrize("alias", ["Raib", "Nak Seli", "Miss Selena", "Dede", "Mr. Budi", "李明", "ひろし"])
    def test_names_are_recognised(self, alias):
        assert characters.name_like(alias) is True

    @pytest.mark.parametrize("alias", ["", " ", "kawan", "sang Pengintai", "the king", "my lord", "x", "李"])
    def test_other_words_are_not(self, alias):
        assert characters.name_like(alias) is False


class TestStripQuotes:
    def test_curly_quotes_are_removed_with_their_content(self):
        assert characters.strip_quotes("Aku pergi. “Aku tidak mau,” katanya.") == "Aku pergi.  katanya."

    def test_the_indonesian_style_where_one_mark_opens_and_closes(self):
        assert characters.strip_quotes("”Aku lapar,” kata Ali, ”kamu?” Aku diam.") == " kata Ali,  Aku diam."

    def test_straight_and_guillemet_quotes(self):
        assert characters.strip_quotes('I said "I am here" and «je suis là» too.') == "I said  and  too."

    def test_an_unclosed_quote_removes_nothing(self):
        assert characters.strip_quotes("Aku bilang ”halo dan pergi") == "Aku bilang ”halo dan pergi"

    def test_a_quote_longer_than_the_limit_is_not_removed(self):
        text = "”" + "a" * 600 + "”"
        assert characters.strip_quotes(text) == text


class TestCounting:
    def test_aliases_add_to_the_main_name(self):
        result = build(repeat("Raib dan Ra bermain.", 2), [person("Raib", ["Ra"])])
        assert by_name(result)["Raib"].count == 4

    def test_the_longest_alias_wins_so_a_phrase_is_counted_once(self):
        result = build(repeat("Putri Raib datang.", 3), [person("Raib", ["Putri Raib"])])
        assert by_name(result)["Raib"].count == 3

    def test_only_whole_words_count(self):
        result = build(repeat("Alina bertemu Ali di Alicante.", 3), [person("Ali")])
        assert by_name(result)["Ali"].count == 3

    def test_matching_is_case_sensitive(self):
        result = build(repeat("Ali dan ali dan ALI.", 3), [person("Ali")])
        assert by_name(result)["Ali"].count == 3

    def test_a_name_needs_three_mentions(self):
        result = build(repeat("Rana pulang.", 3) + repeat("Dede menunggu.", 2), [person("Rana"), person("Dede")])
        assert list(by_name(result)) == ["Rana"]

    def test_characters_are_ordered_by_mentions_and_capped_at_25(self):
        texts = [para(f"Tokoh{chr(65 + i)}{chr(97 + i)} lewat.") for i in range(30) for _ in range(40 - i)]
        people = [person(f"Tokoh{chr(65 + i)}{chr(97 + i)}") for i in range(30)]
        result = build(texts, people)
        counts = [c.count for c in result.characters]
        assert len(counts) == 25 and counts == sorted(counts, reverse=True) and counts[0] == 40

    def test_a_generic_word_given_as_a_nickname_is_not_counted(self):
        paragraphs = repeat("Ali datang.", 3) + repeat("Seorang kawan datang, kawan baik, kawan lama.", 2) + [para("Kawan, ayo.")]
        result = build(paragraphs, [person("Ali", ["Kawan"])])
        assert by_name(result)["Ali"].count == 3

    def test_a_capitalised_nickname_that_is_not_a_common_word_is_counted(self):
        result = build(repeat("Ali dan Bintang pergi.", 3), [person("Ali", ["Bintang"])])
        assert by_name(result)["Ali"].count == 6

    def test_the_main_name_is_always_counted_even_if_it_looks_generic(self):
        paragraphs = repeat("Papa pulang.", 3) + repeat("papa dan papa", 5)
        assert by_name(build(paragraphs, [person("Papa")]))["Papa"].count == 3

    def test_a_lowercase_nickname_is_not_counted(self):
        result = build(repeat("Raib bertemu sang Pengintai.", 3), [person("Raib", ["sang Pengintai"])])
        assert by_name(result)["Raib"].count == 3

    def test_a_nickname_shared_by_two_people_is_counted_for_neither(self):
        paragraphs = repeat("Rana dan Dede bertemu Sel.", 3)
        result = build(paragraphs, [person("Rana", ["Sel"]), person("Dede", ["Sel"])])
        assert by_name(result)["Rana"].count == 3 and by_name(result)["Dede"].count == 3

    def test_a_person_listed_under_another_persons_nickname_is_that_person(self):
        paragraphs = repeat("Sel dan Rana bertemu.", 3)
        result = build(paragraphs, [person("Sel"), person("Rana", ["Sel"])])
        assert list(by_name(result)) == ["Rana"] and by_name(result)["Rana"].count == 6

    def test_mentions_in_caseless_scripts_are_counted(self):
        result = build(repeat("李明回家了。", 3), [person("李明")])
        assert by_name(result)["李明"].count == 3

    def test_the_chapters_where_a_character_appears_are_remembered(self):
        paragraphs = repeat("Rana pulang.", 2, chapter=1) + repeat("Rana pergi.", 2, chapter=3)
        assert by_name(build(paragraphs, [person("Rana")]))["Rana"].chapters == {1, 3}


class TestNarrator:
    NARRATION = "Aku berjalan pulang bersama Ali. Aku lelah."

    def test_first_person_pronouns_count_for_the_narrator(self):
        result = build(repeat(self.NARRATION, 3), [person("Raib"), person("Ali")], narrator="Raib", pronouns=["aku"])
        assert by_name(result)["Raib"].count == 6 and by_name(result)["Ali"].count == 3

    def test_pronouns_inside_dialogue_do_not_count(self):
        paragraphs = repeat("”Aku lapar,” kata Ali. Aku diam saja.", 3)
        result = build(paragraphs, [person("Raib"), person("Ali")], narrator="Raib", pronouns=["aku"])
        assert by_name(result)["Raib"].count == 3

    def test_any_language_works(self):
        paragraphs = repeat('I walked home with Tom. "I am tired," Tom said.', 3)
        result = build(paragraphs, [person("Amy"), person("Tom")], narrator="Amy", pronouns=["I"])
        assert by_name(result)["Amy"].count == 3

    def test_pronouns_are_whole_words_and_case_insensitive(self):
        paragraphs = repeat("Aku pergi. Akulah yang pulang. aku diam. Makuku.", 3)
        result = build(paragraphs, [person("Raib")], narrator="Raib", pronouns=["aku"])
        assert by_name(result)["Raib"].count == 6

    def test_a_pronoun_listed_as_a_nickname_is_not_counted_twice(self):
        paragraphs = repeat("Aku pulang. ”Aku lapar,” kata Ali.", 3)
        result = build(paragraphs, [person("Raib", ["Aku", "Ra"]), person("Ali")], narrator="Raib", pronouns=["aku"])
        assert by_name(result)["Raib"].count == 3 and "Aku" not in by_name(result)["Raib"].aliases

    def test_a_person_whose_name_is_a_pronoun_is_ignored(self):
        result = build(repeat("Aku pulang bersama Ali.", 3), [person("Aku"), person("Ali")], narrator="", pronouns=["aku"])
        assert list(by_name(result)) == ["Ali"]

    def test_the_narrators_name_is_counted_too(self):
        result = build(repeat("Raib berjalan. Aku lelah.", 3), [person("Raib")], narrator="Raib", pronouns=["aku"])
        assert by_name(result)["Raib"].count == 6

    def test_only_the_chapters_of_the_narrated_chunk_count(self):
        paragraphs = repeat("Aku pulang.", 3, chapter=1) + repeat("Aku pergi.", 3, chapter=2)
        chunks = character_ai.make_chunks(paragraphs, limit=40)
        assert [c.chapters for c in chunks] == [[1], [2]]
        results = [
            {"pov": "pertama", "narrator": "Raib", "pronouns": ["aku"], "people": [person("Raib")], "relations": []},
            {"pov": "ketiga", "narrator": "", "pronouns": [], "people": [person("Raib")], "relations": []},
        ]
        result = characters.build(paragraphs, chunks, results, merge_fn=lambda entries: None)
        assert by_name(result)["Raib"].count == 3

    def test_a_narrator_missing_from_the_people_list_still_gets_a_card(self):
        result = build(repeat("Aku pulang.", 3), [person("Ali")], narrator="Raib", pronouns=["aku"])
        assert by_name(result)["Raib"].count == 3

    def test_an_unnamed_narrator_gets_no_card(self):
        result = build(repeat("Aku pulang bersama Ali.", 3), [person("Ali")], narrator="", pronouns=["aku"])
        assert list(by_name(result)) == ["Ali"]

    def test_the_narrator_is_resolved_through_nicknames(self):
        result = build(repeat("Aku pulang.", 3), [person("Raib", ["Ra"])], narrator="Ra", pronouns=["aku"])
        assert list(by_name(result)) == ["Raib"] and by_name(result)["Raib"].count == 3
