import io
import zipfile

import pytest

from app.extraction import epub_utils as epub
from tests.builders import drm_encryption, make_epub, prose


@pytest.fixture
def read(tmp_path):
    def run(data: bytes):
        path = tmp_path / "buku.epub"
        path.write_bytes(data)
        return epub.read_epub(str(path))

    return run


def p(text):
    return f"<p>{text}</p>"


def body(*paragraphs, heading=None, level=1):
    head = f"<h{level}>{heading}</h{level}>" if heading else ""
    return head + "".join(p(t) for t in paragraphs)


class TestChapters:
    def test_titles_come_from_the_epub3_navigation(self, read):
        data = make_epub(
            [("a.xhtml", body(prose(2))), ("b.xhtml", body(prose(2, 3)))],
            nav={"a.xhtml": "Awal Mula", "b.xhtml": "Pertemuan"},
        )
        _, titles, paras = read(data)
        assert titles == ["Awal Mula", "Pertemuan"]
        assert [n for n, _ in paras] == [1, 2]

    def test_titles_come_from_the_epub2_ncx(self, read):
        data = make_epub(
            [("a.xhtml", body(prose(2))), ("b.xhtml", body(prose(2, 3)))],
            ncx={"a.xhtml": "Satu", "b.xhtml": "Dua"},
        )
        assert read(data)[1] == ["Satu", "Dua"]

    def test_a_heading_gives_the_title_when_there_is_no_navigation(self, read):
        data = make_epub([("a.xhtml", body(prose(2), heading="Bab Pertama")), ("b.xhtml", body(prose(2, 3), heading="Bab Kedua"))])
        assert read(data)[1] == ["Bab Pertama", "Bab Kedua"]

    def test_a_level_two_heading_inside_a_file_starts_a_new_chapter(self, read):
        html = body(prose(2), heading="Bab Satu") + "<h2>Bab Dua</h2>" + p(prose(2, 3))
        _, titles, paras = read(make_epub([("a.xhtml", html)]))
        assert titles == ["Bab Satu", "Bab Dua"] and [n for n, _ in paras] == [1, 2]

    def test_a_level_three_heading_does_not_split(self, read):
        html = body(prose(2), heading="Bab Satu") + "<h3>Sub bagian</h3>" + p(prose(2, 3))
        _, titles, _ = read(make_epub([("a.xhtml", html)]))
        assert titles == ["Bab Satu"]

    def test_files_without_any_title_get_generic_names(self, read):
        data = make_epub([("a.xhtml", body(prose(2))), ("b.xhtml", body(prose(5, 3)))])
        _, titles, _ = read(data)
        assert titles == ["Pembuka", "Bagian 2"]

    def test_a_short_untitled_file_is_merged_into_the_previous_chapter(self, read):
        data = make_epub([("a.xhtml", body(prose(2), heading="Bab Satu")), ("b.xhtml", body("Catatan singkat sekali ini."))])
        _, titles, paras = read(data)
        assert titles == ["Bab Satu"] and {n for n, _ in paras} == {1}

    def test_the_navigation_document_is_not_a_chapter(self, read):
        data = make_epub([("a.xhtml", body(prose(2)))], nav={"a.xhtml": "Satu"})
        assert read(data)[1] == ["Satu"]

    def test_pages_made_mostly_of_links_are_skipped(self, read):
        links = "".join(f'<p><a href="x{i}.xhtml">Bab nomor {i} dengan judul panjang</a></p>' for i in range(8))
        data = make_epub([("daftar.xhtml", links), ("a.xhtml", body(prose(2), heading="Bab Satu"))])
        assert read(data)[1] == ["Bab Satu"]

    def test_non_linear_items_are_skipped(self, read):
        data = make_epub(
            [("a.xhtml", body(prose(2), heading="Bab Satu")), ("catatan.xhtml", body(prose(2, 3), heading="Catatan"))],
            linear={"catatan.xhtml": False},
        )
        assert read(data)[1] == ["Bab Satu"]

    def test_a_contents_heading_is_ignored(self, read):
        html = "<h1>Daftar Isi</h1>" + p(prose(2)) + "<h2>Bab Satu</h2>" + p(prose(2, 3))
        _, titles, _ = read(make_epub([("a.xhtml", html)]))
        assert "Daftar Isi" not in titles


