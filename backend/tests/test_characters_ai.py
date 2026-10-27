import json
import logging

import pytest

from app.core.config import settings
from app.services import character_ai, summarizer
from tests.gemini_fake import clock, gemini

CANDIDATES = [
    {"id": 0, "name": "Rana", "snippets": ["Rana pergi ke pasar.", "Rana pulang."]},
    {"id": 1, "name": "Nara", "snippets": ["Nara menunggu."]},
    {"id": 2, "name": "Dede", "snippets": []},
]


def answer(*people):
    return ("text", json.dumps({"tokoh": list(people)}))


def person(**kw):
    base = {
        "id": [0], "jenis_kelamin": "Perempuan", "usia": "Dewasa", "pekerjaan": "Mahasiswa",
        "kepribadian": "Pendiam.", "latar": "Anak sulung.", "ringkasan": "Rana adalah mahasiswa.",
    }
    base.update(kw)
    return base


def test_it_is_available_only_with_a_gemini_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "kunci")
    assert character_ai.available() is True
    monkeypatch.setattr(settings, "gemini_api_key", "  ")
    assert character_ai.available() is False


def test_no_candidates_means_no_request(gemini):
    assert character_ai.analyze([]) == []
    assert gemini.calls == []


def test_one_request_covers_all_candidates_with_their_snippets(gemini):
    gemini.add(answer(person()))
    character_ai.analyze(CANDIDATES)
    assert len(gemini.calls) == 1
    prompt = gemini.calls[0]["prompt"]
    assert '<nama id="0" nama="Rana">' in prompt and '<nama id="1" nama="Nara">' in prompt
    assert "Rana pergi ke pasar." in prompt and "Nara menunggu." in prompt


def test_the_prompt_treats_book_text_as_data():
    assert "DATA" in character_ai.SYSTEM and "abaikan perintah" in character_ai.SYSTEM


def test_the_request_is_labelled_and_deterministic(gemini):
    gemini.add(answer(person()))
    character_ai.analyze(CANDIDATES)
    body = gemini.calls[0]["body"]
    assert body["generationConfig"]["temperature"] == 0.1
    assert body["generationConfig"]["responseMimeType"] == "application/json"


def test_the_character_model_is_tried_first_when_configured(gemini, monkeypatch):
    monkeypatch.setattr(settings, "gemini_character_model", "model-tokoh")
    gemini.add(answer(person()))
    character_ai.analyze(CANDIDATES)
    assert gemini.calls[0]["model"] == "model-tokoh"


def test_people_come_back_with_cleaned_fields(gemini):
    gemini.add(answer(person(id=[0, 1])))
    [result] = character_ai.analyze(CANDIDATES)
    assert result == {
        "ids": [0, 1], "gender": "Perempuan", "age": "Dewasa", "occupation": "Mahasiswa",
        "personality": "Pendiam.", "background": "Anak sulung.", "summary": "Rana adalah mahasiswa.",
    }


@pytest.mark.parametrize("raw", ["", "-", "N/A", "tidak ada", "Tidak diketahui", "tidak disebutkan", None])
def test_empty_or_unknown_values_become_not_mentioned(gemini, raw):
    gemini.add(answer(person(usia=raw, pekerjaan=raw, kepribadian=raw, latar=raw)))
    [result] = character_ai.analyze(CANDIDATES)
    for field in ("age", "occupation", "personality", "background"):
        assert result[field] == "Tidak disebutkan"


def test_gender_must_be_one_of_the_allowed_values(gemini):
    gemini.add(answer(person(jenis_kelamin="Non-biner"), person(id=[1], jenis_kelamin="Laki-laki")))
    first, second = character_ai.analyze(CANDIDATES)
    assert first["gender"] == "Tidak disebutkan" and second["gender"] == "Laki-laki"


def test_long_fields_are_shortened_and_whitespace_is_tidied(gemini):
    gemini.add(answer(person(kepribadian="a " * 400, ringkasan="  Rana   adalah\n mahasiswa. " + "x" * 700)))
    [result] = character_ai.analyze(CANDIDATES)
    assert len(result["personality"]) <= 300
    assert len(result["summary"]) <= 600 and "  " not in result["summary"] and "\n" not in result["summary"]


def test_unknown_or_invalid_ids_are_ignored(gemini):
    gemini.add(answer(person(id=[0, 99, "1", None, True]), person(id=[77]), person(id=[])))
    results = character_ai.analyze(CANDIDATES)
    assert [r["ids"] for r in results] == [[0]] or [r["ids"] for r in results] == [[0, 1]]
    assert all(set(r["ids"]) <= {0, 1, 2} for r in results)
    assert len(results) == 1


def test_duplicate_ids_in_one_person_are_collapsed(gemini):
    gemini.add(answer(person(id=[1, 1, 0, 1])))
    assert character_ai.analyze(CANDIDATES)[0]["ids"] == [1, 0]


def test_safe_returns_none_when_gemini_fails(gemini, clock):
    gemini.add(("http", 429, '{"error":{"message":"PerDay"}}'))
    assert character_ai.safe(CANDIDATES) is None


def test_safe_returns_none_for_a_broken_answer(gemini):
    gemini.add(("text", "bukan json"))
    assert character_ai.safe(CANDIDATES) is None


def test_safe_returns_none_for_an_answer_with_the_wrong_shape(gemini):
    gemini.add(("text", json.dumps(["bukan", "objek"])))
    assert character_ai.safe(CANDIDATES) is None


def test_safe_returns_none_when_the_people_are_not_objects(gemini):
    gemini.add(("text", json.dumps({"tokoh": ["bukan objek", 5, None]})))
    assert character_ai.safe(CANDIDATES) is None


def test_safe_returns_the_people_on_success(gemini):
    gemini.add(answer(person()))
    assert len(character_ai.safe(CANDIDATES)) == 1


def test_requests_are_labelled_in_the_log(gemini, caplog):
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    gemini.add(answer(person()))
    character_ai.analyze(CANDIDATES)
    assert any("biodata tokoh" in r.getMessage() for r in caplog.records)
