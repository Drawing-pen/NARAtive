# NARAtive: konteks untuk agen pengembang

Dokumen ini dibaca pertama kali oleh agen yang bekerja di repositori ini. Isinya: apa yang dibangun, aturan yang berlaku, dan bentuk keluaran yang diharapkan. Jika dokumen ini bertentangan dengan permintaan terbaru Rana, ikuti Rana dan sebut pertentangannya. Data yang sering berubah (status fitur, daftar endpoint, keputusan) sengaja TIDAK diduplikasi di sini; bacalah `docs/SPEC.md`.

## 1. Proyek

NARAtive adalah situs web yang membaca e-book (PDF atau EPUB), menganalisis isinya paragraf demi paragraf dengan model deep learning, lalu menampilkan rating konten, rentang usia, persentase konten dewasa, dan bobot cerita. Pembaca bisa membaca lewat mode baca dengan Safe Mode, melihat rangkuman, deskripsi tokoh, dan relasi antar tokoh, serta mengunduh hasil analisis dalam PDF. Ada tier Standard (free), Middle, dan High dengan batas dan fitur berbeda, pembayaran Midtrans (atau simulasi), dan email bermerek.

- Mata kuliah: Implementasi dan Pengujian Perangkat Lunak (IPPL), Informatika, Institut Teknologi Kalimantan.
- Pemilik: Rana Afifah Dzikro (11241076), dikerjakan sendiri. Bahasa percakapan: Indonesia, kata ganti "aku" dan "kamu".
- Hasil adalah prediksi model, bukan pengganti penilaian manusia. Jangan menulis klaim yang melebihi itu di UI maupun dokumen.
- SRS dan SDD ada di `docs/`. Rana memperbarui SRS, SDD, dan diagramnya sendiri; jangan mengubahnya.

**`docs/SPEC.md` adalah sumber kebutuhan resmi dan satu-satunya tempat keputusan, aturan bisnis, status use case, dan changelog (bagian 14).** Jika SPEC.md berbeda dengan berkas ini atau SRS/SDD, SPEC.md yang menang. Jika berbeda dengan kode, kode adalah kenyataan: laporkan selisihnya dan perbarui SPEC.md atas persetujuan Rana (Rana sudah mengizinkan agen mengedit SPEC.md untuk keperluan ini). Item "Undecided" tidak boleh dibangun tanpa persetujuan.

## 2. Aturan kerja

1. **Siklus per irisan fitur:** (a) aturan diputuskan Rana dan ditulis ke SPEC.md, (b) tes yang gagal lebih dulu, (c) implementasi minimal, (d) verifikasi dan laporan jujur tentang apa yang diuji dan belum, (e) sinkronkan SPEC.md dan changelognya. Kode yang ada diperbaiki per irisan, bukan ditulis ulang.
2. **Jangan membangun yang tidak diminta.** Usulan boleh disampaikan, tunggu persetujuan Rana.
3. **Rancang untuk semua jenis buku**, jangan disetel ke satu atau dua buku contoh: bahasa, kata ganti orang pertama, PDF teks, scan, dan berkolom apa pun. Perbaikan parser dan LLM harus umum dan diuji dengan data buatan kode yang beragam.
4. **Batas tier tidak diubah** (halaman per unggahan, kuota bulanan, e-book aktif) kecuali Rana memutuskannya; semua tier menerima semua jenis PDF.
5. **Jangan menulis komentar di kode** (Python, Vue, JS, SQL, migrasi). Kode lama kadang masih berkomentar; jangan menambah yang baru dan jangan menghapus komentar yang tidak sedang kamu ubah.
6. **Model asli saja.** Hasil analisis berasal dari model terlatih; tidak boleh ada data tiruan yang dipresentasikan sebagai hasil. Pengecualian yang disetujui: deteksi seksual hibrida (maksimum skor model dan skor kamus), dan LLM (9router, Gemini cadangan) untuk bobot cerita, rangkuman, serta deteksi tokoh dan relasi.
7. **Jangan pernah menampilkan isi `backend/.env`**, terutama kata sandi MySQL dan kunci API. Jangan memasukkannya ke log, dokumen, atau jawaban. Jangan commit atau push kecuali Rana meminta.
8. Lingkungan Rana adalah **Windows (cmd)**. Perintah pip selalu `python -m pip ...`. Beri perintah untuk Rana dalam format cmd, bukan bash. Tes backend dijalankan dengan `.venv\Scripts\python.exe -B -m pytest` di folder `backend` (python sistem tidak punya paketnya).
9. Beberapa file memakai akhir baris **CRLF**. Pertahankan gaya akhir baris file yang kamu ubah.
10. Hormati batas fungsi: jangan menyentuh `model/` (berkas besar, tidak di-commit) dan jangan melatih ulang model kecuali diminta.
11. Jujur soal hasil: kalau sesuatu belum diuji dengan data atau layanan asli, katakan. Jangan menyatakan "selesai" tanpa pengujian.
12. Tes tidak boleh menyentuh layanan nyata: `conftest.py` mengosongkan `ROUTER_*`; pakai `tests/gemini_fake.py`, `tests/router_fake.py`, atau monkeypatch `_generate`.
13. Berkas yang berubah sendiri di disk (misalnya ditimpa IDE) jangan dipulihkan tanpa menanyakan Rana, kecuali jelas merusak fungsi dan versi sebelumnya sudah diketahui.

