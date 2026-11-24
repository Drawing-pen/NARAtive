import json
import re

import pytest

from app.core.config import settings
from app.ml import lexicon
from app.ml.analyzer import summarize
from app.services import llm_analyzer
from app.services.llm_analyzer import AnalysisError, Scene, make_chunks, parse_scenes, redact, scene_scores
from app.services.summarizer import SafetyBlock, SummaryError

EXPLICIT = "Mereka bersetubuh di ranjang."
VERY_EXPLICIT = "Mereka bersetubuh lalu bercinta semalaman."
PLAIN = "Dia berjalan ke pasar membeli sayur."


def numbered(prompt: str) -> dict[int, str]:
    return {int(n): text for n, text in re.findall(r"^\[(\d+)\] (.*)$", prompt, flags=re.M)}


class FakeLLM:
    def __init__(self, plan=None):
        self.plan = plan or (lambda paragraphs: [])
        self.calls = []

    def __call__(self, prompt, system="", schema=None, temperature=0.3, max_tokens=2048, prefer="", purpose=""):
        paragraphs = numbered(prompt)
        self.calls.append({"prompt": prompt, "system": system, "paragraphs": paragraphs, "temperature": temperature, "purpose": purpose, "schema": schema})
        result = self.plan(paragraphs)
        if isinstance(result, Exception):
            raise result
        return json.dumps({"adegan": result})


@pytest.fixture
def llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(llm_analyzer, "_generate", fake)
    return fake


def items(*texts, chapter=1):
    return [(chapter, t) for t in texts]


class TestChunks:
    def test_whole_chapters_are_grouped_up_to_the_limit(self):
        data = [(1, "a" * 100), (2, "b" * 100), (3, "c" * 100)]
        chunks = make_chunks(data, limit=250)
        assert [c.indices for c in chunks] == [[0, 1], [2]]

    def test_a_chapter_longer_than_the_limit_is_cut_at_paragraph_boundaries(self):
        data = [(1, "a" * 100)] * 5
        chunks = make_chunks(data, limit=250)
        assert [c.indices for c in chunks] == [[0, 1], [2, 3], [4]]

    def test_every_paragraph_appears_exactly_once_and_in_order(self):
        data = [(1, "x" * 60), (1, "y" * 60), (2, "z" * 60), (3, "w" * 500), (3, "v" * 60)]
        chunks = make_chunks(data, limit=200)
        flat = [i for c in chunks for i in c.indices]
        assert flat == list(range(len(data)))

    def test_the_prompt_numbers_paragraphs_from_one_in_each_chunk(self):
        data = [(1, "a" * 100), (1, "b" * 100), (1, "c" * 100)]
        chunks = make_chunks(data, limit=250)
        assert numbered(chunks[0].prompt) == {1: "a" * 100, 2: "b" * 100}
        assert numbered(chunks[1].prompt) == {1: "c" * 100}

    def test_newlines_inside_a_paragraph_are_collapsed(self):
        chunk = make_chunks([(1, "baris satu\nbaris dua")], limit=1000)[0]
        assert numbered(chunk.prompt) == {1: "baris satu baris dua"}

    def test_no_paragraphs_means_no_chunks(self):
        assert make_chunks([], limit=1000) == []

    def test_the_limit_defaults_to_the_setting(self, monkeypatch):
        monkeypatch.setattr(settings, "analyzer_chunk_chars", 150)
        assert len(make_chunks([(1, "a" * 100), (1, "b" * 100)])) == 2


