import logging
import smtplib
import threading
from email.message import EmailMessage

from app.core.config import settings

log = logging.getLogger("uvicorn.error")


def _deliver(msg: EmailMessage) -> None:
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:
        log.exception("Invoice gagal dikirim ke %s", msg["To"])


def send(to: str, subject: str, body: str) -> None:
    """Kirim email di thread terpisah agar proses pembayaran tidak menunggu SMTP; tanpa SMTP hanya dicatat di log."""
    if not settings.smtp_host:
        log.info("[email belum diatur, tidak terkirim] ke %s | %s\n%s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.smtp_from, to, subject
    msg.set_content(body)
    threading.Thread(target=_deliver, args=(msg,), daemon=True).start()
