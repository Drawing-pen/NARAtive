from datetime import datetime, timedelta
from pathlib import Path

import pymupdf

from app.core.plans import PERIOD_DAYS, PLAN_LABEL
from app.db.models import Transaction, User

WIB = timedelta(hours=7)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
BRAND = "NARAtive"
TAGLINE = "Analisis rating konten e-book"
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "email-logo.png"
LOGO_WIDTH = 130
LOGO_RATIO = 163 / 520

def money(amount: int) -> str:
    return f"Rp {amount:,}".replace(",", ".")


def stamp(moment: datetime) -> str:
    local = moment + WIB
    return f"{local.day} {MONTHS[local.month - 1]} {local.year} {local:%H:%M}"


def item_name(tx: Transaction) -> str:
    if tx.kind == "upgrade":
        return f"Paket {PLAN_LABEL[tx.plan]} ({PERIOD_DAYS} hari)"
    return "Analisis tambahan (pay-per-check)"


def method_label(tx: Transaction) -> str:
    if tx.payment_method:
        return tx.payment_method
    return f"Virtual Account {tx.bank.upper()}" if tx.bank else "Pembayaran online"


def build(user: User, tx: Transaction) -> dict:
    quantity = tx.quantity if tx.kind == "pay_per_check" else 1
    return {
        "number": tx.order_id,
        "status": tx.status,
        "issued_at": tx.created_at,
        "due_at": tx.expires_at,
        "paid_at": tx.paid_at,
        "customer_name": user.name,
        "customer_email": user.email,
        "method": method_label(tx),
        "items": [{"no": 1, "name": item_name(tx), "unit_price": tx.amount // quantity, "quantity": quantity, "total": tx.amount}],
        "subtotal": tx.amount,
        "total": tx.amount,
    }


NAVY = (0.141, 0.212, 0.373)
INK = (0.122, 0.165, 0.278)
MUTED = (0.357, 0.400, 0.522)
CAPTION = (0.502, 0.529, 0.647)
LINE = (0.898, 0.867, 0.804)
PAPER = (0.973, 0.957, 0.925)
GREEN = (0.106, 0.478, 0.263)
GREEN_BG = (0.906, 0.965, 0.925)
RED = (0.659, 0.224, 0.169)
LEFT, RIGHT = 50, 545


def _fit(text: str, font: str, size: float, width: float) -> str:
    if pymupdf.get_text_length(text, fontname=font, fontsize=size) <= width:
        return text
    while text and pymupdf.get_text_length(text + "...", fontname=font, fontsize=size) > width:
        text = text[:-1]
    return text + "..."


def _text(page, x: float, y: float, text: str, size: float = 9, bold: bool = False, color=INK, right: bool = False) -> None:
    font = "hebo" if bold else "helv"
    if right:
        x -= pymupdf.get_text_length(text, fontname=font, fontsize=size)
    page.insert_text((x, y), text, fontsize=size, fontname=font, color=color)


def pdf(user: User, tx: Transaction) -> bytes:
    data = build(user, tx)
    item = data["items"][0]
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    if LOGO_PATH.is_file():
        page.insert_image(pymupdf.Rect(LEFT, 46, LEFT + LOGO_WIDTH, 46 + LOGO_WIDTH * LOGO_RATIO), filename=str(LOGO_PATH))
        _text(page, LEFT, 102, TAGLINE, 8.5, color=MUTED)
    else:
        _text(page, LEFT, 72, BRAND, 20, True, NAVY)
        _text(page, LEFT, 87, TAGLINE, 8.5, color=MUTED)
    _text(page, RIGHT, 72, "INVOICE", 24, True, NAVY, right=True)
    page.draw_rect(pymupdf.Rect(RIGHT - 96, 84, RIGHT, 102), color=None, fill=GREEN_BG, radius=0.2)
    _text(page, RIGHT - 48 - pymupdf.get_text_length("TERBAYAR", fontname="hebo", fontsize=9) / 2, 96, "TERBAYAR", 9, True, GREEN)
    page.draw_line((LEFT, 120), (RIGHT, 120), color=LINE, width=0.8)

    _text(page, LEFT, 150, "DITAGIHKAN KEPADA", 7.5, True, CAPTION)
    _text(page, LEFT, 170, _fit(data["customer_name"], "hebo", 13, 220), 13, True, NAVY)
    _text(page, LEFT, 187, _fit(f"Email : {data['customer_email']}", "helv", 9.5, 220), 9.5, color=MUTED)

    page.draw_rect(pymupdf.Rect(300, 136, RIGHT, 244), color=LINE, fill=PAPER, width=0.8, radius=0.06)
    rows = [("No. Invoice", data["number"], INK), ("Tanggal Invoice", stamp(data["issued_at"]), INK), ("Batas Pembayaran", stamp(data["due_at"]), INK)]
    for n, (label, value, color) in enumerate(rows):
        _text(page, 314, 162 + n * 22, label, 9, color=MUTED)
        _text(page, RIGHT - 14, 162 + n * 22, _fit(value, "hebo", 9, 130), 9, True, color, right=True)
    page.draw_line((314, 212), (RIGHT - 14, 212), color=LINE, width=0.6)
    _text(page, 314, 232, "Tanggal Terbayar", 9, color=MUTED)
    _text(page, RIGHT - 14, 232, stamp(data["paid_at"]), 9, True, GREEN, right=True)

    _text(page, LEFT, 276, "INFORMASI PEMBAYARAN", 7.5, True, CAPTION)
    page.draw_rect(pymupdf.Rect(LEFT, 286, RIGHT, 336), color=LINE, width=0.8, radius=0.1)
    _text(page, LEFT + 18, 316, _fit(data["method"], "hebo", 13, 400), 13, True, NAVY)

    _text(page, LEFT, 376, "NO", 7.5, True, CAPTION)
    _text(page, LEFT + 34, 376, "ITEM", 7.5, True, CAPTION)
    _text(page, 390, 376, "HARGA SATUAN", 7.5, True, CAPTION, right=True)
    _text(page, 455, 376, "JUMLAH", 7.5, True, CAPTION, right=True)
    _text(page, RIGHT, 376, "TOTAL", 7.5, True, CAPTION, right=True)
    page.draw_line((LEFT, 384), (RIGHT, 384), color=LINE, width=0.8)
    _text(page, LEFT, 408, str(item["no"]), 10)
    _text(page, LEFT + 34, 408, _fit(item["name"], "hebo", 10, 230), 10, True, NAVY)
    _text(page, 390, 408, money(item["unit_price"]), 10, right=True)
    _text(page, 455, 408, str(item["quantity"]), 10, right=True)
    _text(page, RIGHT, 408, money(item["total"]), 10, right=True)
    page.draw_line((LEFT, 420), (RIGHT, 420), color=LINE, width=0.8)

    _text(page, 340, 448, "Subtotal Item", 9, color=MUTED)
    _text(page, RIGHT, 448, money(data["subtotal"]), 9, right=True)
    page.draw_line((340, 460), (RIGHT, 460), color=LINE, width=0.8)
    _text(page, 340, 482, "Total Bayar", 10.5, True, INK)
    _text(page, RIGHT, 482, money(data["total"]), 12, True, RED, right=True)

    _text(page, LEFT, 790, "Invoice ini dibuat otomatis oleh NARAtive.", 8, color=CAPTION)
    out = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return out