class TestRedaction:
    def test_plain_text_is_unchanged(self):
        assert redact(PLAIN, lexicon.sexual_lexicon_score(PLAIN)) == PLAIN

    def test_a_moderate_paragraph_keeps_context_but_loses_the_explicit_word(self):
        out = redact(EXPLICIT, lexicon.sexual_lexicon_score(EXPLICIT))
        assert "bersetubuh" not in out and "[eksplisit]" in out and "ranjang" in out

    def test_a_very_explicit_paragraph_is_replaced_by_a_marker(self):
        assert lexicon.sexual_lexicon_score(VERY_EXPLICIT) >= 0.8
        assert redact(VERY_EXPLICIT, lexicon.sexual_lexicon_score(VERY_EXPLICIT)) == "[paragraf eksplisit]"

    def test_weak_terms_below_the_weight_floor_stay(self):
        text = "Paha ayam goreng itu enak."
        assert redact(text, lexicon.sexual_lexicon_score(text)) == text

    def test_lexicon_redact_helper_replaces_only_strong_matches(self):
        assert lexicon.redact("Mereka bersetubuh di ranjang.", 0.3) == "Mereka [eksplisit] di ranjang."


class TestParsing:
    def scenes(self, payload, count=10):
        return parse_scenes(json.dumps({"adegan": payload}), count)

    def test_a_valid_scene_is_read(self):
        assert self.scenes([{"dari": 2, "sampai": 4, "jenis": "kekerasan", "tingkat": 2}]) == [Scene(2, 4, "violence", 2)]

    def test_the_three_kinds_map_to_score_dimensions(self):
        data = [{"dari": 1, "sampai": 1, "jenis": j, "tingkat": 2} for j in ("kekerasan", "bahasa_kasar", "seksual")]
        assert sorted(s.jenis for s in self.scenes(data)) == ["profanity", "sexual", "violence"]

    def test_ranges_outside_the_numbers_are_dropped(self):
        data = [
            {"dari": 0, "sampai": 2, "jenis": "kekerasan", "tingkat": 2},
            {"dari": 9, "sampai": 11, "jenis": "kekerasan", "tingkat": 2},
            {"dari": 4, "sampai": 3, "jenis": "kekerasan", "tingkat": 2},
            {"dari": 2, "sampai": 3, "jenis": "kekerasan", "tingkat": 2},
        ]
        assert self.scenes(data) == [Scene(2, 3, "violence", 2)]

    def test_unknown_kinds_are_dropped_and_bad_levels_count_as_one(self):
        data = [
            {"dari": 1, "sampai": 2, "jenis": "emosi", "tingkat": 3},
            {"dari": 3, "sampai": 4, "jenis": "kekerasan", "tingkat": 9},
            {"dari": 5, "sampai": 5, "jenis": "kekerasan"},
        ]
        assert self.scenes(data) == [Scene(3, 4, "violence", 1), Scene(5, 5, "violence", 1)]

    def test_overlapping_scenes_of_one_kind_are_merged_with_the_higher_level(self):
        data = [
            {"dari": 1, "sampai": 3, "jenis": "kekerasan", "tingkat": 2},
            {"dari": 3, "sampai": 5, "jenis": "kekerasan", "tingkat": 3},
        ]
        assert self.scenes(data) == [Scene(1, 5, "violence", 3)]

    def test_scenes_of_different_kinds_stay_separate(self):
        data = [
            {"dari": 1, "sampai": 3, "jenis": "kekerasan", "tingkat": 2},
            {"dari": 2, "sampai": 4, "jenis": "seksual", "tingkat": 2},
        ]
        assert len(self.scenes(data)) == 2

    def test_invalid_json_is_an_error(self):
        with pytest.raises(ValueError):
            parse_scenes("bukan json", 3)

    def test_a_missing_scene_list_means_no_scenes(self):
        assert parse_scenes("{}", 3) == []


