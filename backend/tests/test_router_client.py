import logging

import pytest

from app.core.config import settings
from app.services import summarizer
from tests.gemini_fake import clock, gemini
from tests.router_fake import BASE, KEY, router

SCHEMA = {"type": "OBJECT", "properties": {"ok": {"type": "BOOLEAN"}}}

FAILURES = [
    pytest.param(("http", 429, '{"error":"terlalu cepat"}'), id="429"),
    pytest.param(("http", 500, "x"), id="500"),
    pytest.param(("http", 503, "x"), id="503"),
    pytest.param(("http", 401, "kunci salah"), id="401"),
    pytest.param(("http", 403, "ditolak"), id="403"),
    pytest.param(("http", 404, "model tidak ada"), id="404"),
    pytest.param(("net",), id="jaringan"),
    pytest.param(("empty",), id="tanpa-pilihan"),
    pytest.param(("text", "   "), id="teks-kosong"),
    pytest.param(("filtered",), id="content-filter"),
]


class TestRequest:
    def test_it_posts_to_chat_completions_with_a_bearer_key(self, router):
        assert summarizer._generate("Halo") == "Dari router"
        call = router.calls[0]
        assert call["url"] == f"{BASE}/chat/completions"
        assert call["auth"] == f"Bearer {KEY}"

    def test_a_trailing_slash_on_the_base_url_is_tolerated(self, router, monkeypatch):
        monkeypatch.setattr(settings, "router_base_url", BASE + "/")
        summarizer._generate("Halo")
        assert router.calls[0]["url"] == f"{BASE}/chat/completions"

    def test_the_body_has_system_user_model_and_limits(self, router):
        summarizer._generate("Isi pertanyaan", system="Aturan sistem", temperature=0.1, max_tokens=777)
        body = router.calls[0]["body"]
        assert body["model"] == "rm1"
        assert body["messages"] == [{"role": "system", "content": "Aturan sistem"}, {"role": "user", "content": "Isi pertanyaan"}]
        assert body["temperature"] == 0.1 and body["max_tokens"] == 777

    def test_streaming_is_turned_off_explicitly(self, router):
        # 9router membalas dengan stream SSE bila tidak diminta lain (ditemukan pada uji langsung)
        summarizer._generate("Halo")
        assert router.calls[0]["body"]["stream"] is False

    def test_the_key_never_appears_in_the_url_or_body(self, router):
        summarizer._generate("Halo")
        call = router.calls[0]
        assert KEY not in call["url"] and KEY not in str(call["body"])

    def test_the_configured_timeout_is_used(self, router, monkeypatch):
        monkeypatch.setattr(settings, "router_timeout", 33.0)
        summarizer._generate("Halo")
        assert router.calls[0]["timeout"] == 33.0

    def test_gemini_is_not_called_when_the_router_answers(self, router, gemini):
        summarizer._generate("Halo")
        assert gemini.calls == []

    def test_the_preferred_gemini_model_does_not_change_the_router_model(self, router, gemini):
        router.add(("http", 500, "x"))
        summarizer._generate("Halo", prefer="gemini-khusus")
        assert router.calls[0]["body"]["model"] == "rm1"
        assert gemini.calls[0]["model"] == "gemini-khusus"

    def test_the_router_has_no_minimum_interval(self, router, clock, monkeypatch):
        monkeypatch.setattr(settings, "gemini_min_interval", 6.0)
        summarizer._generate("satu")
        summarizer._generate("dua")
        assert clock.sleeps == []


