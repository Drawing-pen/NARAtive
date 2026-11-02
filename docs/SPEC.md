# SPEC NARAtive (prototipe)

Sumber kebutuhan untuk agen coding. Diturunkan dari SRS dan SDD (22 September 2026), keputusan pemilik proyek selama pengerjaan, dan kode yang ada saat ini.

## 0. Cara memakai dokumen ini

- Kata HARUS dan TIDAK BOLEH berarti wajib.
- Urutan otoritas: (1) dokumen ini, (2) `CLAUDE.md` untuk aturan kerja dan konvensi, (3) `docs/ALUR_BISNIS.md` sebagai rincian alur use case dan daftar FR/NRF, (4) SRS dan SDD PDF hanya sebagai latar. Jika SRS dan dokumen ini berbeda, dokumen ini menang. Contoh: SRS menyebut harga paket TBA, di sini harga sementara ada di `app/core/plans.py` (bagian 4). Berkas `docs/ALUR_BISNIS.md` belum ada di repositori. Selisih yang kamu temukan harus dilaporkan, jangan diselesaikan sendiri.
- Jika sesuatu yang dibutuhkan tidak ditulis di sini, BERHENTI dan tanya. Jangan menebak. Item di bagian 13 (Undecided) TIDAK BOLEH diimplementasikan berdasarkan asumsi.
- Fitur berstatus "Belum" atau "Di luar prototipe" (bagian 3) TIDAK BOLEH dikerjakan kecuali pemilik proyek memintanya secara eksplisit.
- Prototipe dijalankan di localhost, tidak di-deploy (bagian 11).
- Pemilik proyek memperbarui SRS, SDD, dan diagram sendiri. Agen TIDAK BOLEH mengubah berkas di `docs/`.

## 1. Tujuan dan cakupan

NARAtive menganalisis e-book (PDF atau EPUB) paragraf demi paragraf, lalu menampilkan rating konten, rentang usia, persentase konten dewasa, dan bobot cerita. Pembaca dapat membaca lewat mode baca dengan Safe Mode, melihat rangkuman, biodata tokoh, dan relasi antar tokoh, serta mengunduh hasil analisis sebagai PDF. Semua hasil adalah prediksi model dan hanya panduan awal, bukan penilaian editorial. UI TIDAK BOLEH mengklaim lebih dari itu.

Alur ujung ke ujung yang HARUS berjalan tanpa bug di localhost:

daftar akun, masuk, unggah e-book, tunggu analisis, lihat hasil analisis, baca dengan Safe Mode, buat rangkuman, deteksi dan lihat tokoh, lihat relasi tokoh per bab, ubah judul, unduh PDF, hapus e-book, keluar.

## 2. Glosarium dan istilah UI

Istilah UI wajib Bahasa Indonesia. Nama di kode memakai Bahasa Inggris (lihat bagian 5).

| Istilah UI | Nama di kode | Arti |
|---|---|---|
| Pengguna | tabel `users` | Pemilik akun. `tier` (free tampil sebagai Standard, middle, high) menentukan batas unggahan dan akses profil sensitivitas; `role` belum dipakai |
| Paket / Tier | `users.tier`, `app/core/plans.py` | Standard, Middle, High. Tier yang berlaku (`access_tier`) kembali ke free bila `tier_expires_at` lewat |
| E-book | tabel `documents` | Satu berkas yang diunggah. Satu e-book sama dengan satu item koleksi |
| Koleksi | halaman `/koleksi` | Daftar e-book milik pengguna, termasuk seri |
| Seri | tabel `collections` | Kelompok berurutan 2 sampai 50 e-book yang saling bersambung (UC-02). Tiap buku tetap dianalisis sendiri |
| Profil sensitivitas | tabel `sensitivity_profiles` | Ambang Safe Mode personal per jenis konten (UC-12), khusus High |
| Transaksi | tabel `transactions` | Satu pembayaran Virtual Account: upgrade paket atau analisis tambahan (pay-per-check) |
| Kuota | tabel `usage_quota`, `users.extra_checks` | Pemakaian analisis per bulan dan sisa analisis tambahan |
| Bab | tabel `chapters` | Bagian e-book. Memuat rangkuman per bab |
| Paragraf | tabel `paragraphs` | Blok teks sampai 900 karakter beserta skor model |
| Rating Konten | `documents.rating` | General, Teen, Mature, Explicit |
| Rentang Usia | properti `age_range` | Semua umur, 13+, 17+, 21+ |
| Persentase Konten Dewasa | `documents.pct_adult` | Proporsi paragraf seksual atau kekerasan |
| Bobot Cerita | `documents.heaviness` | Skor 0 sampai 100 beratnya konflik dan tema |
| Safe Mode | state di halaman mode baca | Menyamarkan paragraf seksual, bisa dibuka satu per satu |
| Rangkuman | `chapters.summary`, `documents.summary` | Rangkuman per bab dan keseluruhan, dari Gemini |
| Tokoh | tabel `characters` | Tokoh yang terdeteksi beserta deskripsinya |
| Relasi | tabel `character_relations` | Hubungan dua tokoh per bab: akrab atau konflik |
| Status Analisis | `documents.status` | queued, analyzing, done, failed |
| Status Rangkuman | `documents.summary_status` | running, done, partial (semua bab punya rangkuman, sebagian atau rangkuman keseluruhannya sederhana tanpa AI), failed (kosong = belum pernah dibuat) |
| Status Tokoh | `documents.characters_status` | running, done, partial (tokoh tersimpan, LLM gagal), failed (kosong = belum pernah dideteksi) |

Teks UI untuk status: queued dan analyzing tampil sebagai "sedang dianalisis" atau "sedang diproses" beserta estimasi waktu; done sebagai selesai; failed sebagai gagal.

## 3. Cakupan fitur

Penyebut: 19 UC di SRS. Selesai: 16 dari 19 (±84%), dengan UC-03 sebagian. FR-01 sampai FR-03 (autentikasi) tidak punya UC.

| UC / FR | Isi singkat | Status |
|---|---|---|
| FR-01 sampai FR-03 | Registrasi (dengan kode verifikasi email), login, logout | Prototipe, minimal: TANPA lupa kata sandi |
| UC-01 | Unggah e-book | Prototipe, dengan pemeriksaan halaman, kuota bulanan, dan e-book aktif menurut tier |
| UC-02 | Koleksi dari beberapa dokumen | Prototipe, disebut "seri" di UI |
| UC-03 | Hasil analisis rating | Prototipe, sebagian: rincian per dimensi dan alasan rating Middle Tier belum |
| UC-04 | Membaca e-book | Prototipe |
| UC-05 | Safe Mode | Prototipe: hanya paragraf seksual |
| UC-06 | Hapus e-book | Prototipe |
| UC-07, UC-08 | Pembayaran, riwayat | Prototipe: Virtual Account, mode simulasi atau Midtrans |
| UC-09 | Rangkuman | Prototipe, bergantung kuota Gemini |
| UC-10 | Biodata tokoh | Prototipe: 100% LLM (9router, Gemini cadangan) per potongan bab, penghitungan oleh kode (R13) |
| UC-11 | Relasi tokoh | Prototipe, enam jenis hubungan |
| UC-12 | Profil sensitivitas | Prototipe, khusus High |
| UC-13 | Unduh PDF | Prototipe. PDF belum memuat rangkuman |
| UC-14 sampai UC-16 | Panel admin | Di luar prototipe |
| UC-17, UC-18 | Ganti cover, ganti foto tokoh | Prototipe, khusus High (13A R6, F-GAMBAR) |
| UC-19 | Ubah judul | Prototipe |

Konsekuensi lingkup:
- Tabel `subscriptions` dan `payment_methods` dari SDD TIDAK dibuat; status langganan disimpan di `users.tier` dan `users.tier_expires_at`. Tabel `transactions`, `usage_quota`, `sensitivity_profiles`, dan `collections` dibuat.
- Kolom `users.is_active` dipakai (akun tidak aktif ditolak). `users.tier` ditegakkan untuk batas unggahan (bagian 4) dan untuk mengubah profil sensitivitas (High). Matriks tier ditegakkan di server (13A R2): membuat rangkuman, tokoh, dan relasi untuk Middle ke atas; unduh PDF dan mengubah profil sensitivitas untuk High; hasil yang sudah ada tetap bisa dilihat. Rincian rating belum punya endpoint (placeholder). `users.role` TIDAK dipakai.
- `DEV_UNLOCK_ALL_TIERS=true` memperlakukan semua akun sebagai High (khusus pengembangan, jangan aktif di produksi).
- Tombol fitur yang belum jadi tampil sebagai terkunci tanpa fungsi.

## 4. Aturan produk

- Format unggahan: PDF atau EPUB, divalidasi dari isi dan hasil pembacaan, bukan hanya ekstensi. EPUB berDRM ditolak dengan pesan yang jelas. Format lain di luar cakupan.
- Berkas tanpa teks yang dapat dianalisis ditolak. File asli TIDAK disimpan setelah teksnya masuk basis data.
- Judul awal diambil dari nama berkas tanpa ekstensi. Judul maksimal 255 karakter, tidak boleh kosong setelah trim. Mengubah judul TIDAK memicu analisis ulang.
- Paragraf pendek digabung menjadi blok sampai 900 karakter. Penanda adegan (`* * *`) memotong blok. Jumlah halaman EPUB adalah perkiraan (karakter dibagi 1800).
- Bahasa kasar TIDAK dihitung dalam rating maupun persentase konten dewasa. Hanya dimensi seksual dan kekerasan.
- Safe Mode standar hanya menyamarkan paragraf seksual dan dapat dibuka satu per satu dengan mengetuk. Penyaringan bahasa kasar dan kekerasan hanya lewat profil sensitivitas (UC-12, High): ambang 0,1 sampai 0,95 per jenis, null berarti tidak disamarkan. Pengguna non-High selalu memakai profil standar.
- Paragraf seksual TIDAK BOLEH dikirim ke Gemini; diganti penanda `[adegan dewasa dilewati]`.
- Rangkuman, tokoh, dan relasi hanya dapat dimulai setelah analisis berstatus done. Hasilnya disimpan dan TIDAK dihitung ulang tanpa permintaan pengguna.
- Isolasi data: pengguna hanya dapat mengakses e-book miliknya. ID milik pengguna lain atau yang tidak ada mengembalikan 404.
- Menghapus e-book menghapus bab, paragraf, rangkuman, tokoh, dan relasinya (cascade).
- Batas per tier (`app/core/plans.py`), diperiksa setelah teks terbaca dan sebelum dokumen disimpan; terlewati menghasilkan 402 dengan pesan Bahasa Indonesia:

| Tier | Halaman per unggahan | Analisis per bulan | E-book aktif |
|---|---|---|---|
| free (Standard) | 50 | 3 | 3 |
| middle | 300 | 15 | 50 |
| high | tanpa batas | tanpa batas | tanpa batas |

- Kuota dihitung per bulan kalender (UTC), reset otomatis lewat baris `usage_quota` periode baru. Kuota bulanan dipakai dulu, lalu `users.extra_checks` (analisis tambahan). Pemakaian dicatat dalam transaksi yang sama dengan penyimpanan dokumen.
- Pembayaran: Virtual Account bank bca, bni, bri, permata, berlaku 24 jam. Upgrade middle Rp29.000 atau high Rp59.000 untuk 30 hari (perpanjangan atau kenaikan paket saat paket berbayar masih berlaku menambah 30 hari dari tanggal berakhir, sisa hari tidak hangus); analisis tambahan Rp5.000 per analisis, 1 sampai 10 per pembelian; High tidak boleh membeli analisis tambahan. Harga sementara, SRS menyebut TBA. Tanpa `MIDTRANS_SERVER_KEY` berjalan mode simulasi tanpa uang sungguhan, hanya bila semua `CORS_ORIGINS` adalah localhost (selain itu `provider` = `unavailable` dan checkout 503); webhook Midtrans diverifikasi `signature_key` dan nominal; penyelesaian pembayaran idempoten; kode verifikasi, instruksi pembayaran saat checkout, dan invoice dikirim lewat email bermerek berbentuk teks dan HTML (13A R8; hanya dicatat di log bila `SMTP_HOST` kosong).
- Seri: 2 sampai 50 e-book berurutan, satu e-book hanya di satu seri (dipindah otomatis dari seri lain), seri yang kosong otomatis dihapus, membubarkan seri tidak menghapus e-book.
- Ukuran berkas unggahan (byte) TIDAK dibatasi.
- Privasi: isi e-book terkirim ke Gemini (rangkuman, bobot cerita) dan, bila diaktifkan, ke penyedia LLM lain. Pada tier gratis, konten dapat dipakai penyedia untuk peningkatan produk dan dibaca reviewer manusia. Cantumkan sebagai catatan di README, jangan di UI.