## 3. Arsitektur dan struktur

| Lapisan | Teknologi |
|---|---|
| Frontend | Vue 3 (script setup), Vite, Vue Router, Tailwind CSS v4, Axios, Iconify, markdown-it, Vitest |
| Backend | FastAPI, SQLAlchemy 2, Alembic, PyMuPDF dan pymupdf4llm, PyJWT, bcrypt, wordfreq |
| Basis data | MySQL 8 (SQLite untuk tes) |
| Model | xlm-roberta-base + LoRA, 4 kepala (bahasa kasar, seksual, kekerasan, emosi) di `model/` |
| LLM | 9router (utama, kompatibel OpenAI) dengan Gemini sebagai cadangan, satu pintu `_generate` di `services/summarizer.py` |
| Lain | Midtrans (atau simulasi), SMTP untuk email, Docker Compose |

```
backend/
  app/main.py                 pintu masuk, CORS, router, pemulihan status yang menggantung
  app/api/routers/            auth, documents, billing, images, collections, sensitivity
  app/api/schemas.py          skema Pydantic
  app/core/                   config.py (pengaturan dari .env), security.py (JWT, bcrypt), plans.py (batas tier)
  app/db/                     database.py, models.py, db_setup.py
  app/extraction/             parser PDF dan EPUB: pdf_utils, epub_utils (lama), pdf_markdown,
                              epub_markdown, markdown_utils, reader (pemilih parser)
  app/ml/                     model.py, analyzer.py, lexicon.py
  app/services/               jobs (antrean analisis), summarizer (satu pintu LLM, rangkuman), heaviness,
                              characters dan character_ai (tokoh dan relasi), accounts, verification,
                              password_reset, billing, payments, mailer, email_templates, images,
                              export, sensitivity, collections, summary_local
  app/tools/                  skrip bantu (compare_parsers, tokoh, rescore, rate_heaviness, atur_tier, ...)
  alembic/versions/           migrasi 0001 sampai 0020
frontend/src/
  pages/                      Home, Koleksi, HasilAnalisis, ReadingMode, Summary, Tokoh, Relasi, Sensitivitas,
                              Profil, Berlangganan, Auth (masuk, daftar, lupa kata sandi), NotFound, Sidebar
  components/                 Header, Footer, Navbar, Logo, BookCard, SeriesCard, dialog dan viewer seri,
                              CheckoutDialog, badge dan chip, UserAvatar, ReadingBlock, dll.
  lib/                        api.js (Axios + token), auth.js, characters.js, content.js, markdown.js, icons.js
  router/index.js
docs/                         SPEC.md (sumber kebutuhan), SRS dan SDD (milik Rana), CLAUDE.md (berkas ini)
```

