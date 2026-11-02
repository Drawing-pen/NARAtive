import pytest

from app.extraction import pdf_utils as pdf
from tests.builders import blank_pdf, make_pdf, prose


@pytest.fixture
def read(tmp_path):
    def run(data: bytes):
        path = tmp_path / "buku.pdf"
        path.write_bytes(data)
        return pdf.read_pdf(str(path))

    return run


class TestCleanText:
    def test_ligatures_are_expanded(self):
        assert pdf.clean_text("oﬃce ﬁnal ﬂow") == "office final flow"

    def test_soft_hyphens_vanish(self):
        assert pdf.clean_text("pem­baca") == "pembaca"

    def test_whitespace_is_collapsed(self):
        assert pdf.clean_text("  satu \n\t dua   tiga  ") == "satu dua tiga"

    def test_control_characters_are_removed(self):
        assert pdf.clean_text("ha\u0001lo​ dunia") == "halo dunia"

    def test_urls_are_removed(self):
        text = pdf.clean_text("Baca juga di www.contoh.blogspot.com untuk lanjutannya")
        assert "blogspot" not in text and text.startswith("Baca juga di")

    def test_a_hyphen_at_a_line_break_keeps_the_compound_word(self):
        assert pdf.clean_text("kata- kata") == "kata-kata"

    def test_a_function_word_glued_to_the_next_word_is_separated(self):
        assert pdf.clean_text("one ofThe best") == "one of The best"

    def test_normal_text_is_untouched(self):
        sentence = "Rana berjalan pulang melewati jalan yang sepi."
        assert pdf.clean_text(sentence) == sentence


class TestChunkLong:
    def test_a_short_paragraph_is_unchanged(self):
        assert pdf._chunk_long("Pendek saja.") == ["Pendek saja."]

    def test_a_long_paragraph_splits_at_sentence_ends(self):
        text = prose(30)
        chunks = pdf._chunk_long(text)
        assert len(chunks) > 1
        assert all(len(c) <= pdf.MAX_PARAGRAPH_CHARS + 100 for c in chunks)
        assert all(c.endswith(".") for c in chunks)

    def test_nothing_is_lost_when_splitting(self):
        text = prose(30)
        assert " ".join(pdf._chunk_long(text)).split() == text.split()

    def test_exactly_the_maximum_is_kept_whole(self):
        text = ("a" * (pdf.MAX_PARAGRAPH_CHARS - 1)) + "."
        assert pdf._chunk_long(text) == [text]


class TestJoinPages:
    def test_a_new_page_starting_a_sentence_starts_a_new_paragraph(self):
        assert pdf._join_pages(["Kalimat selesai.", "Kalimat baru."]) == "Kalimat selesai.\n\nKalimat baru."

    def test_a_sentence_continuing_on_the_next_page_stays_together(self):
        joined = pdf._join_pages(["Rana pergi ke", "pasar kemarin."])
        assert "\n\n" not in joined and joined.startswith("Rana pergi ke")

    def test_a_lowercase_start_after_a_full_stop_is_a_new_paragraph(self):
        assert "\n\n" in pdf._join_pages(["Selesai.", "lanjut huruf kecil"])


class TestSplitChapters:
    def split(self, text, **kw):
        return pdf.split_chapters(text, **kw)

    def test_numbered_headings_become_chapters(self):
        titles, paras = self.split(f"Bab 1\n\n{prose(2)}\n\nBab 2\n\n{prose(2, 3)}")
        assert titles == ["Bab 1", "Bab 2"]
        assert [n for n, _ in paras] == [1, 2]

    @pytest.mark.parametrize("heading", ["Chapter 3", "CHAPTER IV", "Bagian Dua", "Episode 5", "Part One"])
    def test_other_heading_styles_are_recognised(self, heading):
        titles, _ = self.split(f"{heading}\n\n{prose(2)}")
        assert titles == [heading]

    @pytest.mark.parametrize("heading", ["Prolog", "Epilog", "Pendahuluan", "Penutup", "Kata Pengantar"])
    def test_standalone_headings_are_recognised(self, heading):
        titles, _ = self.split(f"{heading}\n\n{prose(2)}")
        assert titles == [heading]

    def test_a_subtitle_on_the_next_line_joins_the_heading(self):
        titles, _ = self.split(f"Bab 1\nAwal Mula\n\n{prose(2)}")
        assert titles == ["Bab 1 — Awal Mula"]

    def test_without_headings_there_is_one_chapter(self):
        titles, paras = self.split(prose(3))
        assert titles == ["Isi naskah"] and [n for n, _ in paras] == [1]

    def test_text_before_the_first_heading_becomes_an_opening_chapter(self):
        titles, paras = self.split(f"{prose(2)}\n\nBab 1\n\n{prose(2, 2)}")
        assert titles == ["Pembuka", "Bab 1"]
        assert [n for n, _ in paras] == [1, 2]

    def test_fragments_shorter_than_twenty_characters_are_dropped(self):
        _, paras = self.split(f"Bab 1\n\nTamat.\n\n{prose(2)}")
        assert all(len(t) >= 20 for _, t in paras)

    def test_a_table_of_contents_is_not_turned_into_chapters(self):
        toc = "Bab 1\nBab 2\nBab 3\nBab 4"
        titles, _ = self.split(f"{toc}\n\nBab 1\n\n{prose(2)}\n\nBab 2\n\n{prose(2, 2)}")
        assert titles == ["Bab 1", "Bab 2"]

    def test_extra_headings_supplied_by_the_caller_are_used(self):
        titles, _ = self.split(f"Awal Mula\n\n{prose(2)}\n\nPertemuan\n\n{prose(2, 2)}", extra={"Awal Mula", "Pertemuan"})
        assert titles == ["Awal Mula", "Pertemuan"]

    def test_a_long_paragraph_is_cut_into_pieces(self):
        _, paras = self.split(f"Bab 1\n\n{prose(40)}")
        assert len(paras) > 1 and all(n == 1 for n, _ in paras)

    def test_lines_of_a_paragraph_are_merged(self):
        _, paras = self.split("Bab 1\n\nRana berjalan pulang melewati\njalan yang sepi dan gelap sekali.")
        assert paras == [(1, "Rana berjalan pulang melewati jalan yang sepi dan gelap sekali.")]


