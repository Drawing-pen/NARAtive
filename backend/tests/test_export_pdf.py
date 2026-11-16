from datetime import datetime, timedelta
from types import SimpleNamespace

import pymupdf
import pytest

from app.api.routers import documents
from app.db import models
from app.ml.analyzer import THRESHOLDS
from app.services.export import EMOTION_NEGATIVE_NOTE, build_pdf


def par(text, chapter=1, **scores):
    base = {"profanity": 0.0, "sexual": 0.0, "violence": 0.0}
    base.update(scores)
    return SimpleNamespace(text=text, chapter_no=chapter, **base)


def chapter(number, title, summary=None):
    return SimpleNamespace(number=number, title=title, summary=summary)


def info(**overrides):
    base = dict(
        title="Cerita Rana", page_count=120, rating="Teen", age_range="13+", pct_adult=4.5, heaviness=31.2,
        pct_profanity=1.0, pct_sexual=0.5, pct_violence=3.0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def render(doc=None, chapters=None, paragraphs=None):
    data = build_pdf(
        doc or info(),
        chapters if chapters is not None else [chapter(1, "Bab Satu"), chapter(2, "Bab Dua")],
        paragraphs if paragraphs is not None else [par("Rana pulang ke rumah.", 1), par("Dede menunggu di depan pintu.", 2)],
        THRESHOLDS,
    )
    pdf = pymupdf.open("pdf", data)
    return data, pdf, " ".join(page.get_text("text") for page in pdf)


class TestBuildPdf:
    def test_it_produces_a_real_pdf(self):
        data, pdf, _ = render()
        assert data.startswith(b"%PDF") and len(pdf) >= 1

    def test_the_summary_shows_title_rating_age_adult_share_and_weight(self):
        _, _, text = render()
        for part in ("Cerita Rana", "Teen", "13+", "4.5%", "31.2", "120 halaman", "2 paragraf"):
            assert part in text

    def test_missing_values_are_shown_as_dashes(self):
        _, _, text = render(info(rating=None, age_range=None, pct_adult=None, heaviness=None))
        assert text.count("-") >= 4

    def test_the_three_dimension_shares_are_listed(self):
        _, _, text = render()
        assert "1.0% paragraf" in text and "0.5% paragraf" in text and "3.0% paragraf" in text

    def test_chapters_get_headings_in_order(self):
        _, _, text = render()
        assert text.index("Bab Satu") < text.index("Rana pulang") < text.index("Bab Dua") < text.index("Dede menunggu")

    def test_a_chapter_without_a_title_falls_back_to_its_number(self):
        _, _, text = render(chapters=[], paragraphs=[par("Isi tanpa judul bab.", 3)])
        assert "Bab 3" in text

    def test_flagged_paragraphs_carry_their_dimension_labels(self):
        paragraphs = [par("Paragraf biasa saja.", 1), par("Paragraf kasar sekali.", 1, profanity=0.9), par("Paragraf berdarah.", 1, violence=0.85, sexual=0.6)]
        _, _, text = render(paragraphs=paragraphs)
        assert "[Bahasa kasar]" in text
        assert "[Seksual, Kekerasan]" in text
        assert "3 paragraf" in text

    def test_the_flag_count_in_the_note_matches(self):
        paragraphs = [par("Satu.", 1, sexual=0.9), par("Dua.", 1, sexual=0.7), par("Tiga biasa.", 1)]
        _, _, text = render(paragraphs=paragraphs)
        assert "(2 paragraf)" in text.replace("\n", " ")

    def test_thresholds_are_inclusive_and_per_dimension(self):
        paragraphs = [par("Tepat di ambang.", 1, profanity=0.5), par("Kekerasan di bawah ambang.", 1, violence=0.79)]
        _, _, text = render(paragraphs=paragraphs)
        assert "[Bahasa kasar]" in text and "[Kekerasan]" not in text

    def test_the_emotion_note_is_included(self):
        _, _, text = render()
        assert EMOTION_NEGATIVE_NOTE.split(" = ")[0] in text.replace("\n", " ")

    def test_titles_and_text_are_html_escaped(self):
        _, _, text = render(info(title="<b>Judul</b> & Co"), paragraphs=[par("Kata <i>miring</i> & tanda.", 1)])
        assert "<b>Judul</b> & Co" in text and "<i>miring</i>" in text

    def test_every_page_is_numbered(self):
        paragraphs = [par("Kalimat panjang yang berulang agar dokumen membutuhkan lebih dari satu halaman. " * 6, 1) for _ in range(60)]
        _, pdf, _ = render(paragraphs=paragraphs)
        assert len(pdf) > 1
        for number, page in enumerate(pdf, start=1):
            assert f"{number} / {len(pdf)}" in page.get_text("text")

    def test_an_empty_book_still_produces_a_pdf(self):
        data, pdf, text = render(paragraphs=[], chapters=[])
        assert data.startswith(b"%PDF") and "0 paragraf" in text


class TestSummaries:
    def test_the_overall_summary_gets_its_own_section_before_the_chapters(self):
        _, _, text = render(info(summary="Rana dan Dede tumbuh bersama di desa kecil."))
        flat = text.replace("\n", " ")
        assert "Rangkuman cerita" in flat and "Rana dan Dede tumbuh bersama di desa kecil." in flat
        assert flat.index("Rangkuman cerita") < flat.index("Bab Satu")

    def test_chapter_summaries_appear_under_their_headings(self):
        chapters = [chapter(1, "Bab Satu", "Rana pulang membawa buku."), chapter(2, "Bab Dua", "Dede menunggu dengan sabar.")]
        _, _, text = render(chapters=chapters)
        flat = text.replace("\n", " ")
        assert flat.index("Bab Satu") < flat.index("Rangkuman bab: Rana pulang membawa buku.") < flat.index("Rana pulang ke rumah.")
        assert flat.index("Bab Dua") < flat.index("Rangkuman bab: Dede menunggu dengan sabar.") < flat.index("Dede menunggu di depan pintu.")

    def test_nothing_is_added_when_no_summary_exists(self):
        _, _, text = render()
        assert "Rangkuman" not in text

    def test_chapters_without_a_summary_are_skipped_quietly(self):
        chapters = [chapter(1, "Bab Satu", "Hanya bab satu yang dirangkum."), chapter(2, "Bab Dua", None)]
        _, _, text = render(chapters=chapters)
        assert text.count("Rangkuman bab:") == 1

    def test_blank_summaries_count_as_missing(self):
        _, _, text = render(info(summary="   "), chapters=[chapter(1, "Bab Satu", "  "), chapter(2, "Bab Dua", "")])
        assert "Rangkuman" not in text

    def test_summary_text_is_html_escaped(self):
        _, _, text = render(info(summary="Ia berkata <b>tebal</b> & pergi."), chapters=[chapter(1, "Bab Satu", "Isi <i>miring</i> & lagi.")])
        flat = text.replace("\n", " ")
        assert "<b>tebal</b> & pergi." in flat and "<i>miring</i> & lagi." in flat

    def test_a_multi_paragraph_summary_keeps_its_paragraphs(self):
        _, _, text = render(info(summary="Paragraf rangkuman pertama.\n\nParagraf rangkuman kedua."))
        assert "Paragraf rangkuman pertama." in text and "Paragraf rangkuman kedua." in text

    def test_the_summary_does_not_replace_the_flagged_text(self):
        _, _, text = render(info(summary="Ada kekerasan di cerita ini."), paragraphs=[par("Paragraf berdarah.", 1, violence=0.9)])
        assert "[Kekerasan]" in text and "Ada kekerasan di cerita ini." in text


@pytest.fixture
def high(make_user):
    return make_user("high", expires_at=datetime.utcnow() + timedelta(days=10))


class TestExportEndpoint:
    def test_a_finished_book_downloads_as_a_pdf_attachment(self, client, db, auth, high, make_doc):
        doc = make_doc(high, title="Laskar Pelangi")
        res = client.get(f"/documents/{doc.id}/export", headers=auth(high))
        assert res.status_code == 200 and res.headers["content-type"] == "application/pdf"
        assert res.headers["content-disposition"] == 'attachment; filename="NARAtive - Laskar Pelangi.pdf"'
        assert pymupdf.open("pdf", res.content)[0].get_text("text")

    def test_the_pdf_reflects_the_stored_scores(self, client, db, auth, high, make_doc):
        doc = make_doc(high)
        doc.paragraphs[0].sexual = 0.95
        db.commit()
        res = client.get(f"/documents/{doc.id}/export", headers=auth(high))
        text = " ".join(page.get_text("text") for page in pymupdf.open("pdf", res.content))
        assert "[Seksual]" in text and "Paragraf pertama." in text

    def test_a_book_with_a_summary_exports_it(self, client, db, auth, high, make_doc):
        doc = make_doc(high, summary="Rangkuman seluruh buku uji.")
        res = client.get(f"/documents/{doc.id}/export", headers=auth(high))
        text = " ".join(page.get_text("text") for page in pymupdf.open("pdf", res.content)).replace("\n", " ")
        assert "Rangkuman cerita" in text and "Rangkuman seluruh buku uji." in text and "Rangkuman bab: Ringkasan bab satu." in text

    def test_a_book_without_a_summary_exports_without_one(self, client, db, auth, high, make_doc):
        doc = make_doc(high)
        res = client.get(f"/documents/{doc.id}/export", headers=auth(high))
        assert "Rangkuman" not in " ".join(page.get_text("text") for page in pymupdf.open("pdf", res.content))

    def test_an_unfinished_book_cannot_be_exported(self, client, auth, high, make_doc):
        doc = make_doc(high, status="analyzing")
        res = client.get(f"/documents/{doc.id}/export", headers=auth(high))
        assert res.status_code == 409 and res.json()["detail"] == "Analisis belum selesai."

    def test_another_users_book_is_not_found(self, client, auth, high, make_user, make_doc):
        other = make_user("high", expires_at=datetime.utcnow() + timedelta(days=10))
        doc = make_doc(other)
        assert client.get(f"/documents/{doc.id}/export", headers=auth(high)).status_code == 404

    def test_a_missing_book_is_not_found(self, client, auth, high):
        assert client.get("/documents/99999/export", headers=auth(high)).status_code == 404

    def test_a_build_failure_is_reported_politely(self, client, auth, high, make_doc, monkeypatch):
        monkeypatch.setattr(documents, "build_pdf", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("meledak")))
        doc = make_doc(high)
        res = client.get(f"/documents/{doc.id}/export", headers=auth(high))
        assert res.status_code == 500 and res.json()["detail"] == "Gagal menyusun PDF. Coba lagi."

    @pytest.mark.parametrize(
        "title,expected",
        [
            ('Judul: "Aneh"/Uji?', "Judul_ _Aneh__Uji_"),
            ("a" * 200, "a" * 80),
            ("???", "___"),
        ],
    )
    def test_the_file_name_is_made_safe(self, client, auth, high, make_doc, title, expected):
        doc = make_doc(high, title=title)
        res = client.get(f"/documents/{doc.id}/export", headers=auth(high))
        assert res.headers["content-disposition"] == f'attachment; filename="NARAtive - {expected}.pdf"'

    def test_a_blank_title_falls_back_to_a_generic_name(self, client, db, auth, high, make_doc):
        doc = make_doc(high, title="   ")
        res = client.get(f"/documents/{doc.id}/export", headers=auth(high))
        assert res.headers["content-disposition"] == 'attachment; filename="NARAtive - hasil.pdf"'

    def test_login_is_required(self, client, make_doc, high):
        doc = make_doc(high)
        assert client.get(f"/documents/{doc.id}/export").status_code == 401