class TestWhichProvider:
    def test_configured_is_true_with_only_the_router(self, router, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        assert summarizer.configured() is True

    def test_configured_is_true_with_only_gemini(self, gemini):
        assert summarizer.configured() is True

    def test_configured_is_false_with_neither(self, router, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        monkeypatch.setattr(settings, "router_api_key", "")
        assert summarizer.configured() is False

    @pytest.mark.parametrize("field", ["router_base_url", "router_api_key", "router_model"])
    def test_the_router_needs_base_url_key_and_model(self, router, gemini, monkeypatch, field):
        monkeypatch.setattr(settings, field, "")
        assert summarizer._generate("Halo") == "Rangkuman tunggal."
        assert router.calls == [] and len(gemini.calls) == 1

    def test_a_blank_key_of_spaces_counts_as_missing(self, router, gemini, monkeypatch):
        monkeypatch.setattr(settings, "router_api_key", "   ")
        summarizer._generate("Halo")
        assert router.calls == [] and len(gemini.calls) == 1

    def test_without_a_router_gemini_behaves_as_before(self, gemini):
        gemini.add(("text", "Halo"))
        assert summarizer._generate("Tes") == "Halo"


class TestFallbackToGemini:
    @pytest.mark.parametrize("failure", FAILURES)
    def test_a_router_failure_falls_back_to_gemini(self, router, gemini, failure):
        router.add(failure)
        gemini.add(("text", "Dari Gemini"))
        assert summarizer._generate("Halo") == "Dari Gemini"
        assert len(router.calls) == 1 and len(gemini.calls) == 1

    def test_gemini_receives_the_same_prompt(self, router, gemini):
        router.add(("http", 500, "x"))
        summarizer._generate("Pertanyaan asli")
        assert gemini.calls[0]["prompt"] == "Pertanyaan asli"

    def test_the_router_is_not_retried_for_the_same_request(self, router, gemini, clock):
        router.add(("http", 503, "x"))
        summarizer._generate("Halo")
        assert len(router.calls) == 1 and clock.sleeps == []

    def test_a_safety_block_by_the_router_is_judged_again_by_gemini(self, router, gemini):
        router.add(("filtered",))
        gemini.add(("json", {"promptFeedback": {"blockReason": "SAFETY"}}))
        with pytest.raises(summarizer.SafetyBlock):
            summarizer._generate("Halo")

    def test_when_both_fail_the_gemini_error_is_raised(self, router, gemini, clock):
        router.add(("http", 500, "x"))
        gemini.add(*[("http", 400, "salah")])
        with pytest.raises(summarizer.SummaryError) as err:
            summarizer._generate("Halo")
        assert "Gemini" in str(err.value)


class TestRouterOnly:
    @pytest.fixture(autouse=True)
    def no_gemini(self, router, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")

    def test_a_429_is_a_quota_error(self, router):
        router.add(("http", 429, "pelan-pelan"))
        with pytest.raises(summarizer.QuotaError) as err:
            summarizer._generate("Halo")
        assert "9router" in str(err.value)

    @pytest.mark.parametrize("failure,fragment", [
        (("http", 500, "x"), "500"),
        (("http", 401, "x"), "401"),
        (("net",), "9router"),
        (("empty",), "9router"),
    ])
    def test_other_failures_are_summary_errors(self, router, failure, fragment):
        router.add(failure)
        with pytest.raises(summarizer.SummaryError) as err:
            summarizer._generate("Halo")
        assert fragment in str(err.value) and "9router" in str(err.value)

    def test_a_content_filter_is_a_safety_block(self, router):
        router.add(("filtered",))
        with pytest.raises(summarizer.SafetyBlock):
            summarizer._generate("Halo")

    def test_the_error_never_leaks_the_key(self, router):
        router.add(("http", 401, f"Kunci {KEY} tidak sah"))
        with pytest.raises(summarizer.SummaryError) as err:
            summarizer._generate("Halo")
        assert KEY not in str(err.value)


class TestCooldown:
    def test_after_a_failure_the_router_is_skipped_for_60_seconds(self, router, gemini, clock):
        router.add(("http", 500, "x"))
        summarizer._generate("satu")
        summarizer._generate("dua")
        summarizer._generate("tiga")
        assert len(router.calls) == 1 and len(gemini.calls) == 3

    def test_the_router_is_tried_again_after_60_seconds(self, router, gemini, clock):
        router.add(("http", 500, "x"))
        summarizer._generate("satu")
        clock.now += 61
        assert summarizer._generate("dua") == "Dari router"
        assert len(router.calls) == 2

    def test_it_is_still_held_just_before_60_seconds(self, router, gemini, clock):
        router.add(("http", 500, "x"))
        summarizer._generate("satu")
        clock.now += 59
        summarizer._generate("dua")
        assert len(router.calls) == 1

    @pytest.mark.parametrize("failure", [
        pytest.param(("http", 429, "x"), id="429"),
        pytest.param(("http", 401, "x"), id="401"),
        pytest.param(("http", 404, "x"), id="404"),
        pytest.param(("net",), id="jaringan"),
    ])
    def test_service_failures_hold_the_router(self, router, gemini, failure):
        router.add(failure)
        summarizer._generate("satu")
        summarizer._generate("dua")
        assert len(router.calls) == 1

    @pytest.mark.parametrize("failure", [
        pytest.param(("filtered",), id="content-filter"),
        pytest.param(("empty",), id="tanpa-pilihan"),
        pytest.param(("text", "  "), id="teks-kosong"),
    ])
    def test_content_failures_do_not_hold_the_router(self, router, gemini, failure):
        router.add(failure)
        summarizer._generate("satu")
        assert summarizer._generate("dua") == "Dari router"
        assert len(router.calls) == 2

    def test_broken_json_does_not_hold_the_router(self, router, gemini):
        router.add(("text", "bukan json"))
        summarizer._generate("satu", schema=SCHEMA)
        router.add(("text", '{"ok": true}'))
        assert summarizer._generate("dua", schema=SCHEMA) == '{"ok": true}'
        assert len(router.calls) == 2

    def test_a_success_does_not_hold_the_router(self, router):
        summarizer._generate("satu")
        summarizer._generate("dua")
        assert len(router.calls) == 2

    def test_while_held_and_without_gemini_the_error_names_the_router(self, router, monkeypatch):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        router.add(("http", 500, "x"))
        with pytest.raises(summarizer.SummaryError):
            summarizer._generate("satu")
        with pytest.raises(summarizer.SummaryError) as err:
            summarizer._generate("dua")
        assert "9router" in str(err.value) and len(router.calls) == 1


class TestJson:
    def test_a_schema_asks_for_json_and_is_written_into_the_system_text(self, router):
        router.add(("text", '{"ok": true}'))
        summarizer._generate("Nilai", system="Aturan", schema=SCHEMA)
        call = router.calls[0]
        assert call["body"]["response_format"] == {"type": "json_object"}
        assert call["system"].startswith("Aturan")
        assert '"ok"' in call["system"] and "JSON" in call["system"]

    def test_without_a_schema_there_is_no_response_format(self, router):
        summarizer._generate("Halo")
        assert "response_format" not in router.calls[0]["body"]
        assert router.calls[0]["system"] == summarizer.SYSTEM

    def test_valid_json_is_returned(self, router):
        router.add(("text", '{"ok": true}'))
        assert summarizer._generate("Nilai", schema=SCHEMA) == '{"ok": true}'

    def test_code_fences_around_json_are_removed(self, router):
        router.add(("text", '```json\n{"ok": true}\n```'))
        assert summarizer._generate("Nilai", schema=SCHEMA) == '{"ok": true}'

    def test_json_wrapped_in_plain_fences_is_also_removed(self, router):
        router.add(("text", '```\n{"ok": true}\n```'))
        assert summarizer._generate("Nilai", schema=SCHEMA) == '{"ok": true}'

    def test_broken_json_falls_back_to_gemini(self, router, gemini):
        router.add(("text", "ini bukan json"))
        gemini.add(("text", '{"ok": false}'))
        assert summarizer._generate("Nilai", schema=SCHEMA) == '{"ok": false}'
        assert gemini.calls[0]["body"]["generationConfig"]["responseSchema"] == SCHEMA

    def test_text_that_is_not_json_is_fine_without_a_schema(self, router):
        router.add(("text", "ini bukan json"))
        assert summarizer._generate("Halo") == "ini bukan json"


class TestLogging:
    def test_a_success_is_logged_with_the_provider_purpose_and_tokens(self, router, caplog):
        with caplog.at_level(logging.INFO, logger="uvicorn.error"):
            summarizer._generate("Halo", purpose="rangkuman bab (tunggal)")
        line = next(r.getMessage() for r in caplog.records if "9router" in r.getMessage())
        assert "rangkuman bab (tunggal)" in line and "rm1" in line and "ok" in line and "11" in line and "7" in line

    def test_a_switch_to_gemini_is_logged_as_a_warning(self, router, gemini, caplog):
        router.add(("http", 500, "x"))
        with caplog.at_level(logging.WARNING):
            summarizer._generate("Halo")
        assert any("9router" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)

    def test_the_key_is_never_logged(self, router, gemini, caplog):
        router.add(("http", 401, f"Kunci {KEY} tidak sah"))
        with caplog.at_level(logging.DEBUG):
            summarizer._generate("Halo")
        assert KEY not in caplog.text


class TestCallers:
    def test_the_overall_summary_prompt_works_through_the_router(self, router, gemini):
        router.add(("text", "Ringkas dari router"))
        assert summarizer._chapter_summary("Bab 1", "Isi bab.") == "Ringkas dari router"
        assert gemini.calls == []
