from app.db import models


def paragraphs(client, auth, user, doc):
    return client.get(f"/documents/{doc.id}/paragraphs", headers=auth(user)).json()


def test_old_paragraphs_have_no_markdown_and_are_plain(client, auth, make_user, make_doc):
    user = make_user("free")
    items = paragraphs(client, auth, user, make_doc(user))
    assert items and all(p["markdown"] is None and p["kind"] == "p" for p in items)


def test_markdown_and_kind_are_returned_with_the_plain_text(client, db, auth, make_user, make_doc):
    user = make_user("free")
    doc = make_doc(user)
    first = doc.paragraphs[0]
    first.markdown, first.kind, first.text = "## Sub judul", "h", "Sub judul"
    doc.paragraphs[1].markdown = "Kalimat dengan **huruf tebal** di dalamnya."
    db.commit()
    items = paragraphs(client, auth, user, doc)
    assert (items[0]["markdown"], items[0]["kind"], items[0]["text"]) == ("## Sub judul", "h", "Sub judul")
    assert items[1]["markdown"] == "Kalimat dengan **huruf tebal** di dalamnya." and items[1]["kind"] == "p"


def test_a_new_paragraph_defaults_to_the_plain_kind(db, make_user, make_doc):
    doc = make_doc(make_user("free"))
    db.add(models.Paragraph(document_id=doc.id, idx=99, chapter_no=1, text="Teks baru yang cukup panjang."))
    db.commit()
    fresh = db.query(models.Paragraph).filter_by(idx=99).one()
    assert fresh.kind == "p" and fresh.markdown is None


def test_the_analysis_still_works_on_the_plain_text(db, make_user, make_doc):
    doc = make_doc(make_user("free"))
    doc.paragraphs[0].markdown = "**Teks** tebal."
    db.commit()
    assert doc.paragraphs[0].text == "Paragraf pertama."
