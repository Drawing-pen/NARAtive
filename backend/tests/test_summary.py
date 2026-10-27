import json
import logging
from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.db import models
from app.services import summarizer
from tests.gemini_fake import DAILY_429, clock, gemini

MARKER = "[adegan dewasa dilewati]"
VIOLENCE_MARKER = "[adegan kekerasan dilewati]"
PROFANITY_MARKER = "[bahasa kasar dilewati]"
ALL_FILTERED = "Bab ini sebagian besar berisi adegan yang dilewati dalam rangkuman (kekerasan, bahasa kasar, atau konten dewasa)."
UNAVAILABLE = "Rangkuman bab ini tidak dapat dibuat."


def build_book(db, owner, chapters, status="done", summary_status="running"):
    doc = models.Document(
        user_id=owner.id, title="Buku Uji", filename="buku.pdf", page_count=10, paragraph_count=0,
        status=status, summary_status=summary_status,
    )
    idx = 0
    for number, (title, paragraphs) in enumerate(chapters, start=1):
        doc.chapters.append(models.Chapter(number=number, title=title))
        for item in paragraphs:
            text, scores = (item, {}) if isinstance(item, str) else item
            doc.paragraphs.append(models.Paragraph(
                idx=idx, chapter_no=number, text=text,
                sexual=scores.get("sexual", 0.0), violence=scores.get("violence", 0.0), profanity=scores.get("profanity", 0.0),
            ))
            idx += 1
    doc.paragraph_count = idx
    db.add(doc)
    db.commit()
    return doc


def reload(db, doc):
    db.expire_all()
    return db.get(models.Document, doc.id)


def summaries(doc):
    return {c.number: c.summary for c in doc.chapters}


def sources(doc):
    return {c.number: c.summary_source for c in doc.chapters}


@pytest.fixture
def middle(make_user):
    return make_user("middle", expires_at=datetime.utcnow() + timedelta(days=10))


