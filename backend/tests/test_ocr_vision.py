import base64
import subprocess
from types import SimpleNamespace

import pymupdf
import pytest

from app.core.config import settings
from app.extraction import ocr, vision
from tests.builders import make_pdf, make_scanned_pdf, prose
from tests.gemini_fake import clock, gemini
from tests.router_fake import router

real_binary = ocr.tesseract_binary

TSV_HEAD = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"


def tsv_row(level, conf, text):
    return f"{level}\t1\t1\t1\t1\t1\t0\t0\t10\t10\t{conf}\t{text}\n"


def echo(call):
    count = len(call["images"])
    return ("text", "\n".join(f"===HALAMAN {k}===\n{prose(2, k)}" for k in range(1, count + 1)))


def page_texts(path):
    with pymupdf.open(path) as doc:
        return [page.get_text("text") for page in doc]


class TestParsePages:
    def test_every_marked_page_is_returned_by_its_number(self):
        answer = "===HALAMAN 1===\nsatu satu\n===HALAMAN 2===\ndua dua\n\ntiga tiga\n===HALAMAN 3===\nempat"
        assert vision.parse_pages(answer, 3) == {1: "satu satu", 2: "dua dua\n\ntiga tiga", 3: "empat"}

    def test_a_missing_marker_leaves_that_page_out(self):
        answer = "===HALAMAN 1===\nsatu\n===HALAMAN 3===\ntiga"
        assert vision.parse_pages(answer, 3) == {1: "satu", 3: "tiga"}

    def test_a_marker_out_of_order_or_repeated_is_dropped(self):
        answer = "===HALAMAN 2===\ndua\n===HALAMAN 1===\nsatu\n===HALAMAN 2===\nlagi"
        assert vision.parse_pages(answer, 3) == {2: "dua"}

    def test_a_marker_beyond_the_batch_is_ignored(self):
        assert vision.parse_pages("===HALAMAN 1===\nsatu\n===HALAMAN 9===\nsembilan", 2) == {1: "satu"}

    def test_an_answer_without_markers_gives_nothing(self):
        assert vision.parse_pages("Ini teks tanpa penanda halaman.", 2) == {}

    def test_a_page_with_only_blank_text_counts_as_missing(self):
        assert vision.parse_pages("===HALAMAN 1===\n   \n===HALAMAN 2===\ndua", 2) == {2: "dua"}

    def test_text_before_the_first_marker_is_ignored(self):
        assert vision.parse_pages("Berikut hasilnya:\n===HALAMAN 1===\nsatu", 1) == {1: "satu"}


class TestGroups:
    def test_pages_are_grouped_by_the_page_limit(self, monkeypatch):
        monkeypatch.setattr(settings, "vision_batch_pages", 3)
        assert vision.groups([10] * 5) == [[0, 1, 2], [3, 4]]

    def test_a_group_is_cut_when_the_payload_would_pass_the_limit(self, monkeypatch):
        monkeypatch.setattr(settings, "vision_batch_pages", 8)
        monkeypatch.setattr(settings, "vision_batch_mb", 6)
        mb = 1024 * 1024
        assert vision.groups([4 * mb, 1 * mb, 4 * mb, 1 * mb]) == [[0, 1], [2, 3]]

    def test_one_oversized_page_still_goes_alone(self, monkeypatch):
        monkeypatch.setattr(settings, "vision_batch_mb", 1)
        mb = 1024 * 1024
        assert vision.groups([3 * mb, 10, 10]) == [[0], [1, 2]]

    def test_no_pages_means_no_groups(self):
        assert vision.groups([]) == []


