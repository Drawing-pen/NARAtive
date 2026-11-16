import json
import sys
from datetime import datetime, timedelta

import pytest

from app.core.security import create_access_token
from app.db import models
from app.tools import jadikan_admin

URL = "/admin/overview"


@pytest.fixture
def admin(make_user, db):
    user = make_user(email="pemilik@example.com")
    user.role = "admin"
    db.commit()
    return user


def tx(db, user, *, status="paid", kind="upgrade", plan="middle", amount=29_000, paid_at=None, n=[0]):
    n[0] += 1
    row = models.Transaction(
        user_id=user.id, order_id=f"NAR-{n[0]:05d}", kind=kind, plan=plan, amount=amount, bank="bca",
        va_number=f"8800{n[0]:08d}", provider="simulated", status=status,
        expires_at=datetime.utcnow() + timedelta(hours=24),
        paid_at=paid_at if paid_at is not None else (datetime.utcnow() if status == "paid" else None),
    )
    db.add(row)
    db.commit()
    return row


def overview(client, auth, admin):
    response = client.get(URL, headers=auth(admin))
    assert response.status_code == 200, response.text
    return response.json()


class TestAkses:
    def test_tanpa_token_401(self, client):
        assert client.get(URL).status_code == 401

    def test_pengguna_biasa_403(self, client, auth, make_user):
        response = client.get(URL, headers=auth(make_user()))
        assert response.status_code == 403
        assert response.json()["detail"] == "Fitur ini khusus admin."

    def test_admin_boleh(self, client, auth, admin):
        assert client.get(URL, headers=auth(admin)).status_code == 200

    def test_admin_tidak_aktif_ditolak(self, client, auth, admin, db):
        admin.is_active = False
        db.commit()
        assert client.get(URL, headers=auth(admin)).status_code == 401

    def test_pengguna_tidak_bisa_mengangkat_diri(self, client, auth, make_user, db):
        user = make_user()
        client.patch("/auth/me", json={"name": "Baru", "role": "admin"}, headers=auth(user))
        db.refresh(user)
        assert user.role == "user"
        assert client.get(URL, headers=auth(user)).status_code == 403


class TestPengguna:
    def test_hitung_per_tier_tanpa_admin_dan_tier_kedaluwarsa_jadi_free(self, client, auth, admin, make_user, db):
        make_user("free")
        make_user("middle", expires_at=datetime.utcnow() + timedelta(days=5))
        make_user("middle", expires_at=datetime.utcnow() - timedelta(days=1))
        make_user("high")
        mati = make_user("free")
        mati.is_active = False
        db.commit()
        users = overview(client, auth, admin)["users"]
        assert users["total"] == 5
        assert users["inactive"] == 1
        assert users["per_tier"] == {"free": 2, "middle": 1, "high": 1}
        assert sum(users["per_tier"].values()) == users["total"] - users["inactive"]

    def test_pendaftar_30_hari_terisi_nol(self, client, auth, admin, make_user, db):
        user = make_user()
        user.created_at = datetime.utcnow() - timedelta(days=3)
        old = make_user()
        old.created_at = datetime.utcnow() - timedelta(days=90)
        db.commit()
        signups = overview(client, auth, admin)["users"]["signups"]
        assert len(signups) == 30
        assert signups[-1]["date"] == datetime.utcnow().date().isoformat()
        by_date = {row["date"]: row["count"] for row in signups}
        assert by_date[(datetime.utcnow() - timedelta(days=3)).date().isoformat()] == 1
        assert sum(by_date.values()) == 1


class TestPendapatan:
    def test_hanya_yang_paid_dihitung(self, client, auth, admin, make_user, db):
        user = make_user()
        tx(db, user, amount=29_000)
        tx(db, user, plan="high", amount=59_000)
        tx(db, user, kind="pay_per_check", plan=None, amount=5_000)
        tx(db, user, status="pending", amount=59_000)
        tx(db, user, status="failed", amount=29_000)
        revenue = overview(client, auth, admin)["revenue"]
        assert revenue["paid_total"] == 93_000
        assert revenue["paid_this_month"] == 93_000
        assert revenue["by_status"]["paid"] == 3
        assert revenue["by_status"]["pending"] == 1
        assert revenue["by_status"]["failed"] == 1
        assert revenue["by_status"]["expired"] == 0
        assert revenue["by_plan"]["middle"] == {"count": 1, "amount": 29_000}
        assert revenue["by_plan"]["high"] == {"count": 1, "amount": 59_000}
        assert revenue["by_plan"]["pay_per_check"] == {"count": 1, "amount": 5_000}

    def test_pendapatan_bulan_ini_dan_per_hari(self, client, auth, admin, make_user, db):
        user = make_user()
        tx(db, user, amount=29_000)
        tx(db, user, amount=59_000, plan="high", paid_at=datetime.utcnow() - timedelta(days=100))
        revenue = overview(client, auth, admin)["revenue"]
        assert revenue["paid_total"] == 88_000
        assert revenue["paid_this_month"] == 29_000
        assert len(revenue["per_day"]) == 30
        assert revenue["per_day"][-1] == {"date": datetime.utcnow().date().isoformat(), "amount": 29_000}
        assert sum(row["amount"] for row in revenue["per_day"]) == 29_000

    def test_transaksi_admin_tidak_dihitung(self, client, auth, admin, db):
        tx(db, admin, amount=59_000)
        assert overview(client, auth, admin)["revenue"]["paid_total"] == 0