class TestEndpoints:
    @pytest.fixture(autouse=True)
    def started(self, monkeypatch):
        self.started = []
        monkeypatch.setattr(summarizer, "configured", lambda: True)
        monkeypatch.setattr(summarizer, "start", lambda doc_id: self.started.append(doc_id))

    def test_cannot_start_before_the_analysis_is_done(self, client, db, middle, auth):
        doc = build_book(db, middle, [("Bab 1", ["Isi."])], status="analyzing", summary_status=None)
        res = client.post(f"/documents/{doc.id}/summary", headers=auth(middle))
        assert res.status_code == 409
        assert res.json()["detail"] == "Rangkuman bisa dibuat setelah analisis selesai."
        assert self.started == []

    def test_needs_the_gemini_key_on_the_server(self, client, db, middle, auth, monkeypatch):
        monkeypatch.undo()
        monkeypatch.setattr(settings, "gemini_api_key", "")
        monkeypatch.setattr(summarizer, "start", lambda doc_id: self.started.append(doc_id))
        doc = build_book(db, middle, [("Bab 1", ["Isi."])], summary_status=None)
        res = client.post(f"/documents/{doc.id}/summary", headers=auth(middle))
        assert res.status_code == 503
        assert res.json()["detail"] == "Layanan rangkuman belum diatur di server (GEMINI_API_KEY kosong)."
        assert self.started == []

    def test_starting_marks_the_summary_as_running_and_launches_one_job(self, client, db, middle, auth):
        doc = build_book(db, middle, [("Bab 1", ["Isi."]), ("Bab 2", ["Isi."])], summary_status=None)
        res = client.post(f"/documents/{doc.id}/summary", headers=auth(middle))
        assert res.status_code == 202
        body = res.json()
        assert body["status"] == "running" and body["total_chapters"] == 2 and body["done_chapters"] == 0
        assert self.started == [doc.id]

    def test_asking_again_while_running_does_not_start_a_second_job(self, client, db, middle, auth):
        doc = build_book(db, middle, [("Bab 1", ["Isi."])], summary_status="running")
        for _ in range(2):
            assert client.post(f"/documents/{doc.id}/summary", headers=auth(middle)).status_code == 202
        assert self.started == []

    def test_regenerating_a_finished_summary_starts_from_scratch(self, client, db, middle, auth):
        doc = build_book(db, middle, [("Bab 1", ["Isi."])], summary_status="done")
        doc.summary = "Lama."
        doc.chapters[0].summary = "Bab lama."
        db.commit()
        client.post(f"/documents/{doc.id}/summary", headers=auth(middle))
        fresh = reload(db, doc)
        assert fresh.summary_status == "running" and fresh.summary is None
        assert summaries(fresh) == {1: None}
        assert self.started == [doc.id]

    def test_retrying_a_failed_summary_keeps_finished_chapters(self, client, db, middle, auth):
        doc = build_book(db, middle, [("Bab 1", ["Isi."]), ("Bab 2", ["Isi."])], summary_status="failed")
        doc.chapters[0].summary = "Sudah jadi."
        db.commit()
        client.post(f"/documents/{doc.id}/summary", headers=auth(middle))
        fresh = reload(db, doc)
        assert fresh.summary_status == "running"
        assert summaries(fresh) == {1: "Sudah jadi.", 2: None}

    def test_continuing_a_partial_summary_keeps_every_chapter_for_the_job_to_sort_out(self, client, db, middle, auth):
        doc = build_book(db, middle, [("Bab 1", ["Isi."]), ("Bab 2", ["Isi."])], summary_status="partial")
        doc.summary = "Sederhana."
        doc.chapters[0].summary, doc.chapters[0].summary_source = "Dari AI.", "ai"
        doc.chapters[1].summary, doc.chapters[1].summary_source = "Lokal.", "local"
        db.commit()
        res = client.post(f"/documents/{doc.id}/summary", headers=auth(middle))
        assert res.status_code == 202
        fresh = reload(db, doc)
        assert fresh.summary_status == "running" and fresh.summary is None
        assert summaries(fresh) == {1: "Dari AI.", 2: "Lokal."}
        assert sources(fresh) == {1: "ai", 2: "local"}
        assert self.started == [doc.id]

    def test_the_summary_tells_where_each_chapter_came_from(self, client, db, middle, auth):
        doc = build_book(db, middle, [("Bab 1", ["Isi."]), ("Bab 2", ["Isi."]), ("Bab 3", ["Isi."])], summary_status="partial")
        doc.chapters[0].summary, doc.chapters[0].summary_source = "Dari AI.", "ai"
        doc.chapters[1].summary, doc.chapters[1].summary_source = "Lokal.", "local"
        doc.chapters[2].summary = "Data lama."
        db.commit()
        body = client.get(f"/documents/{doc.id}/summary", headers=auth(middle)).json()
        assert body["status"] == "partial"
        assert [c["summary_source"] for c in body["chapters"]] == ["ai", "local", None]

    def test_reading_the_summary_shows_progress_and_content(self, client, db, middle, auth):
        doc = build_book(db, middle, [("Bab 1", ["Isi."]), ("Bab 2", ["Isi."])], summary_status="running")
        doc.chapters[0].summary = "Satu."
        db.commit()
        body = client.get(f"/documents/{doc.id}/summary", headers=auth(middle)).json()
        assert body["status"] == "running" and body["done_chapters"] == 1 and body["total_chapters"] == 2
        assert body["overall"] is None
        assert [c["summary"] for c in body["chapters"]] == ["Satu.", None]

    def test_never_created_summary_has_no_status(self, client, db, middle, auth):
        doc = build_book(db, middle, [("Bab 1", ["Isi."])], summary_status=None)
        body = client.get(f"/documents/{doc.id}/summary", headers=auth(middle)).json()
        assert body["status"] is None and body["overall"] is None


