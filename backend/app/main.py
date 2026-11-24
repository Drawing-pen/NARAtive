import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.services.jobs import start_worker
from app.services.reader_jobs import start_worker as start_reader
from app.services import characters as character_service
from app.services.summarizer import reset_stale
from app.services.llm_analyzer import available as analysis_ready
from app.api.routers import admin, auth, billing, collections, documents, images, sensitivity

log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not analysis_ready():
        log.warning("Layanan AI belum dikonfigurasi (9router atau Gemini); unggahan akan ditolak sampai terisi.")
    try:
        start_worker()
    except Exception as e:
        log.warning("Antrean analisis belum berjalan (%s).", e.__class__.__name__)
    try:
        start_reader()
    except Exception as e:
        log.warning("Pekerja pembaca PDF belum berjalan (%s).", e.__class__.__name__)
    try:
        reset_stale()
        character_service.reset_stale()
    except Exception as e:
        log.warning("Status rangkuman dan tokoh belum bisa dipulihkan (%s).", e.__class__.__name__)
    yield


app = FastAPI(title="NARAtive API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(images.router)
app.include_router(collections.router)
app.include_router(billing.router)
app.include_router(sensitivity.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}