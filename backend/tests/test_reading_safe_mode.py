from datetime import datetime, timedelta

from app.db import models
from app.ml.analyzer import THRESHOLDS

STANDARD = {"profanity": None, "sexual": 0.5, "violence": None}
PROFILE = {"profanity": 0.4, "sexual": 0.3, "violence": 0.7}


def future():
    return datetime.utcnow() + timedelta(days=10)


def past():
    return datetime.utcnow() - timedelta(days=1)


def test_chapters_are_listed_in_order(client, db, make_user, make_doc, auth):
    user = make_user("free")
    doc = make_doc(user)
    db.add_all([models.Chapter(document_id=doc.id, number=3, title="Bab 3"), models.Chapter(document_id=doc.id, number=2, title="Bab 2")])
    db.commit()
    res = client.get(f"/documents/{doc.id}/chapters", headers=auth(user))
    assert res.status_code == 200
    assert [c["number"] for c in res.json()] == [1, 2, 3]
    assert res.json()[0] == {"number": 1, "title": "Bab 1"}


def test_paragraphs_come_in_reading_order_with_scores(client, make_user, make_doc, auth):
    user = make_user("free")
    doc = make_doc(user)
    res = client.get(f"/documents/{doc.id}/paragraphs", headers=auth(user))
    assert res.status_code == 200
    body = res.json()
    assert [p["idx"] for p in body] == [0, 1]
    assert set(body[0]) == {"idx", "chapter_no", "text", "profanity", "sexual", "violence", "emotion"}
    assert body[0]["text"] == "Paragraf pertama."


def test_paragraphs_of_an_unfinished_document_have_no_scores(client, db, make_user, make_doc, auth):
    user = make_user("free")
    doc = make_doc(user, status="queued")
    db.query(models.Paragraph).filter_by(document_id=doc.id).update({"sexual": None, "violence": None, "profanity": None, "emotion": None})
    db.commit()
    res = client.get(f"/documents/{doc.id}/paragraphs", headers=auth(user))
    assert res.status_code == 200
    assert all(p["sexual"] is None and p["violence"] is None for p in res.json())


def test_reading_data_of_another_user_is_not_found(client, make_user, make_doc, auth):
    owner, other = make_user("free"), make_user("free")
    doc = make_doc(owner)
    for path in ("chapters", "paragraphs", ""):
        res = client.get(f"/documents/{doc.id}/{path}".rstrip("/"), headers=auth(other))
        assert res.status_code == 404
        assert res.json()["detail"] == "Dokumen tidak ditemukan."


def test_reading_requires_login(client, make_user, make_doc):
    doc = make_doc(make_user("free"))
    for path in ("chapters", "paragraphs"):
        res = client.get(f"/documents/{doc.id}/{path}")
        assert res.status_code == 401
        assert res.json()["detail"] == "Silakan masuk terlebih dahulu."


def test_unknown_document_is_not_found(client, make_user, auth):
    user = make_user("free")
    assert client.get("/documents/9999/paragraphs", headers=auth(user)).status_code == 404


def test_standard_safe_mode_only_hides_sexual_content(client, make_user, auth):
    user = make_user("free")
    res = client.get("/sensitivity", headers=auth(user))
    assert res.status_code == 200
    body = res.json()
    assert body["thresholds"] == STANDARD
    assert body["standard"] == STANDARD
    assert body["editable"] is False and body["personal"] is False


def test_standard_sexual_threshold_matches_the_model_threshold(client, make_user, auth):
    user = make_user("free")
    sexual = client.get("/sensitivity", headers=auth(user)).json()["thresholds"]["sexual"]
    assert sexual == THRESHOLDS["sexual"] == 0.5


def test_sensitivity_requires_login(client):
    assert client.get("/sensitivity").status_code == 401


def test_high_starts_with_the_standard_profile_but_can_edit(client, make_user, auth):
    user = make_user("high", expires_at=future())
    body = client.get("/sensitivity", headers=auth(user)).json()
    assert body["editable"] is True and body["personal"] is False
    assert body["thresholds"] == STANDARD