Rute frontend: `/` beranda, `/koleksi`, `/profil`, `/berlangganan`, `/masuk`, `/daftar`, `/lupa-sandi`; ruang kerja satu buku di `/buku/:id` dengan anak `baca`, `rangkuman`, `tokoh`, `relasi`, `sensitivitas`. Halaman buku, koleksi, dan profil butuh login (`meta.requiresAuth`); halaman masuk, daftar, dan lupa kata sandi hanya untuk tamu (`meta.guest`).

## 4. Cara kerja analisis (ringkas; rinciannya di SPEC.md)

**Alur:** unggah PDF atau EPUB, ekstrak teks menjadi bab dan paragraf (blok sampai 900 karakter; parser dipilih `DOCUMENT_PARSER`, bawaan `auto`: EPUB Markdown, PDF parser lama), antre, model menilai tiap paragraf dengan konteks jendela N-1, N, N+1, agregasi dokumen, simpan. File asli tidak disimpan, hanya teksnya.

**Ambang deteksi per paragraf:** bahasa kasar 0,5; seksual 0,5; kekerasan 0,8. Deteksi seksual hibrida: nilai akhir = maksimum skor model dan skor kamus kata eksplisit. Rating dan ambang tidak boleh diubah tanpa diminta Rana.

| Rating | Usia | Syarat |
|---|---|---|
| Explicit | 21+ | seksual ≥ 3% dan ≥ 3 paragraf |
| Mature | 17+ | kekerasan ≥ 15% dan ≥ 3 paragraf, atau seksual ≥ 1% dan ≥ 2 paragraf |
| Teen | 13+ | kekerasan ≥ 3% dan ≥ 2 paragraf, atau seksual ≥ 0,5% dan ≥ 2 paragraf |
| General | Semua umur | di luar syarat di atas |

Bahasa kasar tidak dihitung dalam rating maupun persentase konten dewasa. Persentase konten dewasa adalah proporsi paragraf yang terdeteksi seksual atau kekerasan. Bobot cerita (0 sampai 100) memadukan penilaian LLM (berbobot 0,7) dan sinyal emosi negatif dari model (0,3); tanpa LLM hanya sinyal model. Safe Mode standar menyamarkan paragraf seksual.

**Rangkuman:** per bab lalu digabung, disimpan agar tidak diproses ulang; paragraf seksual tidak dikirim (diganti penanda); kelompok yang ditahan filter keamanan diulang dengan teks lebih ketat.

**Tokoh dan relasi (R13):** 100% LLM tanpa NER. Teks dipotong per bab sampai 40.000 karakter, satu panggilan LLM per potongan (maksimal `CHARACTER_PARALLEL` paralel), satu panggilan gabung; jumlah sebutan, kata ganti narator orang pertama di luar dialog, dan bobot relasi dihitung kode; relasi hanya dipakai bila kutipan buktinya ada di teks dan memuat kedua tokoh; potongan yang ditolak filter keamanan dibelah sampai paragraf pemicunya terisolasi. Kartu tokoh hanya berisi nama, "Juga disebut", dan deskripsi (tanpa label peran).

## 5. Status fitur dan API

Status use case ada di `docs/SPEC.md` bagian 3 dan daftar endpoint di bagian 9; dokumentasi interaktif API ada di `/docs` saat server berjalan. Jangan menduplikasinya di sini.

## 6. Data

Tabel utama: `users`, `documents`, `chapters`, `paragraphs` (teks polos, `markdown`, `kind`), `characters`, `character_relations`, `collections`, `transactions`, `usage_quota`, `sensitivity_profiles`, `email_verifications`, `password_resets`. Relasi tabel memakai `ondelete=CASCADE`. Perubahan skema selalu lewat migrasi Alembic baru; jangan mengubah migrasi lama. Terapkan dengan `python -m alembic upgrade head` (atau `python -m app.db.db_setup`). Beberapa kolom `characters` (`role`, `gender`, `age`, `occupation`, `personality`, `background`) tidak dipakai lagi sejak R12 dan dibiarkan kosong.

## 7. LLM dan kendala yang diketahui

