from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.services import summarizer

MIDDLE_ONLY = "Fitur ini khusus pengguna Middle Tier."
HIGH_ONLY = "Fitur ini khusus pengguna High Tier."


@pytest.fixture(autouse=True)
def no_background_work(monkeypatch):
    from app.api.routers import documents
    monkeypatch.setattr(summarizer, "configured", lambda: True)
    monkeypatch.setattr(summarizer, "start", lambda doc_id: None)
    monkeypatch.setattr(documents.character_service, "start", lambda doc_id, ai=False: None)
    monkeypatch.setattr(documents.character_service.character_ai, "available", lambda: True)
    monkeypatch.setattr(documents, "build_pdf", lambda *a, **k: b"%PDF-1.4 uji")


def past():
    return datetime.utcnow() - timedelta(days=1)


def future():
    return datetime.utcnow() + timedelta(days=10)


def test_standard_cannot_create_summary(client, make_user, make_doc, auth):
    user = make_user("free")
    doc = make_doc(user)
    res = client.post(f"/documents/{doc.id}/summary", headers=auth(user))
    assert res.status_code == 403
    assert res.json()["detail"] == MIDDLE_ONLY


def test_standard_cannot_detect_characters(client, make_user, make_doc, auth):
    user = make_user("free")
    doc = make_doc(user)
    res = client.post(f"/documents/{doc.id}/characters", headers=auth(user))
    assert res.status_code == 403
    assert res.json()["detail"] == MIDDLE_ONLY


def test_standard_cannot_detect_characters_with_ai(client, make_user, make_doc, auth):
    user = make_user("free")
    doc = make_doc(user)
    assert client.post(f"/documents/{doc.id}/characters?ai=true", headers=auth(user)).status_code == 403


def test_standard_without_stored_summary_is_locked(client, make_user, make_doc, auth):
    user = make_user("free")
    doc = make_doc(user)
    res = client.get(f"/documents/{doc.id}/summary", headers=auth(user))
    assert res.status_code == 403
    assert res.json()["detail"] == MIDDLE_ONLY


def test_standard_without_stored_characters_is_locked(client, make_user, make_doc, auth):
    user = make_user("free")
    doc = make_doc(user)
    res = client.get(f"/documents/{doc.id}/characters", headers=auth(user))
    assert res.status_code == 403
    assert res.json()["detail"] == MIDDLE_ONLY


def test_standard_can_still_view_stored_summary(client, make_user, make_doc, auth):
    user = make_user("free")
    doc = make_doc(user, summary="Rangkuman keseluruhan.")
    res = client.get(f"/documents/{doc.id}/summary", headers=auth(user))
    assert res.status_code == 200
    assert res.json()["overall"] == "Rangkuman keseluruhan."


def test_standard_can_still_view_stored_characters(client, make_user, make_doc, auth):
    user = make_user("free")
    doc = make_doc(user, characters=["Rana", "Dede"])
    res = client.get(f"/documents/{doc.id}/characters", headers=auth(user))
    assert res.status_code == 200
    assert {c["name"] for c in res.json()["characters"]} == {"Rana", "Dede"}


def test_standard_cannot_regenerate_existing_summary(client, make_user, make_doc, auth):
    user = make_user("free")
    doc = make_doc(user, summary="Rangkuman lama.")
    assert client.post(f"/documents/{doc.id}/summary", headers=auth(user)).status_code == 403


def test_middle_can_create_summary(client, make_user, make_doc, auth):
    user = make_user("middle", expires_at=future())
    doc = make_doc(user)
    assert client.post(f"/documents/{doc.id}/summary", headers=auth(user)).status_code == 202


def test_middle_can_detect_characters(client, make_user, make_doc, auth):
    user = make_user("middle", expires_at=future())
    doc = make_doc(user)
    assert client.post(f"/documents/{doc.id}/characters", headers=auth(user)).status_code == 202


def test_middle_sees_empty_state_not_lock(client, make_user, make_doc, auth):
    user = make_user("middle", expires_at=future())
    doc = make_doc(user)
    assert client.get(f"/documents/{doc.id}/summary", headers=auth(user)).status_code == 200
    assert client.get(f"/documents/{doc.id}/characters", headers=auth(user)).status_code == 200


def test_high_can_create_summary_and_characters(client, make_user, make_doc, auth):
    user = make_user("high", expires_at=future())
    doc = make_doc(user)
    assert client.post(f"/documents/{doc.id}/summary", headers=auth(user)).status_code == 202
    assert client.post(f"/documents/{doc.id}/characters", headers=auth(user)).status_code == 202


def test_expired_middle_is_treated_as_standard(client, make_user, make_doc, auth):
    user = make_user("middle", expires_at=past())
    doc = make_doc(user)
    assert client.post(f"/documents/{doc.id}/summary", headers=auth(user)).status_code == 403


def test_expired_middle_still_sees_what_was_made(client, make_user, make_doc, auth):
    user = make_user("middle", expires_at=past())
    doc = make_doc(user, summary="Dibuat saat masih Middle.", characters=["Rana"])
    assert client.get(f"/documents/{doc.id}/summary", headers=auth(user)).status_code == 200
    assert client.get(f"/documents/{doc.id}/characters", headers=auth(user)).status_code == 200


