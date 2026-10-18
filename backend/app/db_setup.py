import re
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import make_url

from .config import settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


def create_database_if_missing() -> None:
    url = make_url(settings.database_url)
    if not url.drivername.startswith("mysql"):
        return  
    name = url.database
    if not name or not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise SystemExit(f"Nama database '{name}' tidak valid (hanya huruf, angka, underscore).")
    engine = create_engine(url.set(database=None), isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    engine.dispose()
    print(f"Database '{name}' siap.")


def drop_all_tables() -> None:
    engine = create_engine(settings.database_url)
    meta = MetaData()
    meta.reflect(bind=engine)
    with engine.begin() as conn:
        if engine.dialect.name == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        meta.drop_all(conn)
        if engine.dialect.name == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    engine.dispose()
    print(f"{len(meta.tables)} tabel dihapus.")


def migrate() -> None:
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    print("Migrasi selesai.")


if __name__ == "__main__":
    create_database_if_missing()
    if "--fresh" in sys.argv:
        drop_all_tables()
    migrate()