def test_high_saves_a_personal_profile(client, make_user, auth):
    user = make_user("high", expires_at=future())
    res = client.put("/sensitivity", json=PROFILE, headers=auth(user))
    assert res.status_code == 200
    assert res.json()["thresholds"] == PROFILE and res.json()["personal"] is True
    again = client.get("/sensitivity", headers=auth(user)).json()
    assert again["thresholds"] == PROFILE and again["personal"] is True


def test_saving_again_replaces_the_profile_without_duplicates(client, db, make_user, auth):
    user = make_user("high", expires_at=future())
    client.put("/sensitivity", json=PROFILE, headers=auth(user))
    client.put("/sensitivity", json={"profanity": None, "sexual": 0.9, "violence": None}, headers=auth(user))
    assert db.query(models.SensitivityProfile).filter_by(user_id=user.id).count() == 1
    assert client.get("/sensitivity", headers=auth(user)).json()["thresholds"] == {"profanity": None, "sexual": 0.9, "violence": None}


def test_null_means_that_content_type_is_not_hidden(client, make_user, auth):
    user = make_user("high", expires_at=future())
    body = {"profanity": None, "sexual": None, "violence": None}
    res = client.put("/sensitivity", json=body, headers=auth(user))
    assert res.status_code == 200 and res.json()["thresholds"] == body


def test_thresholds_outside_the_allowed_range_are_rejected(client, make_user, auth):
    user = make_user("high", expires_at=future())
    for bad in (0.05, 0.96, 1.5, -0.1):
        res = client.put("/sensitivity", json={**PROFILE, "sexual": bad}, headers=auth(user))
        assert res.status_code == 422
    assert client.put("/sensitivity", json={**PROFILE, "sexual": 0.1}, headers=auth(user)).status_code == 200
    assert client.put("/sensitivity", json={**PROFILE, "sexual": 0.95}, headers=auth(user)).status_code == 200


def test_incomplete_profile_is_rejected(client, make_user, auth):
    user = make_user("high", expires_at=future())
    assert client.put("/sensitivity", json={"sexual": 0.5}, headers=auth(user)).status_code == 422


def test_reset_returns_to_the_standard_profile(client, db, make_user, auth):
    user = make_user("high", expires_at=future())
    client.put("/sensitivity", json=PROFILE, headers=auth(user))
    res = client.delete("/sensitivity", headers=auth(user))
    assert res.status_code == 200
    assert res.json()["thresholds"] == STANDARD and res.json()["personal"] is False
    assert db.query(models.SensitivityProfile).filter_by(user_id=user.id).count() == 0


def test_reset_without_a_profile_is_harmless(client, make_user, auth):
    user = make_user("high", expires_at=future())
    assert client.delete("/sensitivity", headers=auth(user)).status_code == 200


def test_profiles_are_private_per_user(client, make_user, auth):
    first, second = make_user("high", expires_at=future()), make_user("high", expires_at=future())
    client.put("/sensitivity", json=PROFILE, headers=auth(first))
    assert client.get("/sensitivity", headers=auth(second)).json()["thresholds"] == STANDARD


def test_expired_high_falls_back_to_standard_but_keeps_the_saved_profile(client, db, make_user, auth):
    user = make_user("high", expires_at=future())
    client.put("/sensitivity", json=PROFILE, headers=auth(user))
    user.tier_expires_at = past()
    db.commit()
    body = client.get("/sensitivity", headers=auth(user)).json()
    assert body["thresholds"] == STANDARD and body["editable"] is False and body["personal"] is False
    assert db.query(models.SensitivityProfile).filter_by(user_id=user.id).count() == 1
    user.tier_expires_at = future()
    db.commit()
    assert client.get("/sensitivity", headers=auth(user)).json()["thresholds"] == PROFILE


def test_downgraded_user_cannot_use_a_leftover_profile(client, db, make_user, auth):
    user = make_user("high", expires_at=future())
    client.put("/sensitivity", json=PROFILE, headers=auth(user))
    user.tier = "free"
    db.commit()
    assert client.get("/sensitivity", headers=auth(user)).json()["thresholds"] == STANDARD
