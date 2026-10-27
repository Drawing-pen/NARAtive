import logging

import pytest

from app.core.config import settings
from app.services import summarizer
from tests.gemini_fake import DAILY_429, MINUTE_429, clock, gemini, minute_429


def test_request_goes_to_the_configured_model_with_the_key_in_a_header(gemini):
    gemini.add(("text", "Halo"))
    assert summarizer._generate("Tes") == "Halo"
    call = gemini.calls[0]
    assert call["url"].endswith("models/m1:generateContent")
    assert call["key"] == "kunci-rahasia"
    assert "kunci-rahasia" not in call["url"]
    assert "kunci-rahasia" not in str(call["body"])


def test_request_asks_gemini_to_block_only_high_risk_content(gemini):
    gemini.add(("text", "Halo"))
    summarizer._generate("Tes")
    thresholds = {s["threshold"] for s in gemini.calls[0]["body"]["safetySettings"]}
    assert thresholds == {"BLOCK_ONLY_HIGH"}


def test_all_text_parts_are_joined(gemini):
    gemini.add(("parts", ["Satu ", "dua"]))
    assert summarizer._generate("Tes") == "Satu dua"


def test_server_errors_are_retried_after_5_15_and_40_seconds(gemini, clock):
    gemini.add(("http", 503, "x"), ("http", 500, "x"), ("http", 502, "x"), ("text", "Akhirnya"))
    assert summarizer._generate("Tes") == "Akhirnya"
    assert clock.sleeps == [5, 15, 40]
    assert len(gemini.calls) == 4


def test_server_errors_give_up_after_three_retries(gemini, clock):
    gemini.add(*[("http", 503, "x")] * 4)
    with pytest.raises(summarizer.SummaryError) as err:
        summarizer._generate("Tes")
    assert "(503)" in str(err.value)
    assert clock.sleeps == [5, 15, 40]
    assert len(gemini.calls) == 4


def test_network_failures_are_retried_then_reported(gemini, clock):
    gemini.add(("net",), ("net",), ("net",), ("net",))
    with pytest.raises(summarizer.SummaryError) as err:
        summarizer._generate("Tes")
    assert "Tidak bisa menghubungi Gemini" in str(err.value)
    assert clock.sleeps == [5, 15, 40]


def test_network_failure_recovers(gemini, clock):
    gemini.add(("net",), ("text", "Pulih"))
    assert summarizer._generate("Tes") == "Pulih"


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_client_errors_are_not_retried(gemini, clock, code):
    gemini.add(("http", code, "ditolak"))
    with pytest.raises(summarizer.SummaryError) as err:
        summarizer._generate("Tes")
    assert f"({code})" in str(err.value)
    assert len(gemini.calls) == 1 and clock.sleeps == []


def test_per_minute_limit_waits_for_the_suggested_delay(gemini, clock):
    gemini.add(("http", 429, minute_429(7)), ("text", "Lolos"))
    assert summarizer._generate("Tes") == "Lolos"
    assert any(8 <= s <= 9 for s in clock.sleeps)
    assert len(gemini.calls) == 2


def test_suggested_delay_is_capped_at_ninety_seconds(gemini, clock):
    gemini.add(("http", 429, minute_429(500)), ("text", "Lolos"))
    assert summarizer._generate("Tes") == "Lolos"
    assert max(clock.sleeps) <= 91


def test_per_minute_limit_gives_up_after_four_waits(gemini, clock):
    gemini.add(*[("http", 429, MINUTE_429)] * 5)
    with pytest.raises(summarizer.QuotaError):
        summarizer._generate("Tes")
    assert len(gemini.calls) == 5
    assert len(clock.sleeps) == 4


def test_daily_limit_moves_to_the_fallback_model(gemini, clock, monkeypatch):
    monkeypatch.setattr(settings, "gemini_fallback_model", "m2")
    gemini.add(("http", 429, DAILY_429), ("text", "Dari cadangan"))
    assert summarizer._generate("Tes") == "Dari cadangan"
    assert [c["model"] for c in gemini.calls] == ["m1", "m2"]


def test_blocked_model_stays_blocked_for_an_hour(gemini, clock, monkeypatch):
    monkeypatch.setattr(settings, "gemini_fallback_model", "m2")
    gemini.add(("http", 429, DAILY_429), ("text", "satu"))
    summarizer._generate("Tes")
    gemini.add(("text", "dua"))
    summarizer._generate("Tes")
    assert gemini.calls[-1]["model"] == "m2"
    clock.now += 3601
    gemini.add(("text", "tiga"))
    summarizer._generate("Tes")
    assert gemini.calls[-1]["model"] == "m1"


