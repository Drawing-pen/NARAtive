import pytest

from app.extraction import pdf_markdown as pm
from tests.builders import blank_pdf, make_pdf, prose

HEADER = "Kumpulan Cerita Rana dan Dede Edisi Pertama"


def assemble(pages, toc=None, count=None):
    return pm.assemble(pages, toc or [], count or len(pages))


def texts(blocks):
    return [b.text for _, b in blocks]


class TestChapters:
    def test_regex_headings_start_chapters(self):
        titles, blocks = assemble([f"Bab 1\n\n{prose(2)}", f"Bab 2\n\n{prose(2, 3)}"])
        assert titles == ["Bab 1", "Bab 2"] and [n for n, _ in blocks] == [1, 2]

    @pytest.mark.parametrize("heading", ["Chapter 3", "Bagian Dua", "Episode 5", "Prolog", "Epilog", "Pendahuluan"])
    def test_other_heading_styles(self, heading):
        titles, _ = assemble([f"{heading}\n\n{prose(2)}", f"Bab 9\n\n{prose(2, 3)}"])
        assert heading in titles

    def test_markdown_headings_count_even_when_the_text_has_no_keyword(self):
        titles, blocks = assemble([f"# **Awal Mula**\n\n{prose(2)}", f"# **Pertemuan**\n\n{prose(2, 3)}"])
        assert titles == ["Awal Mula", "Pertemuan"] and [n for n, _ in blocks] == [1, 2]

    def test_a_chapter_title_is_not_repeated_as_a_block(self):
        _, blocks = assemble([f"# Bab 1\n\n{prose(2)}", f"# Bab 2\n\n{prose(2, 3)}"])
        assert not any(t.startswith("Bab ") for t in texts(blocks))

    def test_a_subtitle_joins_the_heading(self):
        titles, _ = assemble([f"# **Bab 1**\n\n## _Awal Mula_\n\n{prose(2)}", f"Bab 2\n\n{prose(2, 3)}"])
        assert titles[0] == "Bab 1 — Awal Mula"

    def test_lower_level_headings_stay_as_blocks(self):
        _, blocks = assemble([f"Bab 1\n\n{prose(2)}\n\n### Sub bagian\n\n{prose(2, 3)}", f"Bab 2\n\n{prose(2, 4)}"])
        kinds = [(b.kind, b.level) for _, b in blocks]
        assert ("h", 3) in kinds

    def test_text_before_the_first_heading_is_an_opening_chapter(self):
        titles, blocks = assemble([f"{prose(2)}\n\nBab 1\n\n{prose(2, 3)}", f"Bab 2\n\n{prose(2, 4)}"])
        assert titles == ["Pembuka", "Bab 1", "Bab 2"] and [n for n, _ in blocks] == [1, 2, 3]

    def test_without_headings_there_is_one_chapter(self):
        titles, blocks = assemble([prose(3), prose(3, 2)])
        assert titles == ["Isi naskah"] and {n for n, _ in blocks} == {1}

    def test_a_table_of_contents_is_not_turned_into_chapters(self):
        toc_page = "Bab 1\n\nBab 2\n\nBab 3\n\nBab 4"
        titles, _ = assemble([toc_page, f"Bab 1\n\n{prose(2)}", f"Bab 2\n\n{prose(2, 3)}"])
        assert titles == ["Bab 1", "Bab 2"]

    def test_the_pdf_outline_gives_the_titles(self):
        pages = [f"Awal Mula\n\n{prose(2)}", f"Pertemuan\n\n{prose(2, 3)}", f"Akhir\n\n{prose(2, 4)}"]
        toc = [[1, "Awal Mula", 1], [1, "Pertemuan", 2], [1, "Akhir", 3]]
        titles, blocks = assemble(pages, toc)
        assert titles == ["Awal Mula", "Pertemuan", "Akhir"] and [n for n, _ in blocks] == [1, 2, 3]

    def test_an_outline_title_missing_from_the_page_is_inserted(self):
        pages = [prose(2), prose(2, 3), prose(2, 4)]
        toc = [[1, "Awal", 1], [1, "Tengah", 2], [1, "Akhir", 3]]
        titles, blocks = assemble(pages, toc)
        assert titles == ["Awal", "Tengah", "Akhir"] and [n for n, _ in blocks] == [1, 2, 3]

    def test_a_long_book_without_headings_is_split_every_twenty_pages(self):
        pages = [f"{prose(1, i)} Nomor unik {i * 7919}." for i in range(1, 46)]
        titles, blocks = assemble(pages)
        assert len(titles) == 3 and titles[0].startswith("Halaman 1") and titles[-1].startswith("Halaman 41")
        assert {n for n, _ in blocks} == {1, 2, 3}

    def test_a_short_book_without_headings_is_not_split_by_pages(self):
        titles, _ = assemble([f"{prose(1, i)} Nomor unik {i * 7919}." for i in range(1, 11)])
        assert titles == ["Isi naskah"]

    def test_too_many_large_headings_are_not_chapters(self):
        pages = [f"# Judul nomor {2 * i}\n\n{prose(1, i)}\n\n# Judul nomor {2 * i + 1}\n\n{prose(1, i + 3)}" for i in range(6)]
        titles, _ = assemble(pages)
        assert titles == ["Isi naskah"]