class TestAvailability:
    def test_it_needs_a_configured_llm(self, monkeypatch):
        monkeypatch.setattr(settings, "ocr_engine", "auto")
        assert vision.available() is False

    def test_a_configured_router_makes_it_available(self, router, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        assert vision.available() is True

    def test_gemini_alone_is_enough(self, gemini):
        assert vision.available() is True

    def test_the_tesseract_mode_turns_it_off(self, router, monkeypatch):
        monkeypatch.setattr(settings, "ocr_engine", "tesseract")
        assert vision.available() is False

    def test_turning_ocr_off_turns_vision_off_too(self, router, monkeypatch):
        monkeypatch.setattr(settings, "ocr_enabled", False)
        assert vision.available() is False

    @pytest.mark.parametrize("name,expected", [("auto", "auto"), ("TESSERACT", "tesseract"), (" router ", "router"), ("aneh", "auto"), ("", "auto")])
    def test_unknown_engine_names_mean_auto(self, monkeypatch, name, expected):
        monkeypatch.setattr(settings, "ocr_engine", name)
        assert ocr.engine_mode() == expected


class TestTranscribe:
    @pytest.fixture(autouse=True)
    def only_the_router(self, router, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        router.default = echo
        return router

    def test_one_request_carries_the_instruction_and_every_image(self, router):
        images = [b"gambar-satu", b"gambar-dua", b"gambar-tiga"]
        result = vision.transcribe_group(images)
        assert len(router.calls) == 1 and len(result) == 3 and all(result)
        call = router.calls[0]
        assert call["images"] == ["data:image/jpeg;base64," + base64.b64encode(i).decode() for i in images]
        assert "===HALAMAN" in call["prompt"] and "[tidak terbaca]" in call["prompt"]

    def test_the_token_budget_grows_with_the_page_count(self, router):
        vision.transcribe_group([b"a", b"b"])
        assert router.calls[0]["body"]["max_tokens"] == 1500 * 2 + 4000

    def test_it_only_transcribes_and_treats_the_image_text_as_data(self, router):
        vision.transcribe_group([b"a"])
        text = (router.calls[0]["system"] + router.calls[0]["prompt"]).lower()
        assert "data" in text and "perintah" in text

    def test_the_answers_come_back_in_page_order(self, router):
        result = vision.transcribe_group([b"a", b"b"])
        assert result == [prose(2, 1), prose(2, 2)]

    def test_a_page_missing_from_the_answer_is_asked_again_once(self, router):
        router.add(lambda call: ("text", f"===HALAMAN 1===\n{prose(1, 1)}\n===HALAMAN 3===\n{prose(1, 3)}"))
        result = vision.transcribe_group([b"a", b"b", b"c"])
        assert len(router.calls) == 2 and len(router.calls[1]["images"]) == 1
        assert router.calls[1]["images"] == [router.calls[0]["images"][1]]
        assert result[0] == prose(1, 1) and result[1] == prose(2, 1) and result[2] == prose(1, 3)

    def test_a_page_still_missing_after_the_second_ask_is_none(self, router):
        router.add(("text", "===HALAMAN 1===\nsatu"), ("text", "tanpa penanda sama sekali"))
        assert vision.transcribe_group([b"a", b"b"]) == ["satu", None]
        assert len(router.calls) == 2

    def test_a_blocked_batch_is_split_until_the_pages_can_be_read(self, router):
        router.add(("filtered",))
        result = vision.transcribe_group([b"a", b"b", b"c", b"d"])
        assert [len(c["images"]) for c in router.calls] == [4, 2, 2]
        assert all(result)

    def test_a_single_page_that_stays_blocked_is_none_and_the_others_survive(self, router):
        router.add(("filtered",), ("text", "===HALAMAN 1===\nsatu"), ("filtered",))
        assert vision.transcribe_group([b"a", b"b"]) == ["satu", None]

    def test_a_service_failure_gives_none_for_every_page_instead_of_raising(self, router):
        router.add(("http", 500, "mati"))
        assert vision.transcribe_group([b"a", b"b"]) == [None, None]

    def test_the_page_text_is_never_written_to_the_log(self, router, caplog):
        router.add(("text", "===HALAMAN 1===\nRAHASIA-ISI-HALAMAN"))
        with caplog.at_level("DEBUG"):
            vision.transcribe_group([b"a"])
        assert "RAHASIA-ISI-HALAMAN" not in caplog.text

    def test_gemini_is_the_fallback_and_receives_the_images_inline(self, router, gemini, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "kunci-rahasia")
        router.add(("http", 500, "mati"))
        gemini.add(("text", "===HALAMAN 1===\nDari Gemini"))
        assert vision.transcribe_group([b"gambar"]) == ["Dari Gemini"]
        parts = gemini.calls[0]["body"]["contents"][0]["parts"]
        assert parts[0]["text"].startswith(vision.INSTRUCTION[:20])
        assert parts[1] == {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(b"gambar").decode()}}


class TestRender:
    def test_a_page_becomes_a_small_jpeg(self):
        with pymupdf.open(stream=make_scanned_pdf(["halaman"]), filetype="pdf") as doc:
            data = vision.render(doc[0])
        assert data[:3] == b"\xff\xd8\xff"
        with pymupdf.open(stream=data, filetype="jpeg") as image:
            assert max(image[0].rect.width, image[0].rect.height) <= 1700 and len(data) < 400_000


class TestTextPage:
    def test_it_has_the_same_size_as_the_original_page(self):
        data = vision.text_page(420, 595, prose(3))
        with pymupdf.open("pdf", data) as doc:
            assert len(doc) == 1 and doc[0].rect.width == 420 and doc[0].rect.height == 595
            assert "Rana berjalan" in doc[0].get_text("text")

    def test_long_text_is_shrunk_until_it_fits(self):
        text = "\n\n".join(prose(3, n) for n in range(12))
        with pymupdf.open("pdf", vision.text_page(420, 595, text)) as doc:
            assert len(doc) == 1
            assert doc[0].get_text("text").count("Rana berjalan") >= 4

    def test_the_unreadable_marker_is_kept(self):
        with pymupdf.open("pdf", vision.text_page(420, 595, "Kata pertama [tidak terbaca] kata terakhir")) as doc:
            assert "[tidak terbaca]" in doc[0].get_text("text")


class TestTesseractConfidence:
    def test_the_mean_covers_only_real_words(self):
        tsv = (TSV_HEAD + tsv_row(4, -1, "") + tsv_row(5, 90, "Rana") + tsv_row(5, 60, "pulang") + tsv_row(5, -1, "x") + tsv_row(5, 80, ""))
        assert ocr.parse_tsv(tsv) == (75.0, 2)

    def test_no_words_means_no_confidence(self):
        assert ocr.parse_tsv(TSV_HEAD + tsv_row(4, -1, "")) == (None, 0)
        assert ocr.parse_tsv("") == (None, 0)

    def test_a_malformed_row_is_ignored(self):
        assert ocr.parse_tsv(TSV_HEAD + "5\t1\tmerusak\n" + tsv_row(5, "abc", "kata") + tsv_row(5, 70, "baik")) == (70.0, 1)

    def test_the_binary_is_found_on_the_path_first(self, monkeypatch):
        monkeypatch.setattr(ocr.shutil, "which", lambda name: "/usr/bin/tesseract")
        assert real_binary() == "/usr/bin/tesseract"

    def test_standard_locations_are_tried_next(self, monkeypatch, tmp_path):
        found = tmp_path / "tesseract"
        found.write_bytes(b"x")
        monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
        monkeypatch.setattr(ocr, "STANDARD_BINARIES", ["/tidak/ada/sama/sekali", str(found)])
        assert real_binary() == str(found)

    def test_nothing_found_means_none(self, monkeypatch):
        monkeypatch.setattr(ocr.shutil, "which", lambda name: None)
        monkeypatch.setattr(ocr, "STANDARD_BINARIES", ["/tidak/ada/sama/sekali"])
        assert real_binary() is None

    @pytest.fixture
    def scan(self):
        with pymupdf.open(stream=make_scanned_pdf(["halaman"]), filetype="pdf") as doc:
            yield doc[0]

    def test_without_the_binary_the_confidence_is_unknown(self, scan, monkeypatch):
        monkeypatch.setattr(ocr, "tesseract_binary", lambda: None)
        assert ocr.measure(scan) == (None, 0)

    def test_it_asks_the_command_line_for_a_tsv_with_a_time_limit(self, scan, monkeypatch):
        seen = {}

        def run(command, **kwargs):
            seen.update(command=command, **kwargs)
            return SimpleNamespace(returncode=0, stdout=(TSV_HEAD + tsv_row(5, 80, "kata") + tsv_row(5, 40, "lain")).encode())

        monkeypatch.setattr(ocr, "tesseract_binary", lambda: "/x/tesseract")
        monkeypatch.setattr(ocr, "usable_languages", lambda: "ind+eng")
        monkeypatch.setattr(ocr, "tessdata_dir", lambda: "/data")
        monkeypatch.setattr(ocr.subprocess, "run", run)
        assert ocr.measure(scan) == (60.0, 2)
        assert seen["command"] == ["/x/tesseract", "stdin", "stdout", "-l", "ind+eng", "--tessdata-dir", "/data", "tsv"]
        assert seen["timeout"] == settings.ocr_timeout and seen["input"][:4] == b"\x89PNG"

    def test_a_failing_command_means_unknown_confidence(self, scan, monkeypatch):
        monkeypatch.setattr(ocr, "tesseract_binary", lambda: "/x/tesseract")
        monkeypatch.setattr(ocr.subprocess, "run", lambda command, **kw: SimpleNamespace(returncode=1, stdout=b""))
        assert ocr.measure(scan) == (None, 0)

    def test_a_page_that_runs_over_the_time_limit_raises_so_it_is_skipped(self, scan, monkeypatch):
        def slow(command, **kwargs):
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])

        monkeypatch.setattr(ocr, "tesseract_binary", lambda: "/x/tesseract")
        monkeypatch.setattr(ocr.subprocess, "run", slow)
        with pytest.raises(subprocess.TimeoutExpired):
            ocr.measure(scan)


