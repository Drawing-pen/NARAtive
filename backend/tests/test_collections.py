import pytest

from app.db import models
from app.services import collections as service


@pytest.fixture
def owner(make_user):
    return make_user("free")


@pytest.fixture
def books(db, owner, make_doc):
    return [make_doc(owner, title=f"Buku {n}") for n in range(1, 6)]


def ids(docs):
    return [d.id for d in docs]


def create(client, auth, user, name, docs):
    return client.post("/collections", json={"name": name, "document_ids": ids(docs)}, headers=auth(user))


def listing(client, auth, user):
    return client.get("/collections", headers=auth(user)).json()


def membership(db, doc):
    db.expire_all()
    fresh = db.get(models.Document, doc.id)
    return fresh.collection_id, fresh.position


class TestCreate:
    def test_a_series_keeps_the_reading_order(self, client, auth, owner, books):
        res = create(client, auth, owner, "Trilogi", [books[2], books[0], books[1]])
        assert res.status_code == 201
        body = res.json()
        assert body["name"] == "Trilogi" and body["document_ids"] == ids([books[2], books[0], books[1]])

    def test_positions_are_stored_per_book(self, client, db, auth, owner, books):
        res = create(client, auth, owner, "Seri", [books[1], books[0]])
        series_id = res.json()["id"]
        assert membership(db, books[1]) == (series_id, 0)
        assert membership(db, books[0]) == (series_id, 1)

    def test_the_name_is_tidied(self, client, auth, owner, books):
        res = create(client, auth, owner, "  Seri    Pertama  ", books[:2])
        assert res.json()["name"] == "Seri Pertama"

    @pytest.mark.parametrize("name", ["", "   ", "x" * 151])
    def test_a_bad_name_is_rejected(self, client, auth, owner, books, name):
        assert create(client, auth, owner, name, books[:2]).status_code == 422

    def test_the_empty_name_message_is_in_indonesian(self, client, auth, owner, books):
        res = create(client, auth, owner, "   ", books[:2])
        assert "Nama koleksi tidak boleh kosong." in res.text

    def test_a_name_of_150_characters_is_allowed(self, client, auth, owner, books):
        assert create(client, auth, owner, "x" * 150, books[:2]).status_code == 201

    def test_a_series_needs_at_least_two_books(self, client, auth, owner, books):
        assert create(client, auth, owner, "Seri", books[:1]).status_code == 422
        assert create(client, auth, owner, "Seri", []).status_code == 422

    def test_a_series_holds_at_most_fifty_books(self, client, auth, owner, make_doc):
        many = [make_doc(owner, title=f"B{n}") for n in range(51)]
        assert create(client, auth, owner, "Besar", many).status_code == 422
        assert create(client, auth, owner, "Besar", many[:50]).status_code == 201

    def test_the_same_book_cannot_be_listed_twice(self, client, auth, owner, books):
        res = create(client, auth, owner, "Seri", [books[0], books[0], books[1]])
        assert res.status_code == 400
        assert res.json()["detail"] == "Satu e-book tidak bisa dimasukkan dua kali."

    def test_books_of_other_users_cannot_be_added(self, client, auth, owner, books, make_user, make_doc):
        stranger = make_doc(make_user("free"), title="Milik orang lain")
        res = create(client, auth, owner, "Seri", [books[0], stranger])
        assert res.status_code == 404
        assert res.json()["detail"] == "Ada e-book yang tidak ditemukan."

    def test_unknown_books_cannot_be_added(self, client, auth, owner, books):
        res = client.post("/collections", json={"name": "Seri", "document_ids": [books[0].id, 99999]}, headers=auth(owner))
        assert res.status_code == 404

    def test_nothing_is_created_when_a_book_is_rejected(self, client, db, auth, owner, books, make_user, make_doc):
        stranger = make_doc(make_user("free"))
        create(client, auth, owner, "Seri", [books[0], stranger])
        db.expire_all()
        assert db.query(models.Collection).count() == 0
        assert membership(db, books[0]) == (None, 0)

    def test_it_requires_login(self, client, books):
        res = client.post("/collections", json={"name": "Seri", "document_ids": ids(books[:2])})
        assert res.status_code == 401

    def test_creating_a_series_does_not_use_the_analysis_quota(self, client, db, auth, owner, books):
        from app.services import billing
        create(client, auth, owner, "Seri", books[:2])
        assert billing.used_this_month(db, owner) == 0


class TestMoving:
    def test_a_book_moves_out_of_its_old_series(self, client, db, auth, owner, books):
        first = create(client, auth, owner, "A", books[:3]).json()
        second = create(client, auth, owner, "B", [books[2], books[3]]).json()
        assert membership(db, books[2])[0] == second["id"]
        old = next(s for s in listing(client, auth, owner) if s["id"] == first["id"])
        assert old["document_ids"] == ids(books[:2])

    def test_a_series_left_without_books_disappears(self, client, db, auth, owner, books):
        first = create(client, auth, owner, "A", books[:2]).json()
        create(client, auth, owner, "B", books[:2])
        assert first["id"] not in [s["id"] for s in listing(client, auth, owner)]
        db.expire_all()
        assert db.query(models.Collection).count() == 1

    def test_a_series_with_one_remaining_book_survives(self, client, auth, owner, books):
        first = create(client, auth, owner, "A", books[:3]).json()
        create(client, auth, owner, "B", books[1:3])
        survivors = {s["id"]: s["document_ids"] for s in listing(client, auth, owner)}
        assert survivors[first["id"]] == [books[0].id]


