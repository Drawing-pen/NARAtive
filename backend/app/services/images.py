import os
import uuid

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

MAX_BYTES = 2 * 1024 * 1024
FOLDER = "images"
MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def sniff(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def read_upload(file: UploadFile) -> tuple[bytes, str]:
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Ukuran gambar maksimal 2 MB.")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File gambar kosong.")
    ext = sniff(data)
    if ext is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Format gambar tidak didukung. Gunakan JPG, PNG, atau WebP.")
    return data, ext


def save(data: bytes, ext: str) -> str:
    os.makedirs(os.path.join(settings.upload_dir, FOLDER), exist_ok=True)
    relative = f"{FOLDER}/{uuid.uuid4().hex}{ext}"
    with open(os.path.join(settings.upload_dir, relative), "wb") as f:
        f.write(data)
    return relative


def load(relative: str | None) -> tuple[bytes, str]:
    if relative:
        try:
            with open(os.path.join(settings.upload_dir, relative), "rb") as f:
                return f.read(), MEDIA_TYPES[os.path.splitext(relative)[1]]
        except FileNotFoundError:
            pass
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Gambar belum diatur.")


def remove(*relatives: str | None) -> None:
    for relative in relatives:
        if relative:
            try:
                os.remove(os.path.join(settings.upload_dir, relative))
            except FileNotFoundError:
                pass
