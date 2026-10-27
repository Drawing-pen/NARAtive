# NARAtive: konteks untuk agen pengembang

Dokumen ini dibaca pertama kali oleh agen yang bekerja di repositori ini. Isinya: apa yang dibangun, aturan yang berlaku, bentuk keluaran yang diharapkan, dan apa yang akan dibangun berikutnya. Jika dokumen ini bertentangan dengan permintaan terbaru Rana, ikuti Rana dan sebut pertentangannya.

## 1. Proyek

NARAtive adalah situs web yang membaca e-book (PDF atau EPUB), menganalisis isinya paragraf demi paragraf dengan model deep learning, lalu menampilkan rating konten, rentang usia, persentase konten dewasa, dan bobot cerita. Pembaca bisa membaca lewat mode baca dengan Safe Mode, melihat rangkuman, biodata tokoh, dan relasi antar tokoh, serta mengunduh hasil analisis dalam PDF.

- Mata kuliah: Implementasi dan Pengujian Perangkat Lunak (IPPL), Informatika, Institut Teknologi Kalimantan.
- Pemilik: Rana Afifah Dzikro (11241076), dikerjakan sendiri. Bahasa percakapan: Indonesia, kata ganti "aku" dan "kamu".
- Hasil adalah prediksi model, bukan pengganti penilaian manusia. Jangan menulis klaim yang melebihi itu di UI maupun dokumen.
- SRS dan SDD ada di `docs/`. Rana memperbarui SRS, SDD, dan diagramnya sendiri. Kalau kode menyimpang dari dokumen, laporkan penyimpangannya, jangan mengubah dokumen.
- Alur bisnis tiap use case (UC-01 sampai UC-19), daftar FR dan NRF beserta statusnya, pemetaan tabel SDD ke kode, dan selisih SRS dengan kode ada di file berikut. Baca sebelum mengerjakan fitur apa pun:

@docs/SPEC.md
@docs/ALUR_BISNIS.md

`docs/SPEC.md` adalah sumber kebutuhan resmi. Jika SPEC.md berbeda dengan berkas ini, ALUR_BISNIS.md, atau SRS/SDD, SPEC.md yang menang. Jika berbeda dengan kode, laporkan selisihnya, jangan pilih sendiri. Item di bagian "Undecided" SPEC.md tidak boleh dibangun tanpa persetujuan.

## 2. Aturan kerja

1. Ikuti SRS, SDD, FR, dan UC. Kerjakan selangkah demi selangkah.
2. **Jangan membangun yang tidak diminta.** Usulan boleh disampaikan, tetapi tunggu persetujuan Rana sebelum mengerjakannya.
3. **Jangan menulis komentar di kode** (Python, Vue, JS, SQL, migrasi). Kode yang sudah ada kadang masih berkomentar; jangan menambah yang baru, dan jangan menghapus komentar yang tidak sedang kamu ubah.
4. **Model asli saja.** Hasil analisis harus berasal dari model terlatih. Tidak boleh ada data tiruan yang dipresentasikan sebagai hasil. Pengecualian yang disetujui: deteksi seksual hibrida (maksimum skor model dan skor kamus), Gemini untuk rangkuman (UC-09) dan sebagian penilaian bobot cerita.
5. **Tidak ada penerapan tier dan tidak ada batas unggah** pada tahap prototype. Label tier di UI hanya penanda rencana. Jangan menambah penguncian fitur kecuali Rana memutuskannya.
6. **Jangan pernah menampilkan isi `backend/.env`**, terutama kata sandi MySQL dan kunci API. Jangan memasukkannya ke log, dokumen, atau jawaban.
7. Lingkungan Rana adalah **Windows (cmd)**. Perintah pip selalu `python -m pip ...`. Beri perintah dalam format cmd, bukan bash.
8. Bantuan penyerahan: kirim **hanya file yang berubah**, **satu per satu**, jangan dibungkus zip. Beri label **NEW** atau **LAMA (timpa)** dan path relatif dari akar repositori (contoh: `backend/app/api/schemas.py`).
9. Beberapa file memakai akhir baris **CRLF** (misalnya `frontend/src/lib/content.js` dan `frontend/src/pages/HasilAnalisisPage.vue`). Pertahankan gaya akhir baris file yang kamu ubah.
10. Hormati batas fungsi: jangan menyentuh `model/` (berkas besar, tidak di-commit) dan jangan melatih ulang model kecuali diminta.
11. Jujur soal hasil: kalau sesuatu belum diuji dengan data atau model asli, katakan. Jangan menyatakan "selesai" tanpa pengujian.

