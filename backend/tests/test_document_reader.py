import logging

import pytest

from app.api.routers import documents
from app.core.config import settings
from app.db import models
from app.extraction import reader
from app.extraction.epub_utils import EpubError
from tests.builders import blank_pdf, drm_encryption, make_epub, make_pdf, prose


@pytest.fixture
def files(tmp_path):
    def save(name, data):
        path = tmp_path / name
        path.write_bytes(data)
        return str(path)

    return save


def pdf_book():
    return make_pdf([f"Bab 1\n\n{prose(3)}", f"Bab 2\n\n{prose(3, 4)}"], sizes={"Bab 1": 22, "Bab 2": 22})


def epub_book():
    return make_epub([("a.xhtml", f"<h1>Bab Satu</h1><p>Kata <b>tebal</b> {prose(3)}</p>"), ("b.xhtml", f"<h1>Bab Dua</h1><p>{prose(3, 4)}</p>")])


class TestLegacy:
    @pytest.fixture(autouse=True)
    def legacy(self, monkeypatch):
        monkeypatch.setattr(settings, "document_parser", "legacy")

    def test_pdf_blocks_are_plain_paragraphs_without_markdown(self, files):
        parsed = reader.read_document(files("a.pdf", pdf_book()), ".pdf")
        assert parsed.parser == "legacy" and parsed.titles == ["Bab 1", "Bab 2"]
        assert all(b.kind == "p" and b.markdown is None and b.text for _, b in parsed.blocks)

    def test_epub_blocks_are_plain_paragraphs_without_markdown(self, files):
        parsed = reader.read_document(files("a.epub", epub_book()), ".epub")
        assert parsed.parser == "legacy" and all(b.markdown is None for _, b in parsed.blocks)

    def test_page_count_is_reported(self, files):
        assert reader.read_document(files("a.pdf", pdf_book()), ".pdf").page_count == 2


class TestAuto:
    @pytest.fixture(autouse=True)
    def auto(self, monkeypatch):
        monkeypatch.setattr(settings, "document_parser", "auto")

    def test_it_is_the_default(self):
        from app.core.config import Settings
        assert Settings(_env_file=None).document_parser == "auto"

    def test_a_pdf_uses_the_legacy_parser(self, files):
        parsed = reader.read_document(files("a.pdf", pdf_book()), ".pdf")
        assert parsed.parser == "legacy" and all(b.markdown is None for _, b in parsed.blocks)

    def test_an_epub_uses_the_markdown_parser(self, files):
        parsed = reader.read_document(files("a.epub", epub_book()), ".epub")
        assert parsed.parser == "markdown" and any("**tebal**" in b.markdown for _, b in parsed.blocks)

    def test_a_failing_epub_markdown_parser_falls_back_to_legacy(self, files, monkeypatch):
        def boom(path):
            raise RuntimeError("rusak")

        monkeypatch.setattr(reader, "read_epub_markdown", boom)
        assert reader.read_document(files("a.epub", epub_book()), ".epub").parser == "legacy"


