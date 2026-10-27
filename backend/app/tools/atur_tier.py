import sys

from sqlalchemy import select

from app.core.security import TIER_RANK
from app.db.database import SessionLocal
from app.db.models import User


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[2] not in TIER_RANK:
        print(f"Pemakaian: python -m app.tools.atur_tier email@kamu.com {'|'.join(TIER_RANK)}")
        return
    email, tier = sys.argv[1].strip().lower(), sys.argv[2]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"Akun {email} belum terdaftar. Daftar dulu lewat halaman registrasi.")
            return
        user.tier = tier
        db.commit()
        print(f"Tingkatan {email} sekarang: {tier}. Muat ulang halaman agar terbaca di aplikasi.")


if __name__ == "__main__":
    main()
