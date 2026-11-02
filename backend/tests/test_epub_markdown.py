import re

import pytest

from app.extraction import epub_markdown
from app.extraction import epub_utils as epub
from app.extraction import markdown_utils as md
from tests.builders import drm_encryption, make_epub, prose


@pytest.fixture
def path_for(tmp_path):
    def build(data: bytes) -> str:
        path = tmp_path / "buku.epub"
        path.write_bytes(data)
        return str(path)

    return build


@pytest.fixture
def read(path_for):
    return lambda data: epub_markdown.read_epub_markdown(path_for(data))


def one(html):
    return make_epub([("a.xhtml", f"<h1>Bab Satu</h1>{html}")])


def blocks_of(read, html):
    return [b for _, b in read(one(html))[2]]


class TestParityWithTheLegacyParser:
    def book(self):
        return make_epub(
            [
                ("a.xhtml", f"<h1>Bab Satu</h1><p>{prose(2)}</p><p>{prose(1, 3)}</p>"),
                ("b.xhtml", "<h1>Bab Dua</h1>" + "".join(f"<p>{prose(2, i)}</p>" for i in range(6))),
            ],
            nav={"a.xhtml": "Awal", "b.xhtml": "Lanjut"},
        )

    def test_titles_and_chapter_numbers_match(self, path_for):
        path = path_for(self.book())
        legacy = epub.read_epub(path)
        new = epub_markdown.read_epub_markdown(path)
        assert new[1] == legacy[1] and [n for n, _ in new[2]] == [n for n, _ in legacy[2]]

    def test_the_plain_text_of_every_block_matches(self, path_for):
        path = path_for(self.book())
        legacy = epub.read_epub(path)
        new = epub_markdown.read_epub_markdown(path)
        assert [b.text for _, b in new[2]] == [t for _, t in legacy[2]]

    def test_the_page_estimate_matches(self, path_for):
        path = path_for(self.book())
        assert epub_markdown.read_epub_markdown(path)[0] == epub.read_epub(path)[0]


class TestInlineMarks:
    def test_bold_and_italic_become_markdown(self, read):
        [block] = blocks_of(read, f"<p>Kata <strong>penting</strong> dan <em>miring</em> {prose(1)}</p>")
        assert block.markdown.startswith("Kata **penting** dan *miring* ")
        assert block.text.startswith("Kata penting dan miring ")

    def test_b_and_i_tags_work_too(self, read):
        [block] = blocks_of(read, f"<p>Ada <b>tebal</b> dan <i>miring</i> di sini {prose(1)}</p>")
        assert "**tebal**" in block.markdown and "*miring*" in block.markdown

    def test_nested_marks(self, read):
        [block] = blocks_of(read, f"<p>Ini <b><i>sangat</i></b> penting sekali {prose(1)}</p>")
        assert "***sangat***" in block.markdown

    def test_spaces_inside_a_mark_move_outside(self, read):
        [block] = blocks_of(read, f"<p>Kata <b>tebal </b>lalu <i> miring</i> {prose(1)}</p>")
        assert "**tebal** lalu" in block.markdown and "*miring*" in block.markdown

    def test_empty_marks_disappear(self, read):
        [block] = blocks_of(read, f"<p>Sebelum <b></b><i> </i>sesudah {prose(1)}</p>")
        assert "*" not in block.markdown

    def test_links_keep_their_text_only(self, read):
        [block] = blocks_of(read, f'<p>Buka <a href="http://jahat.example/x">tautan ini</a> sekarang {prose(1)}</p>')
        assert "http" not in block.markdown and "tautan ini" in block.text and "[" not in block.markdown

    def test_images_are_dropped(self, read):
        [block] = blocks_of(read, f'<p>Sebelum <img src="a.png" alt="gambar"/> sesudah {prose(1)}</p>')
        assert "png" not in block.markdown and "gambar" not in block.markdown


class TestEscaping:
    @pytest.mark.parametrize("original", [
        "hitung 2*3*4 dan snake_case_ini sekarang juga ya",
        "kurung [satu] dan [dua](tiga) tetap teks biasa",
        "tanda <kurung> sudut dan a < b > c tetap teks",
        "garis \\ miring balik dan `kode` tetap teks biasa",
        "<script>alert(1)</script> tetap sebagai teks biasa saja",
    ])
    def test_special_characters_survive_a_round_trip(self, read, original):
        escaped = original.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        [block] = blocks_of(read, f"<p>{escaped} {prose(1)}</p>")
        assert block.text.startswith(original)
        assert not re.search(r"(?<!\\)<", block.markdown)

    @pytest.mark.parametrize("start", ["# bukan judul", "- bukan butir", "+ bukan butir", "1. bukan daftar", "2) bukan daftar", "> bukan kutipan"])
    def test_block_starts_that_look_like_markdown_stay_paragraphs(self, read, start):
        escaped = start.replace(">", "&gt;")
        [block] = blocks_of(read, f"<p>{escaped} {prose(1)}</p>")
        assert block.kind == "p" and block.text.startswith(start)
        assert [b.kind for b in md.parse_blocks(block.markdown)] == ["p"]


