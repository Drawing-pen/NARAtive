from datetime import datetime, timedelta

import pytest

from app.db import models
from app.ml.analyzer import THRESHOLDS, explain, rate


def pct(sexual=0.0, violence=0.0):
    return {"sexual": sexual, "violence": violence, "profanity": 0.0}


def hits(sexual=0, violence=0):
    return {"sexual": sexual, "violence": violence, "profanity": 0}


class TestExplain:
    def test_explicit_names_the_sexual_rule(self):
        [reason] = explain(pct(sexual=3.0), hits(sexual=3))
        assert reason == "Konten seksual 3,0% paragraf (3 paragraf) mencapai batas Explicit: minimal 3% dan 3 paragraf."

    def test_mature_by_violence(self):
        [reason] = explain(pct(violence=15.0), hits(violence=3))
        assert reason == "Kekerasan 15,0% paragraf (3 paragraf) mencapai batas Mature: minimal 15% dan 3 paragraf."

    def test_mature_by_sexual(self):
        [reason] = explain(pct(sexual=1.0), hits(sexual=2))
        assert reason == "Konten seksual 1,0% paragraf (2 paragraf) mencapai batas Mature: minimal 1% dan 2 paragraf."

    def test_mature_by_both_lists_both(self):
        reasons = explain(pct(sexual=1.2, violence=20.0), hits(sexual=3, violence=40))
        assert len(reasons) == 2 and "Kekerasan" in reasons[0] and "Konten seksual" in reasons[1]

    def test_teen_by_violence(self):
        [reason] = explain(pct(violence=3.0), hits(violence=2))
        assert reason == "Kekerasan 3,0% paragraf (2 paragraf) mencapai batas Teen: minimal 3% dan 2 paragraf."

    def test_teen_by_sexual_with_a_decimal_threshold(self):
        [reason] = explain(pct(sexual=0.5), hits(sexual=2))
        assert reason == "Konten seksual 0,5% paragraf (2 paragraf) mencapai batas Teen: minimal 0,5% dan 2 paragraf."

    def test_general_says_nothing_reached_the_teen_limits_with_the_real_numbers(self):
        [reason] = explain(pct(sexual=0.2, violence=1.5), hits(sexual=1, violence=3))
        assert reason.startswith("Tidak ada dimensi yang mencapai batas Teen")
        assert "kekerasan minimal 3% dan 2 paragraf" in reason and "konten seksual minimal 0,5% dan 2 paragraf" in reason
        assert "kekerasan 1,5% (3 paragraf)" in reason and "konten seksual 0,2% (1 paragraf)" in reason

    def test_a_clean_book_is_explained_too(self):
        [reason] = explain(pct(), hits())
        assert "kekerasan 0,0% (0 paragraf)" in reason and "konten seksual 0,0% (0 paragraf)" in reason

    def test_a_percentage_without_enough_paragraphs_does_not_count(self):
        [reason] = explain(pct(sexual=5.0), hits(sexual=2))
        assert "Mature" in reason

    @pytest.mark.parametrize(
        "sexual,violence,s_hits,v_hits",
        [(3.0, 0.0, 3, 0), (2.9, 0.0, 99, 0), (1.0, 0.0, 2, 0), (0.5, 0.0, 2, 0), (0.4, 0.0, 99, 0), (0.0, 15.0, 0, 3), (0.0, 14.9, 0, 99), (0.0, 3.0, 0, 2), (0.0, 2.9, 0, 99), (0.0, 0.0, 0, 0)],
    )
    def test_the_reason_always_names_the_level_that_rate_gives(self, sexual, violence, s_hits, v_hits):
        rating = rate(pct(sexual=sexual, violence=violence), hits(sexual=s_hits, violence=v_hits))
        text = " ".join(explain(pct(sexual=sexual, violence=violence), hits(sexual=s_hits, violence=v_hits)))
        if rating == "General":
            assert "Tidak ada dimensi yang mencapai batas Teen" in text
        else:
            assert f"batas {rating}" in text

    def test_profanity_never_appears_in_the_reasons(self):
        reasons = explain({"sexual": 0.0, "violence": 5.0, "profanity": 80.0}, {"sexual": 0, "violence": 5, "profanity": 99})
        assert all("kasar" not in r.lower() for r in reasons)


def scored(db, doc, scores):
    """scores: daftar (kasar, seksual, kekerasan) per paragraf."""
    doc.paragraphs = [
        models.Paragraph(idx=i, chapter_no=1, text=f"Paragraf {i}.", profanity=p, sexual=s, violence=v, emotion="sad", emotion_score=0.5)
        for i, (p, s, v) in enumerate(scores)
    ]
    doc.paragraph_count = len(scores)
    db.commit()
    return doc


@pytest.fixture
def middle(make_user):
    return make_user("middle", expires_at=datetime.utcnow() + timedelta(days=10))


def fetch(client, auth, user, doc):
    return client.get(f"/documents/{doc.id}/rating", headers=auth(user))


