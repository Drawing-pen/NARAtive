from app.services import characters


def para(text="Teks.", chapter=1, emotion=None, emotion_score=None, violence=0.0, profanity=0.0, sexual=0.0):
    return {
        "chapter_no": chapter, "emotion": emotion, "emotion_score": emotion_score,
        "violence": violence, "profanity": profanity, "sexual": sexual, "text": text,
    }


def book(scenes):
    paragraphs, mentions = [], []
    for scene in scenes:
        names = scene.pop("names") if isinstance(scene, dict) else scene[0]
        paragraphs.append(para(**scene) if isinstance(scene, dict) else para())
        mentions.append(names)
    return paragraphs, mentions


def simple(names_per_paragraph, chapter=1, **kw):
    return [{"names": names, "chapter": chapter, **kw} for names in names_per_paragraph]


def build(scenes, ai_fn=None):
    paragraphs, mentions = book([dict(s) for s in scenes])
    return characters.build(paragraphs, mentions, ai_fn=ai_fn)


def by_name(result):
    return {c.name: c for c in result.characters}


def names_only(counts):
    scenes = []
    for name, n in counts.items():
        scenes += simple([[name]] * n)
    return scenes


def test_a_name_needs_three_mentions_to_become_a_character():
    result = build(names_only({"Rana": 3, "Dede": 2, "Budi": 1}))
    assert [c.name for c in result.characters] == ["Rana"]


def test_mentions_are_counted_per_occurrence():
    result = build(simple([["Rana", "Rana"], ["Rana"]]))
    assert by_name(result)["Rana"].count == 3


def test_at_most_25_characters_are_kept_most_mentioned_first():
    counts = {f"Tokoh{chr(65 + i)}{chr(97 + i)}": 40 - i for i in range(30)}
    result = build(names_only(counts))
    assert len(result.characters) == 25
    assert [c.count for c in result.characters] == sorted((c.count for c in result.characters), reverse=True)
    assert result.characters[0].count == 40 and result.characters[-1].count == 16


def test_roles_follow_rank_and_share_of_mentions():
    result = build(names_only({"Aaa": 100, "Bbb": 90, "Ccc": 60, "Ddd": 20, "Eee": 5, "Fff": 3}))
    roles = {c.name: c.role for c in result.characters}
    assert roles == {
        "Aaa": "Tokoh utama", "Bbb": "Tokoh utama", "Ccc": "Tokoh utama",
        "Ddd": "Tokoh pendukung", "Eee": "Tokoh pendukung", "Fff": "Tokoh figuran",
    }


def test_the_second_ranked_name_is_always_a_lead_even_with_a_low_share():
    result = build(names_only({"Aaa": 100, "Bbb": 10, "Ccc": 5}))
    roles = {c.name: c.role for c in result.characters}
    assert roles["Bbb"] == "Tokoh utama" and roles["Ccc"] == "Tokoh pendukung"


def test_a_short_name_is_merged_into_the_single_longer_name_that_contains_it():
    result = build(simple([["Rana"]] * 3 + [["Rana Afifah"]] * 4))
    assert len(result.characters) == 1
    rana = result.characters[0]
    assert rana.name == "Rana Afifah" and rana.count == 7
    assert rana.aliases == ["Rana"]


def test_titles_do_not_create_separate_characters():
    result = build(simple([["Dr. Budi"]] * 2 + [["Budi"]] * 2))
    assert len(result.characters) == 1 and result.characters[0].count == 4


def test_interjections_are_not_characters():
    result = build(names_only({"Jesus": 6, "Rana": 5}))
    assert [c.name for c in result.characters] == ["Rana"]


def test_a_common_word_that_is_mostly_lowercase_in_the_text_is_not_a_character():
    paragraphs = [para("Dia will pergi.") for _ in range(10)] + [para("Will datang.") for _ in range(4)] + [para("Rana datang.") for _ in range(5)]
    mentions = [[] for _ in range(10)] + [["Will"]] * 4 + [["Rana"]] * 5
    result = characters.build(paragraphs, mentions)
    assert [c.name for c in result.characters] == ["Rana"]


def test_a_single_word_name_is_kept_when_it_is_not_a_common_lowercase_word():
    paragraphs = [para("Rana datang.") for _ in range(4)]
    result = characters.build(paragraphs, [["Rana"]] * 4)
    assert [c.name for c in result.characters] == ["Rana"]


def test_a_nickname_prefix_merges_into_the_only_matching_name_when_they_never_appear_together():
    result = build(simple([["De"]] * 3 + [["Dede Dering"]] * 5))
    assert [c.name for c in result.characters] == ["Dede Dering"]
    assert result.characters[0].count == 8