class TestReadPdf:
    def test_page_count_is_reported(self, read):
        count, _, _ = read(make_pdf([prose(2, i) for i in range(3)]))
        assert count == 3 and pdf.count_pages is not None

    def test_chapters_come_from_headings_in_the_text(self, read):
        _, titles, paras = read(make_pdf([f"Bab 1\n\n{prose(3)}", f"Bab 2\n\n{prose(3, 4)}"]))
        assert titles == ["Bab 1", "Bab 2"]
        assert {n for n, _ in paras} == {1, 2}

    def test_each_paragraph_lands_in_the_right_chapter(self, read):
        _, titles, paras = read(make_pdf([f"Bab 1\n\n{SENTENCES_ONE}", f"Bab 2\n\n{SENTENCES_TWO}"]))
        assert all("Rana berjalan" in t for n, t in paras if n == 1)
        assert all("Hujan turun" in t for n, t in paras if n == 2)

    def test_a_pdf_without_headings_is_one_chapter(self, read):
        _, titles, paras = read(make_pdf([prose(3), prose(3, 2)]))
        assert titles == ["Isi naskah"] and {n for n, _ in paras} == {1}

    def test_the_pdf_outline_gives_the_chapter_titles(self, read):
        pages = [f"Awal Mula\n\n{prose(3)}", f"Pertemuan\n\n{prose(3, 2)}", f"Akhir\n\n{prose(3, 4)}"]
        toc = [[1, "Awal Mula", 1], [1, "Pertemuan", 2], [1, "Akhir", 3]]
        _, titles, paras = read(make_pdf(pages, toc=toc))
        assert titles == ["Awal Mula", "Pertemuan", "Akhir"]
        assert [n for n, _ in paras] == [1, 2, 3]

    def test_big_lines_are_used_as_titles_when_nothing_else_works(self, read):
        pages = [f"Awal\n\n{prose(3)}", f"Tengah\n\n{prose(3, 2)}"]
        _, titles, _ = read(make_pdf(pages, sizes={"Awal": 22, "Tengah": 22}))
        assert titles == ["Awal", "Tengah"]

    def test_page_numbers_in_the_margin_are_removed(self, read):
        _, _, paras = read(make_pdf([f"Bab 1\n\n{prose(3)}", f"Bab 2\n\n{prose(3, 2)}"], footer_numbers=True))
        assert not any(t.rstrip().endswith((" 1", " 2")) or t in {"1", "2"} for _, t in paras)

    def test_a_running_header_is_removed_from_a_longer_book(self, read):
        header = "Kumpulan Cerita Rana dan Dede Edisi Pertama"
        pages = [prose(2, i) for i in range(1, 11)]
        _, _, paras = read(make_pdf(pages, header=header))
        assert paras and not any("Kumpulan Cerita" in t for _, t in paras)

    @pytest.mark.parametrize("pages,removed", [(3, False), (7, False), (8, True)])
    def test_headers_are_only_removed_from_books_of_eight_pages_or_more(self, read, pages, removed):
        header = "Kumpulan Cerita Rana dan Dede Edisi Pertama"
        _, _, paras = read(make_pdf([prose(2, i) for i in range(1, pages + 1)], header=header))
        assert paras and any("Kumpulan Cerita" in t for _, t in paras) is not removed

    def test_a_long_pdf_without_headings_is_split_every_twenty_pages(self, read):
        pages = [f"Halaman isi {i}. {prose(1, i)} Nomor unik {i * 7919}." for i in range(1, 46)]
        count, titles, paras = read(make_pdf(pages))
        assert count == 45 and len(titles) == 3
        assert titles[0].startswith("Halaman 1") and titles[-1].startswith("Halaman 41")
        assert {n for n, _ in paras} == {1, 2, 3}

    def test_a_pdf_without_any_text_gives_no_paragraphs(self, read):
        _, _, paras = read(blank_pdf(3))
        assert paras == []

    def test_a_corrupt_file_raises(self, tmp_path):
        path = tmp_path / "rusak.pdf"
        path.write_bytes(b"%PDF-1.4 ini bukan pdf yang sebenarnya")
        with pytest.raises(Exception):
            pdf.read_pdf(str(path))

    def test_count_pages_matches_read_pdf(self, tmp_path):
        path = tmp_path / "b.pdf"
        path.write_bytes(make_pdf([prose(2), prose(2, 1), prose(2, 2)]))
        assert pdf.count_pages(str(path)) == 3


SENTENCES_ONE = "Rana berjalan pulang melewati jalan yang sepi sambil memikirkan semua kejadian hari itu."
SENTENCES_TWO = "Hujan turun pelan ketika mereka akhirnya duduk berdua di beranda yang berderit tua itu."
