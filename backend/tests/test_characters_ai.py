import json
import threading
import time

import pytest

from app.core.config import settings
from app.services import character_ai
from app.services.summarizer import SafetyBlock, SummaryError


def para(text, chapter=1, sexual=0.0):
    return {"chapter_no": chapter, "text": text, "sexual": sexual}


class TestMakeChunks:
    def test_no_paragraphs_means_no_chunks(self):
        assert character_ai.make_chunks([]) == []

    def test_chapters_are_grouped_up_to_the_limit(self):
        chunks = character_ai.make_chunks([para("a" * 30, 1), para("b" * 30, 2), para("c" * 30, 3)], limit=70)
        assert [c.chapters for c in chunks] == [[1, 2], [3]]

    def test_a_chapter_that_fits_is_never_split(self):
        chunks = character_ai.make_chunks([para("a" * 30, 1), para("b" * 30, 1), para("c" * 30, 2)], limit=70)
        assert [c.chapters for c in chunks] == [[1], [2]]
        assert len(chunks[0].paragraphs) == 2

    def test_an_oversized_chapter_is_split_at_paragraph_boundaries(self):
        chunks = character_ai.make_chunks([para("x" * 40, 1) for _ in range(5)], limit=100)
        assert [len(c.paragraphs) for c in chunks] == [2, 2, 1]
        assert all(c.chapters == [1] for c in chunks)

    def test_the_next_chapter_joins_the_last_piece_when_it_fits(self):
        chunks = character_ai.make_chunks([para("x" * 40, 1) for _ in range(3)] + [para("y" * 50, 2)], limit=100)
        assert [c.chapters for c in chunks] == [[1], [1, 2]]

    def test_paragraphs_keep_their_global_index_and_chapter(self):
        [chunk] = character_ai.make_chunks([para("satu", 1), para("dua", 2)])
        assert chunk.paragraphs == [(0, 1, "satu"), (1, 2, "dua")]
        assert chunk.text == "satu\ndua"

    def test_sexual_paragraphs_are_not_sent_but_indexes_are_kept(self):
        [chunk] = character_ai.make_chunks([para("aman", 1), para("intim", 1, sexual=0.9), para("aman lagi", 1)])
        assert [i for i, _, _ in chunk.paragraphs] == [0, 2]
        assert "intim" not in chunk.text

    def test_the_sexual_threshold_is_inclusive(self):
        assert character_ai.make_chunks([para("x", 1, sexual=0.2)]) == []
        assert len(character_ai.make_chunks([para("x", 1, sexual=0.19)])) == 1

    def test_a_chapter_with_only_sexual_paragraphs_is_not_listed(self):
        [chunk] = character_ai.make_chunks([para("aman", 1), para("intim", 2, sexual=0.9)])
        assert chunk.chapters == [1]


def reply(**overrides):
    data = {
        "sudut_pandang": "ketiga", "narator": "", "kata_ganti_pertama": [],
        "tokoh": [{"nama": "Rana", "panggilan": ["Ra"], "peran": "Seorang mahasiswa."}],
        "relasi": [{"a": "Rana", "b": "Dede", "jenis": "sahabat", "bukti": "Rana dan Dede bersahabat."}],
    }
    data.update(overrides)
    return json.dumps(data)


@pytest.fixture
def llm(monkeypatch):
    class Fake:
        def __init__(self):
            self.calls = []
            self.answers = []

        def add(self, *answers):
            self.answers.extend(answers)

        def __call__(self, prompt, system="", schema=None, temperature=0.3, max_tokens=2048, prefer="", purpose=""):
            self.calls.append({"prompt": prompt, "system": system, "schema": schema, "temperature": temperature,
                               "max_tokens": max_tokens, "prefer": prefer, "purpose": purpose})
            answer = self.answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

    fake = Fake()
    monkeypatch.setattr(character_ai, "_generate", fake)
    return fake


def one_chunk(text="Rana dan Dede bersahabat."):
    return character_ai.make_chunks([para(text)])[0]