## 3. Arsitektur dan struktur

| Lapisan | Teknologi |
|---|---|
| Frontend | Vue 3 (script setup), Vite, Vue Router, Pinia, Tailwind CSS v4, Axios, Iconify |
| Backend | FastAPI, SQLAlchemy 2, Alembic, PyMuPDF, PyJWT, bcrypt, wordfreq |
| Basis data | MySQL 8 (SQLite hanya untuk uji cepat) |
| Model | xlm-roberta-base + LoRA, 4 kepala (bahasa kasar, seksual, kekerasan, emosi) |
| Layanan eksternal | Gemini API (rangkuman, bobot cerita); model NER Hugging Face (tokoh); Midtrans (rencana) |

```
backend/
  app/main.py                 pintu masuk, CORS, router, pemulihan status yang menggantung
  app/api/routers/            auth.py, documents.py
  app/api/schemas.py          skema Pydantic
  app/core/                   config.py (pengaturan dari .env), security.py (JWT, bcrypt)
  app/db/                     database.py, models.py, db_setup.py
  app/extraction/             pdf_utils.py, epub_utils.py
  app/ml/                     model.py, analyzer.py, lexicon.py
  app/services/               jobs.py (antrean analisis), summarizer.py, heaviness.py,
                              characters.py, export.py
  app/tools/                  skrip bantu: rescore, rate_heaviness, tokoh, klaim_dokumen, laporan
  alembic/versions/           migrasi 0001 sampai 0010
frontend/src/
  pages/                      Home, Koleksi, HasilAnalisis, ReadingMode, Summary, Tokoh, Relasi,
                              Auth, Berlangganan, NotFound, Sidebar
  components/                 Header, Footer, Navbar, Logo, RatingBadge, StatusChip, TierChip,
                              SoonButton, MeterBar
  lib/                        api.js (Axios + token), auth.js, characters.js, content.js, icons.js
  router/index.js
```

Peta rute frontend: `/` beranda, `/koleksi`, `/berlangganan`, `/masuk`, `/daftar`; ruang kerja satu buku di `/buku/:id` dengan anak `baca`, `rangkuman`, `tokoh`, `relasi`. Halaman buku dan koleksi butuh login (`meta.requiresAuth`).

## 4. Aturan bisnis dan cara kerja analisis

**Alur:** unggah PDF atau EPUB, ekstrak teks menjadi bab dan paragraf (blok sampai 900 karakter), antre, model menilai tiap paragraf dengan konteks jendela N-1, N, N+1, agregasi dokumen, simpan. File asli tidak disimpan, hanya teksnya.

**Ambang deteksi per paragraf:** bahasa kasar 0,5; seksual 0,5; kekerasan 0,8. Deteksi seksual hibrida: nilai akhir = maksimum antara skor model dan skor kamus kata eksplisit.

**Rating.** Bahasa kasar tidak dihitung dalam rating maupun persentase konten dewasa.

| Rating | Usia | Syarat |
|---|---|---|
| Explicit | 21+ | seksual ≥ 3% dan ≥ 3 paragraf |
| Mature | 17+ | kekerasan ≥ 15% dan ≥ 3 paragraf, atau seksual ≥ 1% dan ≥ 2 paragraf |
| Teen | 13+ | kekerasan ≥ 3% dan ≥ 2 paragraf, atau seksual ≥ 0,5% dan ≥ 2 paragraf |
| General | Semua umur | di luar syarat di atas |

