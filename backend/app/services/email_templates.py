from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape

from app.core.config import settings
from app.core.plans import PERIOD_DAYS, PLAN_LABEL
from app.db.models import Transaction, User

NAVY = "#24365f"
AMBER = "#efb54d"
PAPER = "#f8f4ec"
CARD = "#ffffff"
LINE = "#e5ddcd"
SAND = "#efe8da"
INK = "#1f2a47"
MUTED = "#5b6685"
FONT = "'Segoe UI',Helvetica,Arial,sans-serif"
SERIF = "Georgia,'Times New Roman',serif"
MONO = "'Courier New',Courier,monospace"
WIB = timedelta(hours=7)
FOOTER = "Email ini dikirim otomatis, mohon tidak dibalas."
LOGO_CID = "narative-logo"


@dataclass(frozen=True)
class Email:
    subject: str
    text: str
    html: str


def site_url(path: str = "") -> str:
    return settings.frontend_url.rstrip("/") + path


def money(amount: int) -> str:
    return f"Rp {amount:,}".replace(",", ".")


def wib(moment: datetime) -> str:
    return f"{moment + WIB:%d-%m-%Y %H:%M} WIB"


def wib_date(moment: datetime) -> str:
    return f"{moment + WIB:%d-%m-%Y}"


def item_label(tx: Transaction) -> str:
    if tx.kind == "upgrade":
        return f"Paket {PLAN_LABEL[tx.plan]} ({PERIOD_DAYS} hari)"
    return f"{tx.quantity} analisis tambahan (pay-per-check)"


def _e(value) -> str:
    return escape(str(value), quote=True)


def _title(text: str) -> str:
    return f'<h1 style="margin:0 0 16px;font-family:{SERIF};font-size:24px;line-height:1.3;color:{NAVY};">{_e(text)}</h1>'


def _paragraph(text: str, muted: bool = False) -> str:
    color = MUTED if muted else INK
    size = "13px" if muted else "15px"
    return f'<p style="margin:0 0 16px;font-family:{FONT};font-size:{size};line-height:1.6;color:{color};">{_e(text)}</p>'


def _code_box(code: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 20px;"><tr>'
        f'<td align="center" style="background:{SAND};border:1px solid {LINE};border-radius:12px;padding:20px 12px;'
        f'font-family:{MONO};font-size:34px;font-weight:700;letter-spacing:10px;color:{NAVY};">{_e(code)}</td></tr></table>'
    )


def _rows(rows: list[tuple[str, str]]) -> str:
    cells = "".join(
        f'<tr><td style="padding:10px 0;border-top:1px solid {LINE};font-family:{FONT};font-size:13px;color:{MUTED};width:38%;vertical-align:top;">{_e(label)}</td>'
        f'<td style="padding:10px 0;border-top:1px solid {LINE};font-family:{FONT};font-size:14px;font-weight:600;color:{INK};vertical-align:top;">{_e(value)}</td></tr>'
        for label, value in rows
    )
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:4px 0 20px;">{cells}</table>'


def _highlight(label: str, value: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:4px 0 20px;"><tr>'
        f'<td style="background:{SAND};border:1px solid {LINE};border-radius:12px;padding:16px 18px;">'
        f'<div style="font-family:{FONT};font-size:12px;letter-spacing:1px;text-transform:uppercase;color:{MUTED};">{_e(label)}</div>'
        f'<div style="padding-top:6px;font-family:{MONO};font-size:24px;font-weight:700;letter-spacing:2px;color:{NAVY};">{_e(value)}</div>'
        f"</td></tr></table>"
    )


def _notice(text: str) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 20px;"><tr>'
        f'<td style="background:#fdf3dc;border-left:4px solid {AMBER};border-radius:6px;padding:12px 14px;'
        f'font-family:{FONT};font-size:13px;line-height:1.5;color:{INK};">{_e(text)}</td></tr></table>'
    )


def _button(label: str, url: str) -> str:
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:4px 0 8px;"><tr>'
        f'<td align="center" style="background:{NAVY};border-radius:10px;">'
        f'<a href="{_e(url)}" style="display:inline-block;padding:13px 26px;font-family:{FONT};font-size:15px;font-weight:700;'
        f'color:#ffffff;text-decoration:none;">{_e(label)}</a></td></tr></table>'
    )


def _page(title: str, preheader: str, content: str) -> str:
    return (
        '<!doctype html><html lang="id"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_e(title)}</title></head>"
        f'<body style="margin:0;padding:0;background:{PAPER};">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{PAPER};">{_e(preheader)}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAPER};"><tr>'
        f'<td align="center" style="padding:32px 16px;">'
        f'<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="width:100%;max-width:560px;">'
        f'<tr><td style="background:{CARD};border:1px solid {LINE};border-top:4px solid {AMBER};border-radius:14px;padding:28px;">'
        f'<img src="cid:{LOGO_CID}" alt="NARAtive" width="240" height="75" '
        f'style="display:block;border:0;width:240px;max-width:100%;height:auto;margin:0 0 18px;font-family:{SERIF};font-size:24px;font-weight:700;color:{NAVY};">'
        f'<div style="height:1px;line-height:1px;font-size:1px;background:{LINE};margin:0 0 24px;">&nbsp;</div>'
        f"{content}</td></tr>"
        f'<tr><td align="center" style="padding:20px 8px 0;font-family:{FONT};font-size:12px;line-height:1.6;color:{MUTED};">'
        f"{_e(FOOTER)}<br>NARAtive · Analisis konten e-book</td></tr>"
        "</table></td></tr></table></body></html>"
    )