class TestPipeline:
    def test_chapters_are_summarised_in_one_request_then_the_whole_book(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Satu."]), ("Bab 2", ["Dua."]), ("Bab 3", ["Tiga."])])
        summarizer.run(doc.id)
        fresh = reload(db, doc)
        assert fresh.summary_status == "done"
        assert fresh.summary == "Rangkuman keseluruhan."
        assert summaries(fresh) == {1: "Rangkuman bab 1.", 2: "Rangkuman bab 2.", 3: "Rangkuman bab 3."}
        assert len(gemini.batch_prompts()) == 1 and len(gemini.overall_prompts()) == 1
        assert len(gemini.calls) == 2

    def test_the_overall_request_uses_the_chapter_summaries(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Awal", ["Satu."]), ("Akhir", ["Dua."])])
        summarizer.run(doc.id)
        prompt = gemini.overall_prompts()[0]["prompt"]
        assert "Bab 1 (Awal): Rangkuman bab 1." in prompt and "Bab 2 (Akhir): Rangkuman bab 2." in prompt

    def test_sexual_paragraphs_are_never_sent_and_are_replaced_by_a_marker(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", [
            "Pembuka aman.",
            ("RAHASIA-ADEGAN-A", {"sexual": 0.9}),
            ("RAHASIA-ADEGAN-B", {"sexual": 0.8}),
            "Penutup aman.",
            ("Hampir lolos.", {"sexual": 0.49}),
        ])])
        summarizer.run(doc.id)
        sent = " ".join(c["prompt"] for c in gemini.calls)
        assert "RAHASIA-ADEGAN" not in sent
        prompt = gemini.batch_prompts()[0]["prompt"]
        assert prompt.count(MARKER) == 1
        assert "Pembuka aman." in prompt and "Penutup aman." in prompt and "Hampir lolos." in prompt

    def test_violent_but_not_sexual_paragraphs_are_still_sent(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", [("Pertarungan berdarah.", {"violence": 0.99, "profanity": 0.9})])])
        summarizer.run(doc.id)
        assert "Pertarungan berdarah." in gemini.batch_prompts()[0]["prompt"]

    def test_long_chapters_are_sent_as_beginning_middle_and_end(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["AWAL" + "x" * 20000 + "AKHIR"])])
        summarizer.run(doc.id)
        prompt = gemini.batch_prompts()[0]["prompt"]
        assert "AWAL" in prompt and "AKHIR" in prompt and "[...]" in prompt
        assert len(prompt) < 9000

    def test_chapters_without_text_are_marked_unavailable_and_not_sent(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Isi satu."]), ("Kosong", []), ("Bab 3", ["Isi tiga."])])
        summarizer.run(doc.id)
        fresh = reload(db, doc)
        assert summaries(fresh) == {1: "Rangkuman bab 1.", 2: UNAVAILABLE, 3: "Rangkuman bab 3."}
        assert 'nomor="2"' not in gemini.batch_prompts()[0]["prompt"]
        assert fresh.summary_status == "done"
        assert "Bab 2" not in gemini.overall_prompts()[0]["prompt"]

    def test_more_than_twenty_chapters_are_split_into_requests(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [(f"Bab {n}", [f"Isi bab {n}."]) for n in range(1, 26)])
        summarizer.run(doc.id)
        sizes = [c["prompt"].count("<bab nomor=") for c in gemini.batch_prompts()]
        assert sizes == [20, 5]
        assert reload(db, doc).summary_status == "done"

    def test_requests_are_also_split_by_size(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [(f"Bab {n}", ["y" * 30000]) for n in range(1, 17)])
        summarizer.run(doc.id)
        sizes = [c["prompt"].count("<bab nomor=") for c in gemini.batch_prompts()]
        assert len(sizes) == 2 and sum(sizes) == 16
        assert all(len(c["prompt"]) < 95000 for c in gemini.batch_prompts())

    def test_a_chapter_missing_from_the_answer_is_summarised_on_its_own(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Satu."]), ("Bab 2", ["Dua."]), ("Bab 3", ["Tiga."])])
        gemini.add(("text", json.dumps({"bab": [{"nomor": 1, "rangkuman": "Satu jadi."}, {"nomor": 3, "rangkuman": "Tiga jadi."}]})))
        summarizer.run(doc.id)
        fresh = reload(db, doc)
        assert summaries(fresh) == {1: "Satu jadi.", 2: "Rangkuman tunggal.", 3: "Tiga jadi."}
        assert len(gemini.single_prompts()) == 1 and 'berjudul "Bab 2"' in gemini.single_prompts()[0]["prompt"]

    def test_an_unreadable_answer_falls_back_to_a_local_summary(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Satu hari yang panjang."])])
        gemini.add(("text", "bukan json"))
        summarizer.run(doc.id)
        fresh = reload(db, doc)
        assert summaries(fresh) == {1: "Satu hari yang panjang."}
        assert sources(fresh) == {1: "local"}
        assert fresh.summary_status == "partial" and fresh.summary == "Rangkuman keseluruhan."
    def test_an_unreadable_answer_for_many_chapters_is_retried_in_halves(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [(f"Bab {n}", [f"Isi {n}."]) for n in range(1, 5)])
        gemini.add(("text", "rusak"))
        summarizer.run(doc.id)
        assert [c["prompt"].count("<bab nomor=") for c in gemini.batch_prompts()] == [4, 2, 2]
        assert reload(db, doc).summary_status == "done"

    def test_resuming_only_does_the_chapters_that_are_not_finished(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Satu."]), ("Bab 2", ["Dua."])], summary_status="failed")
        doc.chapters[0].summary = "Sudah jadi dulu."
        db.commit()
        summarizer.run(doc.id)
        fresh = reload(db, doc)
        assert summaries(fresh) == {1: "Sudah jadi dulu.", 2: "Rangkuman bab 2."}
        prompt = gemini.batch_prompts()[0]["prompt"]
        assert 'nomor="2"' in prompt and 'nomor="1"' not in prompt
        assert fresh.summary_status == "done"

    def test_chapters_marked_unavailable_are_tried_again_on_resume(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Satu."]), ("Bab 2", ["Dua."])], summary_status="failed")
        doc.chapters[0].summary = "Bagus."
        doc.chapters[1].summary = UNAVAILABLE
        db.commit()
        summarizer.run(doc.id)
        assert summaries(reload(db, doc)) == {1: "Bagus.", 2: "Rangkuman bab 2."}

    def test_a_failed_overall_summary_keeps_the_chapters_and_resumes_with_one_request(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Satu."]), ("Bab 2", ["Dua."])])
        gemini.add(gemini.smart, ("http", 400, "salah"))
        summarizer.run(doc.id)
        failed = reload(db, doc)
        assert failed.summary_status == "failed" and failed.summary is None
        assert summaries(failed) == {1: "Rangkuman bab 1.", 2: "Rangkuman bab 2."}
        gemini.calls.clear()
        summarizer.run(doc.id)
        assert len(gemini.calls) == 1 and len(gemini.overall_prompts()) == 1
        assert reload(db, doc).summary_status == "done"

    def test_running_out_of_quota_finishes_locally_and_can_be_upgraded_later(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [(f"Bab {n}", [f"Isi bab {n}."]) for n in range(1, 22)])
        gemini.add(gemini.smart, ("http", 429, DAILY_429))
        summarizer.run(doc.id)
        partial = reload(db, doc)
        assert partial.summary_status == "partial"
        assert all(summaries(partial).values())
        assert [n for n, src in sources(partial).items() if src == "local"] == [21]
        assert summaries(partial)[21] == "Isi bab 21."
        assert partial.summary and "Rangkuman bab 1." in partial.summary
        summarizer._blocked.clear()
        gemini.calls.clear()
        summarizer.run(doc.id)
        assert [c["prompt"].count("<bab nomor=") for c in gemini.batch_prompts()] == [1]
        again = reload(db, doc)
        assert again.summary_status == "done" and sources(again)[21] == "ai"
        assert summaries(again)[21] == "Rangkuman bab 21." and again.summary == "Rangkuman keseluruhan."

    def test_resuming_retries_chapters_that_only_have_a_local_summary(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Satu."]), ("Bab 2", ["Dua."])], summary_status="partial")
        doc.chapters[0].summary, doc.chapters[0].summary_source = "Dari AI.", "ai"
        doc.chapters[1].summary, doc.chapters[1].summary_source = "Sederhana.", "local"
        db.commit()
        summarizer.run(doc.id)
        fresh = reload(db, doc)
        prompt = gemini.batch_prompts()[0]["prompt"]
        assert 'nomor="2"' in prompt and 'nomor="1"' not in prompt
        assert summaries(fresh) == {1: "Dari AI.", 2: "Rangkuman bab 2."}
        assert sources(fresh) == {1: "ai", 2: "ai"}
        assert fresh.summary_status == "done"

    def test_a_server_error_on_the_overall_summary_falls_back_to_a_local_overall(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Satu."]), ("Bab 2", ["Dua."])])
        gemini.add(gemini.smart, *[("http", 503, "x")] * 4)
        summarizer.run(doc.id)
        fresh = reload(db, doc)
        assert fresh.summary_status == "partial"
        assert fresh.summary and "Rangkuman bab 1." in fresh.summary
        assert sources(fresh) == {1: "ai", 2: "ai"}

    def test_a_chapter_that_cannot_be_summarised_on_its_own_falls_back_to_a_local_summary(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Satu."]), ("Bab 2", ["Kalimat dua."]), ("Bab 3", ["Tiga."])])
        gemini.add(
            ("text", json.dumps({"bab": [{"nomor": 1, "rangkuman": "Satu jadi."}, {"nomor": 3, "rangkuman": "Tiga jadi."}]})),
            *[("http", 503, "x")] * 4,
        )
        summarizer.run(doc.id)
        fresh = reload(db, doc)
        assert summaries(fresh) == {1: "Satu jadi.", 2: "Kalimat dua.", 3: "Tiga jadi."}
        assert sources(fresh) == {1: "ai", 2: "local", 3: "ai"}
        assert fresh.summary_status == "partial"

    def test_the_local_summary_only_uses_text_that_passes_the_strict_filter(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", [
            "Pagi hari.", ("DARAH-RAHASIA.", {"violence": 0.8}), ("KASAR-RAHASIA.", {"profanity": 0.7}), ("INTIM-RAHASIA.", {"sexual": 0.25}), "Malam tiba.",
        ])])
        gemini.add(("json", {"promptFeedback": {"blockReason": "SAFETY"}}), ("json", {"promptFeedback": {"blockReason": "SAFETY"}}))
        summarizer.run(doc.id)
        chapter = summaries(reload(db, doc))[1]
        assert "Pagi hari." in chapter and "Malam tiba." in chapter and "RAHASIA" not in chapter
    def test_credential_errors_stop_immediately(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Satu."]), ("Bab 2", ["Dua."])])
        gemini.add(("http", 403, "kunci salah"))
        summarizer.run(doc.id)
        assert reload(db, doc).summary_status == "failed"
        assert len(gemini.calls) == 1

    def test_a_safety_block_is_retried_once_with_markers_instead_of_the_filtered_paragraphs(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", [
            "Aman saja.", ("KEKERASAN-KERAS", {"violence": 0.6}), ("SEKSUAL-RINGAN", {"sexual": 0.3}), ("KASAR-SEKALI", {"profanity": 0.55}),
        ])])
        gemini.add(("json", {"promptFeedback": {"blockReason": "SAFETY"}}))
        summarizer.run(doc.id)
        first, second = gemini.batch_prompts()
        for word in ("KEKERASAN-KERAS", "SEKSUAL-RINGAN", "KASAR-SEKALI"):
            assert word in first["prompt"] and word not in second["prompt"]
        for marker in (VIOLENCE_MARKER, MARKER, PROFANITY_MARKER):
            assert marker in second["prompt"] and marker not in first["prompt"]
        assert "Aman saja." in second["prompt"]
        fresh = reload(db, doc)
        assert fresh.summary_status == "done" and summaries(fresh) == {1: "Rangkuman bab 1."}
        assert sources(fresh) == {1: "ai"}
        assert len(gemini.batch_prompts()) == 2

    def test_consecutive_filtered_paragraphs_collapse_into_one_marker_of_each_kind(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", [
            "Awal.", ("K1", {"violence": 0.9}), ("K2", {"violence": 0.8}), ("S1", {"sexual": 0.4}), ("S2", {"sexual": 0.4}), "Akhir.",
        ])])
        gemini.add(("json", {"promptFeedback": {"blockReason": "SAFETY"}}))
        summarizer.run(doc.id)
        second = gemini.batch_prompts()[1]["prompt"]
        assert second.count(VIOLENCE_MARKER) == 1 and second.count(MARKER) == 1
    def test_a_second_safety_block_falls_back_to_a_local_summary_without_a_third_try(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Rana pulang ke rumah.", ("Perkelahian berdarah RAHASIA.", {"violence": 0.9}), "Ia tidur nyenyak."])])
        gemini.add(("json", {"promptFeedback": {"blockReason": "SAFETY"}}), ("json", {"promptFeedback": {"blockReason": "PROHIBITED_CONTENT"}}))
        summarizer.run(doc.id)
        fresh = reload(db, doc)
        assert len(gemini.batch_prompts()) == 2 and len(gemini.single_prompts()) == 0
        chapter = summaries(fresh)[1]
        assert "Rana pulang ke rumah." in chapter and "Ia tidur nyenyak." in chapter and "RAHASIA" not in chapter
        assert sources(fresh) == {1: "local"}
        assert fresh.summary_status == "partial" and fresh.summary == "Rangkuman keseluruhan."
    def test_a_block_on_one_chapter_does_not_stop_the_rest_when_the_stricter_text_passes(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Aman satu."]), ("Bab 2", ["Aman dua.", ("Keras.", {"violence": 0.7})])])
        gemini.add(("json", {"promptFeedback": {"blockReason": "SAFETY"}}))
        summarizer.run(doc.id)
        assert summaries(reload(db, doc)) == {1: "Rangkuman bab 1.", 2: "Rangkuman bab 2."}

    def test_a_chapter_that_is_only_markers_after_filtering_is_never_resent(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Aman satu."]), ("Bab 2", [("Hanya kekerasan RAHASIA.", {"violence": 0.9})])])
        gemini.add(("json", {"promptFeedback": {"blockReason": "SAFETY"}}))
        summarizer.run(doc.id)
        fresh = reload(db, doc)
        second = gemini.batch_prompts()[1]["prompt"]
        assert 'nomor="2"' not in second
        assert len(gemini.single_prompts()) == 0
        assert "RAHASIA" not in " ".join(c["prompt"] for c in gemini.calls[1:])
        assert summaries(fresh) == {1: "Rangkuman bab 1.", 2: ALL_FILTERED}
        assert sources(fresh) == {1: "ai", 2: "local"}
        assert fresh.summary_status == "partial"
    def test_when_nothing_can_be_summarised_the_status_is_failed(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Kosong", [])])
        summarizer.run(doc.id)
        fresh = reload(db, doc)
        assert fresh.summary_status == "failed" and fresh.summary is None
        assert gemini.calls == []

    def test_a_missing_document_is_ignored(self, gemini):
        summarizer.run(99999)
        assert gemini.calls == []

    def test_content_is_only_sent_once_per_run_request(self, db, make_user, gemini):
        doc = build_book(db, make_user("middle"), [("Bab 1", ["RAHASIA-ISI-BUKU"])])
        summarizer.run(doc.id)
        assert sum("RAHASIA-ISI-BUKU" in c["prompt"] for c in gemini.calls) == 1


class TestRequestLabels:
    def test_each_kind_of_request_is_labelled_in_the_log(self, db, make_user, gemini, caplog):
        caplog.set_level(logging.INFO, logger="uvicorn.error")
        doc = build_book(db, make_user("middle"), [("Bab 1", ["Satu."]), ("Bab 2", ["Dua."]), ("Bab 3", ["Tiga."])])
        gemini.add(("text", json.dumps({"bab": [{"nomor": 1, "rangkuman": "Satu."}, {"nomor": 3, "rangkuman": "Tiga."}]})))
        summarizer.run(doc.id)
        lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Gemini |")]
        assert ["kelompok" in l for l in lines].count(True) == 1
        assert sum("rangkuman bab (tunggal)" in l for l in lines) == 1
        assert sum("rangkuman keseluruhan" in l for l in lines) == 1
        assert len(lines) == len(gemini.calls) == 3

    def test_heaviness_and_character_requests_are_labelled(self, gemini, caplog, monkeypatch):
        from app.services import character_ai, heaviness
        caplog.set_level(logging.INFO, logger="uvicorn.error")
        gemini.add(("text", json.dumps({"kerumitan_konflik": 4, "berat_tema": 5, "beban_membaca": 6, "alasan": "Sedang."})))
        heaviness.rate("Judul", ["Bab 1"], ["Isi."])
        gemini.add(("text", json.dumps({"tokoh": []})))
        character_ai.analyze([{"id": 0, "name": "Rana", "snippets": ["Rana pergi."]}])
        lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Gemini |")]
        assert "bobot cerita" in lines[0] and "biodata tokoh" in lines[1]


class TestRecovery:
    def test_summaries_left_running_are_marked_failed_on_startup(self, db, make_user):
        owner = make_user("middle")
        running = build_book(db, owner, [("Bab 1", ["Satu."])], summary_status="running")
        done = build_book(db, owner, [("Bab 1", ["Satu."])], summary_status="done")
        never = build_book(db, owner, [("Bab 1", ["Satu."])], summary_status=None)
        summarizer.reset_stale()
        assert reload(db, running).summary_status == "failed"
        assert reload(db, done).summary_status == "done"
        assert reload(db, never).summary_status is None
