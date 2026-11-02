import re

import pytest

from app.extraction import markdown_utils as md
from tests.builders import prose


class TestPlainText:
    @pytest.mark.parametrize("source,expected", [
        ("Kalimat **tebal** dan _miring_ serta *miring lain*.", "Kalimat tebal dan miring serta miring lain."),
        ("# **Bab 1**", "Bab 1"),
        ("## _Awal Mula_", "Awal Mula"),
        ("### Judul kecil", "Judul kecil"),
        ("- butir satu", "butir satu"),
        ("* butir dua", "butir dua"),
        ("3. butir tiga", "butir tiga"),
        ("> kutipan penting", "kutipan penting"),
        ("Lihat [halaman ini](https://contoh.com/x) ya", "Lihat halaman ini ya"),
        ("Sebelum ![gambar](a.png) sesudah", "Sebelum sesudah"),
        ("Ada `kode` di sini", "Ada kode di sini"),
        ("Harga 5 \\* 3 sama dengan 15", "Harga 5 * 3 sama dengan 15"),
        ("Baris satu<br>baris dua", "Baris satu baris dua"),
        ("  spasi   berlebih \t di sini ", "spasi berlebih di sini"),
        ("***tebal miring***", "tebal miring"),
    ])
    def test_markup_is_stripped(self, source, expected):
        assert md.plain_text(source) == expected

    def test_snake_case_words_keep_their_underscores(self):
        assert md.plain_text("variabel kata_kata_ini tetap") == "variabel kata_kata_ini tetap"

    def test_a_multiplication_sign_is_not_taken_for_emphasis(self):
        assert md.plain_text("hitung 2*3*4 sekarang") == "hitung 2*3*4 sekarang"

    def test_paragraphs_of_one_block_are_joined_with_a_newline(self):
        assert md.plain_text("Paragraf **satu**.\n\nParagraf dua.") == "Paragraf satu.\nParagraf dua."

    def test_plain_text_is_unchanged(self):
        sentence = "Rana berjalan pulang melewati jalan yang sepi."
        assert md.plain_text(sentence) == sentence

    def test_html_in_the_book_stays_as_text(self):
        assert md.plain_text("<script>alert(1)</script> halo") == "alert(1) halo"


class TestSplitBlock:
    def test_a_short_block_is_returned_whole(self):
        assert md.split_block("Pendek **saja**.") == ["Pendek **saja**."]

    def test_a_long_block_is_cut_at_sentence_ends(self):
        pieces = md.split_block(prose(30))
        assert len(pieces) > 1 and all(len(md.plain_text(p)) <= 900 + 100 for p in pieces)
        assert all(p.rstrip().endswith(".") for p in pieces)

    def test_no_words_are_lost(self):
        text = prose(30)
        assert " ".join(md.split_block(text)).split() == text.split()

    def test_bold_that_spans_the_cut_is_closed_and_reopened(self):
        long = "**" + prose(30) + "**"
        pieces = md.split_block(long)
        assert len(pieces) > 1
        for piece in pieces:
            assert piece.count("**") % 2 == 0
        assert pieces[0].startswith("**") and pieces[-1].rstrip().endswith("**")

    def test_italic_that_spans_the_cut_is_closed_and_reopened(self):
        long = "_" + prose(30) + "_"
        pieces = md.split_block(long)
        for piece in pieces:
            assert len(re.findall(r"(?<!\w)_|_(?!\w)", piece)) % 2 == 0

    def test_a_cut_inside_a_span_keeps_the_plain_text_identical(self):
        long = "Awal " + "**" + prose(30) + "**" + " akhir."
        rebuilt = " ".join(md.plain_text(p) for p in md.split_block(long))
        assert rebuilt.split() == md.plain_text(long).split()

    def test_the_limit_can_be_changed(self):
        assert len(md.split_block(prose(4), limit=100)) > 1

    def test_a_single_huge_sentence_stays_in_one_piece(self):
        word = "kata " * 400
        assert len(md.split_block(word.strip() + ".")) == 1