**Persentase konten dewasa:** proporsi paragraf yang terdeteksi seksual atau kekerasan.

**Bobot cerita (0 sampai 100):** seberapa berat dan rumit konflik serta tema sampai membuat pembaca pusing. Penilaian Gemini berbobot 0,7 (cuplikan ±15.000 karakter, rubrik kerumitan konflik, berat tema, beban membaca, masing-masing 0 sampai 10, beserta alasan) dan sinyal model berbobot 0,3 (proporsi paragraf emosi negatif dengan keyakinan ≥ 0,85). Tanpa Gemini, hanya sinyal model yang dipakai.

**Safe Mode standar** hanya menyamarkan paragraf seksual; bisa dibuka satu per satu. Penyaringan bahasa kasar dan kekerasan serta ambang personal adalah UC-12 (belum dibangun).

**Rangkuman (UC-09):** per bab lalu digabung, disimpan di basis data agar tidak diproses ulang. Paragraf seksual tidak dikirim ke Gemini; diganti penanda `[adegan dewasa dilewati]`. Kelompok bab yang ditahan filter keamanan Gemini diulang sekali dengan teks yang lebih ketat.

**Tokoh dan relasi (UC-10, UC-11):**
- Nama dikenali model NER (`NER_MODEL`, bawaan `Davlan/xlm-roberta-base-ner-hrl`, belum terbukti untuk bahasa Indonesia), hanya grup PER dengan skor ≥ 0,85.
- Nama dibersihkan, gelar dibuang, nama pendek yang menjadi bagian dari satu nama panjang digabung. Tokoh minimal disebut 3 kali, maksimum 25.
- Peran: "Tokoh utama", "Tokoh pendukung", "Tokoh figuran" menurut peringkat dan rasio sebutan.
- Relasi per bab: dua tokoh dalam paragraf yang sama atau berdekatan, minimal bobot 2. Jenis "konflik" bila ≥ 40% jendela memuat paragraf konflik (marah ≥ 0,6, kekerasan ≥ 0,5, atau bahasa kasar ≥ 0,5), selain itu "akrab".
- Biodata saat ini disusun dari fakta hitungan. Hasil otomatis bisa keliru (nama panggilan terbaca tokoh berbeda, nama tempat terbaca tokoh).
- Deteksi berjalan di latar belakang dengan status `running`, `done`, `failed`, dan dipicu otomatis setelah analisis selesai atau lewat tombol.

## 5. Status fitur

Nomor UC mengikuti README dan SRS.

| UC | Fitur | Status |
|---|---|---|
| UC-01 | Unggah e-book (PDF, EPUB) | Selesai |
| UC-02 | Membuat koleksi dari beberapa dokumen | Belum |
| UC-03 | Hasil analisis rating | Selesai (rincian per dimensi dan alasan rating untuk Middle Tier belum sepenuhnya) |
| UC-04 | Membaca e-book | Selesai |
| UC-05 | Safe Mode | Selesai |
| UC-06 | Hapus e-book | Selesai |
| UC-07 | Bayar fitur premium (Midtrans) | Belum |
| UC-08 | Riwayat pembayaran | Belum |
| UC-09 | Rangkuman | Selesai (bergantung kuota Gemini) |
| UC-10 | Biodata tokoh | Selesai (dasar; lihat bagian 8) |
| UC-11 | Relasi antar tokoh | Selesai (dasar) |
| UC-12 | Profil sensitivitas | Belum |
| UC-13 | Unduh PDF | Selesai |
| UC-14 sampai UC-16 | Panel admin | Belum |
| UC-17 | Ganti cover | Belum |
| UC-18 | Ganti foto tokoh | Belum |
| UC-19 | Ubah judul | Selesai |
| FR-01 sampai FR-03 | Registrasi, login, logout | Selesai (minimal: email dan kata sandi tanpa verifikasi email) |

