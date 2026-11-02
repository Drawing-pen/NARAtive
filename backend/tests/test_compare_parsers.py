import pytest

from app.tools import compare_parsers as compare
from tests.builders import make_epub, make_pdf, prose

HEADER = "Kumpulan Cerita Rana dan Dede Edisi Pertama"


@pytest.fixture
def files(tmp_path):
    def save(name, data):
        path = tmp_path / name
        path.write_bytes(data)
        return str(path)

    return save


def pdf_book():
    return make_pdf([f"Bab 1\n\n{prose(3)}", f"Bab 2\n\n{prose(3, 4)}"], sizes={"Bab 1": 22, "Bab 2": 22})


def epub_book():
    return make_epub([("a.xhtml", f"<h1>Bab Satu</h1><p>Kata <b>tebal</b> {prose(3)}</p>"), ("b.xhtml", f"<h1>Bab Dua</h1><p>{prose(3, 4)}</p>")])


class TestCompare:
    def test_both_parsers_are_reported_for_a_pdf(self, files):
        result = compare.compare(files("a.pdf", pdf_book()))
        assert set(result) == {"legacy", "markdown"}
        for report in result.values():
            assert report["chapters"] == ["Bab 1", "Bab 2"] and report["blocks"] >= 2 and report["chars"] > 100
            assert report["pages"] == 2 and report["seconds"] >= 0

    def test_both_parsers_are_reported_for_an_epub(self, files):
        result = compare.compare(files("a.epub", epub_book()))
        assert result["legacy"]["chapters"] == result["markdown"]["chapters"] == ["Bab Satu", "Bab Dua"]

    def test_the_markdown_report_counts_formatting(self, files):
        report = compare.compare(files("a.epub", epub_book()))["markdown"]
        assert report["formatted"] >= 1 and report["kinds"]["p"] >= 1

    def test_the_legacy_report_has_no_formatting(self, files):
        report = compare.compare(files("a.epub", epub_book()))["legacy"]
        assert report["formatted"] == 0

    def test_repeated_headers_are_flagged_when_they_leak(self, files):
        data = make_pdf([prose(2, i) for i in range(1, 5)], header=HEADER)
        report = compare.compare(files("a.pdf", data))["markdown"]
        assert any("Kumpulan Cerita" in text for text, _ in report["repeated"])

    def test_repeated_headers_are_not_flagged_once_removed(self, files):
        data = make_pdf([prose(2, i) for i in range(1, 11)], header=HEADER)
        for report in compare.compare(files("a.pdf", data)).values():
            assert not any("Kumpulan Cerita" in text for text, _ in report["repeated"])

    def test_a_parser_that_fails_is_reported_not_raised(self, files, monkeypatch):
        monkeypatch.setattr(compare.reader, "parse_markdown", lambda path, ext: (_ for _ in ()).throw(RuntimeError("rusak")))
        result = compare.compare(files("a.pdf", pdf_book()))
        assert result["markdown"]["error"] == "rusak" and "error" not in result["legacy"]


class TestMain:
    def test_it_prints_a_report_per_file(self, files, capsys):
        code = compare.main([files("a.pdf", pdf_book()), files("b.epub", epub_book())])
        out = capsys.readouterr().out
        assert code == 0 and "a.pdf" in out and "b.epub" in out and "legacy" in out and "markdown" in out

    def test_the_report_lists_chapter_titles(self, files, capsys):
        compare.main([files("a.pdf", pdf_book())])
        assert "Bab 1" in capsys.readouterr().out

    def test_an_unsupported_file_is_reported_and_the_rest_continue(self, files, capsys):
        code = compare.main([files("catatan.txt", b"isi"), files("a.pdf", pdf_book())])
        out = capsys.readouterr().out
        assert code == 1 and "catatan.txt" in out and "tidak didukung" in out.lower() and "a.pdf" in out

    def test_a_missing_file_is_reported(self, tmp_path, capsys):
        assert compare.main([str(tmp_path / "hilang.pdf")]) == 1
        assert "tidak ditemukan" in capsys.readouterr().out.lower()

    def test_no_arguments_prints_usage(self, capsys):
        assert compare.main([]) == 2
        assert "pemakaian" in capsys.readouterr().out.lower()
