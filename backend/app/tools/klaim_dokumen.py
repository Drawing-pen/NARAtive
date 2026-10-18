import sys

from sqlalchemy import select

from app.core.security import DEFAULT_EMAIL
from app.db.database import SessionLocal
from app.db.models import Document, User


def main() -> None:
    if len(sys.argv) != 2:
        print("Pemakaian: python -m app.tools.klaim_dokumen email@kamu.com")
        return
    email = sys.argv[1].strip().lower()
    with SessionLocal() as db:
        target = db.scalar(select(User).where(User.email == email))
        if target is None:
            print(f"Akun {email} belum terdaftar. Daftar dulu lewat halaman registrasi.")
            return
        old = db.scalar(select(User).where(User.email == DEFAULT_EMAIL))
        if old is None or old.id == target.id:
            print("Tidak ada dokumen lama yang perlu dipindahkan.")
            return
        docs = db.scalars(select(Document).where(Document.user_id == old.id)).all()
        for d in docs:
            d.user_id = target.id
        db.commit()
        print(f"{len(docs)} dokumen dipindahkan ke {email}.")


if __name__ == "__main__":
    main()