def test_a_nickname_prefix_is_not_merged_when_both_names_share_a_paragraph():
    result = build(simple([["De", "Dede Dering"]] + [["De"]] * 2 + [["Dede Dering"]] * 5))
    assert sorted(c.name for c in result.characters) == ["De", "Dede Dering"]


def test_a_nickname_prefix_is_not_merged_when_two_names_could_match():
    result = build(simple([["Ra"]] * 3 + [["Rana Putri"]] * 5 + [["Rani Sari"]] * 5))
    assert "Ra" in {c.name for c in result.characters}


def test_a_pair_needs_a_weight_of_two_to_become_a_relation():
    gap = [[], []]
    once = build(simple([["Rana", "Dede"]] + gap + [["Rana"]] + gap + [["Dede"]] + gap + [["Rana"]] + gap + [["Dede"]]))
    twice = build(simple([["Rana", "Dede"]] + gap + [["Rana", "Dede"]] + gap + [["Rana"]] + gap + [["Dede"]]))
    assert once.relations == []
    assert len(twice.relations) == 1 and twice.relations[0][4] == 2


def test_consecutive_paragraphs_count_towards_the_same_pair():
    result = build(simple([["Rana"], ["Dede"], ["Rana"], ["Dede"], ["Rana"], ["Dede"]]))
    assert len(result.relations) == 1
    assert result.relations[0][4] >= 2


def test_pairs_far_apart_are_not_related():
    scenes = simple([["Rana"]] * 3 + [[] for _ in range(5)] + [["Dede"]] * 3)
    assert build(scenes).relations == []


def test_relations_are_kept_per_chapter():
    scenes = simple([["Rana", "Dede"]] * 2, chapter=1) + simple([["Rana", "Dede"]] * 3, chapter=2)
    result = build(scenes)
    assert sorted((chapter, weight) for chapter, _, _, _, weight in result.relations) == [(1, 2), (2, 3)]


def test_a_relation_without_any_cue_is_an_acquaintance():
    result = build(simple([["Rana", "Dede"]] * 3))
    assert [kind for _, _, _, kind, _ in result.relations] == ["kenalan"]


def test_relationship_words_in_the_shared_paragraphs_decide_the_kind():
    def kind_for(text):
        paragraphs = [para(text) for _ in range(3)]
        result = characters.build(paragraphs, [["Rana", "Dede"]] * 3)
        return result.relations[0][3]

    assert kind_for("Rana dan Dede adalah sahabat karib.") == "sahabat"
    assert kind_for("Rana mencium Dede, kekasih tercintanya.") == "pasangan"
    assert kind_for("Rana dan Dede adalah saudara, kakak dan adik.") == "keluarga"
    assert kind_for("Rana dan Dede berteman, kawan lama.") == "teman"
    assert kind_for("Rana membenci Dede, musuh bebuyutannya.") == "musuh"


def test_a_single_cue_is_not_enough_to_name_a_relationship():
    paragraphs = [para("Rana bertemu Dede, sahabat."), para("Rana dan Dede berbicara."), para("Rana menatap Dede.")]
    result = characters.build(paragraphs, [["Rana", "Dede"]] * 3)
    assert result.relations[0][3] in ("sahabat", "kenalan")
    assert sum(1 for _ in result.relations) == 1


def test_conflict_in_at_least_40_percent_of_the_windows_makes_them_enemies():
    violent = [{"names": ["Rana", "Dede"], "violence": 0.9}] * 2
    calm = [{"names": ["Rana", "Dede"]}] * 3
    result = build(violent + calm)
    assert result.relations[0][3] == "musuh"


def test_less_conflict_than_that_does_not_make_them_enemies():
    violent = [{"names": ["Rana", "Dede"], "violence": 0.9}]
    calm = [{"names": ["Rana", "Dede"]}] * 6
    result = build(violent + calm)
    assert result.relations[0][3] == "kenalan"


def test_each_kind_of_conflict_signal_counts():
    def kind_for(**signal):
        scenes = [{"names": ["Rana", "Dede"], **signal}] * 3
        return build(scenes).relations[0][3]

    assert kind_for(violence=0.5) == "musuh"
    assert kind_for(profanity=0.5) == "musuh"
    assert kind_for(emotion="angry", emotion_score=0.6) == "musuh"
    assert kind_for(violence=0.49) == "kenalan"
    assert kind_for(profanity=0.49) == "kenalan"
    assert kind_for(emotion="angry", emotion_score=0.59) == "kenalan"
    assert kind_for(emotion="sad", emotion_score=0.99) == "kenalan"


