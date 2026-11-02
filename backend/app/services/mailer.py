import logging
import smtplib
import threading
from email.message import EmailMessage
from pathlib import Path

from app.core.config import settings
from app.services.email_templates import LOGO_CID

log = logging.getLogger("uvicorn.error")

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "email-logo.png"


def _deliver(msg: EmailMessage) -> None:
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:
        log.exception("Invoice gagal dikirim ke %s", msg["To"])


def _attach_logo(msg: EmailMessage) -> None:
    try:
        data = LOGO_PATH.read_bytes()
    except OSError:
        log.warning("Logo email tidak ditemukan: %s", LOGO_PATH)
        return
    msg.get_body(("html",)).add_related(data, "image", "png", cid=f"<{LOGO_CID}>", filename="narative.png", disposition="inline")


def send(to: str, subject: str, body: str, html: str | None = None) -> None:
    """Kirim email di thread terpisah agar proses pembayaran tidak menunggu SMTP; tanpa SMTP hanya dicatat di log."""
    if not settings.smtp_host:
        log.info("[email belum diatur, tidak terkirim] ke %s | %s\n%s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.smtp_from, to, subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")
        if f"cid:{LOGO_CID}" in html:
            _attach_logo(msg)
    threading.Thread(target=_deliver, args=(msg,), daemon=True).start()