class TestCleaning:
    def test_page_numbers_at_the_edge_are_removed(self):
        _, blocks = assemble([f"Bab 1\n\n{prose(2)}\n\n1", f"{prose(2, 3)}\n\n2"])
        assert not any(t.strip().isdigit() for t in texts(blocks))

    def test_a_running_header_is_removed_from_a_book_of_eight_pages_or_more(self):
        pages = [f"{HEADER}\n\n{prose(2, i)}\n\n{i}" for i in range(1, 11)]
        _, blocks = assemble(pages)
        assert blocks and not any("Kumpulan Cerita" in t for t in texts(blocks))

    @pytest.mark.parametrize("count,removed", [(3, False), (7, False), (8, True)])
    def test_the_header_threshold(self, count, removed):
        pages = [f"{HEADER}\n\n{prose(2, i)}" for i in range(1, count + 1)]
        _, blocks = assemble(pages)
        assert any("Kumpulan Cerita" in t for t in texts(blocks)) is not removed

    def test_a_roman_numeral_chapter_heading_is_not_mistaken_for_a_page_number(self):
        titles, blocks = assemble([f"# IV\n\n{prose(2)}", f"# V\n\n{prose(2, 3)}"])
        assert titles == ["IV", "V"] and len(blocks) == 2

    def test_a_sentence_split_across_pages_is_joined(self):
        pages = [f"{prose(1)} Rana pergi ke", f"pasar kemarin sore bersama Dede. {prose(1, 3)}"]
        _, blocks = assemble(pages)
        assert any("pergi ke pasar kemarin" in t for t in texts(blocks))

    def test_a_new_paragraph_on_the_next_page_is_not_joined(self):
        pages = [f"{prose(1)}", f"{prose(1, 3)}"]
        _, blocks = assemble(pages)
        assert texts(blocks) == [f"{prose(1)}\n{prose(1, 3)}"]

    def test_ligatures_and_urls_are_cleaned(self):
        _, blocks = assemble(["Bab 1\n\nKantor oﬃce kami ada di www.contoh.blogspot.com dekat pasar lama itu.", f"Bab 2\n\n{prose(2)}"])
        first = texts(blocks)[0]
        assert "office" in first and "blogspot" not in first

    def test_tiny_paragraphs_are_dropped(self):
        _, blocks = assemble([f"Bab 1\n\nTamat.\n\n{prose(2)}", f"Bab 2\n\n{prose(2, 3)}"])
        assert all(len(b.text) >= 20 for _, b in blocks if b.kind == "p")


class TestMarkdownIsKept:
    def test_bold_and_italic_survive_with_plain_text_alongside(self):
        _, blocks = assemble(["Bab 1\n\nRana **berlari** cepat dan _sangat_ jauh melewati jalan sepi itu.", f"Bab 2\n\n{prose(2)}"])
        block = blocks[0][1]
        assert "**berlari**" in block.markdown and block.text == "Rana berlari cepat dan sangat jauh melewati jalan sepi itu."

    def test_spaces_inside_marks_are_tidied(self):
        _, blocks = assemble(["Bab 1\n\nRana **berlari **cepat sekali melewati jalan yang sangat sepi itu.", f"Bab 2\n\n{prose(2)}"])
        assert "**berlari** cepat" in blocks[0][1].markdown

    def test_lists_and_quotes_keep_their_kind(self):
        page = "Bab 1\n\n- butir pertama yang cukup panjang\n- butir kedua yang cukup panjang\n\n> kutipan yang cukup panjang untuk dibaca"
        _, blocks = assemble([page, f"Bab 2\n\n{prose(2)}"])
        assert [b.kind for _, b in blocks[:3]] == ["li", "li", "quote"]

    def test_a_long_paragraph_is_cut_with_balanced_marks(self):
        _, blocks = assemble([f"Bab 1\n\n**{prose(40)}**", f"Bab 2\n\n{prose(2)}"])
        long_blocks = [b for n, b in blocks if n == 1]
        assert len(long_blocks) > 1 and all(b.markdown.count("**") % 2 == 0 for b in long_blocks)
        assert all(len(b.text) <= 1000 for b in long_blocks)

    def test_images_and_rules_are_dropped(self):
        _, blocks = assemble([f"Bab 1\n\n![gambar](a.png)\n\n---\n\n{prose(2)}", f"Bab 2\n\n{prose(2, 3)}"])
        assert all("gambar" not in b.text and "---" not in b.markdown for _, b in blocks)