def test_a_chapter_without_cues_takes_the_kind_of_the_whole_book():
    paragraphs = (
        [para("Rana dan Dede adalah sahabat karib, teman baik.", chapter=1) for _ in range(3)]
        + [para("Rana dan Dede berjalan.", chapter=2) for _ in range(3)]
    )
    result = characters.build(paragraphs, [["Rana", "Dede"]] * 6)
    kinds = {chapter: kind for chapter, _, _, kind, _ in result.relations}
    assert kinds == {1: "sahabat", 2: "sahabat"}


def test_the_basic_biodata_states_the_role_and_how_often_the_name_appears():
    result = build(names_only({"Rana": 6, "Dede": 4}))
    rana = by_name(result)["Rana"]
    assert rana.biodata.startswith("Rana adalah tokoh utama")


def test_the_basic_biodata_quotes_the_first_description_in_the_text():
    paragraphs = [para("Budi, seorang guru matematika, datang.")] + [para("Budi pulang.") for _ in range(3)]
    result = characters.build(paragraphs, [["Budi"]] * 4)
    assert "seorang guru matematika" in result.characters[0].biodata


def test_paragraphs_with_sexual_content_are_never_quoted_in_the_biodata():
    paragraphs = [para("Budi, seorang kekasih rahasia, datang.", sexual=0.9)] + [para("Budi pulang.") for _ in range(3)]
    result = characters.build(paragraphs, [["Budi"]] * 4)
    assert "rahasia" not in result.characters[0].biodata


def test_characters_remember_the_chapters_where_they_appear():
    scenes = simple([["Rana"]] * 2, chapter=1) + simple([["Rana"]] * 2, chapter=3)
    assert build(scenes).characters[0].chapters == {1, 3}


def test_ai_receives_candidates_with_short_snippets_and_without_sexual_paragraphs():
    seen = {}

    def fake_ai(items):
        seen["items"] = items
        return []

    paragraphs = [para(f"Rana melakukan hal nomor {i} dengan penuh semangat dan keyakinan.") for i in range(10)]
    paragraphs.append(para("Rana RAHASIA-INTIM di sini.", sexual=0.9))
    mentions = [["Rana"]] * 11
    characters.build(paragraphs, mentions, ai_fn=fake_ai)
    [item] = seen["items"]
    assert item["name"] == "Rana" and len(item["snippets"]) == 3
    assert all(len(s) <= 203 for s in item["snippets"])
    assert "RAHASIA" not in " ".join(item["snippets"])


def test_ai_is_asked_about_at_most_twelve_names():
    seen = {}

    def fake_ai(items):
        seen["n"] = len(items)
        return []

    counts = {f"Tokoh{chr(65 + i)}{chr(97 + i)}": 10 for i in range(20)}
    paragraphs, mentions = book([dict(s) for s in names_only(counts)])
    characters.build(paragraphs, mentions, ai_fn=fake_ai)
    assert seen["n"] == 12


def test_ai_merges_names_that_are_the_same_person_and_fills_the_profile():
    def fake_ai(items):
        ids = {item["name"]: item["id"] for item in items}
        return [{
            "ids": [ids["Rana"], ids["Nara"]], "gender": "Perempuan", "age": "Dewasa muda", "occupation": "Mahasiswa",
            "personality": "Pendiam dan teliti.", "background": "Anak sulung.", "summary": "Rana adalah mahasiswa pendiam.",
        }]

    result = build(names_only({"Rana": 6, "Nara": 3, "Dede": 4}), ai_fn=fake_ai)
    people = by_name(result)
    assert set(people) == {"Rana", "Dede"}
    rana = people["Rana"]
    assert rana.count == 9 and "Nara" in rana.aliases
    assert rana.profile["gender"] == "Perempuan" and rana.profile["personality"] == "Pendiam dan teliti."
    assert rana.biodata == "Rana adalah mahasiswa pendiam."
    assert people["Dede"].profile["personality"] is None


def test_ai_does_not_override_facts_found_in_the_text():
    paragraphs = [para("Mr Budi berkata dia lelah.") for _ in range(4)]

    def fake_ai(items):
        return [{"ids": [0], "gender": "Perempuan", "age": None, "occupation": None, "personality": "Ceria.", "background": None, "summary": ""}]

    result = characters.build(paragraphs, [["Mr Budi"]] * 4, ai_fn=fake_ai)
    assert result.characters[0].profile["gender"] == "Laki-laki"
    assert result.characters[0].profile["personality"] == "Ceria."
    assert result.characters[0].name == "Mr Budi"
    assert result.characters[0].biodata.startswith("Mr Budi adalah")


def test_when_ai_returns_nothing_the_basic_result_is_kept():
    result = build(names_only({"Rana": 6, "Dede": 4}), ai_fn=lambda items: None)
    assert sorted(c.name for c in result.characters) == ["Dede", "Rana"]
    assert result.characters[0].profile["personality"] is None
