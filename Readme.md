# NARAtive

**Sistem Penilaian Konten dan Eksplorasi Naratif E-book Berbasis Website dengan Pendekatan AI**
*(Narrative Analysis & Rating Assistant)*


NARAtive adalah situs web yang membaca e-book (PDF atau EPUB), menganalisis isinya paragraf demi paragraf dengan model deep learning, lalu menampilkan **rating konten**, **rentang usia pembaca**, **persentase konten dewasa**, dan **bobot cerita**. Hasilnya bisa dibaca langsung lewat mode baca dengan **Safe Mode** yang menyamarkan paragraf bermuatan seksual, dilengkapi rangkuman cerita dan unduhan hasil analisis dalam bentuk PDF.

> Seluruh hasil bersifat prediksi model dan hanya panduan awal, bukan pengganti penilaian editorial manusia.

---

## Daftar Isi

1. [Latar belakang](#latar-belakang)
2. [Fitur dan status pengerjaan](#fitur-dan-status-pengerjaan)
3. [Cara kerja analisis](#cara-kerja-analisis)
4. [Arsitektur dan teknologi](#arsitektur-dan-teknologi)
5. [Struktur repositori](#struktur-repositori)
6. [Menjalankan secara lokal](#menjalankan-secara-lokal)
7. [Endpoint API](#endpoint-api)
8. [Perintah yang sering dipakai](#perintah-yang-sering-dipakai)
9. [Rencana model bisnis](#rencana-model-bisnis)
10. [Batasan yang diketahui](#batasan-yang-diketahui)
11. [Dokumen](#dokumen)

---

## Latar belakang

Platform cerita daring seperti Wattpad dan AO3 membuat pembaca, terutama pembaca muda dan orang tua, sulit menilai kelayakan usia sebuah cerita sebelum membacanya. Penilaian manual oleh editor lambat dan tidak konsisten antar individu. Pembaca juga sering lupa detail cerita seperti tokoh dan alurnya pada novel yang panjang.

NARAtive menjawab dua masalah itu sekaligus: **menilai konten secara otomatis** dan **membantu memahami cerita** lewat rangkuman, biodata tokoh, dan relasi antar tokoh.

## Fitur dan status pengerjaan

Rancangan lengkap memuat **19 use case** (UC-01 sampai UC-16 dari SRS, ditambah UC-17 sampai UC-19 dari revisi terbaru). Rilis prototype UTS ini mengimplementasikan **8 dari 19 (±42%)**.

| UC | Fitur | Aktor | FR | Status |
|----|-------|-------|----|--------|
| UC-01 | Mengunggah dokumen e-book (PDF dan EPUB) | Standard | FR-04 | Selesai |
| UC-02 | Membuat koleksi dari beberapa dokumen | Standard | FR-05 | Selesai (di UI disebut "seri"; tiap buku tetap dianalisis sendiri) |
| UC-03 | Melihat hasil analisis rating konten | Standard | FR-06 | Selesai (rincian per dimensi dan alasan rating untuk Middle Tier belum) |
| UC-04 | Membaca e-book hasil analisis | Standard | FR-07 | Selesai |
| UC-05 | Menerapkan Safe Mode | Standard | FR-08 | Selesai |
| UC-06 | Menghapus e-book dari koleksi | Standard | FR-09 | Selesai |
| UC-07 | Membayar fitur premium (Midtrans) | Standard | FR-10, FR-23 | Selesai (mode simulasi; Midtrans sandbox bila kunci diisi) |
| UC-08 | Melihat riwayat pembayaran | Standard | FR-11 | Selesai |
| UC-09 | Melihat rangkuman cerita (per bab dan keseluruhan) | Middle | FR-12 | Selesai |
| UC-10 | Melihat biodata tokoh | Middle | FR-13 | Belum |
| UC-11 | Melihat progres relasi antar tokoh | Middle | FR-14 | Belum |
| UC-12 | Mengatur profil sensitivitas personal | High | FR-15 | Selesai |
| UC-13 | Mengunduh hasil analisis (PDF) | High | FR-16 | Selesai |
| UC-14 | Melihat laporan pendapatan | Admin | FR-17 | Belum |
| UC-15 | Melihat daftar akun user | Admin | FR-18 | Belum |
| UC-16 | Menangguhkan akun user | Admin | FR-19 | Belum |
| UC-17 | Mengganti cover e-book | High | – | Belum (tombol sudah ada di UI) |
| UC-18 | Mengganti foto profil tokoh | High | – | Belum |
| UC-19 | Mengubah judul e-book | Standard | – | Selesai |


### Model

- Backbone **xlm-roberta-base** dengan **LoRA**, empat kepala klasifikasi: bahasa kasar, seksual, kekerasan, dan emosi.
- Konteks **sliding window**: paragraf N dinilai bersama N-1 dan N+1, skor tetap dicatat untuk paragraf N.
- Mendukung Bahasa Indonesia dan Inggris.
- Deteksi seksual bersifat **hibrida**: nilai akhir = maksimum antara skor model dan skor kamus kata eksplisit, karena model sendiri meleset pada prosa novel romansa.
- Ambang deteksi per paragraf: bahasa kasar 0,5, seksual 0,5, kekerasan 0,8.

### Rating konten

| Rating | Rentang usia | Syarat (persentase paragraf terdeteksi dan jumlah minimal paragraf) |
|--------|--------------|----------------------------------------------------------------------|
| Explicit | 21+ | seksual ≥ 3% dan ≥ 3 paragraf |
| Mature | 17+ | kekerasan ≥ 15% dan ≥ 3 paragraf, atau seksual ≥ 1% dan ≥ 2 paragraf |
| Teen | 13+ | kekerasan ≥ 3% dan ≥ 2 paragraf, atau seksual ≥ 0,5% dan ≥ 2 paragraf |
| General | Semua umur | di luar syarat di atas |

**Persentase konten dewasa** adalah proporsi paragraf yang terdeteksi seksual atau kekerasan.

### Bobot cerita

Skor 0 sampai 100 yang menjawab: *seberapa berat dan rumit konflik serta tema cerita sampai membuat pembaca pusing mengikutinya*. Cerita yang emosional tetapi konfliknya sederhana akan mendapat skor rendah.


### Safe Mode

Safe Mode standar hanya menyamarkan paragraf **seksual**. Paragraf disamarkan dan bisa dibuka satu per satu dengan mengetuknya. Penyaringan bahasa kasar dan kekerasan, serta pengaturan ambang sendiri, direncanakan lewat Profil Sensitivitas.

### Rangkuman 

Dibuat Gemini per bab lalu digabung menjadi rangkuman keseluruhan, disimpan di basis data agar tidak diproses ulang. 

## Arsitektur dan teknologi

| Lapisan | Teknologi |
|---------|-----------|
| Frontend | Vue 3, Vite, Vue Router, Pinia, Tailwind CSS v4, Axios, Iconify |
| Backend | FastAPI, SQLAlchemy 2, Alembic, PyMuPDF, wordfreq |
| Basis data | MySQL 8 (SQLite untuk uji cepat) |
| Model | XLM-RoBERTa base + LoRA (PyTorch, Transformers, PEFT), dilatih di Google Colab |
| Layanan eksternal | Gemini API (rangkuman dan bobot cerita); Midtrans (pembayaran, rencana) |
| Komunikasi | REST API, JSON |

Analisis berjalan di **antrean satu pekerja** di sisi server sehingga kegagalan satu dokumen tidak menjatuhkan sistem (NRF-08), dan halaman hasil memperbarui statusnya otomatis selama dokumen belum selesai.

## Struktur repositori

```
NARAtive_IPPL2026/
├── README.md
├── docs/                     SRS dan SDD
├── model/                    model_best.pt dan tokenizer_xlmr/ (tidak di-commit)
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/versions/     migrasi 0001–0008
│   └── app/
│       ├── main.py
│       ├── api/              routers/documents.py, schemas.py
│       ├── core/             config.py, security.py
│       ├── db/               database.py, models.py, db_setup.py
│       ├── extraction/       pdf_utils.py, epub_utils.py
│       ├── ml/               model.py, analyzer.py, lexicon.py
│       ├── services/         jobs.py, summarizer.py, heaviness.py, export.py
│       └── tools/            skrip bantu (rescore, rate_heaviness, laporan skor)
└── frontend/
    └── src/
        ├── pages/            HomePage, KoleksiPage, HasilAnalisisPage,
        │                     ReadingModePage, SummaryPage, BerlanggananPage,
        │                     NotFoundPage, Sidebar
        ├── components/       Header, Footer, Navbar, Logo, RatingBadge,
        │                     StatusChip, TierChip, SoonButton, MeterBar
        ├── lib/              api.js, content.js, icons.js
        ├── router/
        └── assets/
```

## Menjalankan dengan Docker (paling mudah)

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) dan pastikan sedang berjalan, lalu:

```bash
git clone https://github.com/Drawing-pen/NARAtive_IPPL2026.git
cd NARAtive_IPPL2026
docker compose up --build
```

Buka <http://localhost:5173>. Database MySQL, migrasi, dan unduhan model (`model_best.pt`, sekitar 1,1 GB, dari [Hugging Face](https://huggingface.co/Roena33/narative-model)) berjalan otomatis pada start pertama. Build pertama memakan beberapa menit dan beberapa GB.

Opsional: bila diberi file `.env`, taruh di folder utama repo (sejajar dengan `docker-compose.yml`). Isinya antara lain `GEMINI_API_KEY` untuk rangkuman dan bobot cerita; tanpa itu aplikasi tetap jalan, hanya fitur Gemini yang mati. Bila `model/model_best.pt` sudah ada, unduhan dilewati.

## Menjalankan secara lokal

### 1. Model

Letakkan hasil pelatihan di folder `model/` pada akar repositori:

```
model/model_best.pt
model/tokenizer_xlmr/
```

`model_best.pt` besar sehingga tidak ikut di-commit (`tokenizer_xlmr/` ikut). Tanpa berkas ini, analisis tidak bisa berjalan.

### 2. Backend (Windows, cmd)

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install transformers peft sentencepiece scikit-learn
```

Buat `backend/.env` (jangan di-commit):

```
DATABASE_URL=mysql+pymysql://USER:PASSWORD@localhost:3306/narative
SECRET_KEY=isi-string-acak-minimal-32-karakter
CORS_ORIGINS=http://localhost:5173
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.8-flash
```

`GEMINI_API_KEY` dibuat di <https://aistudio.google.com/apikey>. Kosongkan jika belum punya; rating tetap jalan, hanya rangkuman dan penilaian bobot dari Gemini yang tidak tersedia.

Siapkan basis data lalu jalankan server:

```bat
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

API tersedia di `http://localhost:8000`, dokumentasi interaktif di `http://localhost:8000/docs`.

### 3. Frontend

```bat
cd frontend
npm install
npm run dev
```

Buka `http://localhost:5173`.

## Endpoint API

Semua berada di bawah `/documents`.

| Metode | Path | Fungsi | UC |
|--------|------|--------|----|
| POST | `/documents` | Unggah PDF atau EPUB dan mulai analisis | UC-01 |
| GET | `/documents` | Daftar e-book di halaman koleksi | UC-06 |
| GET | `/documents/{id}` | Hasil analisis dan status | UC-03 |
| GET | `/documents/{id}/chapters` | Daftar bab | UC-04 |
| GET | `/documents/{id}/paragraphs` | Paragraf beserta skor, untuk mode baca dan Safe Mode | UC-04, UC-05 |
| DELETE | `/documents/{id}` | Hapus e-book | UC-06 |
| GET | `/documents/{id}/summary` | Ambil rangkuman tersimpan | UC-09 |
| POST | `/documents/{id}/summary` | Mulai pembuatan rangkuman | UC-09 |
| GET | `/documents/{id}/export` | Unduh hasil analisis (PDF) | UC-13 |
| PATCH | `/documents/{id}` | Ubah judul | UC-19 |
| GET | `/collections` | Daftar seri beserta urutan bukunya | UC-02 |
| POST | `/collections` | Buat seri dari beberapa e-book (berurutan) | UC-02 |
| PUT | `/collections/{id}` | Ubah nama, urutan, atau isi seri | UC-02 |
| DELETE | `/collections/{id}` | Bubarkan seri (e-book tidak terhapus) | UC-02 |
| GET | `/billing/overview` | Tingkatan, pemakaian kuota, harga, bank | UC-07 |
| POST | `/billing/checkout` | Buat Virtual Account (upgrade atau pay-per-check) | UC-07 |
| GET | `/billing/transactions` | Riwayat pembayaran | UC-08 |
| POST | `/billing/transactions/{order_id}/cancel` | Batalkan pembayaran yang menunggu | UC-07 |
| POST | `/billing/transactions/{order_id}/simulate-pay` | Simulasi bayar (hanya mode simulasi) | UC-07 |
| POST | `/billing/midtrans/notification` | Webhook status dari Midtrans | UC-07 |
| GET | `/sensitivity` | Ambang Safe Mode yang berlaku (standar atau personal) | UC-05, UC-12 |
| PUT | `/sensitivity` | Simpan profil sensitivitas personal (High Tier) | UC-12 |
| DELETE | `/sensitivity` | Kembalikan ke ambang standar (High Tier) | UC-12 |

## Perintah yang sering dipakai

Dijalankan dari folder `backend` dengan venv aktif.

| Perintah | Kegunaan |
|----------|----------|
| `python -m alembic upgrade head` | Terapkan migrasi basis data |
| `python -m uvicorn app.main:app --reload` | Jalankan server backend |
| `python -m app.tools.atur_tier email free\|middle\|high` | Ubah tingkatan akun secara manual (pembayaran belum tersedia) |
| `python -m app.tools.rescore` | Hitung ulang rating dari skor tersimpan tanpa menjalankan model |
| `python -m app.tools.rate_heaviness` | Nilai bobot cerita dokumen lama lewat Gemini lalu hitung ulang |
| `python -m app.tools.emotion_report` | Sebaran keyakinan emosi untuk menyetel ambang |

## Rencana model bisnis

Rancangan freemium tiga tingkat (belum diterapkan pada prototype):

| | Free | Middle | High |
|---|------|--------|------|
| Halaman per unggahan | 50 | 300 | tanpa batas |
| Kuota analisis per bulan | 3 | 15 | tanpa batas |
| Koleksi aktif | 3 | 50 | tanpa batas |
| Rating dan Safe Mode standar | ✓ | ✓ | ✓ |
| Rangkuman, biodata tokoh, relasi tokoh | – | ✓ | ✓ |
| Profil sensitivitas personal, unduh PDF beranotasi | – | – | ✓ |

Pembayaran direncanakan melalui Midtrans (Virtual Account) beserta invoice otomatis ke email. Batas dihitung per berkas yang diunggah.

## Dokumen

- Software Requirements Specification: `docs/SRS NARAtive_11241076_IPPL B.pdf`
- Software Design Document: `docs/SDD NARAtive_11241076_IPPL B.pdf`