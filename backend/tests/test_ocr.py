import pymupdf
import pytest

from app.core.config import settings
from app.extraction import ocr
from tests.builders import make_pdf, make_scanned_pdf, prose

NORMAL_PAGE = prose(3) + " " + prose(3, 2)


class TestPageNeedsOcr:
    @pytest.mark.parametrize("text", ["", "   \n\t ", "12", "Bab 1", "x" * 24, "1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9"])
    def test_pages_with_almost_no_real_text_need_it(self, text):
        assert ocr.page_needs_ocr(text) is True

    def test_a_page_of_mostly_symbols_and_digits_needs_it(self):
        assert ocr.page_needs_ocr("1234 5678 9012 3456 7890 ,,,, .... ---- 1234 5678 9012 abc " * 4) is True

    def test_a_page_full_of_replacement_characters_needs_it(self):
        assert ocr.page_needs_ocr(("Rana pulang ������ " * 8)) is True

    def test_a_normal_page_does_not(self):
        assert ocr.page_needs_ocr(NORMAL_PAGE) is False

    def test_a_short_but_real_paragraph_does_not(self):
        assert ocr.page_needs_ocr("Rana pulang ke rumah dengan wajah yang sangat gembira.") is False


class TestTextQuality:
    def test_indonesian_prose_is_recognised(self):
        assert ocr.text_quality([NORMAL_PAGE]) >= 0.9

    def test_english_prose_is_recognised(self):
        assert ocr.text_quality(["The old library stood quietly at the end of the street while the children were walking home."]) >= 0.9

    def test_gibberish_is_not(self):
        assert ocr.text_quality(["xkqz vwpf lrtm qzxv bnkw rtpl zxcv mnbq wprt klzx"]) < 0.2

    def test_no_words_means_zero(self):
        assert ocr.text_quality([""]) == 0.0
        assert ocr.text_quality([]) == 0.0


class TestLanguages:
    @pytest.fixture
    def tessdata(self, tmp_path, monkeypatch):
        def install(*names):
            for name in names:
                (tmp_path / f"{name}.traineddata").write_bytes(b"x")
            monkeypatch.setattr(settings, "tessdata_dir", str(tmp_path))

        return install

    def test_installed_languages_come_from_the_folder_without_osd(self, tessdata):
        tessdata("eng", "ind", "osd")
        assert ocr.installed_languages() == {"eng", "ind"}

    def test_the_usable_languages_are_the_requested_ones_that_are_installed(self, tessdata, monkeypatch):
        tessdata("eng")
        monkeypatch.setattr(settings, "ocr_languages", "ind+eng")
        assert ocr.usable_languages() == "eng"

    def test_the_requested_order_is_kept(self, tessdata, monkeypatch):
        tessdata("eng", "ind")
        monkeypatch.setattr(settings, "ocr_languages", "ind+eng")
        assert ocr.usable_languages() == "ind+eng"

    def test_without_a_matching_language_ocr_is_not_ready(self, tessdata, monkeypatch):
        tessdata("deu")
        assert ocr.usable_languages() == "" and ocr.ocr_ready() is False

    def test_it_can_be_turned_off(self, tessdata, monkeypatch):
        tessdata("eng", "ind")
        monkeypatch.setattr(settings, "ocr_enabled", False)
        assert ocr.ocr_ready() is False

    def test_a_ready_setup_says_so(self, tessdata):
        tessdata("eng", "ind")
        assert ocr.ocr_ready() is True

    def test_the_folder_comes_from_the_environment_when_not_configured(self, tmp_path, monkeypatch):
        (tmp_path / "eng.traineddata").write_bytes(b"x")
        monkeypatch.setattr(settings, "tessdata_dir", "")
        monkeypatch.setenv("TESSDATA_PREFIX", str(tmp_path))
        assert ocr.tessdata_dir() == str(tmp_path)

    def test_an_environment_prefix_that_is_the_parent_of_tessdata_works(self, tmp_path, monkeypatch):
        folder = tmp_path / "tessdata"
        folder.mkdir()
        (folder / "eng.traineddata").write_bytes(b"x")
        monkeypatch.setattr(settings, "tessdata_dir", "")
        monkeypatch.setenv("TESSDATA_PREFIX", str(tmp_path))
        assert ocr.tessdata_dir() == str(folder)

    def test_standard_locations_are_tried_last(self, tmp_path, monkeypatch):
        (tmp_path / "eng.traineddata").write_bytes(b"x")
        monkeypatch.setattr(settings, "tessdata_dir", "")
        monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
        monkeypatch.setattr(ocr, "STANDARD_DIRS", ["/tidak/ada/sama/sekali", str(tmp_path)])
        assert ocr.tessdata_dir() == str(tmp_path)

    def test_nothing_found_means_none(self, monkeypatch):
        monkeypatch.setattr(settings, "tessdata_dir", "")
        monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
        monkeypatch.setattr(ocr, "STANDARD_DIRS", ["/tidak/ada/sama/sekali"])
        assert ocr.tessdata_dir() is None
        assert ocr.installed_languages() == set()


