"""Gateway pembayaran Virtual Account.

Tanpa MIDTRANS_SERVER_KEY dipakai mode simulasi: nomor VA dibuat lokal dan pembayaran "dikonfirmasi" lewat
endpoint simulasi. Dengan kunci itu, VA dibuat lewat Core API Midtrans dan status datang lewat notifikasi webhook.
"""
import base64
import hashlib
import hmac
import json
import logging
import secrets
import urllib.error
import urllib.request
from urllib.parse import urlparse

from app.core.config import settings
from app.core.plans import VA_TTL_HOURS

log = logging.getLogger("uvicorn.error")

_SIM_PREFIX = {"bca": "39358", "bni": "8810", "bri": "26215", "permata": "8528"}
_MIDTRANS_STATUS = {
    "settlement": "paid", "capture": "paid", "pending": "pending",
    "expire": "expired", "cancel": "cancelled", "deny": "failed", "failure": "failed",
}


class PaymentError(Exception):
    pass


class PaymentUnavailable(PaymentError):
    pass


_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _local_only() -> bool:
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    return bool(origins) and all(urlparse(o).hostname in _LOCAL_HOSTS for o in origins)


def provider() -> str:
    if settings.midtrans_server_key:
        return "midtrans"
    return "simulated" if _local_only() else "unavailable"


def _base_url() -> str:
    return "https://api.midtrans.com" if settings.midtrans_is_production else "https://api.sandbox.midtrans.com"


def _call(path: str, body: dict | None = None) -> dict:
    token = base64.b64encode(f"{settings.midtrans_server_key}:".encode()).decode()
    req = urllib.request.Request(
        _base_url() + path,
        data=json.dumps(body).encode() if body is not None else b"",
        headers={"Accept": "application/json", "Content-Type": "application/json", "Authorization": f"Basic {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.load(res)
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log.warning("Midtrans %s gagal: %s", path, e)
        raise PaymentError("Layanan pembayaran tidak merespons.") from e


def create_va(order_id: str, amount: int, bank: str) -> str:
    """Buat nomor Virtual Account untuk satu pesanan."""
    if provider() == "unavailable":
        raise PaymentUnavailable("Pembayaran belum tersedia.")
    if provider() == "simulated":
        prefix = _SIM_PREFIX[bank]
        return prefix + "".join(secrets.choice("0123456789") for _ in range(16 - len(prefix)))

    data = _call("/v2/charge", {
        "payment_type": "bank_transfer",
        "transaction_details": {"order_id": order_id, "gross_amount": amount},
        "bank_transfer": {"bank": bank},
        "custom_expiry": {"expiry_duration": VA_TTL_HOURS, "unit": "hour"},
    })
    if str(data.get("status_code")) not in ("200", "201"):
        raise PaymentError(data.get("status_message") or "Gagal membuat Virtual Account.")
    va = data.get("permata_va_number") if bank == "permata" else (data.get("va_numbers") or [{}])[0].get("va_number")
    if not va:
        raise PaymentError("Nomor Virtual Account tidak diterima dari layanan pembayaran.")
    return str(va)


def cancel_va(order_id: str) -> None:
    """Batalkan VA di gateway (UC-07, alur alternatif). Gagal membatalkan tidak menggagalkan pembatalan di sistem."""
    if provider() == "midtrans":
        try:
            _call(f"/v2/{order_id}/cancel")
        except PaymentError:
            pass


def valid_signature(payload: dict) -> bool:
    raw = f"{payload.get('order_id', '')}{payload.get('status_code', '')}{payload.get('gross_amount', '')}{settings.midtrans_server_key}"
    expected = hashlib.sha512(raw.encode()).hexdigest()
    return hmac.compare_digest(expected, str(payload.get("signature_key", "")))


def map_status(midtrans_status: str) -> str | None:
    return _MIDTRANS_STATUS.get(midtrans_status)