class TestEndpoint:
    def test_it_counts_paragraphs_per_dimension_in_a_fixed_order(self, client, db, auth, middle, make_doc):
        doc = scored(db, make_doc(middle), [(0.6, 0.0, 0.9)] * 2 + [(0.0, 0.7, 0.0)] + [(0.0, 0.0, 0.0)] * 7)
        body = fetch(client, auth, middle, doc).json()
        assert [d["key"] for d in body["dimensions"]] == ["violence", "sexual", "profanity"]
        assert [d["label"] for d in body["dimensions"]] == ["Kekerasan", "Konten seksual", "Bahasa kasar"]
        counts = {d["key"]: (d["paragraphs"], d["percent"]) for d in body["dimensions"]}
        assert counts == {"violence": (2, 20.0), "sexual": (1, 10.0), "profanity": (2, 20.0)}

    def test_thresholds_are_reported_and_inclusive(self, client, db, auth, middle, make_doc):
        doc = scored(db, make_doc(middle), [(0.5, 0.5, 0.8), (0.49, 0.49, 0.79)])
        body = fetch(client, auth, middle, doc).json()
        assert {d["key"]: d["threshold"] for d in body["dimensions"]} == {"violence": 0.8, "sexual": 0.5, "profanity": 0.5} == {k: v for k, v in THRESHOLDS.items()}
        assert all(d["paragraphs"] == 1 for d in body["dimensions"])

    def test_percent_is_rounded_to_one_decimal(self, client, db, auth, middle, make_doc):
        doc = scored(db, make_doc(middle), [(0.0, 0.9, 0.0)] + [(0.0, 0.0, 0.0)] * 5)
        sexual = next(d for d in fetch(client, auth, middle, doc).json()["dimensions"] if d["key"] == "sexual")
        assert sexual["percent"] == 16.7

    def test_the_rating_and_reasons_come_with_it(self, client, db, auth, middle, make_doc):
        doc = scored(db, make_doc(middle), [(0.0, 0.0, 0.9)] * 3 + [(0.0, 0.0, 0.0)] * 97)
        body = fetch(client, auth, middle, doc).json()
        assert body["rating"] == "Teen" and body["age_range"] == "13+"
        assert body["reasons"] == ["Kekerasan 3,0% paragraf (3 paragraf) mencapai batas Teen: minimal 3% dan 2 paragraf."]
        assert body["note"] == "Bahasa kasar ditampilkan sebagai informasi dan tidak dihitung dalam rating maupun persentase konten dewasa."

    def test_a_clean_book_is_general(self, client, db, auth, middle, make_doc):
        doc = scored(db, make_doc(middle), [(0.0, 0.0, 0.0)] * 10)
        body = fetch(client, auth, middle, doc).json()
        assert body["rating"] == "General" and body["age_range"] == "Semua umur"
        assert body["reasons"][0].startswith("Tidak ada dimensi yang mencapai batas Teen")

    def test_a_book_without_paragraphs_does_not_crash(self, client, db, auth, middle, make_doc):
        doc = scored(db, make_doc(middle), [])
        body = fetch(client, auth, middle, doc).json()
        assert body["rating"] == "General" and all(d["paragraphs"] == 0 and d["percent"] == 0.0 for d in body["dimensions"])

    def test_the_rating_matches_the_analysis_for_the_same_scores(self, client, db, auth, middle, make_doc):
        scores = [(0.0, 0.9, 0.0)] * 4 + [(0.0, 0.0, 0.0)] * 96
        body = fetch(client, auth, middle, scored(db, make_doc(middle), scores)).json()
        assert body["rating"] == rate({"sexual": 4.0, "violence": 0.0, "profanity": 0.0}, {"sexual": 4, "violence": 0, "profanity": 0}) == "Explicit"

    @pytest.mark.parametrize("tier", ["free", "high"])
    def test_tiers_and_access(self, client, db, auth, make_user, make_doc, tier):
        user = make_user(tier, expires_at=datetime.utcnow() + timedelta(days=10) if tier != "free" else None)
        res = fetch(client, auth, user, scored(db, make_doc(user), [(0.0, 0.0, 0.0)] * 3))
        assert res.status_code == (403 if tier == "free" else 200)

    def test_an_expired_middle_account_is_locked(self, client, db, auth, make_user, make_doc):
        user = make_user("middle", expires_at=datetime.utcnow() - timedelta(days=1))
        assert fetch(client, auth, user, scored(db, make_doc(user), [(0.0, 0.0, 0.0)])).status_code == 403

    def test_an_unfinished_book_is_not_ready(self, client, auth, middle, make_doc):
        res = fetch(client, auth, middle, make_doc(middle, status="analyzing"))
        assert res.status_code == 409 and res.json()["detail"] == "Analisis belum selesai."

    def test_another_users_book_is_not_found(self, client, db, auth, middle, make_user, make_doc):
        other = make_user("middle", expires_at=datetime.utcnow() + timedelta(days=10))
        assert fetch(client, auth, middle, make_doc(other)).status_code == 404

    def test_a_missing_book_is_not_found(self, client, auth, middle):
        assert client.get("/documents/99999/rating", headers=auth(middle)).status_code == 404

    def test_login_is_required(self, client, middle, make_doc):
        assert client.get(f"/documents/{make_doc(middle).id}/rating").status_code == 401