- Semua panggilan LLM lewat `_generate` di `services/summarizer.py`: 9router lebih dulu (`ROUTER_BASE_URL`, `ROUTER_API_KEY`, `ROUTER_MODEL`), Gemini sebagai cadangan. 9router wajib `"stream": false`, token reasoning ikut menghitung `max_tokens`, dan setelah satu kegagalan 9router ditahan 60 detik secara global.
- Gemini gratis sangat terbatas (per menit dan per hari per model); `GEMINI_MIN_INTERVAL`, model cadangan, dan model khusus tokoh diatur lewat `.env`. Jangan menyebut harga atau kuota Gemini di dokumen tanpa verifikasi.
- Isi e-book terkirim ke pihak ketiga (9router dan Gemini); paragraf seksual tidak dikirim. LLM lokal tidak layak di laptop Rana (RAM 8 GB).
- Hal yang belum terbukti harus dibedakan dari yang diuji saat melaporkan (misalnya kualitas deteksi tokoh pada buku orang ketiga berbahasa Indonesia).

## 8. Konvensi kode

**Backend:** FastAPI dengan injeksi `Depends`, pesan error dalam bahasa Indonesia, pengaturan hanya lewat `app/core/config.py` (nilai dari `.env`), tugas panjang berjalan di thread latar dengan status di kolom dokumen, status yang menggantung direset saat server menyala (`reset_stale`). Tidak ada rahasia di kode atau repositori.

**Frontend:** Vue 3 `<script setup>`, teks UI berbahasa Indonesia, Tailwind v4 dengan token warna dari `style.css` (navy, lavender, amber, paper, sand, danger), ikon lucide lewat Iconify, akses API hanya lewat `src/lib/api.js` (menyisipkan token, mengalihkan ke `/masuk` pada 401). Token sesi di `localStorage` kunci `narative.auth` dengan try/catch. Halaman harus bisa dipakai di lebar 390 px tanpa scroll horizontal. Setiap keadaan (memuat, kosong, gagal, tidak ditemukan) punya tampilan sendiri. Pemberitahuan untuk hasil sebagian tidak ditampilkan di UI (hanya di log backend); yang ditampilkan hanya galat krusial.

## 9. Perintah umum (Windows, folder `backend`, venv aktif)

| Perintah | Fungsi |
|---|---|
| `python -m alembic upgrade head` | Terapkan migrasi |
| `python -m uvicorn app.main:app --reload` | Jalankan server |
| `python -m pytest` | Tes backend (butuh sekitar 6 menit) |
| `python -m app.tools.compare_parsers berkas.pdf berkas.epub` | Bandingkan parser lama dan Markdown pada naskah |
| `python -m app.tools.tokoh [id ...]` | Deteksi tokoh dan cetak laporan (butuh 9router atau Gemini) |
| `python -m app.tools.rescore` | Hitung ulang rating dari skor tersimpan |
| `python -m app.tools.rate_heaviness [id ...]` | Nilai bobot cerita lewat LLM lalu hitung ulang |
| `python -m app.tools.atur_tier` | Atur tier akun untuk uji |

Frontend (folder `frontend`): `npm install`, `npm run dev`, `npm run build`, `npm run lint`, `npx vitest run`. Dengan Docker: `docker compose up` (lihat `docker-compose.yml` dan `.env.example`).

## 10. Cara melaporkan hasil

1. Satu kalimat tentang apa yang berubah dan apa dampaknya untuk pengguna.
2. Daftar file yang berubah (bila Rana meminta penyerahan manual: satu per satu, berlabel **NEW** atau **LAMA (timpa)** dengan path dari akar repositori).
3. Langkah yang harus dijalankan Rana (migrasi, restart, instalasi pustaka) dalam format cmd.
4. Apa yang sudah diuji dan bagaimana, serta apa yang belum bisa diuji (layanan nyata, buku nyata, tampilan di browser).
5. Satu langkah berikutnya bila memang ada.

Jangan mengirim ringkasan langkah kerja yang panjang, dan jangan menyatakan fitur beres tanpa pengujian.