@pytest.fixture
def engines(monkeypatch, tmp_path):
    state = SimpleNamespace(tess=[], sent=[], conf={}, words={}, fail=set(), counter=0, on=True)

    def recognize(page):
        state.tess.append(page.number)
        doc = pymupdf.open()
        sheet = doc.new_page(width=page.rect.width, height=page.rect.height)
        sheet.insert_textbox(pymupdf.Rect(36, 40, page.rect.width - 36, page.rect.height - 40), f"Tesseract{page.number} " + prose(3, page.number), fontsize=12)
        return doc.tobytes()

    def measure(page):
        return state.conf.get(page.number, 90.0), state.words.get(page.number, 50)

    def transcribe(images):
        state.sent.append(len(images))
        out = []
        for _ in images:
            state.counter += 1
            out.append(None if state.counter in state.fail else f"Penanda{state.counter} " + prose(2, state.counter))
        return out

    monkeypatch.setattr(ocr, "ocr_ready", lambda: state.on)
    monkeypatch.setattr(ocr, "recognize", recognize)
    monkeypatch.setattr(ocr, "measure", measure)
    monkeypatch.setattr(vision, "available", lambda: vision.mode() != "tesseract")
    monkeypatch.setattr(vision, "transcribe_group", transcribe)
    monkeypatch.setattr(settings, "ocr_engine", "auto")
    monkeypatch.setattr(settings, "vision_max_pages", 60)
    monkeypatch.setattr(settings, "vision_batch_pages", 8)
    state.source = lambda pages: _save(tmp_path, pages)
    state.work = str(tmp_path / "kerja.pdf")
    return state


