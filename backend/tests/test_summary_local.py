from app.services import summary_local

ALL_FILTERED = "Bab ini sebagian besar berisi adegan yang dilewati dalam rangkuman (kekerasan, bahasa kasar, atau konten dewasa)."
ALL_FILTERED_BOOK = "Buku ini sebagian besar berisi adegan yang dilewati dalam rangkuman (kekerasan, bahasa kasar, atau konten dewasa)."
UNAVAILABLE = "Rangkuman bab ini tidak dapat dibuat."


def sentences(n):
    return [f"Kalimat {i}." for i in range(1, n + 1)]


def test_a_short_chapter_keeps_all_its_sentences_in_order():
    assert summary_local.chapter_summary(["Satu hari. Dua hari.", "Tiga hari."]) == "Satu hari. Dua hari. Tiga hari."


def test_a_long_chapter_keeps_the_opening_the_middle_and_the_end():
    result = summary_local.chapter_summary([" ".join(sentences(10))])
    assert result == "Kalimat 1. Kalimat 2. Kalimat 6. Kalimat 10."


def test_exactly_four_sentences_are_all_kept():
    assert summary_local.chapter_summary([" ".join(sentences(4))]) == "Kalimat 1. Kalimat 2. Kalimat 3. Kalimat 4."


def test_sentences_are_split_across_paragraphs_and_punctuation():
    result = summary_local.chapter_summary(["Apakah dia pergi? Ya! Tentu saja."])
    assert result == "Apakah dia pergi? Ya! Tentu saja."


def test_very_long_sentences_are_shortened_to_220_characters():
    result = summary_local.chapter_summary(["a" * 500 + "."])
    assert len(result) <= 220 and result.endswith("…")


def test_a_chapter_without_usable_text_gets_the_fixed_sentence():
    assert summary_local.chapter_summary([]) == ALL_FILTERED
    assert summary_local.chapter_summary(["   ", ""]) == ALL_FILTERED


def test_the_overall_summary_uses_the_first_sentence_of_each_chapter():
    result = summary_local.overall_summary(["Rana pulang. Lalu tidur.", "Dede datang. Pergi lagi."])
    assert result == "Rana pulang. Dede datang."


def test_the_overall_summary_uses_at_most_six_evenly_spread_chapters():
    chapters = [f"Bab {n} dimulai. Sisa bab." for n in range(1, 21)]
    result = summary_local.overall_summary(chapters)
    assert result.count("dimulai.") == 6
    assert result.startswith("Bab 1 dimulai.") and result.endswith("Bab 20 dimulai.")


def test_fixed_and_unavailable_chapters_are_left_out_of_the_overall_summary():
    result = summary_local.overall_summary([ALL_FILTERED, "Rana pulang.", UNAVAILABLE])
    assert result == "Rana pulang."


def test_an_overall_summary_without_any_usable_chapter_gets_the_fixed_sentence():
    assert summary_local.overall_summary([ALL_FILTERED, UNAVAILABLE]) == ALL_FILTERED_BOOK
    assert summary_local.overall_summary([]) == ALL_FILTERED_BOOK
