import io
import zipfile

import pymupdf

SENTENCES = [
    "Rana berjalan pulang melewati jalan yang sepi sambil memikirkan semua kejadian hari itu.",
    "Dede menunggu di depan rumah dengan secangkir teh hangat yang sudah mulai dingin.",
    "Hujan turun pelan ketika mereka akhirnya duduk berdua di beranda yang berderit.",
    "Tidak ada yang berani memulai pembicaraan tentang surat yang datang kemarin sore.",
    "Angin membawa aroma tanah basah dari kebun belakang yang lama tidak terurus.",
    "Lampu jalan menyala satu per satu seolah mengikuti langkah kaki yang tergesa.",
    "Ibu menyimpan semua kenangan itu di dalam kotak kayu tua di bawah ranjang.",
    "Pagi berikutnya kabut menutupi seluruh desa dan membuat suara terdengar jauh.",
]


def prose(n: int, seed: int = 0) -> str:
    return " ".join(SENTENCES[(seed + i) % len(SENTENCES)] for i in range(n))


def make_pdf(pages, *, toc=None, header=None, footer_numbers=False, sizes=None) -> bytes:
    doc = pymupdf.open()
    for number, text in enumerate(pages, start=1):
        page = doc.new_page()
        if header:
            page.insert_text((72, 40), header, fontsize=9, fontname="helv")
        y = 90
        for block in text.split("\n\n"):
            if not block:
                continue
            size = (sizes or {}).get(block.split("\n")[0], 11)
            page.insert_textbox(pymupdf.Rect(72, y, 520, y + 600), block, fontsize=size, fontname="helv")
            y += (block.count("\n") + 1 + len(block) // 85 + 1.5) * size * 1.35
        if footer_numbers:
            page.insert_text((290, 800), str(number), fontsize=10, fontname="helv")
    if toc:
        doc.set_toc(toc)
    data = doc.tobytes()
    doc.close()
    return data


def blank_pdf(pages: int = 2) -> bytes:
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


CONTAINER = (
    '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
    '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
)


def xhtml(body: str, title: str = "x") -> str:
    return f'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title></head><body>{body}</body></html>'


def make_epub(chapters, *, nav=None, ncx=None, extra_files=None, encryption=None, linear=None) -> bytes:
    """chapters: daftar (nama_berkas, isi_body). nav: {berkas: judul} (EPUB3) atau ncx: {berkas: judul} (EPUB2)."""
    manifest = []
    spine = []
    for index, (name, _) in enumerate(chapters):
        manifest.append(f'<item id="c{index}" href="{name}" media-type="application/xhtml+xml"/>')
        flag = "" if linear is None or linear.get(name, True) else ' linear="no"'
        spine.append(f'<itemref idref="c{index}"{flag}/>')
    if nav is not None:
        manifest.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
    if ncx is not None:
        manifest.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
    spine_attr = ' toc="ncx"' if ncx is not None else ""
    opf = (
        '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        f'<manifest>{"".join(manifest)}</manifest><spine{spine_attr}>{"".join(spine)}</spine></package>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", CONTAINER)
        z.writestr("OEBPS/content.opf", opf)
        for name, body in chapters:
            z.writestr(f"OEBPS/{name}", body if isinstance(body, bytes) else xhtml(body))
        if nav is not None:
            links = "".join(f'<li><a href="{name}">{title}</a></li>' for name, title in nav.items())
            z.writestr("OEBPS/nav.xhtml", xhtml(f'<nav epub:type="toc"><ol>{links}</ol></nav>'))
        if ncx is not None:
            points = "".join(
                f'<navPoint id="n{i}"><navLabel><text>{title}</text></navLabel><content src="{name}"/></navPoint>'
                for i, (name, title) in enumerate(ncx.items())
            )
            z.writestr("OEBPS/toc.ncx", f'<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap>{points}</navMap></ncx>')
        if encryption:
            z.writestr("META-INF/encryption.xml", encryption)
        for name, content in (extra_files or {}).items():
            z.writestr(name, content)
    return buffer.getvalue()


def drm_encryption(algorithm: str) -> str:
    return (
        '<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container" xmlns:enc="http://www.w3.org/2001/04/xmlenc#">'
        f'<enc:EncryptedData><enc:EncryptionMethod Algorithm="{algorithm}"/></enc:EncryptedData></encryption>'
    )