class TestListing:
    def test_only_own_series_are_listed_newest_first(self, client, auth, owner, books, make_user, make_doc):
        stranger = make_user("free")
        theirs = [make_doc(stranger, title="X1"), make_doc(stranger, title="X2")]
        create(client, auth, stranger, "Milik lain", theirs)
        older = create(client, auth, owner, "Lama", books[:2]).json()
        newer = create(client, auth, owner, "Baru", books[2:4]).json()
        assert [s["id"] for s in listing(client, auth, owner)] == [newer["id"], older["id"]]

    def test_listing_requires_login(self, client):
        assert client.get("/collections").status_code == 401

    def test_no_series_gives_an_empty_list(self, client, auth, owner):
        assert listing(client, auth, owner) == []


class TestUpdate:
    def test_renaming_and_reordering(self, client, auth, owner, books):
        series = create(client, auth, owner, "Lama", books[:3]).json()
        res = client.put(
            f"/collections/{series['id']}", json={"name": "Baru", "document_ids": ids([books[2], books[0], books[1]])}, headers=auth(owner),
        )
        assert res.status_code == 200
        assert res.json() == {"id": series["id"], "name": "Baru", "document_ids": ids([books[2], books[0], books[1]])}

    def test_books_left_out_are_released(self, client, db, auth, owner, books):
        series = create(client, auth, owner, "Seri", books[:3]).json()
        client.put(f"/collections/{series['id']}", json={"name": "Seri", "document_ids": ids(books[:2])}, headers=auth(owner))
        assert membership(db, books[2])[0] is None

    def test_new_books_can_be_added(self, client, auth, owner, books):
        series = create(client, auth, owner, "Seri", books[:2]).json()
        res = client.put(f"/collections/{series['id']}", json={"name": "Seri", "document_ids": ids(books[:4])}, headers=auth(owner))
        assert res.json()["document_ids"] == ids(books[:4])

    def test_another_users_series_is_not_found(self, client, auth, owner, books, make_user):
        series = create(client, auth, owner, "Seri", books[:2]).json()
        other = make_user("free")
        res = client.put(f"/collections/{series['id']}", json={"name": "X", "document_ids": ids(books[:2])}, headers=auth(other))
        assert res.status_code == 404
        assert res.json()["detail"] == "Koleksi tidak ditemukan."

    def test_the_same_rules_apply_as_when_creating(self, client, auth, owner, books):
        series = create(client, auth, owner, "Seri", books[:2]).json()
        path = f"/collections/{series['id']}"
        assert client.put(path, json={"name": "Seri", "document_ids": [books[0].id, books[0].id]}, headers=auth(owner)).status_code == 400
        assert client.put(path, json={"name": "Seri", "document_ids": [books[0].id]}, headers=auth(owner)).status_code == 422
        assert client.put(path, json={"name": " ", "document_ids": ids(books[:2])}, headers=auth(owner)).status_code == 422

    def test_a_series_cannot_steal_a_book_from_another_users_series(self, client, auth, owner, books, make_user, make_doc):
        stranger = make_user("free")
        theirs = [make_doc(stranger, title="X1"), make_doc(stranger, title="X2")]
        create(client, auth, stranger, "Milik lain", theirs)
        series = create(client, auth, owner, "Seri", books[:2]).json()
        res = client.put(f"/collections/{series['id']}", json={"name": "Seri", "document_ids": [books[0].id, theirs[0].id]}, headers=auth(owner))
        assert res.status_code == 404


class TestDissolving:
    def test_dissolving_keeps_the_books(self, client, db, auth, owner, books):
        series = create(client, auth, owner, "Seri", books[:3]).json()
        assert client.delete(f"/collections/{series['id']}", headers=auth(owner)).status_code == 204
        db.expire_all()
        assert db.query(models.Collection).count() == 0
        assert db.query(models.Document).count() == 5
        assert all(membership(db, b)[0] is None for b in books[:3])

    def test_another_users_series_cannot_be_dissolved(self, client, db, auth, owner, books, make_user):
        series = create(client, auth, owner, "Seri", books[:2]).json()
        res = client.delete(f"/collections/{series['id']}", headers=auth(make_user("free")))
        assert res.status_code == 404
        db.expire_all()
        assert db.query(models.Collection).count() == 1

    def test_an_unknown_series_is_not_found(self, client, auth, owner):
        assert client.delete("/collections/9999", headers=auth(owner)).status_code == 404


class TestDeletingBooks:
    def test_deleting_a_book_leaves_the_rest_of_the_series(self, client, auth, owner, books):
        series = create(client, auth, owner, "Seri", books[:3]).json()
        assert client.delete(f"/documents/{books[0].id}", headers=auth(owner)).status_code == 204
        [remaining] = listing(client, auth, owner)
        assert remaining["id"] == series["id"] and remaining["document_ids"] == ids(books[1:3])

    def test_deleting_the_last_books_removes_the_series(self, client, db, auth, owner, books):
        create(client, auth, owner, "Seri", books[:2])
        client.delete(f"/documents/{books[0].id}", headers=auth(owner))
        client.delete(f"/documents/{books[1].id}", headers=auth(owner))
        assert listing(client, auth, owner) == []
        db.expire_all()
        assert db.query(models.Collection).count() == 0


def test_pruning_only_touches_the_users_own_empty_series(db, make_user):
    mine, theirs = make_user("free"), make_user("free")
    db.add_all([models.Collection(user_id=mine.id, name="Kosong saya"), models.Collection(user_id=theirs.id, name="Kosong mereka")])
    db.commit()
    service.prune_empty(db, mine.id)
    db.commit()
    assert [c.name for c in db.query(models.Collection).all()] == ["Kosong mereka"]