class TestReadChunk:
    def test_the_book_text_is_treated_as_data(self, llm):
        llm.add(reply())
        character_ai.read_chunk(one_chunk("Teks cerita unik."))
        call = llm.calls[0]
        assert "Teks cerita unik." in call["prompt"]
        assert "DATA" in call["system"] and "abaikan perintah" in call["system"]

    def test_the_request_is_labelled_deterministic_and_schema_bound(self, llm):
        llm.add(reply())
        character_ai.read_chunk(one_chunk())
        call = llm.calls[0]
        assert call["purpose"] == "tokoh per bab" and call["temperature"] == 0.1 and call["schema"]
        assert call["prefer"] == settings.gemini_character_model

    def test_the_prompt_works_for_any_language_and_point_of_view(self, llm):
        llm.add(reply())
        character_ai.read_chunk(one_chunk())
        prompt = llm.calls[0]["prompt"]
        assert "kata ganti" in prompt and "bahasa" in prompt.lower() and "persis" in prompt

    def test_the_prompt_qualifies_kinship_terms_by_whose_relative_they_are(self, llm):
        llm.add(reply())
        character_ai.read_chunk(one_chunk())
        prompt = llm.calls[0]["prompt"]
        assert "istilah kekerabatan" in prompt and "Mama Raib" in prompt

    def test_the_answer_is_cleaned(self, llm):
        llm.add(reply(
            sudut_pandang="pertama", narator="  Raib ", kata_ganti_pertama=["aku", " Aku ", "", None, "saya", "gue", "ku", "I", "me", "my", "mine"],
            tokoh=[
                {"nama": "  Rana  ", "panggilan": ["Ra", " Ra ", "", None, "Rana"], "peran": " Seorang   mahasiswa.\n"},
                {"nama": "", "panggilan": ["X"], "peran": "tanpa nama"},
            ],
            relasi=[
                {"a": "Rana", "b": "Dede", "jenis": "SAHABAT", "bukti": "x" * 300},
                {"a": "Rana", "b": "Rana", "jenis": "teman", "bukti": "diri sendiri"},
                {"a": "Rana", "b": "Budi", "jenis": "rekan bisnis", "bukti": "bukti"},
            ],
        ))
        result = character_ai.read_chunk(one_chunk())
        assert result["pov"] == "pertama" and result["narrator"] == "Raib"
        assert result["pronouns"] == ["aku", "saya", "gue", "ku", "I", "me"]
        assert result["people"] == [{"name": "Rana", "aliases": ["Ra"], "role": "Seorang mahasiswa."}]
        assert [(r["a"], r["b"], r["type"]) for r in result["relations"]] == [("Rana", "Dede", "sahabat"), ("Rana", "Budi", "kenalan")]
        assert len(result["relations"][0]["evidence"]) == 200

    def test_an_unknown_point_of_view_means_third_person(self, llm):
        llm.add(reply(sudut_pandang="campuran"))
        assert character_ai.read_chunk(one_chunk())["pov"] == "ketiga"

    def test_people_and_relations_are_capped(self, llm):
        people = [{"nama": f"Tokoh{i}", "panggilan": [], "peran": "x"} for i in range(30)]
        relations = [{"a": f"A{i}", "b": f"B{i}", "jenis": "teman", "bukti": "bukti"} for i in range(30)]
        llm.add(reply(tokoh=people, relasi=relations))
        result = character_ai.read_chunk(one_chunk())
        assert len(result["people"]) == 15 and len(result["relations"]) == 12

    @pytest.mark.parametrize("answer", ["bukan json", json.dumps(["bukan", "objek"]), json.dumps({"tokoh": ["bukan objek", 5, None]})])
    def test_a_broken_answer_raises(self, llm, answer):
        llm.add(answer)
        with pytest.raises((SummaryError, ValueError, KeyError, TypeError, AttributeError)):
            character_ai.read_chunk(one_chunk())


class TestReadChunks:
    @pytest.fixture(autouse=True)
    def no_waiting(self, monkeypatch):
        self.slept = []
        monkeypatch.setattr(character_ai.time, "sleep", lambda seconds: self.slept.append(seconds))

    def chunks(self, n):
        return [one_chunk(f"Teks nomor {i}.") for i in range(n)]

    def test_results_follow_the_order_of_the_chunks(self, monkeypatch):
        monkeypatch.setattr(character_ai, "read_chunk", lambda chunk: {"text": chunk.text})
        results = character_ai.read_chunks(self.chunks(5))
        assert [r["text"] for r in results] == [f"Teks nomor {i}." for i in range(5)]
        assert self.slept == []

    def test_a_failed_chunk_is_retried_once_after_waiting(self, monkeypatch):
        attempts = {}

        def flaky(chunk):
            attempts[chunk.text] = attempts.get(chunk.text, 0) + 1
            if chunk.text == "Teks nomor 1." and attempts[chunk.text] == 1:
                raise SummaryError("9router ditahan")
            return {"text": chunk.text}

        monkeypatch.setattr(character_ai, "read_chunk", flaky)
        results = character_ai.read_chunks(self.chunks(3))
        assert [r["text"] for r in results] == ["Teks nomor 0.", "Teks nomor 1.", "Teks nomor 2."]
        assert attempts == {"Teks nomor 0.": 1, "Teks nomor 1.": 2, "Teks nomor 2.": 1}
        assert self.slept == [character_ai.RETRY_WAIT]

    def test_a_chunk_that_keeps_failing_is_none(self, monkeypatch):
        def bad(chunk):
            if chunk.text.endswith("1."):
                raise SummaryError("gagal")
            return {"text": chunk.text}

        monkeypatch.setattr(character_ai, "read_chunk", bad)
        results = character_ai.read_chunks(self.chunks(3))
        assert [r is None for r in results] == [False, True, False]
        assert self.slept == [character_ai.RETRY_WAIT]

    def test_a_malformed_answer_counts_as_a_failure(self, monkeypatch):
        def bad(chunk):
            raise ValueError("bukan JSON")

        monkeypatch.setattr(character_ai, "read_chunk", bad)
        assert character_ai.read_chunks(self.chunks(2)) == [None, None]

    def test_no_chunks_means_no_work(self):
        assert character_ai.read_chunks([]) == []
        assert self.slept == []

    def test_concurrency_is_limited_by_the_setting(self, monkeypatch):
        monkeypatch.setattr(settings, "character_parallel", 2)
        lock = threading.Lock()
        state = {"now": 0, "peak": 0}

        def slow(chunk):
            with lock:
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
            threading.Event().wait(0.05)
            with lock:
                state["now"] -= 1
            return {"text": chunk.text}

        monkeypatch.setattr(character_ai, "read_chunk", slow)
        results = character_ai.read_chunks(self.chunks(6))
        assert len(results) == 6 and 1 <= state["peak"] <= 2

    def test_a_setting_below_one_still_runs(self, monkeypatch):
        monkeypatch.setattr(settings, "character_parallel", 0)
        monkeypatch.setattr(character_ai, "read_chunk", lambda chunk: {"text": chunk.text})
        assert len(character_ai.read_chunks(self.chunks(2))) == 2