class TestParseBlocks:
    def kinds(self, text):
        return [(b.kind, b.text) for b in md.parse_blocks(text)]

    def test_paragraphs_are_separated_by_blank_lines(self):
        assert self.kinds("Paragraf pertama yang cukup panjang.\n\nParagraf kedua yang cukup panjang.") == [
            ("p", "Paragraf pertama yang cukup panjang."), ("p", "Paragraf kedua yang cukup panjang."),
        ]

    def test_lines_inside_a_paragraph_are_joined(self):
        assert self.kinds("Baris satu\nbaris dua\nbaris tiga") == [("p", "Baris satu baris dua baris tiga")]

    def test_headings_carry_their_level(self):
        blocks = md.parse_blocks("# **Bab 1**\n\n## _Awal Mula_\n\n###### Terkecil")
        assert [(b.kind, b.level, b.text) for b in blocks] == [("h", 1, "Bab 1"), ("h", 2, "Awal Mula"), ("h", 6, "Terkecil")]

    def test_the_markdown_of_a_block_is_kept(self):
        [block] = md.parse_blocks("Kalimat **tebal** di sini.")
        assert block.markdown == "Kalimat **tebal** di sini." and block.text == "Kalimat tebal di sini."

    def test_each_list_item_is_its_own_block(self):
        assert self.kinds("- satu\n- dua\n- tiga") == [("li", "satu"), ("li", "dua"), ("li", "tiga")]

    def test_ordered_list_items_are_recognised(self):
        assert [b.kind for b in md.parse_blocks("1. satu\n2. dua")] == ["li", "li"]

    def test_a_wrapped_list_item_continues_on_the_next_line(self):
        assert self.kinds("- butir yang panjang\n  dan berlanjut di baris berikut\n- butir lain") == [
            ("li", "butir yang panjang dan berlanjut di baris berikut"), ("li", "butir lain"),
        ]

    def test_quotes_are_recognised(self):
        assert self.kinds("> kutipan baris satu\n> baris dua") == [("quote", "kutipan baris satu baris dua")]

    def test_images_and_rules_are_dropped(self):
        assert self.kinds("![gambar](a.png)\n\n---\n\nTeks yang tersisa di sini.") == [("p", "Teks yang tersisa di sini.")]

    def test_a_rule_separates_lines_that_have_no_blank_line_around_it(self):
        assert self.kinds("Kalimat satu yang cukup panjang.\n* * *\nKalimat dua yang cukup panjang.") == [
            ("p", "Kalimat satu yang cukup panjang."), ("p", "Kalimat dua yang cukup panjang."),
        ]

    def test_an_image_line_separates_the_text_around_it(self):
        assert self.kinds("Kalimat satu yang cukup panjang.\n![gambar](a.png)\nKalimat dua yang cukup panjang.") == [
            ("p", "Kalimat satu yang cukup panjang."), ("p", "Kalimat dua yang cukup panjang."),
        ]

    def test_a_table_is_flattened_to_text(self):
        table = "|Nama|Usia|\n|---|---|\n|Rana|20|\n|Dede|21|"
        [block] = md.parse_blocks(table)
        assert block.kind == "p" and "Rana" in block.text and "---" not in block.text and "|" not in block.text

    def test_code_fences_become_paragraphs(self):
        assert self.kinds("```\nteks dalam pagar\n```") == [("p", "teks dalam pagar")]

    def test_empty_blocks_are_skipped(self):
        assert md.parse_blocks("\n\n   \n\n**  **\n\n") == []

    def test_blocks_without_letters_are_skipped(self):
        assert md.parse_blocks("* * *\n\n12 34\n\nTeks yang tersisa di sini.")[0].text == "Teks yang tersisa di sini."


class TestCleanBlock:
    def test_the_prefix_is_kept_and_the_content_cleaned(self):
        assert md.clean_markdown("## oﬃce  baru") == "## office baru"

    def test_inline_marks_survive_cleaning(self):
        assert md.clean_markdown("Kata **ﬁnal**  dan _lain_") == "Kata **final** dan _lain_"

    def test_urls_are_removed(self):
        assert "blogspot" not in md.clean_markdown("Baca di www.contoh.blogspot.com sekarang")

    def test_list_markers_are_kept(self):
        assert md.clean_markdown("- butir  satu") == "- butir satu"


class TestTidyMarks:
    @pytest.mark.parametrize("source,expected", [
        ("**Rana **dan Dede", "**Rana** dan Dede"),
        ("Halo ** Rana** dan Dede", "Halo **Rana** dan Dede"),
        ("Halo _miring _lagi", "Halo _miring_ lagi"),
        ("Halo _ miring_ lagi", "Halo _miring_ lagi"),
        ("**tebal** biasa dan _miring_ biasa", "**tebal** biasa dan _miring_ biasa"),
        ("**tebal **_dan miring _", "**tebal** _dan miring_"),
    ])
    def test_spaces_inside_a_mark_move_outside(self, source, expected):
        assert md.tidy_marks(source) == expected

    def test_empty_marks_disappear(self):
        assert md.tidy_marks("sebelum **  ** sesudah").split() == ["sebelum", "sesudah"]

    @pytest.mark.parametrize("source,expected", [("**tidak ditutup", "tidak ditutup"), ("tanpa pembuka**", "tanpa pembuka"), ("_tidak ditutup lagi", "tidak ditutup lagi")])
    def test_a_mark_without_its_partner_is_removed(self, source, expected):
        assert md.tidy_marks(source) == expected

    def test_underscores_inside_words_are_left_alone(self):
        assert md.tidy_marks("variabel kata_kata_ini tetap") == "variabel kata_kata_ini tetap"

    def test_clean_markdown_tidies_marks_too(self):
        assert md.clean_markdown("Kata **\ufb01nal **dan lain") == "Kata **final** dan lain"


class TestCleanMarkdownLinks:
    def test_links_keep_only_their_text(self):
        assert md.clean_markdown("Buka [tautan ini](https://jahat.example/x) sekarang") == "Buka tautan ini sekarang"

    def test_images_are_removed(self):
        assert md.clean_markdown("Sebelum ![gambar](https://jahat.example/a.png) sesudah") == "Sebelum sesudah"

    def test_headings_keep_their_prefix_when_links_are_removed(self):
        assert md.clean_markdown("## Lihat [bagian](x) ini") == "## Lihat bagian ini"