def _text(*blocks: str) -> str:
    return "\n\n".join(blocks) + f"\n\nSalam,\nNARAtive\n\n{FOOTER}\n"


def verification_email(name: str, code: str, minutes: int) -> Email:
    text = _text(
        f"Halo {name},",
        f"Kode verifikasi NARAtive kamu: {code}",
        f"Kode berlaku {minutes} menit. Jika bukan kamu yang mendaftar, abaikan email ini.",
    )
    html = _page(
        "Kode verifikasi NARAtive",
        f"Kode verifikasimu {code}, berlaku {minutes} menit.",
        _title("Verifikasi emailmu")
        + _paragraph(f"Halo {name},")
        + _paragraph("Masukkan kode berikut di halaman pendaftaran NARAtive untuk menyelesaikan pembuatan akunmu.")
        + _code_box(code)
        + _paragraph(f"Kode berlaku {minutes} menit.")
        + _paragraph("Jika bukan kamu yang mendaftar, abaikan email ini. Akun tidak akan dibuat tanpa kode tersebut.", muted=True),
    )
    return Email("Kode verifikasi NARAtive", text, html)


def password_reset_email(name: str, code: str, minutes: int) -> Email:
    text = _text(
        f"Halo {name},",
        f"Kode untuk mengatur ulang kata sandi NARAtive kamu: {code}",
        f"Kode berlaku {minutes} menit. Jika bukan kamu yang meminta, abaikan email ini; kata sandimu tidak berubah.",
    )
    html = _page(
        "Atur ulang kata sandi NARAtive",
        f"Kodemu {code}, berlaku {minutes} menit.",
        _title("Atur ulang kata sandi")
        + _paragraph(f"Halo {name},")
        + _paragraph("Masukkan kode berikut di halaman lupa kata sandi NARAtive untuk membuat kata sandi baru.")
        + _code_box(code)
        + _paragraph(f"Kode berlaku {minutes} menit.")
        + _paragraph("Jika bukan kamu yang meminta, abaikan email ini; kata sandimu tidak berubah.", muted=True),
    )
    return Email("Atur ulang kata sandi NARAtive", text, html)


def payment_instructions(user: User, tx: Transaction) -> Email:
    bank = tx.bank.upper()
    history = site_url("/profil#riwayat")
    simulated = "Mode simulasi: nomor Virtual Account ini hanya contoh, tidak ada uang sungguhan."
    steps = f"Buka ATM atau m-banking {bank}, pilih Transfer lalu Virtual Account, masukkan nomor di atas, dan bayar sesuai total."
    lines = [
        f"Halo {user.name},",
        "Pesananmu di NARAtive sudah dibuat. Selesaikan pembayaran sebelum batas waktu.",
        f"No. pesanan : {tx.order_id}\nItem        : {item_label(tx)}\nTotal       : {money(tx.amount)}\n"
        f"Bank        : {bank}\nNo. VA      : {tx.va_number}\nBatas bayar : {wib(tx.expires_at)}",
        steps,
    ]
    if tx.provider == "simulated":
        lines.append(simulated)
    lines.append(f"Pembayaran terkonfirmasi otomatis. Pantau statusnya di {history}")
    html_blocks = (
        _title("Selesaikan pembayaranmu")
        + _paragraph(f"Halo {user.name},")
        + _paragraph("Pesananmu di NARAtive sudah dibuat. Transfer ke nomor Virtual Account berikut sebelum batas waktu.")
        + _highlight(f"Virtual Account {bank}", tx.va_number)
        + _rows([
            ("Total", money(tx.amount)),
            ("Item", item_label(tx)),
            ("Batas pembayaran", wib(tx.expires_at)),
            ("No. pesanan", tx.order_id),
        ])
        + _paragraph(steps)
        + (_notice(simulated) if tx.provider == "simulated" else "")
        + _paragraph("Pembayaran terkonfirmasi otomatis dan paketmu langsung aktif. Kamu juga bisa memantau statusnya kapan saja.")
        + _button("Lihat riwayat pembayaran", history)
    )
    return Email(
        f"Selesaikan pembayaran NARAtive {tx.order_id}",
        _text(*lines),
        _page("Selesaikan pembayaran NARAtive", f"Total {money(tx.amount)} ke VA {bank} {tx.va_number}.", html_blocks),
    )


def invoice(user: User, tx: Transaction) -> Email:
    history = site_url("/profil#riwayat")
    rows = [
        ("No. pesanan", tx.order_id),
        ("Item", item_label(tx)),
        ("Total", money(tx.amount)),
        ("Bank (VA)", f"{tx.bank.upper()} {tx.va_number}"),
        ("Dibayar", wib(tx.paid_at)),
    ]
    if tx.kind == "upgrade" and user.tier_expires_at:
        rows.append(("Aktif sampai", wib_date(user.tier_expires_at)))
    detail = "\n".join(f"{label:<12}: {value}" for label, value in rows)
    text = _text(
        f"Halo {user.name},",
        "Terima kasih, pembayaranmu di NARAtive sudah kami terima.",
        detail,
        f"Riwayat pembayaran: {history}",
    )
    html = _page(
        "Invoice NARAtive",
        f"Pembayaran {money(tx.amount)} diterima. Terima kasih!",
        _title("Pembayaran diterima")
        + _paragraph(f"Halo {user.name},")
        + _paragraph("Terima kasih, pembayaranmu di NARAtive sudah kami terima. Berikut rincian invoice-mu.")
        + _rows(rows)
        + _button("Lihat riwayat pembayaran", history),
    )
    return Email(f"Invoice NARAtive {tx.order_id}", text, html)