README di repositori masih menyebut registrasi ditunda dan tokoh belum selesai; abaikan bagian itu dan gunakan tabel ini.

## 6. API

Semua di bawah `/documents` kecuali auth. Semua endpoint dokumen butuh `Authorization: Bearer <token>`, dan dokumen hanya terlihat oleh pemiliknya (404 untuk milik orang lain).

| Metode | Path | Fungsi |
|---|---|---|
| POST | `/auth/register` | Daftar (201; 409 jika email sudah ada) |
| POST | `/auth/login` | Masuk (401 dengan pesan generik) |
| GET | `/auth/me` | Data akun |
| POST | `/documents` | Unggah dan mulai analisis (400 untuk format salah atau tanpa teks; 503 bila model belum terpasang) |
| GET | `/documents` | Daftar milik pengguna |
| GET | `/documents/{id}` | Hasil dan status |
| PATCH | `/documents/{id}` | Ubah judul |
| DELETE | `/documents/{id}` | Hapus beserta data turunan |
| GET | `/documents/{id}/chapters` | Daftar bab |
| GET | `/documents/{id}/paragraphs` | Paragraf dan skor |
| GET, POST | `/documents/{id}/summary` | Ambil, atau mulai buat (202) rangkuman |
| GET, POST | `/documents/{id}/characters` | Status, tokoh, relasi; POST memulai deteksi (202, 409 bila analisis belum selesai) |
| GET | `/documents/{id}/export` | Unduh PDF |

Autentikasi: bcrypt untuk kata sandi, JWT HS256 dengan `sub` berisi id pengguna dan `exp`, kata sandi 8 sampai 72 byte. Akun bawaan lama `standard@narative.local` tidak bisa login; `python -m app.tools.klaim_dokumen email` memindahkan dokumen lama ke akun terdaftar (sekali pakai).

## 7. Data

Tabel utama: `users`, `documents` (status `queued`, `analyzing`, `done`, `failed`; hasil agregat; `summary` dan status rangkuman; `characters_status`), `chapters` (nomor, judul, rangkuman), `paragraphs` (teks, skor tiga dimensi, emosi, `emotion_score`, `chapter_no`), `characters` (nama, peran, biodata, `mention_count`, `photo_path`), `character_relations` (tokoh A dan B, bab, `relation_type`, `weight`; unik per pasangan per bab). Relasi tabel memakai `ondelete=CASCADE`. Perubahan skema selalu lewat migrasi Alembic baru; jangan mengubah migrasi lama. Terapkan dengan `python -m app.db.db_setup` atau `python -m alembic upgrade head`.

## 8. Layanan eksternal dan kendala yang diketahui

**Kunci Gemini gratis sangat terbatas:** 5 permintaan per menit, 250 ribu token masuk per menit, 20 permintaan per hari per model. Batas harian adalah penghalang utama (reset tengah malam waktu Pasifik); dashboard menampilkan puncak 7 hari. Rata-rata satu buku 400 halaman butuh sekitar 5 panggilan bila biodata digabung (1 bobot, 2 kelompok rangkuman bab, 1 rangkuman keseluruhan, 1 biodata) dan sekitar 29 panggilan bila biodata dibuat satu per tokoh. Gemini 3.8 Flash berbayar: sekitar $0,75 input dan $3,75 output per juta token sampai 31 Desember 2026, lalu dua kali lipat (sumber pihak ketiga; verifikasi sebelum menulis di dokumen). Rana sedang kesulitan metode pembayaran untuk Tier 1.

**Perilaku saat ini di `summarizer.py`:** satu penjadwal jeda (`GEMINI_MIN_INTERVAL`, disarankan 13) per proses; 429 harian memblokir model selama satu jam dan pindah ke `GEMINI_FALLBACK_MODEL`; 429 per menit ditunggu sesuai `retryDelay` sampai empat kali lalu gagal; 5xx diulang tiga kali; blokir keamanan memicu `SafetyBlock` dan percobaan ulang dengan teks lebih ketat.