def _save(tmp_path, pages):
    path = tmp_path / "asal.pdf"
    path.write_bytes(make_scanned_pdf(["x"] * pages))
    return str(path)


class TestAutoMode:
    def test_only_pages_below_the_confidence_threshold_go_to_vision(self, engines):
        engines.conf = {1: 50.0}
        result = ocr.prepare_pdf(engines.source(3), engines.work)
        assert engines.tess == [0, 1, 2] and engines.sent == [1]
        assert result.vision_pages == 1 and result.ocr_pages == 3 and result.skipped == 0
        texts = page_texts(result.path)
        assert "Penanda1" in texts[1] and "Tesseract0" in texts[0] and "Tesseract2" in texts[2]

    def test_a_page_exactly_at_the_threshold_stays_with_tesseract(self, engines):
        engines.conf = {0: 75.0}
        ocr.prepare_pdf(engines.source(1), engines.work)
        assert engines.sent == []

    def test_a_page_with_too_few_words_is_not_sent(self, engines):
        engines.conf = {0: 30.0}
        engines.words = {0: 9}
        result = ocr.prepare_pdf(engines.source(1), engines.work)
        assert engines.sent == [] and result.vision_pages == 0

    def test_a_page_with_exactly_the_minimum_words_is_sent(self, engines):
        engines.conf = {0: 30.0}
        engines.words = {0: 10}
        ocr.prepare_pdf(engines.source(1), engines.work)
        assert engines.sent == [1]

    def test_unknown_confidence_counts_as_enough(self, engines, monkeypatch):
        monkeypatch.setattr(ocr, "measure", lambda page: (None, 0))
        ocr.prepare_pdf(engines.source(2), engines.work)
        assert engines.sent == []

    def test_the_page_limit_applies_in_page_order(self, engines, monkeypatch):
        monkeypatch.setattr(settings, "vision_max_pages", 2)
        engines.conf = {0: 40.0, 1: 40.0, 2: 40.0}
        result = ocr.prepare_pdf(engines.source(3), engines.work)
        assert sum(engines.sent) == 2 and result.vision_pages == 2
        assert "Tesseract2" in page_texts(result.path)[2]

    def test_pages_are_sent_in_batches_of_the_configured_size(self, engines, monkeypatch):
        monkeypatch.setattr(settings, "vision_batch_pages", 2)
        engines.conf = {n: 40.0 for n in range(5)}
        ocr.prepare_pdf(engines.source(5), engines.work)
        assert engines.sent == [2, 2, 1]

    def test_a_page_vision_cannot_read_keeps_the_tesseract_text(self, engines):
        engines.conf = {0: 40.0}
        engines.fail = {1}
        result = ocr.prepare_pdf(engines.source(1), engines.work)
        assert result.vision_pages == 0 and result.ocr_pages == 1 and result.skipped == 0
        assert "Tesseract0" in page_texts(result.path)[0]

    def test_without_tesseract_every_page_that_needs_ocr_goes_to_vision(self, engines):
        engines.on = False
        result = ocr.prepare_pdf(engines.source(3), engines.work)
        assert engines.tess == [] and sum(engines.sent) == 3 and result.vision_pages == 3 and result.skipped == 0

    def test_without_tesseract_a_failed_vision_page_is_skipped(self, engines):
        engines.on = False
        engines.fail = {2}
        result = ocr.prepare_pdf(engines.source(3), engines.work)
        assert result.vision_pages == 2 and result.skipped == 1

    def test_text_pages_never_reach_vision(self, engines, tmp_path):
        engines.conf = {1: 40.0}
        mixed = pymupdf.open()
        mixed.insert_pdf(pymupdf.open("pdf", make_pdf([prose(3) + " " + prose(3, 2)])))
        mixed.insert_pdf(pymupdf.open("pdf", make_scanned_pdf(["x"])))
        source = tmp_path / "campur.pdf"
        source.write_bytes(mixed.tobytes())
        ocr.prepare_pdf(str(source), engines.work)
        assert engines.tess == [1] and engines.sent == [1]