def test_summary_and_characters_of_another_user_stay_hidden(client, make_user, make_doc, auth):
    owner = make_user("middle", expires_at=future())
    other = make_user("middle", expires_at=future())
    doc = make_doc(owner, summary="Rahasia.", characters=["Rana"])
    for path in ("summary", "characters"):
        assert client.get(f"/documents/{doc.id}/{path}", headers=auth(other)).status_code == 404
        assert client.post(f"/documents/{doc.id}/{path}", headers=auth(other)).status_code == 404


@pytest.mark.parametrize("tier", ["free", "middle"])
def test_export_pdf_is_high_only(client, make_user, make_doc, auth, tier):
    user = make_user(tier, expires_at=future() if tier != "free" else None)
    doc = make_doc(user)
    res = client.get(f"/documents/{doc.id}/export", headers=auth(user))
    assert res.status_code == 403
    assert res.json()["detail"] == HIGH_ONLY


def test_high_can_export_pdf(client, make_user, make_doc, auth):
    user = make_user("high", expires_at=future())
    doc = make_doc(user)
    res = client.get(f"/documents/{doc.id}/export", headers=auth(user))
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"


def test_expired_high_cannot_export_pdf(client, make_user, make_doc, auth):
    user = make_user("high", expires_at=past())
    doc = make_doc(user)
    assert client.get(f"/documents/{doc.id}/export", headers=auth(user)).status_code == 403


def test_export_of_another_users_document_is_not_found_for_high(client, make_user, make_doc, auth):
    owner = make_user("high", expires_at=future())
    other = make_user("high", expires_at=future())
    doc = make_doc(owner)
    assert client.get(f"/documents/{doc.id}/export", headers=auth(other)).status_code == 404


def test_dev_unlock_opens_every_feature_for_standard(client, make_user, make_doc, auth, monkeypatch):
    monkeypatch.setattr(settings, "dev_unlock_all_tiers", True)
    user = make_user("free")
    doc = make_doc(user)
    assert client.post(f"/documents/{doc.id}/summary", headers=auth(user)).status_code == 202
    assert client.get(f"/documents/{doc.id}/export", headers=auth(user)).status_code == 200


def test_sensitivity_profile_is_high_only(client, make_user, auth):
    body = {"profanity": 0.5, "sexual": 0.5, "violence": 0.8}
    free = make_user("free")
    middle = make_user("middle", expires_at=future())
    high = make_user("high", expires_at=future())
    for user in (free, middle):
        res = client.put("/sensitivity", json=body, headers=auth(user))
        assert res.status_code == 403
        assert res.json()["detail"] == HIGH_ONLY
    assert client.put("/sensitivity", json=body, headers=auth(high)).status_code == 200


def test_everyone_can_read_sensitivity_thresholds(client, make_user, auth):
    user = make_user("free")
    res = client.get("/sensitivity", headers=auth(user))
    assert res.status_code == 200 and res.json()["editable"] is False


def test_standard_keeps_core_features(client, make_user, make_doc, auth):
    user = make_user("free")
    doc = make_doc(user)
    headers = auth(user)
    assert client.get("/documents", headers=headers).status_code == 200
    assert client.get(f"/documents/{doc.id}", headers=headers).status_code == 200
    assert client.get(f"/documents/{doc.id}/chapters", headers=headers).status_code == 200
    assert client.get(f"/documents/{doc.id}/paragraphs", headers=headers).status_code == 200
    renamed = client.patch(f"/documents/{doc.id}", json={"title": "Judul Baru"}, headers=headers)
    assert renamed.status_code == 200 and renamed.json()["title"] == "Judul Baru"


def test_standard_can_build_series_and_delete(client, make_user, make_doc, auth):
    user = make_user("free")
    first, second = make_doc(user, title="Satu"), make_doc(user, title="Dua")
    headers = auth(user)
    series = client.post("/collections", json={"name": "Seri Uji", "document_ids": [first.id, second.id]}, headers=headers)
    assert series.status_code == 201
    assert client.delete(f"/documents/{first.id}", headers=headers).status_code == 204


class FakeAnalyzer:
    def analyze(self, texts):
        return [{"profanity": 0.0, "sexual": 0.0, "violence": 0.0, "emotion": "happy", "emotion_prob": 0.5} for _ in texts]


@pytest.mark.parametrize(
    "tier, expires, runs",
    [("free", None, False), ("middle", "future", True), ("high", "future", True), ("middle", "past", False)],
)
def test_automatic_character_detection_only_for_middle_and_above(make_user, make_doc, monkeypatch, tier, expires, runs):
    from app.services import jobs
    calls = []
    monkeypatch.setattr(jobs, "get_analyzer", lambda: FakeAnalyzer())
    monkeypatch.setattr(jobs, "configured", lambda: False)
    monkeypatch.setattr(jobs.characters, "run", lambda doc_id, ai=False: calls.append(doc_id))
    user = make_user(tier, expires_at={"future": future(), "past": past(), None: None}[expires])
    doc = make_doc(user, status="queued")
    jobs.process(doc.id)
    assert (calls == [doc.id]) is runs