SCAN_TEXT = {0: prose(3, 5), 1: prose(3, 6), 2: prose(3, 7)}


@pytest.fixture
def fake_ocr(monkeypatch):
    calls = []

    def recognize(page):
        calls.append(page.number)
        doc = pymupdf.open()
        sheet = doc.new_page(width=page.rect.width, height=page.rect.height)
        sheet.insert_textbox(pymupdf.Rect(36, 40, page.rect.width - 36, page.rect.height - 40), SCAN_TEXT.get(page.number, prose(2, 9)), fontsize=12)
        return doc.tobytes()

    monkeypatch.setattr(ocr, "ocr_ready", lambda: True)
    monkeypatch.setattr(ocr, "recognize", recognize)
    return calls


def page_texts(path):
    with pymupdf.open(path) as doc:
        return [page.get_text("text") for page in doc]


class TestPreparePdf:
    @pytest.fixture
    def files(self, tmp_path):
        def save(name, data):
            path = tmp_path / name
            path.write_bytes(data)
            return str(path)

        return save, str(tmp_path / "kerja.pdf")

    def test_a_text_pdf_is_used_as_it_is(self, files, fake_ocr):
        save, work = files
        source = save("a.pdf", make_pdf([NORMAL_PAGE, NORMAL_PAGE]))
        result = ocr.prepare_pdf(source, work)
        assert fake_ocr == [] and result.path == source and result.pages == 2 and result.ocr_pages == 0 and result.stopped is False

    def test_a_scanned_pdf_gets_a_text_layer_on_every_page(self, files, fake_ocr):
        save, work = files
        source = save("a.pdf", make_scanned_pdf(["x", "y", "z"]))
        result = ocr.prepare_pdf(source, work)
        assert fake_ocr == [0, 1, 2] and result.path == work and result.ocr_pages == 3 and result.skipped == 0
        texts = page_texts(work)
        assert len(texts) == 3 and all(len(t.strip()) > 100 for t in texts)

    def test_only_the_pages_without_text_are_recognised(self, files, fake_ocr):
        save, work = files
        text_part = pymupdf.open("pdf", make_pdf([NORMAL_PAGE]))
        scan_part = pymupdf.open("pdf", make_scanned_pdf(["x"]))
        mixed = pymupdf.open()
        mixed.insert_pdf(text_part)
        mixed.insert_pdf(scan_part)
        mixed.insert_pdf(text_part)
        source = save("a.pdf", mixed.tobytes())
        result = ocr.prepare_pdf(source, work)
        assert fake_ocr == [1] and result.ocr_pages == 1 and result.pages == 3
        assert len(page_texts(work)) == 3

    def test_progress_is_reported_for_every_page(self, files, fake_ocr):
        save, work = files
        seen = []
        ocr.prepare_pdf(save("a.pdf", make_scanned_pdf(["x", "y", "z"])), work, on_page=seen.append)
        assert seen == [1, 2, 3]

    def test_progress_is_reported_for_text_pdfs_too(self, files, fake_ocr):
        save, work = files
        seen = []
        ocr.prepare_pdf(save("a.pdf", make_pdf([NORMAL_PAGE] * 4)), work, on_page=seen.append)
        assert seen == [1, 2, 3, 4]

    def test_without_ocr_the_pages_that_need_it_are_skipped_not_failed(self, files, monkeypatch):
        save, work = files
        monkeypatch.setattr(ocr, "ocr_ready", lambda: False)
        source = save("a.pdf", make_scanned_pdf(["x", "y"]))
        result = ocr.prepare_pdf(source, work)
        assert result.skipped == 2 and result.ocr_pages == 0 and result.pages == 2

    def test_a_failing_page_is_skipped_and_the_rest_continue(self, files, monkeypatch):
        save, work = files
        monkeypatch.setattr(ocr, "ocr_ready", lambda: True)

        def flaky(page):
            if page.number == 1:
                raise RuntimeError("tesseract mogok")
            doc = pymupdf.open()
            doc.new_page().insert_textbox(pymupdf.Rect(36, 40, 380, 500), prose(3), fontsize=12)
            return doc.tobytes()

        monkeypatch.setattr(ocr, "recognize", flaky)
        result = ocr.prepare_pdf(save("a.pdf", make_scanned_pdf(["x", "y", "z"])), work)
        assert result.ocr_pages == 2 and result.skipped == 1 and result.path == work

    def test_it_can_be_stopped_between_pages(self, files, fake_ocr):
        save, work = files
        calls = {"n": 0}

        def stop():
            calls["n"] += 1
            return calls["n"] > 1

        result = ocr.prepare_pdf(save("a.pdf", make_scanned_pdf(["x", "y", "z"])), work, should_stop=stop)
        assert result.stopped is True and fake_ocr == [0]
        import os
        assert not os.path.exists(work)

    def test_quality_covers_only_the_recognised_pages(self, files, fake_ocr):
        save, work = files
        result = ocr.prepare_pdf(save("a.pdf", make_scanned_pdf(["x", "y"])), work)
        assert result.quality is not None and result.quality >= 0.5

    def test_quality_is_none_when_nothing_was_recognised(self, files, fake_ocr):
        save, work = files
        result = ocr.prepare_pdf(save("a.pdf", make_pdf([NORMAL_PAGE])), work)
        assert result.quality is None

    def test_the_outline_survives(self, files, fake_ocr):
        save, work = files
        source = save("a.pdf", make_scanned_pdf(["x", "y", "z"]))
        with pymupdf.open(source) as doc:
            doc.set_toc([[1, "Bab 1", 1], [1, "Bab 2", 3]])
            doc.save(source, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        ocr.prepare_pdf(source, work)
        with pymupdf.open(work) as doc:
            assert [t[1] for t in doc.get_toc()] == ["Bab 1", "Bab 2"]


@pytest.mark.skipif(not ocr.installed_languages(), reason="Tesseract atau paket bahasanya belum terpasang")
class TestRealOcr:
    def test_a_scanned_page_is_really_read(self, tmp_path, monkeypatch):
        languages = ocr.usable_languages()
        assert languages
        text = "The old library stood quietly at the end of the street while the children were walking home from school."
        source = tmp_path / "scan.pdf"
        source.write_bytes(make_scanned_pdf([text]))
        result = ocr.prepare_pdf(str(source), str(tmp_path / "kerja.pdf"))
        assert result.ocr_pages == 1 and result.path.endswith("kerja.pdf")
        read = " ".join(page_texts(result.path)).lower()
        assert "library" in read and "children" in read
        assert result.quality is not None and result.quality >= 0.8