class TestScores:
    def test_levels_map_to_scores(self):
        scenes = [Scene(1, 1, "violence", 1), Scene(2, 2, "violence", 2), Scene(3, 3, "violence", 3)]
        assert [r["violence"] for r in scene_scores(scenes, 4)] == [0.3, 0.85, 0.95, 0.0]

    def test_everything_outside_a_scene_is_zero_on_all_dimensions(self):
        assert scene_scores([], 2) == [{"profanity": 0.0, "sexual": 0.0, "violence": 0.0}] * 2

    def test_the_highest_level_wins_when_scenes_overlap_in_the_scorer(self):
        scenes = [Scene(1, 2, "sexual", 2), Scene(2, 3, "sexual", 3)]
        assert [r["sexual"] for r in scene_scores(scenes, 3)] == [0.85, 0.95, 0.95]


class TestAnalyze:
    def test_no_paragraphs_make_no_calls(self, llm):
        assert analyze_all([]) == [] and llm.calls == []

    def test_a_scene_marks_its_paragraphs_and_the_rest_stay_clean(self, llm):
        llm.plan = lambda p: [{"dari": 2, "sampai": 3, "jenis": "kekerasan", "tingkat": 2}]
        out = analyze_all(items("satu", "dua", "tiga", "empat"))
        assert [r["violence"] for r in out] == [0.0, 0.85, 0.85, 0.0]
        assert all(set(r) == {"profanity", "sexual", "violence"} for r in out)

    def test_scene_numbers_are_local_to_each_chunk_and_mapped_back(self, llm, monkeypatch):
        monkeypatch.setattr(settings, "analyzer_chunk_chars", 25)
        llm.plan = lambda p: [{"dari": 2, "sampai": 2, "jenis": "kekerasan", "tingkat": 3}]
        out = analyze_all(items("aaaaaaaaaa", "bbbbbbbbbb", "cccccccccc", "dddddddddd"))
        assert len(llm.calls) == 2
        assert [r["violence"] for r in out] == [0.0, 0.95, 0.0, 0.95]

    def test_the_lexicon_still_counts_when_the_llm_misses_a_paragraph(self, llm):
        out = analyze_all(items(PLAIN, VERY_EXPLICIT, PLAIN))
        assert out[1]["sexual"] >= 0.8 and out[0]["sexual"] == 0.0

    def test_the_final_sexual_score_is_the_maximum_of_llm_and_lexicon(self, llm):
        llm.plan = lambda p: [{"dari": 1, "sampai": 2, "jenis": "seksual", "tingkat": 3}]
        out = analyze_all(items(PLAIN, EXPLICIT))
        assert out[0]["sexual"] == 0.95 and out[1]["sexual"] == 0.95

    def test_explicit_text_never_reaches_the_llm(self, llm):
        analyze_all(items(PLAIN, EXPLICIT, VERY_EXPLICIT))
        sent = llm.calls[0]["prompt"]
        assert "bersetubuh" not in sent and "bercinta" not in sent
        assert numbered(sent)[3] == "[paragraf eksplisit]" and "[eksplisit]" in numbered(sent)[2]

    def test_the_call_is_labelled_and_cold(self, llm):
        analyze_all(items(PLAIN))
        assert llm.calls[0]["purpose"] == "sensor per bab" and llm.calls[0]["temperature"] == 0.1
        assert llm.calls[0]["schema"]

    def test_the_prompt_treats_the_text_as_data_and_forbids_quoting(self, llm):
        analyze_all(items(PLAIN))
        assert "kutip" in llm.calls[0]["prompt"].lower()
        assert "DATA" in llm.calls[0]["system"]