def dialogue(count, start=0):
    return "\n\n".join(f"”Kamu bisa ikut latihan sore ini, Kawan nomor {start + i}?”" for i in range(count))


class TestPacking:
    def test_short_paragraphs_are_packed_up_to_the_limit(self):
        _, blocks = assemble([f"Bab 1\n\n{dialogue(40)}", f"Bab 2\n\n{prose(2)}"])
        first = [b for n, b in blocks if n == 1]
        assert 1 < len(first) < 10 and all(len(b.text) <= 900 for b in first)
        assert sum(b.text.count("Kawan nomor") for b in first) == 40

    def test_order_is_kept_inside_packs(self):
        _, blocks = assemble([f"Bab 1\n\n{dialogue(40)}", f"Bab 2\n\n{prose(2)}"])
        numbers = [int(x) for b in blocks if b[0] == 1 for x in __import__("re").findall(r"nomor (\d+)", b[1].text)]
        assert numbers == list(range(40))

    def test_packs_never_cross_a_chapter(self):
        _, blocks = assemble([f"Bab 1\n\n{dialogue(2)}", f"Bab 2\n\n{dialogue(2, 50)}"])
        assert [n for n, _ in blocks] == [1, 2]
        assert "nomor 0" in blocks[0][1].text and "nomor 50" in blocks[1][1].text

    def test_a_list_cuts_the_pack_and_stays_a_list(self):
        page = f"Bab 1\n\n{dialogue(2)}\n\n- butir pertama yang cukup panjang\n- butir kedua yang cukup panjang\n\n{dialogue(2, 10)}"
        _, blocks = assemble([page, f"Bab 2\n\n{prose(2)}"])
        assert [b.kind for _, b in blocks[:4]] == ["p", "li", "li", "p"]


class TestDialogueMisreadAsList:
    def test_a_single_quoted_item_becomes_a_paragraph(self):
        page = "Bab 1\n\nAli mengangguk dan menunjuk dirinya dengan sendok.\n\n- ”Pemain terbaik, Ra, itu aku sendiri?”\n\nAku mendengus panjang."
        _, blocks = assemble([page, f"Bab 2\n\n{prose(2)}"])
        assert all(b.kind == "p" for n, b in blocks if n == 1)
        assert any("Pemain terbaik" in b.text for _, b in blocks)

    def test_a_run_of_dialogue_lines_becomes_paragraphs(self):
        page = "Bab 1\n\n- Pelayan itu berdiri di depan kami dan tersenyum.\n- ”Apakah kalian sudah siap dengan menu utama?”\n- Ali mengangguk dengan gerakan sempurna.\n\nPenutup cerita yang cukup panjang."
        _, blocks = assemble([page, f"Bab 2\n\n{prose(2)}"])
        assert all(b.kind == "p" for n, b in blocks if n == 1)

    def test_a_numbered_list_with_quotes_is_kept(self):
        page = "Bab 1\n\n1. ”butir pertama yang cukup panjang”\n2. ”butir kedua yang cukup panjang”\n\nPenutup cerita yang cukup panjang."
        _, blocks = assemble([page, f"Bab 2\n\n{prose(2)}"])
        assert [b.kind for _, b in blocks[:2]] == ["li", "li"]

    def test_a_list_without_quotes_is_kept(self):
        page = "Bab 1\n\n- butir pertama yang cukup panjang\n- butir kedua yang cukup panjang\n\nPenutup."
        _, blocks = assemble([page, f"Bab 2\n\n{prose(2)}"])
        assert [b.kind for _, b in blocks[:2]] == ["li", "li"]

    def test_a_single_unquoted_item_is_kept(self):
        _, blocks = assemble(["Bab 1\n\nPembuka cerita yang cukup panjang.\n\n- satu butir daftar yang cukup panjang\n\nPenutup cerita yang cukup panjang.", f"Bab 2\n\n{prose(2)}"])
        assert "li" in [b.kind for _, b in blocks]