## 5. Data

MySQL 8 (SQLite hanya untuk uji cepat), SQLAlchemy 2, migrasi hanya lewat Alembic (0001 sampai 0019). Hapus berantai di tingkat database: menghapus baris `users` menghapus `documents`, transaksi, kuota, koleksi, dan profil sensitivitas; menghapus `documents` menghapus `chapters`, `paragraphs`, `characters`, dan relasinya (semua FK ke `users` dan `documents` memakai ON DELETE CASCADE). PK integer auto-increment. Nama tabel dan kolom di bawah adalah nama persis di kode, dan tabel ini adalah satu-satunya sumber skema. Jika sebuah kolom tidak tertulis di sini, tanya. Perubahan skema HARUS lewat migrasi baru; TIDAK BOLEH mengubah migrasi lama.

| Tabel | Kolom |
|---|---|
| `users` | `id`, `name` VARCHAR(100), `email` VARCHAR(255) UNIQUE (disimpan lowercase), `password_hash` VARCHAR(255) (bcrypt), `tier` VARCHAR(10) DEFAULT 'free' (free, middle, high), `role` VARCHAR(10) DEFAULT 'user' (user, admin; tidak dipakai), `is_active` BOOLEAN DEFAULT true, `created_at`, `tier_expires_at` DATETIME NULL (NULL = tidak berbatas waktu), `extra_checks` INT DEFAULT 0 (sisa analisis tambahan) |
| `documents` | `id`, `user_id` FK CASCADE, `collection_id` FK NULL (ON DELETE SET NULL), `position` INT DEFAULT 0 (urutan dalam seri), `title` VARCHAR(255), `filename` VARCHAR(255), `page_count`, `paragraph_count`, `status` (queued, analyzing, done, failed), `rating`, `pct_profanity`, `pct_sexual`, `pct_violence`, `dominant_emotion`, `pct_adult`, `heaviness`, `heaviness_ai`, `heaviness_note` TEXT, `created_at`, `analyzed_at`, `summary` TEXT, `summary_status` (running, done, partial, failed), `characters_status` (running, done, failed), `cover_path` VARCHAR(255) NULL |
| `chapters` | `id`, `document_id` FK, `number`, `title` VARCHAR(255), `summary` TEXT, `summary_source` VARCHAR(10) NULL (ai, local; NULL = data lama dianggap ai) |
| `paragraphs` | `id`, `document_id` FK, `idx`, `chapter_no`, `text` TEXT (teks polos), `markdown` TEXT NULL, `kind` VARCHAR(8) DEFAULT 'p' (p, h, li, quote), `profanity`, `sexual`, `violence` (FLOAT 0 sampai 1), `emotion` (sad, angry, fear, happy), `emotion_score` |
| `characters` | `id`, `document_id` FK CASCADE, `name` VARCHAR(100), `role` VARCHAR(50) (tidak dipakai sejak R12, diisi kosong), `biodata` TEXT (menyimpan deskripsi tokoh), `mention_count`, `photo_path` VARCHAR(255) NULL, `aliases` VARCHAR(255), `gender`, `age`, `occupation`, `personality`, `background` (tidak dipakai sejak R12, dibiarkan NULL; semua boleh NULL) |
| `character_relations` | `id`, `character_a_id` FK CASCADE, `character_b_id` FK CASCADE, `chapter_id` FK CASCADE, `relation_type` VARCHAR(10) (pasangan, sahabat, teman, keluarga, musuh, kenalan; nilai lama akrab dan konflik dibaca frontend sebagai kenalan dan musuh), `weight` INT. UNIQUE (`character_a_id`, `character_b_id`, `chapter_id`) |
| `email_verifications` | `id`, `email` VARCHAR(255) UNIQUE, `name` VARCHAR(100), `password_hash` VARCHAR(255) (bcrypt), `code_hash` VARCHAR(64) (HMAC-SHA256 dengan `SECRET_KEY`), `expires_at`, `attempts` INT DEFAULT 0, `last_sent_at`. Pendaftaran tertunda; baris dihapus saat sukses, hangus, atau email sudah dipakai |
| `collections` | `id`, `user_id` FK CASCADE (indeks), `name` VARCHAR(150), `created_at` |
| `sensitivity_profiles` | `id`, `user_id` FK CASCADE UNIQUE, `profanity`, `sexual`, `violence` FLOAT NULL (NULL = tidak disamarkan), `updated_at` |
| `transactions` | `id`, `user_id` FK CASCADE (indeks), `order_id` VARCHAR(40) UNIQUE, `kind` (upgrade, pay_per_check), `plan` (middle, high; NULL untuk pay_per_check), `quantity` INT DEFAULT 1, `amount` INT (rupiah), `bank`, `va_number`, `provider` (simulated, midtrans), `status` (pending, paid, failed, expired, cancelled), `created_at`, `expires_at`, `paid_at` NULL |
| `usage_quota` | `id`, `user_id` FK CASCADE (indeks), `period` VARCHAR(7) (YYYY-MM), `used` INT DEFAULT 0. UNIQUE (`user_id`, `period`) |

Pemetaan ke nama tabel di SDD (jangan ganti nama di kode): `user` ke `users`, `ebooks` ke `documents`, `analysis_results` ke kolom hasil di `documents`, `chapters` sama, `characters` sama, `characters_relations` ke `character_relations`, `sensitive_paragraphs` ke `paragraphs`. `usage_quota`, `transactions`, `sensitivity_profiles` memakai nama yang sama dengan SDD; `collections` ditambahkan untuk UC-02. Kolom `weight`, kolom biodata tokoh, `tier_expires_at`, dan `extra_checks` belum ada di ERD pemilik.

Aturan data:
- Semua FK anak memakai cascade; hapus lewat ORM.
- Status yang menggantung (`analyzing`, `queued`, `summary_status`/`characters_status` = running) dipulihkan saat server menyala: analisis dimasukkan kembali ke antrean; rangkuman dan tokoh ditandai failed.
- Deteksi ulang tokoh bersifat idempotent: baris lama dihapus lalu dibuat ulang tanpa baris ganda.

## 6. Autentikasi dan sesi

Implementasi manual, tanpa library auth pihak ketiga.

- Endpoint (tanpa prefix `/api`): `POST /auth/register` (202, memulai pendaftaran dan mengirim kode; respons `{email, expires_in: 600, resend_after: 60}`, tanpa token), `POST /auth/register/verify` `{email, code}` (201), `POST /auth/register/resend` `{email}` (202), `POST /auth/login` (200), `GET /auth/me` (200), `PATCH /auth/me` (ubah nama), `PUT /auth/me/password` (204), `DELETE /auth/me` (204, hapus akun), lihat 13A R7 dan F-PROFIL. Respons verify dan login: `{access_token, token_type: "bearer", user: {id, name, email, tier, role, created_at}}`, dengan `tier` berupa tier yang berlaku (free, middle, high).
- Registrasi: `name` (1 sampai 100, spasi ganda dirapikan, tidak boleh kosong), `email` (format valid, di-lowercase), `password` (8 sampai 72 byte). Kata sandi disimpan sebagai hash bcrypt. Akun dibuat hanya setelah kode 6 angka yang dikirim ke email cocok (aturan kode, jeda, dan pesan error di F-AUTH); kata sandi dan kode disimpan sebagai hash di `email_verifications` selama menunggu. Email yang sudah terdaftar ditolak 409. Setelah verifikasi sukses, pengguna langsung masuk (token diterbitkan) dan diarahkan ke Koleksi. Akun baru bertier `free` dan berperan `user`. Akun yang dibuat sebelum fitur ini dianggap terverifikasi.
- Login: `email` dan `password`. Gagal: 401 pesan generik, tanpa membedakan email atau kata sandi. Akun tidak aktif: 403.
- Token: JWT HS256, `sub` berisi id pengguna (string) dan `exp`, rahasia `SECRET_KEY` dari environment, masa berlaku `ACCESS_TOKEN_MINUTES` (bawaan 1440). Tanpa refresh token dan tanpa tabel sesi.
- Frontend menyimpan token dan data pengguna di `localStorage` kunci `narative.auth` dengan try/catch, menyisipkan header `Authorization: Bearer`, dan pada 401 melakukan logout lalu mengarahkan ke `/masuk?next=<alamat>&expired=1`. Parameter `next` hanya diterima bila diawali `/` dan bukan `//`.
- Guard rute: halaman dengan `meta.requiresAuth` (Koleksi dan semua halaman buku) dialihkan ke `/masuk` bila belum login. Halaman `meta.guest` (masuk dan daftar) dialihkan ke Koleksi bila sudah login.
- Logout: hapus sesi di browser dan arahkan ke Beranda. Tidak ada pencabutan token di server.
- Akun bawaan lama `standard@narative.local` tidak bisa login. `python -m app.tools.klaim_dokumen <email>` memindahkan dokumen lama ke akun terdaftar (sekali pakai).
- Rate limit login TIDAK diterapkan di prototipe.

## 7. Penilaian dan aturan analisis

**Model.** xlm-roberta-base + LoRA, empat kepala (bahasa kasar, seksual, kekerasan, emosi). Berkas `model/model_best.pt` dan `model/tokenizer_xlmr/`. TIDAK BOLEH melatih ulang model atau mengubah ambang kecuali diminta. Konteks sliding window: paragraf N dinilai bersama N-1 dan N+1, skor dicatat untuk paragraf N. Mendukung bahasa Indonesia dan Inggris.

**Ambang per paragraf (konstanta tetap, `THRESHOLDS`):** bahasa kasar 0,5; seksual 0,5; kekerasan 0,8. Deteksi seksual hibrida: nilai akhir = maksimum antara skor model dan skor kamus kata eksplisit.

**Rating** (hanya seksual dan kekerasan; persentase paragraf terdeteksi DAN jumlah minimal paragraf):

| Rating | Usia | Syarat |
|---|---|---|
| Explicit | 21+ | seksual ≥ 3% dan ≥ 3 paragraf |
| Mature | 17+ | kekerasan ≥ 15% dan ≥ 3 paragraf, atau seksual ≥ 1% dan ≥ 2 paragraf |
| Teen | 13+ | kekerasan ≥ 3% dan ≥ 2 paragraf, atau seksual ≥ 0,5% dan ≥ 2 paragraf |
| General | Semua umur | di luar syarat di atas |

**Persentase konten dewasa:** proporsi paragraf dengan seksual atau kekerasan di atas ambang, tanpa hitung ganda.

**Bobot cerita (0 sampai 100):** penilaian Gemini (kerumitan konflik, berat tema, beban membaca, masing-masing 0 sampai 10, dari 12 cuplikan sekitar 1.200 karakter) berbobot 0,7, dan sinyal model berbobot 0,3 (proporsi paragraf emosi sad, angry, atau fear dengan keyakinan ≥ 0,85). Tanpa Gemini, hanya sinyal model. Cerita yang emosional tetapi konfliknya sederhana HARUS bernilai rendah.