**Kelemahan desain yang sudah diketahui:**
1. Penilaian bobot cerita oleh Gemini berjalan sebelum status dokumen menjadi `done` di `jobs.py`. Karena antrean hanya satu pekerja, satu dokumen yang menunggu Gemini menahan semua pengguna lain. Dosen meminta waktu analisis tidak lama.
2. Pengatur kecepatan hanya hidup di satu proses; proses kedua (misalnya skrip `rate_heaviness`) tidak berbagi jam.
3. Pekerjaan Gemini yang kena limit gagal setelah empat percobaan, bukan menunggu.
4. LLM lokal tidak layak: laptop Rana RAM 8 GB tanpa GPU khusus.

**Hal yang belum terbukti:** model NER pada teks bahasa Indonesia, pelabelan konflik dan akrab dengan skor model asli, dan Gemini dari lingkungan pengembangan agen. Saat melaporkan, bedakan antara yang diuji dan yang diasumsikan.

## 9. Konvensi kode

**Backend:** FastAPI dengan injeksi `Depends`, pesan error dalam bahasa Indonesia, pengaturan hanya lewat `app/core/config.py` (nilai dari `.env`), tugas panjang berjalan di thread latar belakang dengan status di kolom dokumen, status yang menggantung direset saat server menyala (`reset_stale`). Tidak ada rahasia di kode atau repositori.

**Frontend:** Vue 3 `<script setup>`, komponen dan halaman berbahasa Indonesia di teks UI, Tailwind v4 dengan token warna dari `style.css` (navy, lavender, amber, paper, sand, danger), ikon lucide lewat Iconify, akses API hanya lewat `src/lib/api.js` (menyisipkan token, mengalihkan ke `/masuk` pada 401). Token sesi disimpan di `localStorage` kunci `narative.auth` dengan try/catch. Halaman harus bisa dipakai di lebar 390 px tanpa scroll horizontal. Setiap keadaan (memuat, kosong, gagal, tidak ditemukan) punya tampilan sendiri.

## 10. Perintah umum (Windows, folder `backend`, venv aktif)

| Perintah | Fungsi |
|---|---|
| `python -m app.db.db_setup` | Buat database dan terapkan migrasi |
| `python -m alembic upgrade head` | Terapkan migrasi saja |
| `python -m uvicorn app.main:app --reload` | Jalankan server |
| `python -m app.tools.rescore` | Hitung ulang rating dari skor tersimpan |
| `python -m app.tools.rate_heaviness [id ...]` | Nilai bobot cerita lewat Gemini lalu hitung ulang |
| `python -m app.tools.tokoh [id ...]` | Deteksi tokoh dan cetak laporan |
| `python -m app.tools.klaim_dokumen email` | Pindahkan dokumen akun lama ke email terdaftar |
| `python -m pip install protobuf sentencepiece tiktoken` | Pustaka tokenizer yang dibutuhkan model NER |

Frontend: `npm install`, `npm run dev`, `npm run build`, `npm run lint`.

## 11. Yang akan dibangun

Urutan di bawah adalah usulan. Butir yang berlabel "belum disetujui" tidak boleh dikerjakan sebelum Rana menyetujuinya; tanyakan dulu.

### A. Ketahanan terhadap batas Gemini (prioritas tertinggi, belum disetujui)

Tujuan: fitur rangkuman, bobot cerita, dan tokoh tidak berhenti karena kuota, dan analisis tidak menunggu Gemini.