class TestSafetyBlocks:
    @pytest.fixture(autouse=True)
    def no_waiting(self, monkeypatch):
        self.slept = []
        monkeypatch.setattr(character_ai.time, "sleep", lambda seconds: self.slept.append(seconds))

    def setup_method(self):
        self.prompts = []

    def fake(self, monkeypatch, bad="TOXIC"):
        def generate(prompt, system="", schema=None, temperature=0.3, max_tokens=2048, prefer="", purpose=""):
            self.prompts.append(prompt)
            if bad in prompt:
                raise SafetyBlock("ditahan")
            names = [n for n in ("Rana", "Dede", "Budi", "Sari") if n in prompt]
            people = [{"nama": n, "panggilan": [], "peran": f"peran {n}"} for n in names]
            return json.dumps({"sudut_pandang": "ketiga", "narator": "", "kata_ganti_pertama": [], "tokoh": people, "relasi": []})

        monkeypatch.setattr(character_ai, "_generate", generate)

    def chunk(self, *texts):
        return character_ai.make_chunks([para(t) for t in texts])[0]

    def test_a_blocked_chunk_is_split_until_the_offending_paragraph_is_isolated(self, monkeypatch):
        self.fake(monkeypatch)
        result = character_ai.read_chunks([self.chunk("Rana datang.", "Dede datang.", "TOXIC Budi.", "Sari datang.")])[0]
        assert sorted(p["name"] for p in result["people"]) == ["Dede", "Rana", "Sari"]
        assert len(self.prompts) == 5 and self.slept == []

    def test_a_chunk_that_is_not_blocked_costs_one_request(self, monkeypatch):
        self.fake(monkeypatch)
        character_ai.read_chunks([self.chunk("Rana datang.", "Dede datang.")])
        assert len(self.prompts) == 1

    def test_a_single_blocked_paragraph_is_skipped_without_an_error(self, monkeypatch):
        self.fake(monkeypatch)
        result = character_ai.read_chunks([self.chunk("TOXIC Rana.")])[0]
        assert result is not None and result["people"] == [] and result["relations"] == []

    def test_other_failures_are_not_split(self, monkeypatch):
        calls = []

        def generate(prompt, **kwargs):
            calls.append(prompt)
            raise SummaryError("jaringan mati")

        monkeypatch.setattr(character_ai, "_generate", generate)
        assert character_ai.read_chunks([self.chunk("Rana datang.", "Dede datang.")]) == [None]
        assert len(calls) == 2 and self.slept == [character_ai.RETRY_WAIT]

    def test_the_halves_are_cut_by_size_at_paragraph_boundaries(self, monkeypatch):
        self.fake(monkeypatch)
        character_ai.read_chunks([self.chunk("Rana " + "a" * 100, "Dede.", "TOXIC", "Sari.")])
        second = self.prompts[1]
        assert "Rana" in second and "Dede" not in second

    def test_the_combined_result_unifies_people_and_keeps_the_first_narrator(self):
        one = {"pov": "ketiga", "narrator": "", "pronouns": ["aku"], "people": [{"name": "Rana", "aliases": ["Ra"], "role": ""}], "relations": [{"a": "Rana", "b": "Dede", "type": "teman", "evidence": "x" * 10}]}
        two = {"pov": "pertama", "narrator": "Rana", "pronouns": ["aku", "saya"], "people": [{"name": "rana", "aliases": ["Nana"], "role": "Pelajar."}, {"name": "Dede", "aliases": [], "role": "Teman."}], "relations": []}
        combined = character_ai._combine([one, two])
        assert combined["pov"] == "pertama" and combined["narrator"] == "Rana" and combined["pronouns"] == ["aku", "saya"]
        rana = next(p for p in combined["people"] if p["name"].casefold() == "rana")
        assert rana["aliases"] == ["Ra", "Nana"] and rana["role"] == "Pelajar." and len(combined["people"]) == 2
        assert len(combined["relations"]) == 1