class TestDokumen:
    def test_status_dan_alasan_gagal(self, client, auth, admin, make_user, make_doc, db):
        user = make_user()
        make_doc(user, status="done", summary="Ringkasan.", characters=["Rana"])
        make_doc(user, status="done")
        for reason in ("PDF terenkripsi", "PDF terenkripsi", "Teks tidak terbaca", None):
            doc = make_doc(user, status="failed")
            doc.failure_reason = reason
        db.commit()
        docs = overview(client, auth, admin)["documents"]
        assert docs["total"] == 6
        assert docs["by_status"]["done"] == 2
        assert docs["by_status"]["failed"] == 4
        assert docs["by_status"]["queued"] == 0
        assert docs["failure_reasons"][0] == {"reason": "PDF terenkripsi", "count": 2}
        assert {"reason": "Teks tidak terbaca", "count": 1} in docs["failure_reasons"]
        assert all(row["reason"] for row in docs["failure_reasons"])
        assert docs["summary"] == {"done": 1, "partial": 0, "failed": 0}
        assert docs["characters"] == {"done": 1, "partial": 0, "failed": 0}
        assert len(docs["uploads"]) == 30
        assert sum(row["count"] for row in docs["uploads"]) == 6

    def test_alasan_gagal_maksimal_lima(self, client, auth, admin, make_user, make_doc, db):
        user = make_user()
        for i in range(7):
            make_doc(user, status="failed").failure_reason = f"Alasan {i}"
        db.commit()
        assert len(overview(client, auth, admin)["documents"]["failure_reasons"]) == 5

    def test_dokumen_admin_tidak_dihitung(self, client, auth, admin, make_doc):
        make_doc(admin)
        assert overview(client, auth, admin)["documents"]["total"] == 0


class TestKuota:
    def test_hitung_pengguna_yang_mentok(self, client, auth, admin, make_user, db):
        period = datetime.utcnow().strftime("%Y-%m")
        penuh = make_user("free")
        masih = make_user("free")
        middle_penuh = make_user("middle", expires_at=datetime.utcnow() + timedelta(days=5))
        tinggi = make_user("high")
        for user, used in ((penuh, 3), (masih, 2), (middle_penuh, 15), (tinggi, 500)):
            db.add(models.UsageQuota(user_id=user.id, period=period, used=used))
        db.add(models.UsageQuota(user_id=masih.id, period="2020-01", used=99))
        db.commit()
        assert overview(client, auth, admin)["quota"]["at_limit"] == 2


class TestPrivasi:
    def test_respons_tidak_memuat_data_pribadi(self, client, auth, admin, make_user, make_doc, db):
        user = make_user(email="rahasia.sekali@example.com")
        user.name = "Nama Rahasia Banget"
        db.commit()
        doc = make_doc(user, title="Judul Rahasia Banget")
        doc.failure_reason = "PDF terenkripsi"
        row = tx(db, user)
        raw = json.dumps(client.get(URL, headers=auth(admin)).json())
        for secret in ("rahasia.sekali", "Nama Rahasia", "Judul Rahasia", ".pdf", row.order_id, row.va_number, "pemilik@example.com", "password"):
            assert secret not in raw

    def test_tidak_ada_kunci_identitas(self, client, auth, admin, make_user, make_doc):
        make_doc(make_user())
        raw = json.dumps(client.get(URL, headers=auth(admin)).json())
        for key in ('"email"', '"name"', '"title"', '"filename"', '"user_id"', '"order_id"', '"va_number"', '"id"'):
            assert key not in raw


class TestPerintahJadikanAdmin:
    def run(self, monkeypatch, *args):
        monkeypatch.setattr(sys, "argv", ["jadikan_admin", *args])
        jadikan_admin.main()

    def test_menjadikan_dan_mencabut(self, monkeypatch, make_user, db, capsys):
        user = make_user(email="aku@example.com")
        self.run(monkeypatch, "Aku@Example.com")
        db.refresh(user)
        assert user.role == "admin"
        self.run(monkeypatch, "aku@example.com", "cabut")
        db.refresh(user)
        assert user.role == "user"

    def test_email_tidak_dikenal_dan_argumen_salah(self, monkeypatch, make_user, db, capsys):
        user = make_user()
        self.run(monkeypatch, "tidak-ada@example.com")
        assert "belum terdaftar" in capsys.readouterr().out
        self.run(monkeypatch)
        assert "Pemakaian" in capsys.readouterr().out
        self.run(monkeypatch, user.email, "apa-ini")
        assert "Pemakaian" in capsys.readouterr().out
        db.refresh(user)
        assert user.role == "user"