class TestFailures:
    def test_a_blocked_chunk_is_split_and_both_halves_succeed(self, llm):
        def plan(p):
            if len(p) > 2:
                return SafetyBlock("ditolak")
            return [{"dari": 1, "sampai": 1, "jenis": "kekerasan", "tingkat": 3}]

        llm.plan = plan
        out = analyze_all(items("a", "b", "c", "d"))
        assert [r["violence"] for r in out] == [0.95, 0.0, 0.95, 0.0]
        assert [len(c["paragraphs"]) for c in llm.calls] == [4, 2, 2]

    def test_a_single_blocked_paragraph_falls_back_to_the_lexicon_only(self, llm):
        def plan(p):
            return SafetyBlock("ditolak") if any("bersetubuh" in t or "paragraf eksplisit" in t for t in p.values()) else []

        llm.plan = plan
        out = analyze_all(items(PLAIN, VERY_EXPLICIT, PLAIN))
        assert out[1]["sexual"] >= 0.8 and out[0]["sexual"] == 0.0 and out[2]["sexual"] == 0.0

    def test_a_failed_chunk_is_retried_once_after_the_others(self, llm, monkeypatch):
        monkeypatch.setattr(settings, "analyzer_chunk_chars", 15)
        monkeypatch.setattr(llm_analyzer, "RETRY_WAIT", 0)
        seen = {"n": 0}

        def plan(p):
            seen["n"] += 1
            if seen["n"] == 1:
                return SummaryError("gangguan")
            return [{"dari": 1, "sampai": 1, "jenis": "kekerasan", "tingkat": 3}]

        llm.plan = plan
        out = analyze_all(items("aaaaaaaaaa", "bbbbbbbbbb"))
        assert [r["violence"] for r in out] == [0.95, 0.95]

    def test_a_chunk_that_keeps_failing_uses_the_lexicon_and_the_book_still_finishes(self, llm, monkeypatch):
        monkeypatch.setattr(settings, "analyzer_chunk_chars", 15)
        monkeypatch.setattr(llm_analyzer, "RETRY_WAIT", 0)

        def plan(p):
            if "aaaaaaaaaa" in p.values():
                return SummaryError("gangguan")
            return [{"dari": 1, "sampai": 1, "jenis": "kekerasan", "tingkat": 3}]

        llm.plan = plan
        out = analyze_all(items("aaaaaaaaaa", "bbbbbbbbbb"))
        assert out[0] == {"profanity": 0.0, "sexual": 0.0, "violence": 0.0}
        assert out[1]["violence"] == 0.95

    def test_bad_json_counts_as_a_failure(self, llm, monkeypatch):
        monkeypatch.setattr(llm_analyzer, "RETRY_WAIT", 0)
        monkeypatch.setattr(llm_analyzer, "_generate", lambda *a, **k: "bukan json")
        with pytest.raises(AnalysisError):
            analyze_all(items(PLAIN))

    def test_when_every_chunk_fails_the_whole_analysis_fails(self, llm, monkeypatch):
        monkeypatch.setattr(llm_analyzer, "RETRY_WAIT", 0)
        llm.plan = lambda p: SummaryError("mati")
        with pytest.raises(AnalysisError) as info:
            analyze_all(items(PLAIN, PLAIN))
        assert "Layanan AI belum bisa dihubungi" in str(info.value)
        assert "mati" not in str(info.value)


class TestReadiness:
    def test_ready_only_when_an_llm_is_configured(self, monkeypatch):
        monkeypatch.setattr(llm_analyzer, "configured", lambda: True)
        assert llm_analyzer.available() is True
        monkeypatch.setattr(llm_analyzer, "configured", lambda: False)
        assert llm_analyzer.available() is False


class TestSummarizeWithoutEmotion:
    def results(self, violence_hits, total=10):
        return [{"profanity": 0.0, "sexual": 0.0, "violence": 0.9 if i < violence_hits else 0.0} for i in range(total)]

    def test_the_llm_heaviness_is_used_as_is(self):
        assert summarize(self.results(2), ai=64.0)["heaviness"] == 64.0

    def test_without_the_llm_heaviness_falls_back_to_the_violence_share(self):
        assert summarize(self.results(2), ai=None)["heaviness"] == 20.0

    def test_no_emotion_is_reported(self):
        assert "emotion" not in summarize(self.results(1))

    def test_rating_still_uses_the_thresholds(self):
        assert summarize(self.results(5))["rating"] == "Mature"


def analyze_all(data):
    return llm_analyzer.analyze(data)