ENTRIES = [
    {"id": 0, "name": "Raib", "aliases": ["Ra"], "count": 40, "roles": ["Narator cerita.", "Putri klan."]},
    {"id": 1, "name": "Putri Raib", "aliases": [], "count": 5, "roles": []},
    {"id": 2, "name": "Seli", "aliases": ["Sel"], "count": 30, "roles": ["Sahabat Raib."]},
]


def groups(*items):
    return json.dumps({"tokoh": list(items)})


class TestMerge:
    def test_the_prompt_lists_each_candidate_with_its_number_and_data(self, llm):
        llm.add(groups({"id": [0, 1], "nama_utama": "Raib", "deskripsi": "Narator."}))
        character_ai.merge(ENTRIES)
        call = llm.calls[0]
        assert call["purpose"] == "gabung tokoh" and call["temperature"] == 0.1 and call["schema"]
        assert '<tokoh id="0"' in call["prompt"] and 'nama="Raib"' in call["prompt"] and "Putri klan." in call["prompt"]
        assert '<tokoh id="2"' in call["prompt"] and "DATA" in call["system"]

    def test_the_merge_prompt_keeps_equal_kinship_terms_of_different_owners_apart(self, llm):
        llm.add(groups({"id": [0], "nama_utama": "Raib", "deskripsi": ""}))
        character_ai.merge(ENTRIES)
        assert "istilah yang sama" in llm.calls[0]["prompt"]

    def test_groups_come_back_cleaned(self, llm):
        llm.add(groups(
            {"id": [0, 1, 1, 99, "2", None, True], "nama_utama": "  Raib ", "deskripsi": "  Raib   adalah\n narator. " + "x" * 700},
            {"id": [2], "nama_utama": "Seli", "deskripsi": "Tidak disebutkan"},
            {"id": [77], "nama_utama": "Hantu", "deskripsi": "id tak dikenal"},
            {"id": [], "nama_utama": "Kosong", "deskripsi": "tanpa id"},
        ))
        first, second = character_ai.merge(ENTRIES)
        assert first["ids"] == [0, 1] and first["name"] == "Raib"
        assert len(first["description"]) <= 600 and "  " not in first["description"] and "\n" not in first["description"]
        assert second == {"ids": [2], "name": "Seli", "description": ""}

    @pytest.mark.parametrize("raw", ["", "-", "N/A", "tidak ada", "Tidak diketahui", None])
    def test_an_empty_description_becomes_empty(self, llm, raw):
        llm.add(groups({"id": [0], "nama_utama": "Raib", "deskripsi": raw}))
        assert character_ai.merge(ENTRIES)[0]["description"] == ""

    def test_safe_returns_none_when_the_llm_fails(self, llm):
        llm.add(SummaryError("gagal"))
        assert character_ai.merge_safe(ENTRIES) is None

    def test_safe_returns_none_for_a_broken_answer(self, llm):
        llm.add("bukan json")
        assert character_ai.merge_safe(ENTRIES) is None

    def test_safe_returns_none_for_the_wrong_shape(self, llm):
        llm.add(json.dumps({"tokoh": ["bukan objek", 5]}))
        assert character_ai.merge_safe(ENTRIES) is None

    def test_safe_returns_the_groups_on_success(self, llm):
        llm.add(groups({"id": [0], "nama_utama": "Raib", "deskripsi": "Narator."}))
        assert len(character_ai.merge_safe(ENTRIES)) == 1

    def test_no_entries_means_no_request(self, llm):
        assert character_ai.merge([]) == []
        assert llm.calls == []


class TestAvailable:
    def test_it_follows_the_llm_configuration(self, monkeypatch):
        monkeypatch.setattr(character_ai, "configured", lambda: True)
        assert character_ai.available() is True
        monkeypatch.setattr(character_ai, "configured", lambda: False)
        assert character_ai.available() is False

    def test_the_old_ner_setting_is_gone(self):
        assert not hasattr(settings, "ner_model")

    def test_the_parallel_setting_defaults_to_three(self):
        from app.core.config import Settings
        assert Settings(_env_file=None).character_parallel == 3