class TestStructure:
    def test_lower_level_headings_stay_as_blocks(self, read):
        blocks = blocks_of(read, f"<p>{prose(2)}</p><h3>Sub bagian</h3><p>{prose(2, 3)}</p>")
        assert [b.kind for b in blocks] == ["p", "h", "p"]
        assert (blocks[1].markdown, blocks[1].text, blocks[1].level) == ("### Sub bagian", "Sub bagian", 3)

    def test_chapter_headings_are_not_blocks(self, read):
        _, titles, blocks = read(make_epub([("a.xhtml", f"<h1>Bab Satu</h1><p>{prose(2)}</p><h2>Bab Dua</h2><p>{prose(2, 3)}</p>")]))
        assert titles == ["Bab Satu", "Bab Dua"] and all(b.kind == "p" for _, b in blocks)

    def test_list_items_are_separate_blocks(self, read):
        blocks = blocks_of(read, "<ul><li>satu butir panjang pertama</li><li>dua butir panjang kedua</li></ul>")
        assert [(b.kind, b.markdown) for b in blocks] == [("li", "- satu butir panjang pertama"), ("li", "- dua butir panjang kedua")]

    def test_ordered_list_items_keep_their_kind(self, read):
        blocks = blocks_of(read, "<ol><li>satu butir panjang pertama</li><li>dua butir panjang kedua</li></ol>")
        assert [b.kind for b in blocks] == ["li", "li"]

    def test_blockquote_paragraphs_become_quotes(self, read):
        blocks = blocks_of(read, f"<blockquote><p>Kutipan yang cukup panjang untuk dibaca.</p></blockquote><p>{prose(2)}</p>")
        assert [b.kind for b in blocks] == ["quote", "p"] and blocks[0].markdown == "> Kutipan yang cukup panjang untuk dibaca."

    def test_scripts_and_styles_are_ignored(self, read):
        blocks = blocks_of(read, f"<p>{prose(2)}</p><script>alert('x')</script><style>p{{color:red}}</style>")
        assert "alert" not in " ".join(b.text for b in blocks)

    def test_a_scene_break_without_letters_separates_blocks(self, read):
        blocks = blocks_of(read, "<p>Kalimat pertama yang cukup panjang.</p><p>* * *</p><p>Kalimat kedua yang cukup panjang.</p>")
        assert [b.text for b in blocks] == ["Kalimat pertama yang cukup panjang.", "Kalimat kedua yang cukup panjang."]


class TestPacking:
    def test_short_paragraphs_are_packed_into_one_block(self, read):
        html = "".join(f"<p>Kalimat pendek nomor {i} yang cukup panjang.</p>" for i in range(5))
        [block] = blocks_of(read, html)
        assert block.markdown.count("\n\n") == 4 and block.text.count("\n") == 4

    def test_a_packed_block_stays_under_the_limit(self, read):
        blocks = blocks_of(read, "".join(f"<p>{prose(3, i)}</p>" for i in range(10)))
        assert len(blocks) > 1 and all(len(b.text) <= 900 + 120 for b in blocks)

    def test_a_long_paragraph_keeps_its_marks_balanced_when_cut(self, read):
        blocks = blocks_of(read, f"<p><strong>{prose(40)}</strong></p>")
        assert len(blocks) > 1 and all(b.markdown.count("**") % 2 == 0 for b in blocks)

    def test_headings_lists_and_quotes_break_a_pack(self, read):
        html = "<p>Kalimat pertama yang cukup panjang.</p><ul><li>butir yang cukup panjang ya</li></ul><p>Kalimat kedua yang cukup panjang.</p>"
        assert [b.kind for b in blocks_of(read, html)] == ["p", "li", "p"]

    def test_tiny_fragments_are_dropped(self, read):
        _, titles, blocks = read(make_epub([("a.xhtml", f"<h1>Bab Satu</h1><p>{prose(2)}</p>"), ("b.xhtml", "<h1>Penutup</h1><p>Tamat.</p>")]))
        assert titles == ["Bab Satu"]


class TestErrors:
    def test_drm_is_rejected(self, read):
        data = make_epub([("a.xhtml", f"<h1>Bab</h1><p>{prose(2)}</p>")], encryption=drm_encryption("http://www.w3.org/2001/04/xmlenc#aes128-cbc"))
        with pytest.raises(epub.EpubError, match="DRM"):
            read(data)

    def test_a_broken_file_is_rejected(self, read):
        with pytest.raises(epub.EpubError, match="rusak"):
            read(b"bukan zip")

    def test_a_book_without_text_is_rejected(self, read):
        with pytest.raises(epub.EpubError, match="tidak berisi teks"):
            read(make_epub([("a.xhtml", "<h1>Judul saja</h1>")]))