def test_all_models_out_of_daily_quota_reports_it(gemini, clock, monkeypatch):
    monkeypatch.setattr(settings, "gemini_fallback_model", "m2")
    gemini.add(("http", 429, DAILY_429), ("http", 429, DAILY_429))
    with pytest.raises(summarizer.QuotaError) as err:
        summarizer._generate("Tes")
    assert "Kuota harian Gemini habis" in str(err.value)


def test_single_model_out_of_daily_quota_reports_it(gemini, clock):
    gemini.add(("http", 429, DAILY_429))
    with pytest.raises(summarizer.QuotaError):
        summarizer._generate("Tes")
    assert len(gemini.calls) == 1


def test_calls_are_spaced_by_the_minimum_interval(gemini, clock, monkeypatch):
    monkeypatch.setattr(settings, "gemini_min_interval", 13.0)
    gemini.add(("text", "a"), ("text", "b"))
    summarizer._generate("satu")
    summarizer._generate("dua")
    assert clock.sleeps == [13.0]


def test_safety_block_in_the_prompt_feedback_is_reported(gemini):
    gemini.add(("json", {"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(summarizer.SafetyBlock):
        summarizer._generate("Tes")


def test_safety_stop_without_text_is_reported(gemini):
    gemini.add(("json", {"candidates": [{"finishReason": "SAFETY"}]}))
    with pytest.raises(summarizer.SafetyBlock):
        summarizer._generate("Tes")


def test_empty_answer_without_a_safety_reason_is_a_plain_error(gemini):
    gemini.add(("json", {"candidates": [{"finishReason": "MAX_TOKENS"}]}))
    with pytest.raises(summarizer.SummaryError) as err:
        summarizer._generate("Tes")
    assert not isinstance(err.value, summarizer.SafetyBlock)
    assert "tidak mengembalikan teks" in str(err.value)


def test_no_candidates_at_all_is_a_plain_error(gemini):
    gemini.add(("json", {}))
    with pytest.raises(summarizer.SummaryError):
        summarizer._generate("Tes")


@pytest.fixture
def gemini_log(caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    return lambda: [r.getMessage() for r in caplog.records if r.getMessage().startswith("Gemini |")]


def test_each_request_is_logged_with_purpose_model_and_tokens(gemini, gemini_log):
    gemini.add(("text", "Halo", {"promptTokenCount": 120, "candidatesTokenCount": 15}))
    summarizer._generate("Tes", purpose="bobot cerita")
    [line] = gemini_log()
    assert "bobot cerita" in line and "model=m1" in line and "ok" in line
    assert "token masuk=120 keluar=15" in line


def test_a_request_without_a_label_is_still_logged(gemini, gemini_log):
    gemini.add(("text", "Halo"))
    summarizer._generate("Tes")
    assert "tanpa label" in gemini_log()[0]


def test_every_attempt_is_logged_including_failures(gemini, gemini_log, clock):
    gemini.add(("http", 503, "x"), ("net",), ("http", 429, MINUTE_429), ("text", "Lolos"))
    summarizer._generate("Tes", purpose="rangkuman keseluruhan")
    outcomes = gemini_log()
    assert len(outcomes) == 4
    assert "galat 503" in outcomes[0] and "jaringan gagal" in outcomes[1] and "429 batas per menit" in outcomes[2] and outcomes[3].count("| ok |") == 1


def test_daily_quota_and_safety_blocks_are_logged(gemini, gemini_log, clock, monkeypatch):
    monkeypatch.setattr(settings, "gemini_fallback_model", "m2")
    gemini.add(("http", 429, DAILY_429), ("json", {"promptFeedback": {"blockReason": "SAFETY"}}))
    with pytest.raises(summarizer.SafetyBlock):
        summarizer._generate("Tes", purpose="bobot cerita")
    lines = gemini_log()
    assert "429 kuota harian habis" in lines[0] and "model=m1" in lines[0]
    assert "tanpa teks (SAFETY)" in lines[1] and "model=m2" in lines[1]


def test_logs_never_contain_the_key_or_the_book_text(gemini, gemini_log):
    gemini.add(("text", "Jawaban rahasia"), ("http", 400, "RAHASIA-DARI-SERVER"))
    summarizer._generate("ISI-BUKU-RAHASIA", purpose="rangkuman bab (tunggal)")
    with pytest.raises(summarizer.SummaryError):
        summarizer._generate("ISI-BUKU-RAHASIA", purpose="rangkuman bab (tunggal)")
    joined = " ".join(gemini_log())
    for secret in ("kunci-rahasia", "ISI-BUKU-RAHASIA", "Jawaban rahasia", "RAHASIA-DARI-SERVER"):
        assert secret not in joined