class TestRouterMode:
    def test_the_pages_sent_to_vision_skip_tesseract(self, engines, monkeypatch):
        monkeypatch.setattr(settings, "ocr_engine", "router")
        monkeypatch.setattr(settings, "vision_max_pages", 2)
        result = ocr.prepare_pdf(engines.source(3), engines.work)
        assert engines.tess == [2] and sum(engines.sent) == 2 and result.vision_pages == 2 and result.ocr_pages == 3

    def test_a_failed_vision_page_falls_back_to_running_tesseract(self, engines, monkeypatch):
        monkeypatch.setattr(settings, "ocr_engine", "router")
        engines.fail = {1}
        result = ocr.prepare_pdf(engines.source(2), engines.work)
        assert engines.tess == [0] and result.vision_pages == 1 and result.ocr_pages == 2
        assert "Tesseract0" in page_texts(result.path)[0]

    def test_a_failed_vision_page_without_tesseract_is_skipped(self, engines, monkeypatch):
        monkeypatch.setattr(settings, "ocr_engine", "router")
        engines.on = False
        engines.fail = {1}
        result = ocr.prepare_pdf(engines.source(2), engines.work)
        assert result.skipped == 1 and result.vision_pages == 1


class TestVisionOff:
    def test_the_tesseract_mode_never_uses_vision(self, engines, monkeypatch):
        monkeypatch.setattr(settings, "ocr_engine", "tesseract")
        engines.conf = {0: 20.0, 1: 20.0}
        result = ocr.prepare_pdf(engines.source(2), engines.work)
        assert engines.sent == [] and result.vision_pages == 0 and result.ocr_pages == 2

    def test_without_an_llm_it_behaves_like_tesseract(self, engines, monkeypatch):
        monkeypatch.setattr(vision, "available", lambda: False)
        engines.conf = {0: 20.0}
        result = ocr.prepare_pdf(engines.source(2), engines.work)
        assert engines.sent == [] and engines.tess == [0, 1] and result.vision_pages == 0