class TestParagraphs:
    def test_short_paragraphs_are_packed_together(self, read):
        html = body(*[f"Kalimat pendek nomor {i} yang cukup panjang." for i in range(5)], heading="Bab Satu")
        _, _, paras = read(make_epub([("a.xhtml", html)]))
        assert len(paras) == 1 and paras[0][1].count("\n") == 4

    def test_a_packed_paragraph_stays_under_the_limit(self, read):
        html = body(*[prose(3, i) for i in range(10)], heading="Bab Satu")
        _, _, paras = read(make_epub([("a.xhtml", html)]))
        assert len(paras) > 1 and all(len(t) <= epub.MAX_PARAGRAPH_CHARS + 120 for _, t in paras)

    def test_a_very_long_paragraph_is_cut_at_sentences(self, read):
        _, _, paras = read(make_epub([("a.xhtml", body(prose(40), heading="Bab Satu"))]))
        assert len(paras) > 1 and all(t.rstrip().endswith(".") for _, t in paras)

    def test_fragments_without_letters_separate_paragraphs(self, read):
        html = body("Kalimat pertama yang cukup panjang.", "* * *", "Kalimat kedua yang cukup panjang.", heading="Bab Satu")
        _, _, paras = read(make_epub([("a.xhtml", html)]))
        assert [t for _, t in paras] == ["Kalimat pertama yang cukup panjang.", "Kalimat kedua yang cukup panjang."]

    def test_a_chapter_with_only_a_tiny_fragment_is_dropped(self, read):
        data = make_epub([("a.xhtml", body(prose(2), heading="Bab Satu")), ("b.xhtml", body("Tamat.", heading="Penutup"))])
        _, titles, paras = read(data)
        assert titles == ["Bab Satu"] and all(len(t) >= 20 for _, t in paras)

    def test_scripts_styles_and_svg_are_ignored(self, read):
        html = body(prose(2), heading="Bab Satu") + "<script>alert('x')</script><style>p{color:red}</style><svg><text>gambar</text></svg>"
        _, _, paras = read(make_epub([("a.xhtml", html)]))
        joined = " ".join(t for _, t in paras)
        assert "alert" not in joined and "color" not in joined and "gambar" not in joined

    def test_entities_and_odd_spaces_are_normalised(self, read):
        html = body("Rana &amp; Dede berjalan pulang­bersama melewati jalan sepi itu.", heading="Bab Satu")
        _, _, paras = read(make_epub([("a.xhtml", html)]))
        assert paras[0][1] == "Rana & Dede berjalan pulangbersama melewati jalan sepi itu."

    def test_line_breaks_become_spaces(self, read):
        html = body("Rana berjalan<br/>pulang melewati jalan yang sepi.", heading="Bab Satu")
        _, _, paras = read(make_epub([("a.xhtml", html)]))
        assert paras[0][1] == "Rana berjalan pulang melewati jalan yang sepi."


class TestPageEstimate:
    def test_pages_are_estimated_at_1800_characters_each(self, read):
        html = body(*[prose(4, i) for i in range(12)], heading="Bab Satu")
        pages, _, paras = read(make_epub([("a.xhtml", html)]))
        total = sum(len(t) for _, t in paras)
        assert total > 3600 and pages == round(total / 1800)

    def test_a_tiny_book_is_at_least_one_page(self, read):
        pages, _, _ = read(make_epub([("a.xhtml", body(prose(1), heading="Bab Satu"))]))
        assert pages == 1


class TestEncodings:
    def test_a_byte_order_mark_is_handled(self, read):
        raw = b"\xef\xbb\xbf" + f'<html><body><h1>Bab Satu</h1><p>{prose(2)}</p></body></html>'.encode("utf-8")
        assert read(make_epub([("a.xhtml", raw)]))[1] == ["Bab Satu"]

    def test_a_declared_legacy_encoding_is_honoured(self, read):
        text = "Dia berkata café itu sangat ramai malam ini dan semua orang bergembira bersama."
        raw = f'<?xml version="1.0" encoding="iso-8859-1"?><html><body><h1>Bab Satu</h1><p>{text}</p></body></html>'.encode("latin-1")
        _, _, paras = read(make_epub([("a.xhtml", raw)]))
        assert "café" in paras[0][1]


class TestErrors:
    def test_a_file_that_is_not_a_zip_is_rejected(self, tmp_path):
        path = tmp_path / "x.epub"
        path.write_bytes(b"bukan epub")
        with pytest.raises(epub.EpubError, match="rusak atau bukan EPUB"):
            epub.read_epub(str(path))

    def test_a_missing_container_is_rejected(self, read):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("mimetype", "application/epub+zip")
        with pytest.raises(epub.EpubError, match="Struktur EPUB tidak valid"):
            read(buffer.getvalue())

    def test_drm_protected_books_are_rejected(self, read):
        data = make_epub([("a.xhtml", body(prose(2)))], encryption=drm_encryption("http://www.w3.org/2001/04/xmlenc#aes128-cbc"))
        with pytest.raises(epub.EpubError, match="DRM"):
            read(data)

    @pytest.mark.parametrize("algorithm", ["http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC"])
    def test_font_obfuscation_is_not_treated_as_drm(self, read, algorithm):
        data = make_epub([("a.xhtml", body(prose(2), heading="Bab Satu"))], encryption=drm_encryption(algorithm))
        assert read(data)[1] == ["Bab Satu"]

    def test_a_book_without_text_is_rejected(self, read):
        with pytest.raises(epub.EpubError, match="tidak berisi teks"):
            read(make_epub([("a.xhtml", "<h1>Judul saja</h1>")]))

    def test_an_oversized_archive_is_rejected(self, read, monkeypatch):
        monkeypatch.setattr(epub, "MAX_UNCOMPRESSED", 100)
        with pytest.raises(epub.EpubError, match="terlalu besar"):
            read(make_epub([("a.xhtml", body(prose(2)))]))

    def test_a_missing_chapter_file_is_skipped(self, read):
        data = make_epub([("a.xhtml", body(prose(2), heading="Bab Satu")), ("hilang.xhtml", body(prose(2)))])
        buffer = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(buffer, "w") as dst:
            for item in src.infolist():
                if not item.filename.endswith("hilang.xhtml"):
                    dst.writestr(item, src.read(item.filename))
        assert read(buffer.getvalue())[1] == ["Bab Satu"]
