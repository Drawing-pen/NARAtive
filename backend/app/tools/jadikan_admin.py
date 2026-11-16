import sys

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import User


def main() -> None:
    args = sys.argv[1:]
    if not 1 <= len(args) <= 2 or (len(args) == 2 and args[1] != "cabut"):
        print("Pemakaian: python -m app.tools.jadikan_admin email@kamu.com [cabut]")
        return
    email, revoke = args[0].strip().lower(), len(args) == 2
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"Akun {email} belum terdaftar. Daftar dulu lewat halaman registrasi.")
            return
        user.role = "user" if revoke else "admin"
        db.commit()
        print(f"Peran {email} sekarang: {user.role}. Muat ulang halaman agar terbaca di aplikasi.")


if __name__ == "__main__":
    main()
