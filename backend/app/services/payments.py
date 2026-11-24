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


def snap_base() -> str:
    return "https://app.midtrans.com" if settings.midtrans_is_production else "https://app.sandbox.midtrans.com"


def snap_script_url() -> str:
    return snap_base() + "/snap/snap.js"


def _call(path: str, body: dict | None = None, base: str | None = None) -> dict:
    token = base64.b64encode(f"{settings.midtrans_server_key}:".encode()).decode()
    req = urllib.request.Request(
        (base or _base_url()) + path,
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


def create_snap(order_id: str, amount: int, item_name: str, quantity: int = 1) -> str:
    mode = provider()
    if mode == "unavailable":
        raise PaymentUnavailable("Pembayaran belum tersedia.")
    if mode == "simulated":
        return "SIM-" + secrets.token_hex(8)
    if not settings.midtrans_client_key:
        raise PaymentUnavailable("Pembayaran belum tersedia.")

    data = _call("/snap/v1/transactions", {
        "transaction_details": {"order_id": order_id, "gross_amount": amount},
        "item_details": [{"id": "item-1", "price": amount // quantity, "quantity": quantity, "name": item_name}],
        "expiry": {"unit": "hour", "duration": VA_TTL_HOURS},
    }, base=snap_base())
    token = data.get("token")
    if not token:
        raise PaymentError("Token pembayaran tidak diterima dari layanan pembayaran.")
    return str(token)


_METHOD_LABELS = {
    "echannel": "Mandiri Bill", "qris": "QRIS", "gopay": "GoPay", "shopeepay": "ShopeePay", "credit_card": "Kartu kredit/debit",
    "akulaku": "Akulaku", "kredivo": "Kredivo", "dana": "DANA",
}
SIM_METHODS = {
    "bca": "Virtual Account BCA", "bni": "Virtual Account BNI", "bri": "Virtual Account BRI", "permata": "Virtual Account PERMATA",
    "qris": "QRIS", "gopay": "GoPay",
}


def method_label(data: dict) -> str | None:
    kind = str(data.get("payment_type") or "")
    if not kind:
        return None
    if kind == "bank_transfer":
        banks = data.get("va_numbers") or []
        bank = (banks[0].get("bank") if banks else None) or ("permata" if data.get("permata_va_number") else None)
        return f"Virtual Account {str(bank).upper()}" if bank else "Virtual Account"
    if kind == "cstore":
        store = data.get("store")
        return f"Gerai {str(store).title()}" if store else "Gerai"
    return _METHOD_LABELS.get(kind) or kind.replace("_", " ").title()


def fetch_status(order_id: str) -> dict:
    token = base64.b64encode(f"{settings.midtrans_server_key}:".encode()).decode()
    req = urllib.request.Request(
        _base_url() + f"/v2/{order_id}/status",
        headers={"Accept": "application/json", "Authorization": f"Basic {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.load(res)
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log.warning("Midtrans status %s gagal: %s", order_id, e)
        raise PaymentError("Layanan pembayaran tidak merespons.") from e


def cancel_va(order_id: str) -> None:
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