**Dokumen dewasa yang diblokir Gemini:** bila Gemini menolak karena kebijakan keamanan, ulangi sekali dengan teks yang lebih ketat (ambang seksual 0,2; kekerasan dan bahasa kasar 0,5). Bila tetap ditolak, bobot dari Gemini dilewati.

**Rangkuman.** Per bab dan keseluruhan, dibuat Gemini dalam kelompok bab (maksimal 90.000 karakter atau 20 bab per permintaan; cuplikan awal, tengah, dan akhir sampai 6.000 karakter per bab), 3 sampai 5 kalimat per bab, 5 sampai 8 kalimat untuk keseluruhan, bahasa Indonesia, netral. Setiap bab yang punya teks HARUS mendapat rangkuman, lewat percobaan bertingkat: (1) teks normal dengan paragraf seksual (skor ≥ 0,5) diganti `[adegan dewasa dilewati]`; (2) bila Gemini menolak kelompok bab karena keamanan, sekali ulang dengan paragraf yang disaring lebih ketat diganti penanda, bukan dibuang (seksual ≥ 0,2 menjadi `[adegan dewasa dilewati]`, kekerasan ≥ 0,5 menjadi `[adegan kekerasan dilewati]`, bahasa kasar ≥ 0,5 menjadi `[bahasa kasar dilewati]`; penanda berurutan yang sama digabung); bab yang setelah itu hanya berisi penanda tidak dikirim lagi; (3) rangkuman lokal sederhana tanpa Gemini (`app/services/summary_local.py`) bagi bab yang tetap belum punya rangkuman, yaitu ditolak dua kali, jawaban tidak terbaca, bab hilang dari jawaban dan gagal dirangkum sendiri, atau kuota Gemini habis. Rangkuman lokal berisi kalimat pembuka (2), tengah (1), dan penutup (1) bab dari paragraf yang lolos saringan ketat, maksimal 4 kalimat dan 220 karakter per kalimat; bab yang seluruhnya disaring mendapat kalimat tetap "Bab ini sebagian besar berisi adegan yang dilewati dalam rangkuman (kekerasan, bahasa kasar, atau konten dewasa)." Rangkuman keseluruhan dari Gemini bila bisa; bila gagal (kuota atau galat server) disusun lokal dari kalimat pertama maksimal 6 rangkuman bab yang tersebar merata. Status `partial` bila ada rangkuman lokal; `done` bila semuanya dari Gemini. Bab tanpa paragraf sama sekali tetap bertulis "Rangkuman bab ini tidak dapat dibuat." Galat kredensial atau permintaan salah (400, 401, 403, 404) tetap menghentikan proses dengan status `failed`; begitu pula bila tidak satu pun bab punya rangkuman. Melanjutkan (status `failed` atau `partial`): bab bersumber `ai` tidak diulang, bab bersumber `local` dan yang kosong dicoba lagi lewat Gemini. Rangkuman yang sudah berhasil dapat dibuat ulang dari awal atas permintaan pengguna.