class TestMarkdown:
    @pytest.fixture(autouse=True)
    def markdown(self, monkeypatch):
        monkeypatch.setattr(settings, "document_parser", "markdown")

    def test_a_pdf_gives_markdown_blocks(self, files):
        parsed = reader.read_document(files("a.pdf", pdf_book()), ".pdf")
        assert parsed.parser == "markdown" and parsed.titles == ["Bab 1", "Bab 2"] and parsed.page_count == 2
        assert all(b.markdown for _, b in parsed.blocks)

    def test_an_epub_gives_markdown_blocks(self, files):
        parsed = reader.read_document(files("a.epub", epub_book()), ".epub")
        assert parsed.parser == "markdown" and any("**tebal**" in b.markdown for _, b in parsed.blocks)

    def test_an_unexpected_failure_falls_back_to_the_legacy_parser(self, files, monkeypatch, caplog):
        def boom(path):
            raise RuntimeError("pymupdf4llm rusak")

        monkeypatch.setattr(reader, "read_pdf_markdown", boom)
        caplog.set_level(logging.WARNING, logger="uvicorn.error")
        parsed = reader.read_document(files("a.pdf", pdf_book()), ".pdf")
        assert parsed.parser == "legacy" and parsed.blocks and "pymupdf4llm rusak" in caplog.text

    def test_an_empty_result_falls_back_to_the_legacy_parser(self, files, monkeypatch):
        monkeypatch.setattr(reader, "read_pdf_markdown", lambda path: (2, ["Isi naskah"], []))
        parsed = reader.read_document(files("a.pdf", pdf_book()), ".pdf")
        assert parsed.parser == "legacy" and parsed.blocks

    def test_when_both_parsers_find_nothing_the_result_is_empty(self, files):
        parsed = reader.read_document(files("a.pdf", blank_pdf(2)), ".pdf")
        assert parsed.blocks == []

    def test_epub_errors_are_not_hidden_by_the_fallback(self, files, monkeypatch):
        monkeypatch.setattr(reader, "read_epub", lambda path: (1, ["Bab"], [(1, "Teks yang cukup panjang untuk diterima.")]))
        data = make_epub([("a.xhtml", f"<h1>Bab</h1><p>{prose(2)}</p>")], encryption=drm_encryption("http://www.w3.org/2001/04/xmlenc#aes128-cbc"))
        with pytest.raises(EpubError, match="DRM"):
            reader.read_document(files("a.epub", data), ".epub")

    def test_a_corrupt_pdf_still_raises(self, files):
        with pytest.raises(Exception):
            reader.read_document(files("a.pdf", b"%PDF-1.4 rusak"), ".pdf")

    def test_an_unknown_parser_name_means_legacy(self, files, monkeypatch):
        monkeypatch.setattr(settings, "document_parser", "ngawur")
        assert reader.read_document(files("a.pdf", pdf_book()), ".pdf").parser == "legacy"


class TestUpload:
    @pytest.fixture(autouse=True)
    def environment(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
        monkeypatch.setattr(documents, "model_ready", lambda: True)
        monkeypatch.setattr(documents, "enqueue", lambda doc_id: None)

    def upload(self, client, auth, user, data, name="Buku.pdf", mime="application/pdf"):
        return client.post("/documents", files={"file": (name, data, mime)}, headers=auth(user))

    def test_the_default_stores_plain_paragraphs(self, client, db, auth, make_user, monkeypatch):
        monkeypatch.setattr(settings, "document_parser", "legacy")
        user = make_user("middle")
        doc_id = self.upload(client, auth, user, pdf_book()).json()["id"]
        db.expire_all()
        paragraphs = db.get(models.Document, doc_id).paragraphs
        assert paragraphs and all(p.markdown is None and p.kind == "p" for p in paragraphs)

    def test_the_markdown_parser_stores_markdown_and_kind(self, client, db, auth, make_user, monkeypatch):
        monkeypatch.setattr(settings, "document_parser", "markdown")
        user = make_user("middle")
        doc_id = self.upload(client, auth, user, epub_book(), "Novel.epub", "application/epub+zip").json()["id"]
        db.expire_all()
        paragraphs = db.get(models.Document, doc_id).paragraphs
        assert [p.idx for p in paragraphs] == list(range(len(paragraphs)))
        assert any(p.markdown and "**tebal**" in p.markdown for p in paragraphs)
        assert all("**" not in p.text for p in paragraphs)

    def test_the_stored_text_stays_plain_for_analysis(self, client, db, auth, make_user, monkeypatch):
        monkeypatch.setattr(settings, "document_parser", "markdown")
        user = make_user("middle")
        doc_id = self.upload(client, auth, user, pdf_book()).json()["id"]
        db.expire_all()
        assert all(not p.text.startswith("#") for p in db.get(models.Document, doc_id).paragraphs)

    def test_the_api_returns_the_markdown_to_the_reader(self, client, db, auth, make_user, monkeypatch):
        monkeypatch.setattr(settings, "document_parser", "markdown")
        user = make_user("middle")
        doc_id = self.upload(client, auth, user, epub_book(), "Novel.epub", "application/epub+zip").json()["id"]
        items = client.get(f"/documents/{doc_id}/paragraphs", headers=auth(user)).json()
        assert any(i["markdown"] and "**tebal**" in i["markdown"] for i in items) and all(i["kind"] for i in items)

    def test_a_pdf_without_text_is_still_rejected(self, client, db, auth, make_user, monkeypatch):
        monkeypatch.setattr(settings, "document_parser", "markdown")
        res = self.upload(client, auth, make_user("middle"), blank_pdf(2))
        assert res.status_code == 400 and res.json()["detail"] == "File tidak berisi teks yang dapat dianalisis."