class TestWorkingPdf:
    def test_pages_keep_the_size_of_the_original(self, engines):
        engines.conf = {1: 40.0}
        result = ocr.prepare_pdf(engines.source(3), engines.work)
        with pymupdf.open(result.path) as doc, pymupdf.open(engines.source(3)) as original:
            assert len(doc) == 3
            assert [(p.rect.width, p.rect.height) for p in doc] == [(p.rect.width, p.rect.height) for p in original]

    def test_progress_counts_every_page_exactly_once(self, engines):
        engines.conf = {0: 40.0, 2: 40.0}
        seen = []
        ocr.prepare_pdf(engines.source(4), engines.work, on_page=seen.append)
        assert seen == [1, 2, 3, 4]

    def test_it_can_be_stopped_before_the_vision_batches_run(self, engines):
        engines.conf = {0: 40.0, 1: 40.0, 2: 40.0}
        calls = {"n": 0}

        def stop():
            calls["n"] += 1
            return calls["n"] > 3

        result = ocr.prepare_pdf(engines.source(3), engines.work, should_stop=stop)
        assert result.stopped is True and engines.sent == []

    def test_the_outline_survives_vision_pages(self, engines):
        source = engines.source(3)
        with pymupdf.open(source) as doc:
            doc.set_toc([[1, "Bab 1", 1], [1, "Bab 2", 3]])
            doc.save(source, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        engines.conf = {1: 40.0}
        result = ocr.prepare_pdf(source, engines.work)
        with pymupdf.open(result.path) as doc:
            assert [t[1] for t in doc.get_toc()] == ["Bab 1", "Bab 2"]


class TestLowConfidence:
    def test_tesseract_pages_below_the_threshold_with_enough_words_are_counted(self, engines, monkeypatch):
        monkeypatch.setattr(settings, "ocr_engine", "tesseract")
        engines.conf = {0: 40.0, 1: 90.0, 2: 40.0}
        engines.words = {2: 5}
        result = ocr.prepare_pdf(engines.source(3), engines.work)
        assert result.low_confidence_pages == 1

    def test_pages_rescued_by_vision_are_not_counted(self, engines):
        engines.conf = {0: 40.0, 1: 40.0}
        result = ocr.prepare_pdf(engines.source(2), engines.work)
        assert result.vision_pages == 2 and result.low_confidence_pages == 0

    def test_pages_vision_failed_to_rescue_are_still_counted(self, engines):
        engines.conf = {0: 40.0}
        engines.fail = {1}
        result = ocr.prepare_pdf(engines.source(1), engines.work)
        assert result.low_confidence_pages == 1

    def test_unknown_confidence_is_never_low(self, engines, monkeypatch):
        monkeypatch.setattr(ocr, "measure", lambda page: (None, 0))
        assert ocr.prepare_pdf(engines.source(2), engines.work).low_confidence_pages == 0
