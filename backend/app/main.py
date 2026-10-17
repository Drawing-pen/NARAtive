import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.services.jobs import start_worker
from app.services.summarizer import reset_stale
from app.ml.analyzer import ModelNotInstalled, get_analyzer
from app.api.routers import documents
from app.core.security import ensure_default_user

log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        ensure_default_user()
    except Exception as e:  # tabel belum ada / database belum siap
        log.warning("Database belum siap (%s). Jalankan: python -m app.db.db_setup", e.__class__.__name__)
    # Muat model saat server menyala supaya analisis pertama tidak lambat.
    try:
        get_analyzer()
        log.info("Model analisis siap.")
    except ModelNotInstalled as e:
        log.warning("%s Unggahan akan ditolak sampai model terpasang.", e)
    try:
        start_worker()
    except Exception as e:
        log.warning("Antrean analisis belum berjalan (%s).", e.__class__.__name__)
    try:
        reset_stale()
    except Exception as e:
        log.warning("Status rangkuman belum bisa dipulihkan (%s).", e.__class__.__name__)
    yield


app = FastAPI(title="NARAtive API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(documents.router)


@app.get("/health")
def health():
    return {"status": "ok"}