1. **Pisahkan analisis inti dari Gemini.** Status dokumen menjadi `done` setelah penilaian lokal. Bobot cerita dari Gemini berjalan sesudahnya di latar belakang dan menyempurnakan bobot serta rating bila berhasil. Bila gagal, hasil lokal tetap dipakai. Perilaku ini harus tercatat agar Rana bisa memperbarui SRS.
2. **Antarmuka penyedia LLM ganda** dengan satu pengatur kecepatan bersama dan antrean tahan lama di basis data (status "menunggu antrean", dilanjutkan otomatis, hasil sebagian tidak diulang). Urutan: Gemini, lalu Groq, lalu Cerebras (kuota terpisah, tanpa kartu), lalu satu pintu base URL kustom yang kompatibel dengan OpenAI (Rana sempat mempertimbangkan penjual API di marketplace; hanya untuk demo, data uji, dan bukan jalur tunggal), lalu rangkuman ekstraktif lokal sebagai lapis terakhir.
3. **Ukuran permintaan:** perkecil kelompok bagi penyedia cadangan bila batas token per menit tidak jelas. Bobot cerita sebaiknya menunggu Gemini agar skala penilaiannya konsisten; rangkuman dan biodata boleh pindah ke cadangan.
4. **Biodata tokoh digabung** dalam satu atau dua panggilan, dengan pemulihan hanya untuk entri yang rusak atau terlewat.
5. **Risiko yang harus dicatat di dokumen:** isi e-book terkirim ke pihak ketiga, dan mutu bahasa Indonesia berbeda antar model.

Kriteria selesai: unggah buku 400 halaman saat Gemini dimatikan atau dibatasi tetap menghasilkan rating, rangkuman ekstraktif, dan daftar tokoh tanpa error; dengan Gemini aktif, tiga fitur memakai Gemini bila tersedia; semua ini teruji dengan simulasi kegagalan, bukan hanya jalur normal.

### B. Tokoh yang lebih cerdas (belum disetujui)

1. Gabungkan nama panggilan (misalnya "Ran", "Na", "Roen", "Nara" untuk "Rana Afifah Dzikro") dengan aturan awalan dan kemiripan yang konservatif ditambah penilaian LLM dalam panggilan yang sama dengan biodata. Bila LLM tidak tersedia, hanya aturan yang berjalan.
2. Tambah analisis per tokoh: sifat, profesi, dan peran dalam cerita (apa yang dilakukan tokoh), dari sekitar 8 kutipan kalimat per tokoh yang disebar dari awal sampai akhir buku. LLM wajib hanya memakai kutipan dan menulis "tidak disebutkan" bila tidak ada bukti.
3. Perlu migrasi baru (kolom sifat, profesi, peran cerita), pembaruan halaman biodata, dan catatan untuk revisi SRS UC-10. Halaman tetap berfungsi dengan kolom kosong.
4. Tombol gabung tokoh manual hanya dikerjakan bila Rana memintanya.

### C. Tier terhadap Gemini (menunggu keputusan Rana)

Gagasan: Free tidak memakai Gemini (rangkuman terkunci sesuai SRS atau versi ekstraktif), Middle dan High memakai Gemini. Butuh kolom tier pengguna dan mengubah keputusan "tanpa penerapan tier". Tanyakan dulu apakah rangkuman untuk Free dikunci total.

### D. Di luar cakupan dekat

UC-02, UC-07, UC-08, UC-12, UC-14 sampai UC-18, verifikasi email, dan pembayaran Midtrans. Jangan dikerjakan tanpa permintaan.

## 12. Cara melaporkan hasil

1. Satu kalimat tentang apa yang berubah dan apa dampaknya untuk pengguna.
2. Daftar file yang berubah, masing-masing berlabel **NEW** atau **LAMA (timpa)** dengan path.
3. Langkah yang harus dijalankan Rana (migrasi, restart, instalasi pustaka) dalam format cmd.
4. Apa yang sudah diuji dan bagaimana, serta apa yang belum bisa diuji (misalnya Gemini nyata, model NER nyata, teks bahasa Indonesia).
5. Satu langkah berikutnya bila memang ada.

Jangan mengirim ringkasan langkah kerja yang panjang, dan jangan menyatakan fitur beres tanpa pengujian.