**Tokoh dan relasi (R13, 2026-11-01: 100% LLM, NER dibuang).** Prinsip: berlaku untuk buku apa pun (bahasa, sudut pandang, dan gaya apa pun), tidak disetel ke satu buku; LLM membaca dan memahami, kode menghitung dan memeriksa; panggilan ke 9router dibuat sehemat mungkin.
1. **Pemotongan (`character_ai.make_chunks`):** paragraf berurutan dikelompokkan per bab ke potongan sampai 40.000 karakter (`CHUNK_CHARS`); satu bab tidak dipecah kecuali lebih panjang dari batas (dipecah di batas paragraf). Paragraf seksual (skor ≥ 0,2) tidak dikirim. Jumlah panggilan per buku kira-kira jumlah karakter dibagi 40.000, ditambah satu panggilan gabung.
2. **Panggilan per potongan (`read_chunk`, label log "tokoh per bab"):** teks adalah DATA. LLM mengembalikan JSON: `sudut_pandang` ("pertama" atau "ketiga"), `narator` (nama tokoh yang bercerita bila orang pertama dan bisa diketahui, selain itu kosong), `kata_ganti_pertama` (kata ganti orang pertama tunggal yang dipakai narator dalam bahasa buku itu, mis. "aku", "I", "gue"; kosong bila orang ketiga), `tokoh` (maksimal 15 orang, bukan tempat atau kelompok: nama paling lengkap, panggilan, satu kalimat `peran`), dan `relasi` (maksimal 12: `a`, `b`, `jenis`, `bukti`). Jenis hanya: pasangan, sahabat, teman, keluarga, musuh, kenalan (selain itu menjadi kenalan). `bukti` adalah kutipan persis dari teks, maksimal 20 kata. Nama ditulis persis seperti di teks. Orang yang hanya disebut dengan istilah kekerabatan atau jabatan (Mama, Papa, Sekretaris) ditulis dengan pemilik hubungannya (mis. "Mama Raib" dan "Mama Seli") dan istilah aslinya menjadi panggilan, supaya "Mama" milik dua orang berbeda tidak tertukar; prompt gabung juga melarang menggabungkan istilah yang sama milik orang berbeda. Hasil dibersihkan: nama dan panggilan dirapikan, panggilan yang sama dengan kata ganti pertama potongan itu dibuang, orang yang namanya sebuah kata ganti pertama dilewati, entri tanpa nama dibuang, relasi dengan a = b dibuang, kutipan dipotong 200 karakter.
3. **Paralel dan ulang (`read_chunks`):** maksimal `CHARACTER_PARALLEL` (bawaan 3) panggilan berjalan bersamaan. Karena 9router menahan semua panggilan 60 detik setelah satu kegagalan (R10), potongan yang gagal diulang satu putaran setelah menunggu `RETRY_WAIT` (65 detik) bila ada yang gagal. Potongan yang tetap gagal dilewati. Semua potongan gagal: deteksi gagal (status `failed`). Sebagian gagal: status `partial`.
3b. **Teks ditahan filter keamanan LLM (R13b, 2026-11-01):** bila sebuah potongan ditolak karena kebijakan keamanan (`SafetyBlock`, baik dari 9router maupun Gemini), potongan itu dibelah dua menurut ukuran di batas paragraf dan tiap belahan dibaca ulang, berulang pada belahan yang masih ditolak sampai paragraf pemicunya terisolasi; satu paragraf yang tetap ditolak dilewati (dicatat di log), sisanya tetap terbaca, dan hasil belahan digabung (tokoh dengan nama sama disatukan, relasi digabung, narator dan kata ganti dari belahan pertama yang punya). Paragraf yang dilewati karena ini tidak membuat status menjadi `partial`, sama seperti paragraf seksual yang memang tidak dikirim. Kegagalan selain penolakan keamanan tidak dibelah (ditangani putaran ulang butir 3). Biayanya hanya muncul saat ada penolakan: kira-kira dua panggilan tambahan per tingkat pembelahan. Batas yang diakui: penolakan 9router yang hanya berupa balasan kosong tanpa alasan tidak dikenali sebagai penolakan keamanan (diperlakukan sebagai kegagalan biasa) kecuali Gemini cadangan lalu menolaknya.
4. **Kandidat dan penghitungan oleh kode (`characters.build`):** kandidat digabung dari semua potongan menurut nama persis (tanpa membedakan huruf besar kecil). Jumlah sebutan dihitung kode, bukan LLM: pencocokan kata utuh, peka huruf besar kecil, panggilan terpanjang dulu agar "Putri Raib" tidak dihitung dua kali. Hanya panggilan yang tampak seperti nama (huruf pertama kapital, atau aksara tanpa huruf kapital dengan minimal 2 karakter) yang dihitung. Panggilan satu kata yang bentuk huruf kecilnya muncul sama sering atau lebih sering daripada bentuk kapitalnya dianggap kata umum (mis. "kawan", "tante") dan tidak dihitung; nama utama tokoh selalu dihitung. Panggilan yang dipakai dua tokoh berbeda tidak dihitung untuk keduanya (akibatnya istilah seperti "Mama" yang dimiliki dua orang tidak dihitung untuk keduanya, jumlah sebutannya bisa kurang).
5. **Narator orang pertama:** kata ganti dari `kata_ganti_pertama` dihitung sebagai sebutan narator, hanya di bab-bab potongan yang narator-nya dikenali dan hanya di luar dialog (teks di antara tanda kutip “ ” " « » dibuang dulu). Sebutan ini juga menjadi kehadiran narator di paragraf untuk bobot relasi. Narator yang tidak dikenali namanya tidak mendapat kartu.
6. **Penggabungan (`merge`, label log "gabung tokoh"):** satu panggilan setelah semua potongan, hanya bila potongan lebih dari satu. Kandidat dengan sebutan < 3 dibuang dulu; maksimal 60 kandidat teratas dikirim, masing-masing dengan nomor, nama, panggilan, jumlah sebutan, dan sampai dua kalimat peran. LLM mengembalikan kelompok: `id` (nomor kandidat yang orang sama), `nama_utama`, dan `deskripsi` (satu sampai tiga kalimat: siapa dia dan perannya dalam cerita; maksimal 600 karakter, kosong bila tidak diketahui). Nomor yang tidak dikenal dibuang; kandidat yang tidak masuk kelompok mana pun tetap berdiri sendiri. Panggilan sebuah kelompok adalah gabungan nama dan panggilan semua anggotanya. Bila potongan hanya satu, penggabungan dilewati. Bila panggilan gabung gagal, kandidat tetap dipakai apa adanya (digabung kode bila nama sebuah kandidat sama dengan panggilan kandidat lain), deskripsi memakai kalimat peran, dan status `partial`.
7. **Saringan akhir:** setelah penggabungan, jumlah sebutan dihitung ulang dari semua panggilan kelompok; minimal 3 sebutan, maksimal 25 tokoh, urut dari yang paling sering disebut. Kartu menampilkan sampai 3 panggilan yang tampak seperti nama (paling sering dulu) di "Juga disebut". Deskripsi kosong diganti kalimat peran, lalu "{nama} disebut {n} kali di {m} bab."
8. **Relasi:** relasi dari LLM dipetakan ke tokoh akhir lewat nama atau panggilan (tidak ketemu atau ambigu: dibuang). Relasi hanya dipakai bila `bukti` (minimal 8 karakter) ditemukan di teks potongan (spasi dirapikan, huruf besar kecil diabaikan) DAN paragraf yang memuat bukti itu memuat kedua tokoh (narator dianggap hadir di setiap paragraf bab yang diceritakannya). Bab relasi adalah bab paragraf bukti. Jenis per bab adalah suara terbanyak dari bukti bab itu, selain itu jenis keseluruhan pasangan itu; seri diputus menurut urutan pasangan, keluarga, sahabat, musuh, teman, kenalan. Bobot per bab dihitung kode: paragraf (atau paragraf berikutnya di bab yang sama) tempat salah satu tokoh hadir dan keduanya hadir dalam jendela itu. Tepi dibuat untuk pasangan yang punya minimal satu bukti terverifikasi, pada bab yang bobotnya ≥ 2 atau yang punya bukti sendiri. Pasangan yang tidak pernah dinyatakan LLM tidak mendapat tepi.
9. **Gagal dan konfigurasi:** tanpa 9router maupun Gemini (`available()` salah): POST mengembalikan 409 "Deteksi tokoh butuh layanan AI (9router atau Gemini) di server."; deteksi otomatis setelah analisis dilewati diam-diam. Model NER (`NER_MODEL`, `transformers` untuk tokoh) dibuang; `torch` dan `transformers` tetap dipakai model sensitivitas. Pengaturan baru `CHARACTER_PARALLEL`.
10. **Batas yang diakui:** potongan yang memuat beberapa bab dengan narator berbeda hanya mengenali satu narator; kualitas sudah dicoba pada satu novel Indonesia orang pertama dan satu novel Inggris orang ketiga (3 bab masing-masing), belum seluruh buku; relasi hanya diperiksa bahwa kutipannya ada dan memuat kedua tokoh, bukan bahwa kutipan itu sungguh membuktikan jenisnya; pada novel Indonesia orang pertama 403 halaman (540 ribu karakter) hasil uji langsung: 17 potongan, 18 panggilan, sekitar 4 menit dengan `CHARACTER_PARALLEL` 3.
- Keterbatasan yang HARUS dicantumkan di UI: nama bisa tergabung atau terpisah keliru, nama tempat atau kelompok bisa terbaca sebagai tokoh, deskripsi AI bisa keliru, urutan tokoh bisa keliru bila narator tidak dikenal, dan jenis hubungan hanya perkiraan.

## 8. Pemrosesan

- Analisis berjalan di antrean satu pekerja (thread daemon), dokumen satu per satu. Setelah unggahan tersimpan, status `queued`; pekerja mengubahnya menjadi `analyzing`, lalu `done` atau `failed`. Respons unggahan tidak menunggu analisis.
- Urutan di `process` (jobs.py): model menilai semua paragraf, bobot cerita dari Gemini bila `GEMINI_API_KEY` terisi (kegagalan Gemini dilewati dan dicatat), agregasi, simpan, status done, lalu deteksi tokoh otomatis.
- Rangkuman dan tokoh berjalan di thread latar belakang masing-masing. Hanya satu proses per dokumen; permintaan saat status running tidak memulai proses kedua. Deteksi tokoh memakai kunci agar tidak berjalan paralel antar dokumen.
- Semua panggilan Gemini lewat `summarizer._generate` (satu titik). Perilakunya: jeda minimal `GEMINI_MIN_INTERVAL` detik antar panggilan; 429 harian memblokir model selama satu jam dan pindah ke `GEMINI_FALLBACK_MODEL`, bila semua model terblokir harian muncul pesan kuota habis; 429 per menit ditunggu sesuai `retryDelay` (maksimal 90 detik) sampai 4 kali; 5xx dan gangguan jaringan diulang dengan jeda 5, 15, 40 detik; penolakan keamanan memicu percobaan ulang dengan teks yang lebih ketat. TIDAK ada panggilan Gemini dari tempat lain. Setiap percobaan (berhasil atau gagal) dicatat satu baris di log server berawalan `Gemini |`: keperluan (bobot cerita, rangkuman bab (kelompok), rangkuman bab (tunggal), rangkuman keseluruhan, biodata tokoh), model, hasil (ok, 429 kuota harian habis, 429 batas per menit, galat kode, jaringan gagal, tanpa teks), lama dalam detik, dan jumlah token masuk dan keluar bila ada. Log TIDAK BOLEH memuat kunci, isi buku, atau jawaban Gemini.
- Hemat API: kelompokkan bab, simpan hasil, kunci API hanya dari `GEMINI_API_KEY`. Semua test memakai mock Gemini. Dilarang memanggil Gemini nyata dari test otomatis.
- Pesan kegagalan untuk pengguna ditulis Bahasa Indonesia, tanpa detail teknis, jejak stack, atau kunci.
- Frontend memuat ulang status secara berkala (polling) selama ada proses berjalan: halaman hasil selama analisis belum selesai, halaman rangkuman selama `summary_status` running, halaman tokoh dan relasi setiap 3 detik selama `characters_status` running.

## 9. Layar dan alur

Halaman: Beranda, Koleksi (e-book dan seri), Berlangganan (paket, kuota, checkout, tautan ke riwayat), Profil (`/profil`), Masuk, Daftar, dan ruang kerja satu buku di `/buku/:id` dengan sidebar dan halaman Hasil analisis, Mode baca, Rangkuman, Biodata tokoh, Relasi tokoh, Profil sensitivitas (`/buku/:id/sensitivitas`). Halaman tidak ditemukan untuk rute lain. Semua teks UI Bahasa Indonesia. Halaman buku dan Koleksi butuh login.

### F-AUTH (FR-01 sampai FR-03)
Mengikuti bagian 6. Tombol Keluar tersedia di sidebar dan header untuk halaman terproteksi.
- Email sudah terdaftar: "Email sudah terdaftar. Silakan masuk."
- Login gagal: "Email atau kata sandi salah."
- Akun tidak aktif: "Akun tidak aktif."
- Registrasi dua tahap di halaman Daftar: isi nama, email, kata sandi lalu "Kirim kode verifikasi"; layar berubah ke kolom kode 6 angka dengan tombol "Verifikasi dan daftar", "Kirim ulang kode" (dengan hitung mundur 60 detik), dan "Ubah email atau data". Kode berlaku 10 menit, maksimal 5 kali salah, mendaftar ulang atau kirim ulang sebelum 60 detik ditolak. Pendaftaran tertunda yang hangus atau tidak ditemukan mengembalikan pengguna ke form.
- Kode salah (400): "Kode verifikasi salah."
- Kode kedaluwarsa (400): "Kode verifikasi sudah kedaluwarsa. Kirim ulang kode."
- Percobaan kelima salah (429): "Terlalu banyak percobaan. Mulai pendaftaran lagi."
- Kirim ulang atau daftar ulang terlalu cepat (429): "Tunggu sebentar sebelum meminta kode baru."
- Pendaftaran tertunda tidak ada (404): "Pendaftaran tidak ditemukan. Mulai pendaftaran lagi."
- Kode bukan tepat 6 angka: 422.
- Tanpa `SMTP_HOST` kode hanya dicatat di log server (mode pengembangan).

### F-UNGGAH (UC-01)
Endpoint `POST /documents` (multipart, field `file`), 201 mengembalikan dokumen berstatus queued. PDF dibaca dari memori (bukan dari berkas yang dibuka terus), dan kegagalan menghapus berkas sementara hanya dicatat di log, tidak menggagalkan permintaan (penting di Windows, tempat berkas yang masih dipegang tidak bisa dihapus). Parser mengembalikan jumlah halaman, judul bab, dan daftar paragraf teks biasa (maksimum 900 karakter per paragraf); tes parser di `test_pdf_extraction.py` dan `test_epub_extraction.py` mengunci perilakunya, dan tes endpoint di `test_upload_endpoint.py`.
1. Di Koleksi, pengguna memilih berkas PDF atau EPUB.
2. Sistem memeriksa format dan membaca teks.
3. Sistem menyimpan dokumen, bab, dan paragraf, memasukkan ke antrean, dan menampilkan status "sedang dianalisis".
- Format salah: 400 "Format file tidak didukung. Unggah file berformat PDF atau EPUB."
- Tanpa teks: 400 "File tidak berisi teks yang dapat dianalisis."
- Berkas rusak atau gagal simpan: 400 "File tidak dapat dibaca atau gagal disimpan. Coba unggah lagi."
- EPUB berDRM: 400 dengan pesan dari pembaca EPUB.
- Model belum terpasang: 503 "Model analisis belum terpasang di server. Hubungi pengelola sistem."
- Batas tier terlewati: 402 dengan pesan berisi batasnya (halaman, e-book aktif, atau kuota bulan ini beserta tanggal reset); UI menampilkan tautan "Lihat paket". Pemeriksaan sesudah teks terbaca dan sebelum penyimpanan. Memilih beberapa berkas sekaligus mengunggahnya berurutan dan menawarkan membuat seri bila ≥ 2 berhasil.

### F-KOLEKSI (daftar e-book, UC-06)
`GET /documents` (milik pengguna, terbaru dulu). Menampilkan kartu e-book dengan judul, status, dan ringkasan hasil. Belum ada e-book: keadaan kosong dengan ajakan unggah. Hapus: tombol hapus, dialog konfirmasi, lalu `DELETE /documents/{id}` (204). Batal konfirmasi: tanpa perubahan. Gagal hapus: pesan error dan dapat dicoba lagi.

### F-HASIL (UC-03)
`GET /documents/{id}`. Menampilkan rating, rentang usia, persentase konten dewasa, emosi dominan, bobot cerita beserta catatan alasan, dan estimasi waktu bila belum selesai. Halaman memperbarui diri selama status queued atau analyzing. Dokumen tidak ada atau milik orang lain: 404 "Dokumen tidak ditemukan." dengan tombol ke koleksi. Kartu "Rincian rating" (persentase per dimensi dan alasan rating) saat ini placeholder; TIDAK BOLEH diisi sebelum diminta.

### F-SERI (UC-02)
`GET /collections`, `POST /collections` (201), `PUT /collections/{id}`, `DELETE /collections/{id}` (204). Body `{name, document_ids}`: nama 1 sampai 150 karakter (spasi dirapikan), 2 sampai 50 e-book, urutan array = urutan baca. Pengguna membuat seri dari Koleksi (dialog pilih dan urutkan), melihat isi seri, mengubah, atau membubarkan (e-book tetap ada). E-book yang sudah di seri lain dipindahkan dan seri yang menjadi kosong dihapus.
- Seri tidak ditemukan atau milik orang lain: 404 "Koleksi tidak ditemukan."
- E-book dobel: 400 "Satu e-book tidak bisa dimasukkan dua kali."; e-book tidak ada atau bukan milik: 404 "Ada e-book yang tidak ditemukan."
- Nama kosong: "Nama koleksi tidak boleh kosong."

### F-SENSITIVITAS (UC-12)
`GET /sensitivity` (semua tier) mengembalikan `{editable, personal, thresholds, standard}`; `PUT /sensitivity` `{profanity, sexual, violence}` dan `DELETE /sensitivity` (kembali ke standar) khusus High, selain itu 403 "Fitur ini khusus pengguna High Tier.". Tiap nilai 0,1 sampai 0,95 atau null (tidak disamarkan). Halaman menampilkan penggeser per jenis konten dengan pratinjau; non-High melihat halaman terkunci dengan ajakan ke paket. Mode baca memuat `thresholds` dan memakainya untuk Safe Mode; gagal memuat berarti profil standar.

### F-BAYAR (UC-07, UC-08)
Di halaman Berlangganan. `GET /billing/overview` (tier, `paid_tier`, masa berlaku, pemakaian kuota, harga, bank, `provider`: simulated, midtrans, atau unavailable). `POST /billing/checkout` `{kind, plan, quantity, bank}` (201) membuat Virtual Account dan transaksi pending. Daftar riwayat lewat `GET /billing/transactions`; satu transaksi lewat `GET /billing/transactions/{order_id}`; batal lewat `POST .../cancel` (hanya pending, 409 "Hanya pembayaran yang masih menunggu yang bisa dibatalkan."). Mode simulasi: `POST .../simulate-pay` (403 "Simulasi pembayaran tidak tersedia." bila bukan simulasi). Transaksi pending yang lewat `expires_at` otomatis menjadi expired. Setelah paid, tier atau `extra_checks` langsung berlaku dan invoice dikirim.
- Paket lebih rendah dari yang dimiliki: 400 "Kamu sudah memakai paket yang lebih tinggi."
- High membeli analisis tambahan: 400 "Paket High tanpa batas analisis, tidak perlu membeli analisis tambahan."
- Gateway gagal: 502 "Gagal membuat Virtual Account. ...". Transaksi tidak ada atau bukan milik: 404 "Transaksi tidak ditemukan."
- Webhook `/billing/midtrans/notification`: 404 bila kunci Midtrans kosong, 403 "Signature tidak valid.", 400 "Nominal tidak cocok."

### F-BACA (UC-04, UC-05)
`GET /documents/{id}/chapters` dan `GET /documents/{id}/paragraphs` (setiap paragraf memuat `text` polos, `markdown` yang boleh kosong, dan `kind`). Paragraf yang punya `markdown` dirender terformat oleh `ReadingBlock.vue` memakai `lib/markdown.js` (judul sebagai h3 sampai h6, tebal, miring, daftar, kutipan; tautan, gambar, tabel, kode, dan HTML mentah tidak dirender, isi buku dianggap masukan tidak tepercaya); paragraf tanpa `markdown` tampil sebagai teks biasa. Teks per bab dengan pilihan dan navigasi bab. Safe Mode: tombol aktif dan nonaktif. Saat aktif, paragraf seksual di atas ambang disamarkan; mengetuk membukanya; tombol "Samarkan lagi" menutup kembali yang sudah dibuka di bab itu. Berganti bab menyamarkan ulang. Teks status menyebut jumlah paragraf yang disamarkan di bab itu atau bahwa tidak ada yang disamarkan.
Paragraf disamarkan bila skornya mencapai ambang (lebih besar atau sama dengan). Ambang berasal dari `GET /sensitivity` (standar, atau profil personal High); bila gagal dimuat dipakai profil standar bawaan frontend (seksual 0,5). Pilihan Safe Mode (bawaan aktif), ukuran huruf, dan jenis huruf disimpan di `localStorage` kunci `narative_reader` dengan try/catch. Mengganti bab atau mengubah Safe Mode menyamarkan ulang semua paragraf. Logika penyamaran ini hanya ada di frontend dan dikunci oleh tes komponen (`frontend/src/pages/__tests__/ReadingModePage.spec.js`).

### F-JUDUL (UC-19)
`PATCH /documents/{id}` `{title}`. Judul diubah dari halaman hasil. Kosong: "Judul tidak boleh kosong." Lebih dari 255 karakter: ditolak. Batal: judul lama dipakai.

### F-UNDUH (UC-13)
`GET /documents/{id}/export` mengembalikan PDF (lampiran). Khusus High (403 "Fitur ini khusus pengguna High Tier." untuk tier lain, dicek sebelum status). Hanya bila status done (409 "Analisis belum selesai."). Gagal menyusun: 500 "Gagal menyusun PDF. Coba lagi." Isi PDF saat ini: ringkasan rating, rentang usia, persentase, dan teks bersih per bab dengan paragraf sensitif disorot. Rangkuman belum ada di PDF.

### F-RANGKUMAN (UC-09)
`GET /documents/{id}/summary` dan `POST /documents/{id}/summary` (202). POST khusus Middle ke atas (403 "Fitur ini khusus pengguna Middle Tier."); GET untuk tier lebih rendah hanya bila rangkuman sudah pernah dibuat (`summary_status` terisi), selain itu 403. UI Standard menampilkan kartu terkunci dengan tautan "Lihat paket", dan menyembunyikan tombol buat, buat ulang, dan coba lagi.
1. Pengguna membuka halaman rangkuman. Bila belum pernah dibuat, tampil tombol buat rangkuman.
2. Sistem memulai proses latar belakang dan menampilkan kemajuan bab.
3. Setelah selesai, tampil rangkuman keseluruhan dan per bab.
- Analisis belum selesai: 409 "Rangkuman bisa dibuat setelah analisis selesai."
- Kunci Gemini kosong: 503 "Layanan rangkuman belum diatur di server (GEMINI_API_KEY kosong)."
- Gagal: status failed, memanggil ulang melanjutkan bab yang belum selesai.
- Sebagian (partial): hasil tampil dengan catatan "Sebagian bab dirangkum sederhana tanpa AI karena layanan Gemini sedang dibatasi atau menolak teks.", tombol "Lanjutkan dengan AI" (hanya Middle ke atas) dan tiap bab bersumber lokal diberi label "Ringkasan sederhana (tanpa AI)". `GET /summary` mengembalikan `summary_source` per bab.
- Bab tanpa rangkuman: "Rangkuman bab ini tidak dapat dibuat."

### F-TOKOH (UC-10)
`GET /documents/{id}/characters` (`{status, characters, relations}`) dan `POST /documents/{id}/characters` (202). **Sejak 2026-11-01 (R11) deteksi tokoh selalu lewat LLM (9router lebih dulu, Gemini cadangan, lewat `_generate`; sejak R13 tanpa NER), baik otomatis setelah analisis maupun lewat POST; parameter `?ai` dan tombol "Lengkapi biodata dengan AI" dihapus.** Tanpa LLM yang terkonfigurasi POST mengembalikan 409 (R13 butir 9). Bila sebagian panggilan gagal, tokoh dari potongan yang berhasil tersimpan dengan status `partial`; bila semua gagal, status `failed`. Aturan tier sama dengan rangkuman: POST khusus Middle ke atas, GET untuk tier lebih rendah hanya bila `characters_status` terisi. Deteksi otomatis setelah analisis hanya berjalan bila pemilik buku Middle ke atas. Halaman Biodata dan Relasi menampilkan kartu terkunci bagi yang tidak berhak.
1. Belum pernah dideteksi: tombol "Deteksi tokoh". Setelah analisis selesai, deteksi juga berjalan otomatis (LLM, bila ada yang terkonfigurasi).
2. Berjalan: "Sedang mendeteksi tokoh", halaman memperbarui otomatis.
3. Selesai: kartu tokoh terurut dari yang paling sering disebut, berisi foto atau inisial, nama, "Juga disebut" (bila ada), dan deskripsi (siapa tokohnya dan perannya dalam cerita); tanpa label peran dan tanpa rincian lain (R12). Tombol "Lihat relasi tokoh" dan "Deteksi ulang" (mengulang seluruh deteksi).
4. `partial`: tokoh tampil seperti biasa TANPA pemberitahuan di UI (keputusan pemilik proyek 2026-11-01: hasil tetap ditampilkan walau sebagian bab tidak terbaca atau deskripsi memakai kalimat peran; hanya galat krusial yang disampaikan ke pengguna). Penyebabnya hanya dicatat di log backend (peringatan per potongan yang dilewati dan satu peringatan saat deteksi selesai sebagian); status `partial` tetap tersimpan dan dikembalikan API
- Analisis belum selesai: 409 "Tokoh bisa dideteksi setelah analisis selesai."; UI menampilkan "Tokoh bisa dideteksi setelah analisis buku ini selesai."
- Gagal: "Tokoh gagal dideteksi" dan tombol "Coba lagi".
- Tidak ada tokoh: "Tokoh tidak terdeteksi".

### F-RELASI (UC-11)
Data dari endpoint tokoh yang sama. Pilihan "Semua bab" dan per bab dengan tombol sebelumnya dan berikutnya. Graf lingkaran: tokoh berukuran menurut jumlah disebut, garis berketebalan menurut bobot dan berwarna menurut jenis (pasangan merah muda, sahabat hijau, teman biru, keluarga kuning tua, musuh merah putus-putus, kenalan abu-abu bertitik); arahkan kursor atau fokus untuk menyorot tokoh dan garis terkait. Di bawahnya daftar hubungan berbentuk teks. Legenda hanya memuat jenis yang ada, dan catatan bahwa jenis hubungan hanya perkiraan.
- Kurang dari dua tokoh: "Tokoh belum cukup".
- Tidak ada relasi pada pilihan: "Belum ada relasi terdeteksi pada bab ini."

### F-PROFIL
Halaman `/profil` (wajib masuk), tautannya pada nama pengguna di header. Memuat: informasi akun (nama yang bisa diubah, email, tanggal bergabung, paket dan masa berlakunya), pemakaian (analisis bulan ini terhadap batas dan tanggal reset, analisis tambahan, e-book aktif terhadap batas, batas halaman), riwayat pembayaran lengkap (`#riwayat`; transaksi yang menunggu bisa dilanjutkan lewat `CheckoutDialog`), form ganti kata sandi (kata sandi lama, baru, ulangi; minimal 8 karakter dan konfirmasi diperiksa di browser), dan hapus akun (konfirmasi dengan kata sandi, lalu kembali ke beranda). Halaman Berlangganan tidak lagi memuat daftar transaksi, hanya kartu tautan ke `/profil#riwayat` dengan jumlah yang menunggu. Penghapusan akun lewat `services/accounts.py` menghapus e-book (beserta file cover dan foto tokoh), transaksi, kuota, koleksi, profil sensitivitas, dan kode verifikasi untuk email itu secara eksplisit, sehingga hasilnya sama di MySQL dan SQLite. Pesan galat: "Kata sandi lama salah.", "Kata sandi baru harus berbeda dari yang lama.", "Kata sandi salah." Nama pengguna selalu tampil bersama avatar bundar berisi inisial (`UserAvatar.vue`; ikon pengguna bila nama kosong): di header (avatar tetap tampil di layar kecil, nama disembunyikan), di blok pengguna pada sidebar buku (keduanya menautkan ke `/profil`), dan di kepala halaman Profil.

### F-GAMBAR (UC-17, UC-18)
Di halaman Hasil analisis (cover) dan halaman Tokoh (foto). Router `images` di bawah `/documents`: `PUT`, `GET`, `DELETE` `/{id}/cover` dan `/{id}/characters/{character_id}/photo`. Mengubah (PUT, DELETE) hanya High (403 "Fitur ini khusus pengguna High Tier."); melihat (GET) untuk pemilik e-book tier mana pun. Gambar: JPG, PNG, atau WebP yang dikenali dari isi file, maksimum 2 MB; 400 "Format gambar tidak didukung. Gunakan JPG, PNG, atau WebP.", 400 "File gambar kosong.", 413 "Ukuran gambar maksimal 2 MB.", 404 "Gambar belum diatur." dan 404 "Tokoh tidak ditemukan.". Disimpan di `UPLOAD_DIR/images/` dengan nama acak; mengganti, mengembalikan ke bawaan, menghapus e-book, dan mendeteksi ulang tokoh menghapus file lama. `DocumentOut.has_cover` dan `CharacterOut.has_photo` menunjukkan ada tidaknya gambar. Frontend memuat gambar lewat `AuthImage.vue` (permintaan berisi token, ditampilkan dari blob) dan mengubahnya lewat `PictureControls.vue` (pemeriksaan 2 MB di browser, tombol kembalikan ke bawaan, tautan ke paket bila bukan High). Cover tampil di kartu buku (koleksi) dan halaman Hasil analisis; foto tampil sebagai avatar tokoh. Mendeteksi ulang tokoh membuat tokoh baru sehingga foto lama hilang.

## 10. Pesan error

Backend mengembalikan `detail` berupa teks Bahasa Indonesia; frontend menampilkannya apa adanya atau memakai teks umum. Teks TIDAK BOLEH membocorkan detail teknis, jejak stack, atau rahasia. Pesan yang sudah ditulis di bagian 6, 8, dan 9 dipakai persis.

| Konteks | Status | Pesan |
|---|---|---|
| Belum login | 401 | "Silakan masuk terlebih dahulu." |
| Token kedaluwarsa | 401 | "Sesi berakhir. Silakan masuk lagi." |
| Token tidak valid | 401 | "Sesi tidak valid. Silakan masuk lagi." |
| Akun tidak ditemukan atau tidak aktif | 401 | "Akun tidak ditemukan atau tidak aktif." |
| Dokumen tidak ada atau bukan milik pengguna | 404 | "Dokumen tidak ditemukan." |
| Nama kosong | 422 | "Nama tidak boleh kosong." |
| Kata sandi terlalu panjang | 422 | "Kata sandi terlalu panjang." |
| Judul kosong | 422 | "Judul tidak boleh kosong." |
| Batas tier terlewati saat unggah | 402 | Pesan batas halaman, e-book aktif, atau kuota (bagian 9 F-UNGGAH) |
| Fitur khusus High | 403 | "Fitur ini khusus pengguna High Tier." |
| Fitur khusus Middle ke atas | 403 | "Fitur ini khusus pengguna Middle Tier." |
| Koleksi tidak ada atau bukan milik | 404 | "Koleksi tidak ditemukan." |
| Transaksi tidak ada atau bukan milik | 404 | "Transaksi tidak ditemukan." |

Kegagalan jaringan atau kesalahan tidak dikenal di frontend: pesan umum yang menyuruh pengguna mencoba lagi, tanpa detail teknis.

## 11. Lingkungan localhost

- Database: MySQL 8 lokal (`python -m app.db.db_setup` membuat database dan menerapkan migrasi). SQLite hanya untuk uji cepat.
- Backend FastAPI di port 8000 (`python -m uvicorn app.main:app --reload`), dokumentasi di `/docs`. Frontend Vite di port 5173, memanggil backend lewat `VITE_API_URL` (bawaan `http://localhost:8000`). CORS dari `CORS_ORIGINS`.
- Environment backend (`backend/.env`, jangan di-commit; contoh tanpa nilai di `backend/.env.example`): `DATABASE_URL`, `SECRET_KEY`, `ACCESS_TOKEN_MINUTES`, `MODEL_DIR`, `UPLOAD_DIR`, `CORS_ORIGINS`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL`, `GEMINI_CHARACTER_MODEL`, `GEMINI_MIN_INTERVAL`, `ROUTER_BASE_URL`, `ROUTER_API_KEY`, `ROUTER_MODEL`, `ROUTER_TIMEOUT`, `CHARACTER_PARALLEL`, `SECONDS_PER_PARAGRAPH`, `DEV_UNLOCK_ALL_TIERS`, `MIDTRANS_SERVER_KEY`, `MIDTRANS_IS_PRODUCTION`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `FRONTEND_URL`, `DOCUMENT_PARSER` (`legacy` bawaan atau `markdown`). Perintah bantu `python -m app.tools.atur_tier email free|middle|high` mengubah tier akun. `python -m app.tools.compare_parsers buku1.pdf buku2.epub` membandingkan parser lama dan Markdown pada berkas yang diberikan.
- Pustaka tambahan di luar `requirements.txt` untuk model: `torch` (CPU), `transformers`, `peft`, `sentencepiece`, `scikit-learn`, serta `protobuf` dan `tiktoken` untuk tokenizer NER.
- Tes otomatis: `python -m pip install -r requirements-dev.txt` lalu `python -m pytest` dari folder `backend` (SQLite sementara, email dan Gemini di-mock; tidak memerlukan MySQL atau model).
- Tes frontend: `npm run test` dari folder `frontend` (vitest, jsdom, API di-mock; tidak memerlukan backend).
- Perangkat pengembang: Windows (cmd), RAM 8 GB tanpa GPU khusus. TIDAK BOLEH menambah komponen yang membutuhkan GPU atau RAM besar (misalnya LLM lokal).
- Berkas model, `.env`, dan direktori unggahan masuk `.gitignore`.

## 12. Persyaratan non-fungsional untuk prototipe

- Kata sandi di-hash (bcrypt). Rahasia dan kunci API hanya dari environment, TIDAK BOLEH terekspos ke client atau log (NRF-03, NRF-05).
- Isolasi data antar pengguna (bagian 4).
- Membaca data hasil, daftar, tokoh, dan relasi dari basis data merespons dalam 5 detik pada kondisi normal (NRF-01). Interaksi UI tidak lebih dari 2 detik di luar proses panjang (NRF-02).
- Proses panjang (analisis, rangkuman, tokoh) berjalan di latar belakang dengan status yang terlihat. Kegagalan satu dokumen tidak menjatuhkan sistem (NRF-08). Hasil yang sudah berhasil tetap tersimpan walau sebagian gagal.
- Rangkuman disimpan agar tidak diproses ulang (NRF-09).
- Mendukung dokumen bahasa Indonesia dan Inggris (NRF-10).
- Pesan error jelas dan berbahasa Indonesia, dengan indikator memuat pada unggah, proses, dan pemuatan data (NRF-07).
- Layout responsif untuk desktop dan mobile; tanpa scroll horizontal pada lebar 390 px; setiap keadaan (memuat, kosong, gagal, tidak ditemukan) punya tampilan sendiri (NRF-06).
- Struktur berlapis (api, services, ml, db) dan migrasi Alembic untuk pemeliharaan (NRF-15).

## 13. Undecided

Item di sini TIDAK BOLEH diimplementasikan berdasarkan asumsi. Angkat saat Plan mode dan tunggu keputusan pemilik proyek.

| # | Hal | Keterangan |
|---|---|---|
| U1 | Memisahkan analisis inti dari Gemini | Usulan: status done setelah penilaian lokal, bobot Gemini menyusul di latar belakang dan menyempurnakan bobot dan rating. Mengubah perilaku rating dan perlu dicatat di SRS. Belum disetujui |
| U2 | Penyedia LLM ganda dan antrean tahan lama | Usulan urutan: Gemini, Groq, Cerebras, base URL kustom yang kompatibel OpenAI (untuk demo saja), lalu rangkuman ekstraktif lokal. Belum disetujui. Perlu keputusan apakah bobot cerita menunggu Gemini agar skala konsisten |
| U3 | Biodata tokoh digabung dalam satu atau dua panggilan LLM | Sebagian sudah ada di kode (satu permintaan per buku, hanya lewat tombol, bagian 7), tanpa pemulihan entri rusak. Perlu persetujuan resmi dan keputusan pemulihan |
| U4 | Penggabungan nama panggilan tokoh dan analisis sifat, profesi, peran dalam cerita | Sebagian sudah ada di kode: aturan awalan, LLM dari sekitar 3 kutipan per tokoh, kolom baru (migrasi 0011). Perlu persetujuan resmi dan revisi SRS UC-10. Tombol gabung tokoh manual hanya bila diminta |
| U5 | ~~Penegakan tier terhadap fitur dan penggunaan Gemini~~ | DIPUTUSKAN: matriks tier di 13A R2 dan Gemini untuk semua tier di R3. Menunggu implementasi |
| U6 | ~~Verifikasi email saat registrasi~~ | SELESAI: kode verifikasi 6 angka, lihat bagian 6 dan F-AUTH |
| U7 | Gemini berbayar (Tier 1) | Bergantung pada ketersediaan metode pembayaran pemilik proyek |
| U8 | Isi PDF unduhan | SRS meminta rangkuman di PDF; kode belum. Belum diputuskan |
| U9 | Rincian per dimensi dan alasan rating (UC-03) | Kartu masih placeholder. Belum diputuskan sumber teks alasan rating |
| U10 | Ambang rating dan Safe Mode | Berlaku seperti bagian 7 sampai SRS direvisi; TIDAK BOLEH diubah tanpa diminta |
| U11 | ~~Percobaan ulang rangkuman setelah penolakan keamanan~~ | SELESAI: digantikan 13A R4, lihat bagian 7 |

## 13A. Aturan ditetapkan, belum diimplementasikan

Keputusan pemilik proyek (2026-10-25) untuk siklus pengembangan ulang per irisan. Bagian 0 sampai 12 menggambarkan kode saat ini; bagian ini menggambarkan target. Setiap butir berstatus BELUM sampai dikerjakan lewat siklus: aturan, tes yang gagal, implementasi, verifikasi, sinkron dokumen. Setelah sebuah irisan selesai, isinya dipindahkan ke bagian yang sesuai dan dihapus dari sini.

### R1. Registrasi dengan kode verifikasi email. Status: SELESAI (2026-10-25)
Diimplementasikan dan dipindahkan ke bagian 5, 6, dan 9 (F-AUTH). Tes: `backend/tests/test_register_verification.py`. Belum teruji: pengiriman email lewat SMTP sungguhan dan tampilan UI di browser.

### R2. Matriks tier yang ditegakkan di server. Status: SEBAGIAN SELESAI (2026-10-25)
Selesai dan dipindahkan ke bagian 3, 9 (F-RANGKUMAN, F-TOKOH, F-UNDUH, F-SENSITIVITAS), dan 10: rangkuman, tokoh, relasi (Middle ke atas), PDF dan profil sensitivitas (High), hasil lama tetap terlihat, tier kedaluwarsa dianggap Standard, deteksi tokoh otomatis hanya Middle ke atas. Tes: `backend/tests/test_tier_matrix.py`, `backend/tests/test_upload_limits.py`.

Masih menunggu:
- Rincian rating (UC-03) khusus Middle ke atas, berlaku saat kartunya dibangun (sekarang placeholder tanpa endpoint).

### R3. Gemini untuk semua tier. Status: keputusan, tidak perlu perubahan kode
Gemini dipakai untuk bobot cerita, rangkuman, dan biodata tokoh AI pada semua tier. U5 bagian "Free tidak memakai Gemini" ditutup (tidak jadi). Ketahanan terhadap batas kuota Gemini (RPM, harian) tetap U1 dan U2 dan dicari pemilik proyek; tidak dikerjakan agen sebelum disetujui.

### R5. Aturan pembayaran. Status: SELESAI (2026-10-27)
Diimplementasikan dan dipindahkan ke bagian 4 dan 9 (F-BAYAR). Tes: `backend/tests/test_billing.py` (kelas `TestSimulationOnlyOnLocalhost`, `TestLateSettlement`, dan tes kenaikan paket). Rincian aturan:
- Naik dari Middle ke High saat Middle masih berlaku: masa High dimulai dari tanggal berakhir Middle dan ditambah 30 hari, sehingga sisa hari Middle tidak hangus. Berlaku juga untuk perpanjangan paket yang sama (sudah begitu).
- Notifikasi settlement Midtrans yang datang setelah pesanan kedaluwarsa atau dibatalkan tetap diterapkan (uang sudah diterima). Sudah begitu; tinggal dikunci dengan tes.
- Mode simulasi pembayaran hanya hidup bila `MIDTRANS_SERVER_KEY` kosong DAN semua alamat di `CORS_ORIGINS` adalah localhost, 127.0.0.1, atau [::1]. Bila kunci kosong tetapi asal bukan lokal, `provider` menjadi `unavailable`: checkout ditolak 503 "Pembayaran belum tersedia.", simulate-pay 403, dan `GET /billing/overview` melaporkan `unavailable`.

### R6. Ganti cover (UC-17) dan foto tokoh (UC-18). Status: SELESAI (2026-10-27)
Diimplementasikan dan dijelaskan di bagian 9 (F-GAMBAR). Tes: `backend/tests/test_images.py`, `frontend/src/components/__tests__/PictureControls.spec.js`, `AuthImage.spec.js`. Aturan:
- Hanya High yang boleh mengganti dan mengembalikan ke bawaan (403 "Fitur ini khusus pengguna High Tier."). Pemilik e-book dari tier mana pun tetap bisa melihat gambar yang sudah ada.
- Endpoint: `PUT`, `GET`, `DELETE` `/documents/{id}/cover` dan `/documents/{id}/characters/{character_id}/photo`. PUT menerima `multipart/form-data` dengan field `file`. DELETE mengembalikan 204 (juga bila belum ada gambar). GET mengembalikan 404 bila belum ada gambar atau bukan milik pengguna.
- Jenis gambar ditentukan dari isi file, bukan dari ekstensi atau `Content-Type`: JPG, PNG, atau WebP. Lainnya (termasuk SVG) 400 "Format gambar tidak didukung. Gunakan JPG, PNG, atau WebP." Maksimum 2 MB (413 "Ukuran gambar maksimal 2 MB."). File kosong 400 "File gambar kosong."
- Disimpan di `UPLOAD_DIR/images/` dengan nama acak. Mengganti, mengembalikan ke bawaan, menghapus e-book, atau mendeteksi ulang tokoh menghapus file lama dari disk.
- Skema: kolom baru `documents.cover_path` (VARCHAR 255 NULL), migrasi 0018. `characters.photo_path` sudah ada. Respons `DocumentOut` dan `CharacterOut` memuat `has_cover` dan `has_photo`.
- Dikecualikan dari batas: gambar tidak memakai kuota analisis. Isi gambar tidak didekode (tidak ada Pillow), jadi file yang berawalan benar tetapi rusak tetap tersimpan dan gagal tampil di browser.

### R7. Profil pengguna. Status: SELESAI (2026-10-28)
Diimplementasikan dan dijelaskan di bagian 9 (F-PROFIL). Tes: `backend/tests/test_profile.py`, `frontend/src/pages/__tests__/ProfilPage.spec.js`. Aturan:
- Halaman `/profil` (wajib masuk), tautannya di navbar. Isinya: akun (nama, email, tanggal bergabung, paket dan masa berlakunya), pemakaian (sisa analisis bulan ini, analisis tambahan, jumlah e-book dibanding batas, tanggal reset kuota), riwayat pembayaran lengkap (lanjutkan atau batalkan yang masih menunggu), ubah nama, ganti kata sandi, hapus akun.
- Riwayat pembayaran dipindahkan seluruhnya dari halaman Berlangganan ke Profil. Berlangganan tetap menampilkan ringkasan pemakaian dan tempat membeli, dan tautan `#riwayat` kini mengarah ke `/profil#riwayat`.
- Data dibaca dari `GET /auth/me` (ditambah `created_at`), `GET /billing/overview`, dan `GET /billing/transactions` yang sudah ada.
- `PATCH /auth/me` `{name}`: nama dirapikan seperti saat daftar (1 sampai 100 karakter, spasi ganda dirapikan, 422 bila kosong), membalas `UserOut`.
- `PUT /auth/me/password` `{current_password, new_password}` membalas 204. Kata sandi lama salah: 400 "Kata sandi lama salah.". Kata sandi baru sama dengan yang lama: 400 "Kata sandi baru harus berbeda dari yang lama.". Kata sandi baru 8 sampai 72 byte, seperti saat daftar. Token login yang sudah terbit tetap berlaku (JWT tanpa pencabutan).
- `DELETE /auth/me` `{password}` membalas 204. Kata sandi salah: 400 "Kata sandi salah.". Menghapus akun, seluruh e-book beserta isinya (hapus berantai), file cover dan foto tokoh di disk, transaksi, kuota, koleksi, profil sensitivitas, dan sisa kode verifikasi untuk email itu. Paket berbayar yang masih berlaku hangus tanpa pengembalian dana. Token lama menjadi tidak valid (401). Email yang sama bisa mendaftar lagi.
- Semua endpoint di atas butuh login (401) dan hanya berlaku untuk akun sendiri. Tidak ada pembatasan percobaan kata sandi (sama seperti login).

### R8. Email bermerek. Status: SELESAI (2026-10-28)
Diimplementasikan (`services/email_templates.py`, `mailer.send(..., html)`, `billing.send_instructions`). Tes: `backend/tests/test_email_templates.py` (56 termasuk logo) dan `backend/tests/test_mailer.py`. Belum teruji: tampilan di klien email sungguhan (Gmail, Outlook, aplikasi HP). Aturan:
- Tiga email, masing-masing dikirim sebagai multipart: `text/plain` (tetap lengkap) dan `text/html`.
  1. **Kode verifikasi** (subjek "Kode verifikasi NARAtive"): sapaan, kode 6 angka dalam kotak besar, masa berlaku (menit), peringatan untuk mengabaikan bila bukan pemilik.
  2. **Instruksi pembayaran** (BARU, subjek "Selesaikan pembayaran NARAtive {order_id}"): dikirim sekali saat checkout berhasil dibuat; memuat item, total, bank dan nomor VA, batas waktu, langkah singkat membayar, dan tombol ke `/profil#riwayat`. Pada mode simulasi diberi catatan bahwa nomor VA hanya contoh. Tidak dikirim bila pembuatan VA gagal atau dibuka ulang.
  3. **Invoice** (subjek "Invoice NARAtive {order_id}", tetap): nomor pesanan, item, total, bank dan VA, waktu bayar, masa aktif paket (hanya untuk upgrade), tombol ke `/profil#riwayat`.
- Tampilan HTML: tata letak tabel dengan gaya inline (kompatibel klien email), lebar maksimum 560 px, latar krem, kartu putih, warna navy, kuning, dan krem seperti aplikasi, teks pratinjau tersembunyi, dan footer "Email ini dikirim otomatis, mohon tidak dibalas."
- Logo NARAtive (`backend/app/assets/email-logo.png`, salinan `frontend/src/assets/logo.png` yang dipotong dan dikecilkan menjadi 520 x 163 px, di bawah 60 KB) berada di bagian atas kartu. Logo dilampirkan sebagai gambar inline (`multipart/related`, `Content-ID` `narative-logo`, dirujuk `cid:narative-logo`), bukan ditautkan dari alamat publik, sehingga tampil tanpa perlu server publik. Teks alternatif "NARAtive" menggantikannya bila klien memblokir gambar. Bila file logo hilang, email tetap terkirim tanpa lampiran dan galatnya dicatat di log. Email versi teks tidak berubah.
- Semua nilai dari pengguna (nama, dan lainnya) di-escape HTML. Tidak ada skrip, formulir, atau gambar eksternal (satu-satunya gambar adalah logo inline di atas).
- Waktu di email ditulis WIB (UTC+7), tidak lagi UTC. Uang ditulis "Rp 29.000".
- Pengaturan baru `FRONTEND_URL` (bawaan `http://localhost:5173`) menjadi dasar tautan di email; garis miring di ujung diabaikan.
- Tanpa `SMTP_HOST`, email tetap hanya dicatat di log (versi teks).

### R9. Parser Markdown dan OCR. Status: IRISAN A KODE SELESAI (2026-10-30), bawaan `legacy` menunggu perbandingan; IRISAN B BELUM
Irisan A diimplementasikan. Tes: `backend/tests/test_markdown_storage.py`, `test_markdown_utils.py`, `test_epub_markdown.py`, `test_pdf_markdown.py`, `test_document_reader.py`, `test_compare_parsers.py`, `frontend/src/lib/__tests__/markdown.spec.js`, `frontend/src/pages/__tests__/ReadingModePage.spec.js`. Modul: `app/extraction/markdown_utils.py`, `epub_markdown.py`, `pdf_markdown.py`, `reader.py`, `app/tools/compare_parsers.py`. Langkah yang tersisa untuk menjadikan `markdown` bawaan: pemilik proyek menjalankan `compare_parsers` pada beberapa buku sungguhan (PDF biasa, PDF berkolom, EPUB), membandingkan bab dan kebocoran header, menjalankan analisis pada buku yang sama dengan kedua parser untuk melihat pergeseran skor, lalu menyetujui. Keputusan awal:
Latar: pemilik proyek ingin menutup masalah limit Gemini dan PDF yang sulit dibaca. Keputusan:
- **9router / penyedia LLM kompatibel OpenAI:** DITUNDA sampai pemilik proyek selesai mempelajarinya; belum ada kode. Peran Gemini sesudahnya belum diputuskan. U1 dan U2 tetap Undecided.
- **Dua irisan:** A = Markdown (sinkron seperti sekarang); B = unggahan asinkron dengan progres dan OCR. B dikerjakan setelah A.
- **Paket:** `pymupdf==1.28.2` dan `pymupdf4llm==1.28.2` disematkan (menarik `pymupdf_layout` dan `onnxruntime`, sekitar 100 MB). `pymupdf4llm` 2.0 hanyalah cangkang kosong (kodenya pindah ke pymupdf 2.x), jangan dipakai. Lisensi `pymupdf_layout` belum diverifikasi; cek sebelum rilis komersial.
- **Temuan percobaan:** pymupdf4llm membaca judul dari ukuran huruf (`# **Bab 1**`) dan menjaga urutan baca dua kolom, tetapi TIDAK membuang header berulang dan nomor halaman; kecepatannya sama dengan parser sekarang (sekitar 0,3 detik per halaman); PDF scan tanpa Tesseract menghasilkan teks kosong tanpa galat. Karena itu pembersih yang ada tetap dipakai.
- **Markdown tidak menghemat token** (tanda `#` dan `**` menambah token). Penghematan datang dari pembersihan teks. Gemini, rangkuman, tokoh, analisis lokal, dan PDF hasil tetap memakai teks polos.

**Irisan A, aturan:**
1. Tabel `paragraphs` mendapat kolom `markdown` (TEXT, boleh kosong) dan `kind` (VARCHAR 8, bawaan `p`; nilai `p`, `h`, `li`, `quote`), migrasi 0019. Kolom `text` tetap teks polos dan diturunkan dari Markdown oleh satu fungsi `plain_text()`. Dokumen lama: `markdown` kosong dan tampil sebagai teks biasa; berkas asli tidak disimpan sehingga tidak bisa dikonversi ulang.
2. `GET /documents/{id}/paragraphs` menambah `markdown` dan `kind`.
3. Pengaturan `DOCUMENT_PARSER` (`auto`, `legacy`, atau `markdown`; nama lain berarti `legacy`). **Bawaan `auto` (2026-10-31): EPUB memakai `markdown`, PDF memakai `legacy`.** Dasarnya perbandingan pada buku sungguhan: EPUB nyaris identik dengan parser lama (selisih 4 karakter) dan membawa format; PDF `markdown` memecah paragraf di setiap pergantian baris (median 118 karakter lawan 848) dan salah menandai dialog berawalan ” sebagai butir daftar, sehingga skor bisa bergeser (U10). PDF pindah ke `markdown` hanya setelah perbaikan paragraf umum (R9 irisan A2) dan persetujuan pemilik proyek. `legacy` dan `markdown` memaksa satu parser untuk semua format. `markdown` bila gagal atau menghasilkan hasil kosong otomatis kembali ke `legacy` dan dicatat di log. Alat `app/tools/compare_parsers.py` membandingkan keduanya pada berkas yang diberikan (jumlah dan judul bab, jumlah paragraf, kebocoran header, nomor halaman).
4. PDF: `pymupdf4llm.to_markdown(page_chunks=True)` per halaman dari memori, lalu pembersih yang ada pada tingkat blok (header berulang pada buku 8 halaman ke atas, nomor halaman di tepi halaman, huruf kapital awal, kata terpotong, URL, ligatur). Paragraf yang terputus di pergantian halaman disambung.
5. EPUB: parser HTML yang ada dilengkapi agar menghasilkan Markdown (judul, tebal, miring, daftar, kutipan; gambar dibuang, tabel diratakan menjadi teks). Pengemasan paragraf pendek ke blok sampai 900 karakter tetap (blok EPUB boleh memuat beberapa paragraf Markdown yang dipisah baris kosong).
6. Deteksi bab berurutan: daftar isi PDF, baris "Bab/Chapter" dan sejenisnya, judul Markdown tingkat 1 dan 2, pemecahan per 20 halaman. Judul bab tidak ikut menjadi paragraf. Tiga judul berturutan atau lebih dianggap daftar isi dan dilewati. Teks sebelum judul pertama menjadi bab "Pembuka"; tanpa judul sama sekali: "Isi naskah".
7. Paragraf lebih dari 900 karakter dipecah di akhir kalimat; tanda tebal atau miring yang terpotong ditutup dan dibuka lagi pada potongan berikutnya sehingga tidak ada tanda yang menggantung. Fragmen di bawah 20 karakter dibuang seperti sekarang.
8. Mode baca merender Markdown dengan `markdown-it` (`html: false`), hanya judul (dipetakan ke tingkat 3 sampai 6), tebal, miring, daftar, dan kutipan. Tautan dan gambar TIDAK dirender (hanya teksnya); HTML mentah dari isi buku tampil sebagai teks. Safe Mode tidak berubah: bayangan buram memakai `text` polos, Markdown dirender setelah paragraf dibuka. Blok tanpa `markdown` dirender seperti sekarang.
9. Risiko yang diakui: pemotongan paragraf berubah sehingga skor analisis pada buku yang sama bisa bergeser (rating dan ambang tidak boleh diubah tanpa diminta, U10). Karena itu PDF tetap `legacy` pada bawaan `auto` sampai perbandingan skor selesai.

**Irisan A2, aturan perbaikan PDF markdown (2026-10-31):** perbaikan berlaku umum untuk semua PDF, bukan untuk satu buku.
1. **Pengemasan:** paragraf `p` berurutan dalam satu bab dikemas menjadi blok sampai 900 karakter seperti EPUB (`_pack_blocks`), sehingga granularitas skor mirip parser lama. Judul, daftar, dan kutipan memotong kemasan dan tidak diubah.
2. **Dialog yang salah dibaca sebagai daftar:** deret butir daftar berurutan (satu atau lebih) yang memuat setidaknya satu butir berawalan tanda kutip (`"`, `“`, `”`, `'`, `‘`, `’`) dan tidak memakai penanda angka (`1.`, `2)`) dianggap dialog dan seluruh butirnya menjadi paragraf `p`. Daftar bernomor, dan daftar tanpa butir berawalan tanda kutip, tetap `li`.
3. **Kalimat terputus antarblok:** bila paragraf tidak berakhir tanda akhir kalimat (`.!?"”'’:;)`) dan paragraf berikutnya dimulai huruf kecil, keduanya disambung (aturan yang sama dengan pergantian halaman). Bila paragraf pertama berakhir huruf lalu `-`, tanda hubung dibuang dan kedua bagian dirapatkan tanpa spasi.
4. **Batas yang diakui:** teks ganda akibat salah baca mesin layout pymupdf4llm pada halaman tertentu tidak dideteksi; PDF `markdown` tetap bukan bawaan sampai pergeseran skor diukur dan disetujui.

**Prinsip arah (2026-10-31):** semua tier menerima semua jenis PDF (teks, scan, campuran, berkolom); tier hanya membedakan batas halaman, kuota, dan e-book aktif yang sudah ada di matriks tier (free 50 halaman, middle 300, high tanpa batas), tidak diubah. Perbaikan parser dan OCR harus umum, tidak disetel ke satu buku, dan diuji dengan korpus PDF buatan kode yang beragam.

**Irisan B (ditunda, setelah A):** unggahan langsung selesai, pembacaan berjalan di latar dengan progres per halaman, status gagal dengan alasan (DRM, tanpa teks, mutu OCR buruk), aturan kuota untuk kegagalan, OCR Tesseract bahasa `ind` dan `eng` pada halaman yang tidak punya teks (Tesseract dan paket bahasa dipasang terpisah: Windows lewat installer, Docker lewat apt), batas halaman per tier sebelum OCR, pemeriksaan mutu hasil OCR.

### R10. Penyedia LLM 9router. Status: KODE SELESAI dan DICOBA LANGSUNG 2026-10-31
Tes: `backend/tests/test_router_client.py` (62), alat tiruan `backend/tests/router_fake.py`. Kode: `_generate`, `_router_generate`, `_generate_gemini` di `services/summarizer.py`.
Pemilik proyek menyiapkan 9router (endpoint kompatibel OpenAI `/chat/completions`). Menjawab sebagian U2; Groq dan Cerebras sebagai penyedia tambahan tidak dikerjakan.
1. **Peran:** 9router UTAMA, Gemini CADANGAN, untuk semua tugas LLM (rangkuman bab, rangkuman keseluruhan, bobot cerita, biodata tokoh). Satu titik: `_generate` di `services/summarizer.py`; pemanggil tidak berubah.
2. **Konfigurasi:** `ROUTER_BASE_URL` (contoh `https://host/v1`), `ROUTER_API_KEY`, `ROUTER_MODEL` (nama model atau combo di 9router), `ROUTER_TIMEOUT` (detik, bawaan 120). 9router dianggap aktif hanya bila ketiganya (base URL, kunci, model) terisi. Kunci hanya di `backend/.env`, tidak pernah di kode, log, atau pesan galat.
3. **`configured()`** benar bila 9router ATAU Gemini aktif. Tanpa keduanya, perilaku lama (503 "Layanan rangkuman belum diatur").
4. **Alur satu permintaan:** coba 9router bila aktif dan tidak sedang ditahan; bila gagal, coba Gemini bila aktif (dengan seluruh perilaku Gemini yang sudah ada: model cadangan, penahanan kuota, percobaan ulang); bila Gemini tidak aktif, galat 9router diteruskan.
5. **Dianggap gagal (beralih ke Gemini):** HTTP 429, 5xx, 401/403 (kunci salah), 404 (model tidak ada), jaringan putus atau waktu habis, balasan tanpa teks, `finish_reason` `content_filter`, dan, bila diminta keluaran JSON, balasan yang bukan JSON. Kegagalan yang menandakan layanan bermasalah (429, 5xx, 401/403/404, jaringan, waktu habis) menahan 9router selama 60 detik (permintaan berikutnya langsung ke Gemini), lalu dicoba lagi. Kegagalan yang bergantung pada isi permintaan (`content_filter`, balasan kosong, bukan JSON) hanya mengalihkan permintaan itu dan TIDAK menahan 9router. Selama ditahan dan Gemini tidak aktif, galatnya SummaryError yang menyebut 9router. Tidak ada percobaan ulang ke 9router pada permintaan yang sama (Gemini yang menjadi percobaan ulangnya).
6. **Keluaran JSON (rangkuman kelompok, bobot, tokoh):** 9router tidak dijamin mendukung skema, jadi permintaan memakai `response_format: {"type": "json_object"}` dan skema ditulis ke dalam instruksi sistem sebagai teks. Pagar kode ```` ``` ```` di balasan dibuang sebelum dianggap JSON.
7. **Format permintaan:** `POST {base}/chat/completions`, header `Authorization: Bearer <kunci>`, `messages` berisi `system` dan `user`, `temperature`, `max_tokens`, dan `"stream": false` WAJIB (9router membalas dengan stream SSE bila tidak diminta lain, ditemukan pada uji langsung). Model penalaran di 9router menghitung token berpikir ke `max_tokens`; batas yang terlalu kecil menghasilkan balasan kosong. Tanpa pengaturan keamanan Gemini.
8. **Tidak ada jeda antarpermintaan** untuk 9router (`GEMINI_MIN_INTERVAL` hanya untuk Gemini).
9. **Privasi:** teks buku yang sudah lolos penyaringan (paragraf seksual diganti penanda) dapat sampai ke model apa pun di balik 9router. Catatan README, bukan UI. Aturan penanda tidak berubah.
10. **Log:** satu baris per permintaan seperti Gemini, dengan nama penyedia (`9router` atau `Gemini`), tujuan, model, hasil, dan lama; peralihan dicatat sebagai peringatan.
11. **Skala bobot cerita** bisa bergeser bila model berbeda menilai (U2): diterima, bobot cerita hanya 0,7 dari bobot dan U10 tidak berubah.
12. **Tes:** tidak memanggil 9router atau Gemini sungguhan (aturan bagian 6).

### R4. Setiap bab yang punya teks harus punya rangkuman. Status: SELESAI (2026-10-26)
Diimplementasikan dan dipindahkan ke bagian 5, 7, dan 9 (F-RANGKUMAN). Tes: `backend/tests/test_summary.py`, `backend/tests/test_summary_local.py`, `frontend/src/pages/__tests__/SummaryPage.spec.js`. Belum teruji dengan Gemini nyata: apakah penanda pengganti benar-benar meloloskan bab yang tadinya ditolak.

### Urutan irisan
1. R1 registrasi dengan verifikasi (kerangka tes pytest disiapkan di irisan ini karena repositori belum punya tes).
2. R2 matriks tier dan penegakan batas unggah, termasuk tes.
3. Irisan berikutnya (mode baca, rangkuman, tokoh dan relasi, seri, pembayaran, PDF) diperiksa satu per satu terhadap bagian 0 sampai 12 dan R2.

### R14. Lupa kata sandi dan logo halaman masuk. Status: KODE SELESAI (2026-11-02)
Keputusan pemilik proyek: pengguna yang lupa kata sandi harus bisa mengaturnya ulang dari halaman masuk. Polanya mengikuti pendaftaran (kode 6 angka lewat email). Aturan:
1. **Tabel `password_resets`** (migrasi 0020): `id`, `email` (VARCHAR 255, unik, indeks), `code_hash` (VARCHAR 64, HMAC-SHA256 dengan `SECRET_KEY` seperti pendaftaran), `expires_at`, `attempts` (bawaan 0), `last_sent_at`. Satu rekaman per email.
2. **`POST /auth/password/forgot`** `{email}` → 202 `{email, expires_in: 600, resend_after: 60}` SELALU, baik email terdaftar maupun tidak (tidak membocorkan keberadaan akun lewat respons). Bila akun ada dan aktif dan sudah lewat jeda 60 detik sejak kiriman terakhir: kode 6 angka baru (berlaku 10 menit, percobaan diset 0, kode lama tidak berlaku) dan email "Atur ulang kata sandi NARAtive" dikirim. Dalam jeda 60 detik: tidak mengirim ulang, tetap 202, kode lama tetap berlaku. Akun tidak ada atau tidak aktif: tidak ada rekaman dan tidak ada email. Email dinormalkan ke huruf kecil. Format email salah: 422.
3. **`POST /auth/password/reset`** `{email, code, new_password}`; `code` tepat 6 angka, `new_password` 8 sampai 72 karakter dengan aturan yang sama dengan pendaftaran (maksimal 72 byte). Berhasil: 200 dengan `TokenOut` yang sama dengan masuk (pengguna langsung masuk), kata sandi diganti, rekaman dihapus (kode tidak bisa dipakai dua kali). Gagal: 400 "Kode salah atau sudah kedaluwarsa. Minta kode baru." untuk semua kasus: rekaman tidak ada, kedaluwarsa, kode salah, atau akun sudah hilang atau tidak aktif (pesan sama agar keberadaan akun tidak bocor). Tiap kode salah menambah `attempts`; percobaan ke-5 menghapus rekaman dan mengembalikan 429 "Terlalu banyak percobaan. Minta kode baru." Kode atau kata sandi yang bentuknya tidak sah ditolak 422 oleh skema dan tidak menambah percobaan.
4. **Email** `password_reset_email(name, code, minutes)`: subjek "Atur ulang kata sandi NARAtive", memuat kode, masa berlaku, dan "Jika bukan kamu yang meminta, abaikan email ini; kata sandimu tidak berubah." Versi HTML memakai kerangka yang sama dengan email lain. Tanpa `SMTP_HOST`, email hanya dicatat di log seperti sekarang.
5. **Frontend:** tautan "Lupa kata sandi?" di bawah kolom kata sandi pada halaman Masuk menuju `/lupa-sandi` (nama rute `forgot`, hanya untuk tamu, memakai `AuthPage` mode `lupa`). Langkah 1: kolom email dan tombol "Kirim kode". Langkah 2: pesan "Jika email terdaftar, kode 6 angka sudah dikirim ke {email}. Kode berlaku 10 menit.", kolom kode, kolom kata sandi baru (tampilkan atau sembunyikan, minimal 8 karakter), tombol "Atur ulang kata sandi", "Kirim ulang kode" dengan hitung mundur 60 detik, dan "Ubah email". Berhasil: pengguna masuk otomatis dan menuju halaman tujuan seperti setelah masuk biasa. Validasi di browser: email wajib, kode 6 angka, kata sandi minimal 8 karakter. Pesan galat server ditampilkan apa adanya. Tautan "Kembali ke halaman masuk" tersedia.
6. **Logo:** halaman masuk, daftar, dan lupa kata sandi memakai logo tanpa tulisan (`logo-only.png`, versi terang `logo-light-only.png` tersedia lewat `<Logo mark light>`); header, sidebar, dan footer tetap memakai logo bertulisan.
7. **Batas yang diakui:** token masuk yang sudah terbit tetap berlaku sampai kedaluwarsa setelah kata sandi diganti (token JWT tanpa daftar cabut); tidak ada pembatasan jumlah permintaan per alamat IP selain jeda 60 detik per email; jeda 60 detik berarti permintaan yang terlalu cepat diam-diam tidak mengirim email baru.

## 14. Changelog

Dipindahkan ke `docs/CHANGELOG.md` (2026-11-03) agar SPEC tetap ringkas dan hanya memuat keadaan yang berlaku. Catat setiap perubahan baru di sana, bukan di sini.