class TestBrokenSentences:
    def test_a_word_split_over_two_blocks_is_rejoined(self):
        page = "Bab 1\n\n- ”Hei, Ali.” Kapten mereka datang dan me-\n\n- nepuk bahu Ali dengan keras sekali.\n\nAli mendongak."
        _, blocks = assemble([page, f"Bab 2\n\n{prose(2)}"])
        joined = " ".join(b.text for n, b in blocks if n == 1)
        assert "menepuk bahu Ali" in joined and "me-" not in joined

    def test_a_dash_before_a_capital_is_kept(self):
        page = "Bab 1\n\nMereka menunggu di stasiun sampai pukul sembilan dan-\n\nMalam itu hujan turun deras sekali di kota."
        _, blocks = assemble([page, f"Bab 2\n\n{prose(2)}"])
        assert "dan-" in " ".join(b.text for n, b in blocks if n == 1)

    def test_a_sentence_cut_by_a_line_break_is_joined(self):
        page = "Bab 1\n\nRombongan murid kelas\n\ndua belas itu menuju pojok kantin sekolah.\n\nAli mendongak dengan terkejut."
        _, blocks = assemble([page, f"Bab 2\n\n{prose(2)}"])
        assert "murid kelas dua belas itu" in " ".join(b.text for n, b in blocks if n == 1)

    def test_a_paragraph_ending_a_sentence_is_not_joined_to_a_lowercase_start(self):
        page = "Bab 1\n\nAli menunggu di depan pintu sekolah.\n\nsetelah itu dia pulang sendirian ke rumah."
        _, blocks = assemble([page, f"Bab 2\n\n{prose(2)}"])
        assert "sekolah.\nsetelah" in " ".join(b.text for n, b in blocks if n == 1)


class TestReadPdfMarkdown:
    @pytest.fixture
    def read(self, tmp_path):
        def run(data):
            path = tmp_path / "buku.pdf"
            path.write_bytes(data)
            return pm.read_pdf_markdown(str(path))

        return run

    def test_a_real_pdf_gives_chapters_and_markdown(self, read):
        data = make_pdf([f"Bab 1\n\n{prose(3)}", f"Bab 2\n\n{prose(3, 4)}"], sizes={"Bab 1": 22, "Bab 2": 22})
        count, titles, blocks = read(data)
        assert count == 2 and titles == ["Bab 1", "Bab 2"]
        assert {n for n, _ in blocks} == {1, 2} and all(b.text for _, b in blocks)

    def test_large_headings_without_a_keyword_become_chapters(self, read):
        data = make_pdf([f"Awal\n\n{prose(3)}", f"Tengah\n\n{prose(3, 2)}"], sizes={"Awal": 22, "Tengah": 22})
        assert read(data)[1] == ["Awal", "Tengah"]

    def test_page_numbers_and_headers_are_removed(self, read):
        pages = [prose(2, i) for i in range(1, 11)]
        _, _, blocks = read(make_pdf(pages, header=HEADER, footer_numbers=True))
        assert blocks and not any("Kumpulan Cerita" in b.text or b.text.strip().isdigit() for _, b in blocks)

    def test_the_pdf_outline_is_used(self, read):
        pages = [f"Awal Mula\n\n{prose(3)}", f"Pertemuan\n\n{prose(3, 2)}", f"Akhir\n\n{prose(3, 4)}"]
        toc = [[1, "Awal Mula", 1], [1, "Pertemuan", 2], [1, "Akhir", 3]]
        assert read(make_pdf(pages, toc=toc))[1] == ["Awal Mula", "Pertemuan", "Akhir"]

    def test_a_pdf_without_text_gives_no_blocks(self, read):
        assert read(blank_pdf(3))[2] == []

    def test_a_corrupt_file_raises(self, tmp_path):
        path = tmp_path / "rusak.pdf"
        path.write_bytes(b"%PDF-1.4 rusak")
        with pytest.raises(Exception):
            pm.read_pdf_markdown(str(path))
