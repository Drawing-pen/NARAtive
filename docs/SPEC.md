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
| Tokoh | tabel `characters` | Tokoh yang terdeteksi beserta peran dan biodata |
| Relasi | tabel `character_relations` | Hubungan dua tokoh per bab: akrab atau konflik |
| Status Analisis | `documents.status` | queued, analyzing, done, failed |
| Status Rangkuman | `documents.summary_status` | running, done, partial (semua bab punya rangkuman, sebagian atau rangkuman keseluruhannya sederhana tanpa AI), failed (kosong = belum pernah dibuat) |
| Status Tokoh | `documents.characters_status` | running, done, partial (tokoh tersimpan, biodata AI gagal), failed (kosong = belum pernah dideteksi) |

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
| UC-10 | Biodata tokoh | Prototipe: aturan teks, biodata AI opsional |
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
- Pembayaran: Virtual Account bank bca, bni, bri, permata, berlaku 24 jam. Upgrade middle Rp29.000 atau high Rp59.000 untuk 30 hari (perpanjangan atau kenaikan paket saat paket berbayar masih berlaku menambah 30 hari dari tanggal berakhir, sisa hari tidak hangus); analisis tambahan Rp5.000 per analisis, 1 sampai 10 per pembelian; High tidak boleh membeli analisis tambahan. Harga sementara, SRS menyebut TBA. Tanpa `MIDTRANS_SERVER_KEY` berjalan mode simulasi tanpa uang sungguhan, hanya bila semua `CORS_ORIGINS` adalah localhost (selain itu `provider` = `unavailable` dan checkout 503); webhook Midtrans diverifikasi `signature_key` dan nominal; penyelesaian pembayaran idempoten; invoice dikirim lewat email (hanya dicatat di log bila `SMTP_HOST` kosong).
- Seri: 2 sampai 50 e-book berurutan, satu e-book hanya di satu seri (dipindah otomatis dari seri lain), seri yang kosong otomatis dihapus, membubarkan seri tidak menghapus e-book.
- Ukuran berkas unggahan (byte) TIDAK dibatasi.
- Privasi: isi e-book terkirim ke Gemini (rangkuman, bobot cerita) dan, bila diaktifkan, ke penyedia LLM lain. Pada tier gratis, konten dapat dipakai penyedia untuk peningkatan produk dan dibaca reviewer manusia. Cantumkan sebagai catatan di README, jangan di UI.

## 5. Data

MySQL 8 (SQLite hanya untuk uji cepat), SQLAlchemy 2, migrasi hanya lewat Alembic (0001 sampai 0018). Hapus berantai di tingkat database: menghapus baris `users` menghapus `documents`, transaksi, kuota, koleksi, dan profil sensitivitas; menghapus `documents` menghapus `chapters`, `paragraphs`, `characters`, dan relasinya (semua FK ke `users` dan `documents` memakai ON DELETE CASCADE). PK integer auto-increment. Nama tabel dan kolom di bawah adalah nama persis di kode, dan tabel ini adalah satu-satunya sumber skema. Jika sebuah kolom tidak tertulis di sini, tanya. Perubahan skema HARUS lewat migrasi baru; TIDAK BOLEH mengubah migrasi lama.

| Tabel | Kolom |
|---|---|
| `users` | `id`, `name` VARCHAR(100), `email` VARCHAR(255) UNIQUE (disimpan lowercase), `password_hash` VARCHAR(255) (bcrypt), `tier` VARCHAR(10) DEFAULT 'free' (free, middle, high), `role` VARCHAR(10) DEFAULT 'user' (user, admin; tidak dipakai), `is_active` BOOLEAN DEFAULT true, `created_at`, `tier_expires_at` DATETIME NULL (NULL = tidak berbatas waktu), `extra_checks` INT DEFAULT 0 (sisa analisis tambahan) |
| `documents` | `id`, `user_id` FK CASCADE, `collection_id` FK NULL (ON DELETE SET NULL), `position` INT DEFAULT 0 (urutan dalam seri), `title` VARCHAR(255), `filename` VARCHAR(255), `page_count`, `paragraph_count`, `status` (queued, analyzing, done, failed), `rating`, `pct_profanity`, `pct_sexual`, `pct_violence`, `dominant_emotion`, `pct_adult`, `heaviness`, `heaviness_ai`, `heaviness_note` TEXT, `created_at`, `analyzed_at`, `summary` TEXT, `summary_status` (running, done, partial, failed), `characters_status` (running, done, failed), `cover_path` VARCHAR(255) NULL |
| `chapters` | `id`, `document_id` FK, `number`, `title` VARCHAR(255), `summary` TEXT, `summary_source` VARCHAR(10) NULL (ai, local; NULL = data lama dianggap ai) |
| `paragraphs` | `id`, `document_id` FK, `idx`, `chapter_no`, `text` TEXT, `profanity`, `sexual`, `violence` (FLOAT 0 sampai 1), `emotion` (sad, angry, fear, happy), `emotion_score` |
| `characters` | `id`, `document_id` FK CASCADE, `name` VARCHAR(100), `role` VARCHAR(50), `biodata` TEXT, `mention_count`, `photo_path` VARCHAR(255) NULL, `aliases` VARCHAR(255), `gender` VARCHAR(20), `age` VARCHAR(100), `occupation` VARCHAR(300), `personality` TEXT, `background` TEXT (semua boleh NULL) |
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

- Endpoint (tanpa prefix `/api`): `POST /auth/register` (202, memulai pendaftaran dan mengirim kode; respons `{email, expires_in: 600, resend_after: 60}`, tanpa token), `POST /auth/register/verify` `{email, code}` (201), `POST /auth/register/resend` `{email}` (202), `POST /auth/login` (200), `GET /auth/me` (200). Respons verify dan login: `{access_token, token_type: "bearer", user: {id, name, email, tier, role}}`, dengan `tier` berupa tier yang berlaku (free, middle, high).
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

**Tokoh dan relasi (versi dasar).**
- Nama dikenali pipeline Hugging Face token-classification (`NER_MODEL`, bawaan `Davlan/xlm-roberta-base-ner-hrl`, belum terbukti untuk bahasa Indonesia), hanya grup PER dengan skor ≥ 0,85, posisi dari offset karakter.
- Pembersihan nama: pisah pada tanda kutip dan kurung, ambil potongan dengan huruf terbanyak, buang awalan inisial, 's, dan tanda baca; tolak yang berisi angka, tidak diawali huruf kapital, lebih dari 4 token, atau berisi token kecil yang bukan partikel nama. Gelar dibuang saat kanonisasi.
- Penyatuan nama: nama yang tokennya merupakan bagian dari satu nama lebih panjang yang unik digabung. Bila ambigu, tetap terpisah kecuali satu kandidat berjumlah ≥ 2 kali lipat kandidat berikutnya.
- Saringan: minimal disebut 3 kali, maksimal 25 tokoh, seruan dibuang, nama satu kata berhuruf kecil umum dengan jumlah di bawah 15 dibuang.
- Peran: "Tokoh utama" (peringkat ≤ 2 atau rasio ≥ 0,5 terhadap tokoh teratas), "Tokoh pendukung" (rasio ≥ 0,05), selain itu "Tokoh figuran".
- Penggabungan panggilan awalan: nama satu kata pendek (2 sampai 5 huruf) yang menjadi awalan kata pertama tepat satu nama lain, dan tidak pernah muncul di paragraf yang sama dengan nama itu, digabung (contoh "De" ke "Dede Dering").
- Relasi per bab: dua tokoh dalam paragraf yang sama atau berurutan menambah bobot; pasangan dengan bobot < 2 dibuang. Jenis hubungan: pasangan, sahabat, musuh, teman, keluarga, atau kenalan. Jenis dipilih dari kamus kata hubungan (`character_rules`) pada paragraf kebersamaan, dengan syarat minimal 2 suara; bila ≥ 40% jendela memuat paragraf konflik (marah ≥ 0,6, kekerasan ≥ 0,5, atau bahasa kasar ≥ 0,5) musuh mendapat 2 suara tambahan. Tanpa petunjuk jelas di satu bab dipakai jenis keseluruhan pasangan itu, lalu "kenalan". Tampilan "Semua bab" menjumlahkan bobot per jenis dan memilih jenis berbobot terbesar, mengabaikan kenalan bila ada jenis lain.
- Biodata dasar tanpa Gemini: kalimat peran dan fakta dari aturan teks (`character_rules`): jenis kelamin (kata ganti dan gelar, minimal 3 suara), usia (angka atau tahap hidup), pekerjaan (gelar dan kata profesi), serta deskripsi dari teks. Sengaja konservatif: kosong bila tidak yakin. Nama lain disimpan di `aliases`.
- Biodata AI (opsional, `?ai=true`, lewat tombol "Lengkapi biodata dengan AI"): satu permintaan Gemini per buku (`character_ai`), maksimal 12 kandidat dengan ≥ 2 sebutan, 3 kutipan sekitar 200 karakter per tokoh, paragraf seksual (skor ≥ 0,2) dilewati. Gemini menggabungkan nama yang merujuk orang sama dan mengisi jenis kelamin, usia, pekerjaan, kepribadian, latar, ringkasan; nilai tidak diketahui ditulis "Tidak disebutkan" dan tidak ditampilkan. Model dapat dipisah dengan `GEMINI_CHARACTER_MODEL`. Bila Gemini gagal, tokoh dasar tetap tersimpan dengan status `partial`. Ini berlaku untuk semua bentuk kegagalan, termasuk jawaban Gemini yang berupa JSON valid tetapi bentuknya salah (bukan objek, atau entri bukan objek). Deteksi otomatis setelah analisis TIDAK memakai AI.
- Keterbatasan yang HARUS dicantumkan di UI: nama panggilan bisa terbaca sebagai tokoh berbeda atau tergabung keliru, nama tempat bisa terbaca sebagai tokoh, biodata AI bisa keliru, dan jenis hubungan hanya perkiraan.

## 8. Pemrosesan

- Analisis berjalan di antrean satu pekerja (thread daemon), dokumen satu per satu. Setelah unggahan tersimpan, status `queued`; pekerja mengubahnya menjadi `analyzing`, lalu `done` atau `failed`. Respons unggahan tidak menunggu analisis.
- Urutan di `process` (jobs.py): model menilai semua paragraf, bobot cerita dari Gemini bila `GEMINI_API_KEY` terisi (kegagalan Gemini dilewati dan dicatat), agregasi, simpan, status done, lalu deteksi tokoh otomatis.
- Rangkuman dan tokoh berjalan di thread latar belakang masing-masing. Hanya satu proses per dokumen; permintaan saat status running tidak memulai proses kedua. Deteksi tokoh memakai kunci agar tidak berjalan paralel antar dokumen.
- Semua panggilan Gemini lewat `summarizer._generate` (satu titik). Perilakunya: jeda minimal `GEMINI_MIN_INTERVAL` detik antar panggilan; 429 harian memblokir model selama satu jam dan pindah ke `GEMINI_FALLBACK_MODEL`, bila semua model terblokir harian muncul pesan kuota habis; 429 per menit ditunggu sesuai `retryDelay` (maksimal 90 detik) sampai 4 kali; 5xx dan gangguan jaringan diulang dengan jeda 5, 15, 40 detik; penolakan keamanan memicu percobaan ulang dengan teks yang lebih ketat. TIDAK ada panggilan Gemini dari tempat lain. Setiap percobaan (berhasil atau gagal) dicatat satu baris di log server berawalan `Gemini |`: keperluan (bobot cerita, rangkuman bab (kelompok), rangkuman bab (tunggal), rangkuman keseluruhan, biodata tokoh), model, hasil (ok, 429 kuota harian habis, 429 batas per menit, galat kode, jaringan gagal, tanpa teks), lama dalam detik, dan jumlah token masuk dan keluar bila ada. Log TIDAK BOLEH memuat kunci, isi buku, atau jawaban Gemini.
- Hemat API: kelompokkan bab, simpan hasil, kunci API hanya dari `GEMINI_API_KEY`. Semua test memakai mock Gemini. Dilarang memanggil Gemini nyata dari test otomatis.
- Pesan kegagalan untuk pengguna ditulis Bahasa Indonesia, tanpa detail teknis, jejak stack, atau kunci.
- Frontend memuat ulang status secara berkala (polling) selama ada proses berjalan: halaman hasil selama analisis belum selesai, halaman rangkuman selama `summary_status` running, halaman tokoh dan relasi setiap 3 detik selama `characters_status` running.

## 9. Layar dan alur

Halaman: Beranda, Koleksi (e-book dan seri), Berlangganan (paket, kuota, checkout, riwayat), Masuk, Daftar, dan ruang kerja satu buku di `/buku/:id` dengan sidebar dan halaman Hasil analisis, Mode baca, Rangkuman, Biodata tokoh, Relasi tokoh, Profil sensitivitas (`/buku/:id/sensitivitas`). Halaman tidak ditemukan untuk rute lain. Semua teks UI Bahasa Indonesia. Halaman buku dan Koleksi butuh login.

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
Endpoint `POST /documents` (multipart, field `file`), 201 mengembalikan dokumen berstatus queued.
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
`GET /documents/{id}/chapters` dan `GET /documents/{id}/paragraphs`. Teks per bab dengan pilihan dan navigasi bab. Safe Mode: tombol aktif dan nonaktif. Saat aktif, paragraf seksual di atas ambang disamarkan; mengetuk membukanya; tombol "Samarkan lagi" menutup kembali yang sudah dibuka di bab itu. Berganti bab menyamarkan ulang. Teks status menyebut jumlah paragraf yang disamarkan di bab itu atau bahwa tidak ada yang disamarkan.
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
`GET /documents/{id}/characters` (`{status, characters, relations}`) dan `POST /documents/{id}/characters` (202). Aturan tier sama dengan rangkuman: POST (termasuk `?ai=true`) khusus Middle ke atas, GET untuk tier lebih rendah hanya bila `characters_status` terisi. Deteksi otomatis setelah analisis hanya berjalan bila pemilik buku Middle ke atas. Halaman Biodata dan Relasi menampilkan kartu terkunci bagi yang tidak berhak.
1. Belum pernah dideteksi: tombol "Deteksi tokoh". Setelah analisis selesai, deteksi juga berjalan otomatis (tanpa AI).
2. Berjalan: "Sedang mendeteksi tokoh", halaman memperbarui otomatis.
3. Selesai: kartu tokoh terurut dari yang paling berperan, berisi inisial, nama, peran, "Juga disebut" (bila ada), biodata, dan rincian jenis kelamin, usia, pekerjaan, kepribadian, latar belakang yang diketahui. Tombol "Lihat relasi tokoh", "Lengkapi biodata dengan AI" (atau "Perbarui biodata AI"; memakai 1 permintaan Gemini) dan "Deteksi ulang".
4. `partial`: tokoh tampil, dengan pemberitahuan "Biodata AI belum berhasil dibuat, kemungkinan kuota Gemini sedang habis. Coba lagi nanti."
- `POST .../characters?ai=true` tanpa `GEMINI_API_KEY`: 409 "Biodata AI butuh GEMINI_API_KEY di server."
- Analisis belum selesai: 409 "Tokoh bisa dideteksi setelah analisis selesai."; UI menampilkan "Tokoh bisa dideteksi setelah analisis buku ini selesai."
- Gagal: "Tokoh gagal dideteksi" dan tombol "Coba lagi".
- Tidak ada tokoh: "Tokoh tidak terdeteksi".

### F-RELASI (UC-11)
Data dari endpoint tokoh yang sama. Pilihan "Semua bab" dan per bab dengan tombol sebelumnya dan berikutnya. Graf lingkaran: tokoh berukuran menurut jumlah disebut, garis berketebalan menurut bobot dan berwarna menurut jenis (pasangan merah muda, sahabat hijau, teman biru, keluarga kuning tua, musuh merah putus-putus, kenalan abu-abu bertitik); arahkan kursor atau fokus untuk menyorot tokoh dan garis terkait. Di bawahnya daftar hubungan berbentuk teks. Legenda hanya memuat jenis yang ada, dan catatan bahwa jenis hubungan hanya perkiraan.
- Kurang dari dua tokoh: "Tokoh belum cukup".
- Tidak ada relasi pada pilihan: "Belum ada relasi terdeteksi pada bab ini."

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
- Environment backend (`backend/.env`, jangan di-commit; contoh tanpa nilai di `backend/.env.example`): `DATABASE_URL`, `SECRET_KEY`, `ACCESS_TOKEN_MINUTES`, `MODEL_DIR`, `UPLOAD_DIR`, `CORS_ORIGINS`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL`, `GEMINI_CHARACTER_MODEL`, `GEMINI_MIN_INTERVAL`, `NER_MODEL`, `SECONDS_PER_PARAGRAPH`, `DEV_UNLOCK_ALL_TIERS`, `MIDTRANS_SERVER_KEY`, `MIDTRANS_IS_PRODUCTION`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. Perintah bantu `python -m app.tools.atur_tier email free|middle|high` mengubah tier akun.
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

### R4. Setiap bab yang punya teks harus punya rangkuman. Status: SELESAI (2026-10-26)
Diimplementasikan dan dipindahkan ke bagian 5, 7, dan 9 (F-RANGKUMAN). Tes: `backend/tests/test_summary.py`, `backend/tests/test_summary_local.py`, `frontend/src/pages/__tests__/SummaryPage.spec.js`. Belum teruji dengan Gemini nyata: apakah penanda pengganti benar-benar meloloskan bab yang tadinya ditolak.

### Urutan irisan
1. R1 registrasi dengan verifikasi (kerangka tes pytest disiapkan di irisan ini karena repositori belum punya tes).
2. R2 matriks tier dan penegakan batas unggah, termasuk tes.
3. Irisan berikutnya (mode baca, rangkuman, tokoh dan relasi, seri, pembayaran, PDF) diperiksa satu per satu terhadap bagian 0 sampai 12 dan R2.

## 14. Changelog

| Tanggal | Perubahan |
|---|---|
| 2026-10-25 | Draf awal SPEC dari SRS dan SDD 22 September 2026 dan kode saat ini (migrasi sampai 0010; autentikasi; tokoh dan relasi selesai). Rencana ketahanan Gemini dan analisis tokoh dicatat sebagai Undecided U1 sampai U5 |
| 2026-10-25 | **Sinkronisasi dengan kode yang sudah diimplementasikan.** Kode adalah acuan utama. Rinciannya di bawah baris ini (C1 sampai C8) |
| 2026-10-25 | Badan dokumen (bagian 0 sampai 13) ditulis ulang agar cocok dengan kode, atas izin pemilik proyek. Ditambah F-SERI, F-SENSITIVITAS, F-BAYAR, aturan batas tier dan pembayaran di bagian 4, tabel baru di bagian 5. Teks C1 sampai C8 di atas tetap sebagai catatan sejarahnya |
| | **C1. Tier dan batas penggunaan sekarang ditegakkan** (bagian 0, 3, 4, 5, 8 salah). Migrasi 0014 menambah `users.tier_expires_at` dan `users.extra_checks`, tabel `usage_quota` (`user_id`, `period` YYYY-MM, `used`; unik per pasangan), dan tabel `transactions`. Batas di `app/core/plans.py`: free 50 halaman, 3 analisis per bulan, 3 e-book aktif; middle 300, 15, 50; high tanpa batas. Pemeriksaan di `billing.ensure_can_upload` setelah teks terbaca (sebelum dokumen disimpan) dan pemakaian dicatat dalam transaksi yang sama dengan penyimpanan dokumen. Melewati batas: HTTP 402 dengan pesan Bahasa Indonesia. Kuota bulanan dipakai dulu, lalu `extra_checks` (hasil pay-per-check). Kuota reset otomatis per bulan kalender (UTC). `User.paid_tier` kembali ke free bila `tier_expires_at` lewat; `User.access_tier` adalah tier yang berlaku, dan bernilai high untuk semua akun bila `DEV_UNLOCK_ALL_TIERS=true` (khusus pengembangan). Respons `UserOut` kini memuat `tier` (dari `access_tier`) dan `role`. `python -m app.tools.atur_tier email free\|middle\|high` mengubah tier manual. Yang BELUM ditegakkan di backend: rangkuman, tokoh, relasi, rincian rating, dan unduh PDF tidak dibatasi tier (halaman Berlangganan mencantumkannya sebagai fitur paket, tetapi hanya UC-12 yang dikunci di server). `users.role` tetap tidak dipakai |
| | **C2. UC-07 dan UC-08 (pembayaran dan riwayat) dibangun** (bagian 3 salah). Router `/billing`: `GET /billing/overview`, `POST /billing/checkout` (201), `GET /billing/transactions`, `GET /billing/transactions/{order_id}`, `POST /billing/transactions/{order_id}/cancel`, `POST /billing/transactions/{order_id}/simulate-pay`, `POST /billing/midtrans/notification` (webhook, diverifikasi `signature_key` dan nominal). Pembayaran lewat Virtual Account (bca, bni, bri, permata), masa berlaku 24 jam, status pending, paid, failed, expired, cancelled. Dua jenis pembelian: `upgrade` ke middle atau high (30 hari, perpanjangan menambah dari tanggal berakhir) dan `pay_per_check` (1 sampai 10 analisis tambahan). Harga sementara (SRS: TBA): middle Rp29.000, high Rp59.000, Rp5.000 per analisis tambahan. Tanpa `MIDTRANS_SERVER_KEY` berjalan mode simulasi (VA acak lokal dan endpoint simulate-pay); dengan kunci memakai Core API Midtrans (sandbox kecuali `MIDTRANS_IS_PRODUCTION`). Invoice dikirim lewat email (`services/mailer.py`, SMTP_*); tanpa `SMTP_HOST` hanya dicatat di log. Settle idempoten. Mengatasi sebagian U6 (invoice email), tetapi registrasi tetap tanpa verifikasi email. Variabel baru: `DEV_UNLOCK_ALL_TIERS`, `MIDTRANS_SERVER_KEY`, `MIDTRANS_IS_PRODUCTION`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `GEMINI_CHARACTER_MODEL` (juga di `.env.example` akar dan `docker-compose.yml`). Halaman Berlangganan (`/berlangganan`) kini fungsional: ringkasan kuota, pilihan paket, beli analisis tambahan, dialog checkout (`CheckoutDialog.vue`), riwayat transaksi |
| | **C3. UC-02 dibangun sebagai "seri"** (bagian 2, 3, 5 salah). Migrasi 0013: tabel `collections` (`id`, `user_id` FK CASCADE, `name` VARCHAR(150), `created_at`) dan kolom `documents.collection_id` (FK SET NULL) serta `documents.position`. Router `/collections`: GET, POST (201), `PUT /collections/{id}`, `DELETE /collections/{id}` (204, buku tetap ada). Seri minimal 2 dan maksimal 50 e-book, berurutan (urutan baca), satu e-book hanya di satu seri (memindahkan dari seri lain otomatis), seri yang kosong otomatis dihapus (`prune_empty`, termasuk saat e-book dihapus). Tiap buku tetap dianalisis dan dihitung kuotanya sendiri. Istilah UI: "Seri" (halaman `/koleksi` tetap daftar e-book). Unggah beberapa berkas sekaligus menawarkan langsung membuat seri. Komponen baru: `BookCard`, `SeriesCard`, `SeriesDialog`, `SeriesViewer` |
| | **C4. UC-12 profil sensitivitas dibangun** (bagian 3, 4, 5 salah). Migrasi 0012: tabel `sensitivity_profiles` (`user_id` unik FK CASCADE, `profanity`, `sexual`, `violence` FLOAT nullable, `updated_at`). Router `/sensitivity`: `GET` (semua tier; mengembalikan ambang yang berlaku, `editable`, `personal`, `standard`), `PUT` dan `DELETE` hanya High Tier (403 "Fitur ini khusus pengguna High Tier."). Ambang 0,1 sampai 0,95 per jenis konten; null berarti jenis itu tidak disamarkan. Profil standar: hanya seksual (0,5), perilaku Safe Mode standar tidak berubah. Mode baca memuat ambang dari `/sensitivity` dan menyamarkan semua jenis yang melewati ambang, teks penyamaran menjadi "Konten sensitif disamarkan" bila bukan hanya seksual; gagal memuat profil berarti kembali ke standar. Halaman baru `SensitivitasPage.vue` (rute `sensitivitas` di ruang kerja buku), tautan di sidebar dan mode baca. Tombol "Ganti cover" tetap terkunci tanpa fungsi (UC-17 belum) |
| | **C5. Biodata tokoh diperluas** (bagian 5, 7, 9 F-TOKOH salah). Migrasi 0011: kolom `characters.aliases`, `gender`, `age`, `occupation`, `personality`, `background`. Biodata dasar tetap tanpa Gemini, tetapi kini memakai aturan teks di `services/character_rules.py` (jenis kelamin, usia, pekerjaan dari pola di sekitar nama; sengaja konservatif, kosong bila tidak yakin) dan kalimat deskripsi dari teks. Penggabungan nama panggilan awalan (mis. "De" ke "Dede Dering") dengan aturan konservatif. Opsional "biodata AI": `POST /documents/{id}/characters?ai=true` memakai Gemini (`services/character_ai.py`, satu permintaan per buku, maksimal 12 kandidat, 3 kutipan sekitar 200 karakter per tokoh, paragraf seksual dilewati, `GEMINI_CHARACTER_MODEL` boleh dipisah) untuk menggabungkan nama panggilan dan mengisi kepribadian, latar, ringkasan; tanpa `GEMINI_API_KEY` mengembalikan 409 "Biodata AI butuh GEMINI_API_KEY di server.". Nilai status tokoh baru: `partial` (tokoh tersimpan tetapi Gemini gagal; UI memberi tahu dan menawarkan coba lagi). Deteksi otomatis setelah analisis tetap tanpa AI; AI hanya lewat tombol "Lengkapi biodata dengan AI". Mengerjakan sebagian U3 dan U4 tanpa persetujuan eksplisit di SPEC, perlu ditinjau. Kartu tokoh kini menampilkan "Juga disebut", rincian jenis kelamin, usia, pekerjaan, kepribadian, latar, dan tidak lagi batang "Disebut N kali". Urutan tokoh di UI dijelaskan sebagai "paling berperan". `_generate` menerima parameter `prefer` (model pilihan didahulukan) |
| | **C6. Jenis relasi tokoh diperinci** (bagian 5, 7, 9 F-RELASI salah). `relation_type` kini bernilai pasangan, sahabat, teman, keluarga, musuh, kenalan (tidak lagi hanya akrab dan konflik). Ditentukan dari kamus kata hubungan di paragraf kebersamaan (`relation_votes`, minimal 2 suara) dan porsi paragraf konflik (menambah suara musuh); tanpa petunjuk jelas jatuh ke jenis keseluruhan pasangan itu, lalu "kenalan". Frontend menerjemahkan nilai lama `akrab` menjadi kenalan dan `konflik` menjadi musuh sehingga buku yang belum dideteksi ulang tetap terbaca. Graf berwarna per jenis, legend hanya jenis yang ada, "Semua bab" memilih jenis dengan bobot terbesar (mengabaikan kenalan bila ada jenis lain). Tidak perlu migrasi (kolom VARCHAR(10) cukup). `tools/tokoh.py` menerima `--ai` dan mencetak jenis dinamis |
| | **C7. Perubahan di antarmuka dan alur** (bagian 3 dan 9). Beranda dan sidebar: daftar "Fitur lanjutan" terkunci dihapus dari `Navbar.vue`, diganti tautan nyata ke Profil sensitivitas. Chip tier di header membaca tier dari server (`tierKey()`, free tampil sebagai Standard) dan data pengguna disinkronkan saat aplikasi dibuka (`refreshUser`, memanggil `/auth/me`). Kartu "Rincian rating" masih placeholder (U9 tetap terbuka). Isi PDF belum memuat rangkuman (U8 tetap terbuka). Rate limit login dan verifikasi email tetap tidak ada |
| | **C8. Skema dan migrasi.** Alembic kini 0001 sampai 0014 (bagian 5 dan 11 menyebut 0001 sampai 0010). Tabel baru di kode yang SPEC bagian 3 nyatakan TIDAK dibuat: `transactions`, `usage_quota`, `sensitivity_profiles`, ditambah `collections`. `subscriptions` dan `payment_methods` tetap tidak ada; status langganan disimpan di `users.tier` dan `users.tier_expires_at`. Catatan selisih dokumen: `docs/ALUR_BISNIS.md` dirujuk SPEC.md dan CLAUDE.md tetapi tidak ada di repositori; `Readme.md` masih menyebut UC-10 dan UC-11 "Belum" dan migrasi 0001 sampai 0008, sedangkan kode sudah selesai; Readme menyebut `atur_tier` untuk "pembayaran belum tersedia" padahal pembayaran sudah ada; PDF SRS/SDD lama terhapus dan diganti versi "(3)" dan "(4)" (belum di-commit). Penghitung bagian 3 ("10 dari 19") menjadi 14 dari 19 (UC-01, 02, 03 sebagian, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 19); belum ada: UC-14 sampai UC-18. Belum ada tes otomatis di repositori dan Midtrans nyata, Gemini nyata, serta NER bahasa Indonesia belum teruji dalam sesi ini |
| 2026-10-25 | Siklus pengembangan dimulai ulang per irisan (kode lama dipertahankan dan dibenahi). Ditambah bagian 13A: R1 registrasi dengan kode verifikasi email, R2 matriks tier di server (rincian rating, rangkuman, tokoh, relasi: Middle ke atas; profil sensitivitas, PDF, cover, foto tokoh: High; hasil yang sudah dibuat tetap terlihat), R3 Gemini untuk semua tier. U5 dan U6 diputuskan. Belum ada yang diimplementasikan |
| 2026-10-25 | **Irisan 1 selesai: registrasi dengan kode verifikasi (R1).** Tabel `email_verifications` (migrasi 0015), service `app/services/verification.py`, endpoint `/auth/register` (kini 202), `/auth/register/verify`, `/auth/register/resend`, halaman Daftar dua tahap. 24 tes pytest lulus; migrasi 0015 naik dan turun diuji di SQLite. Perilaku register lama (langsung membuat akun dan token) tidak berlaku lagi. Belum teruji: SMTP sungguhan, UI di browser, MySQL. `npm run lint` melaporkan satu galat lama di `WorkspaceNav.vue` (`RATINGS` tak terpakai) yang tidak berkaitan |
| 2026-10-25 | **Irisan 2 selesai: matriks tier di server (R2, tanpa rincian rating dan UC-17/18).** `ensure_tier`/`has_tier` di `core/security.py`; POST rangkuman dan tokoh `require_tier("middle")`, GET dengan hasil tersimpan terbuka; PDF `require_tier("high")`; `jobs.process` mendeteksi tokoh otomatis hanya untuk Middle ke atas. UI: komponen `TierLock`, tombol buat disembunyikan untuk Standard, tombol PDF menjadi tautan ke paket. 64 tes pytest lulus (24 registrasi, 29 matriks tier, 11 batas unggah). Belum teruji: tampilan UI di browser dan perilaku dengan MySQL. Perilaku lama berubah: Standard tidak lagi bisa membuat rangkuman, tokoh, dan PDF |
| 2026-10-26 | **Irisan 3: mode baca dan Safe Mode (UC-04, UC-05, pemakaian UC-12) diperiksa terhadap SPEC.** Tidak ada penyimpangan perilaku di backend; 20 tes baru (`backend/tests/test_reading_safe_mode.py`) mengunci: urutan bab dan paragraf, 404 untuk dokumen orang lain, 401 tanpa login, profil standar (hanya seksual 0,5), simpan dan reset profil High, rentang ambang 0,1 sampai 0,95 dan null, profil tidak dipakai bila tier turun atau kedaluwarsa tetapi tetap tersimpan. Catatan: logika penyamaran di `ReadingModePage.vue` belum teruji otomatis; `STANDARD_SAFE_MODE` di frontend adalah cermin manual dari `STANDARD_PROFILE` backend; kunci `narative_reader` kini tercatat di F-BACA |
| 2026-10-26 | **Irisan 3a: tes frontend untuk Safe Mode.** Kerangka tes frontend ditambahkan (devDependencies `vitest`, `@vue/test-utils`, `jsdom`; `vitest.config.js`; skrip `npm run test`). 20 tes komponen `ReadingModePage` mengunci: penyamaran seksual saja pada profil standar, ambang tepat sama disamarkan (≥), skor kosong tidak disamarkan, hitungan per bab, buka per paragraf, samarkan lagi per paragraf dan semua, pindah bab menyamarkan ulang, tombol Safe Mode dan penyimpanannya (termasuk saat penyimpanan browser diblokir), profil personal (kekerasan dan bahasa kasar, ambang null, gagal muat jatuh ke standar), serta keadaan belum selesai, tidak ditemukan, galat, dan batas navigasi bab. Diverifikasi dengan tiga perusakan sengaja pada komponen (ambang ≥ jadi >, tidak menyamarkan ulang saat pindah bab, tanpa profil bawaan); masing-masing digagalkan tepat satu tes. Tidak ada perubahan pada kode aplikasi |
| 2026-10-26 | **Irisan 4: rangkuman (UC-09) diperiksa terhadap SPEC bagian 7, 8, 9.** 55 tes baru dengan Gemini palsu dan jam palsu (tanpa panggilan nyata dan tanpa menunggu): `tests/test_gemini_client.py` (23 tes: kunci di header bukan URL, retry 5xx dan jaringan 5/15/40 detik, 4xx tidak diulang, 429 per menit menunggu `retryDelay` maksimal 90 detik dan menyerah setelah 4 tunggu, 429 harian pindah ke model cadangan dan bertahan satu jam, semua model habis melapor kuota, jeda minimal antar panggilan, penolakan keamanan dikenali), `tests/test_summary.py` (32 tes: 409 dan 503, satu proses per dokumen, buat ulang dari awal, lanjut dari bab yang belum selesai, paragraf seksual tidak pernah terkirim dan diganti satu penanda, cuplikan awal-tengah-akhir, bab kosong, pembagian 20 bab dan 90.000 karakter, bab yang hilang dari jawaban dirangkum sendiri, jawaban rusak dibagi dua, rangkuman keseluruhan gagal dilanjutkan dengan satu permintaan, kuota habis di tengah lalu dilanjutkan, kunci salah berhenti langsung, percobaan ulang yang lebih ketat setelah penolakan keamanan, pemulihan status `running` saat server menyala). Semua perilaku sesuai SPEC kecuali satu temuan yang dicatat sebagai U11. Tidak ada perubahan pada kode aplikasi. Total tes: 139 backend, 20 frontend |
| 2026-10-26 | **Pencatatan setiap request Gemini.** `_generate` kini menerima `purpose` dan mencatat satu baris log per percobaan (lihat bagian 8) supaya jumlah request per buku bisa dihitung dari log, bukan perkiraan. Pemanggil diberi label: `heaviness.py` (bobot cerita), `summarizer.py` (rangkuman bab kelompok dan tunggal, rangkuman keseluruhan), `character_ai.py` (biodata tokoh). Perilaku permintaan tidak berubah. 7 tes baru (total 146 backend). Perhitungan dari kode: satu buku memakai 1 request bobot cerita saat unggah (otomatis, semua tier), 1 request per kelompok bab (maksimal 20 bab atau 90.000 karakter) ditambah 1 rangkuman keseluruhan, dan 1 request biodata AI; pengulangan 5xx, 429, dan penolakan keamanan menambah request |
| 2026-10-26 | **Irisan 4b: setiap bab harus punya rangkuman (R4, menutup U11).** Percobaan bertingkat: normal, ulang dengan paragraf sensitif diganti penanda (`[adegan kekerasan dilewati]`, `[bahasa kasar dilewati]`, `[adegan dewasa dilewati]`) bukan dibuang, lalu rangkuman lokal tanpa Gemini (`services/summary_local.py`). Status baru `partial`; kolom baru `chapters.summary_source` (migrasi 0016, naik dan turun diuji di SQLite); `GET /summary` mengembalikan `summary_source`; `POST /summary` pada `partial` melanjutkan dan mengulang bab lokal lewat Gemini. Perilaku lama yang berubah: kuota Gemini habis di tengah proses tidak lagi menghasilkan status `failed`, melainkan `partial` dengan sisa bab dirangkum lokal (bisa ditingkatkan lewat "Lanjutkan dengan AI"); bab yang ditolak dua kali tidak lagi bertulis "tidak dapat dibuat" melainkan dirangkum lokal. Tidak berubah: galat kredensial tetap `failed`; bab tanpa paragraf tetap "tidak dapat dibuat". UI: catatan, tombol Lanjutkan dengan AI, label per bab. Tes: backend 163 (ditambah 24), frontend 26 (ditambah 6). Belum teruji dengan Gemini nyata |
| 2026-10-26 | **Irisan 5: tokoh dan relasi (UC-10, UC-11) diperiksa terhadap SPEC bagian 7 dan 9.** 155 tes baru dengan NER palsu dan Gemini palsu (tanpa model sungguhan), total backend 318: `test_characters_names.py` (44: pembersihan nama, kanonisasi gelar, ambang skor 0,85 inklusif, penyatuan nama panjang dan pendek, nama ambigu), `test_characters_build.py` (33: minimal 3 sebutan, maksimal 25, peran menurut peringkat dan rasio, penggabungan nama panggilan awalan, seruan dan kata umum dibuang, bobot relasi minimal 2, jenis hubungan dari kata petunjuk dan sinyal konflik, jenis seluruh buku sebagai cadangan, biodata dasar, paragraf seksual tidak pernah dikutip, perilaku dengan AI), `test_characters_rules.py` (29: jenis kelamin, usia, pekerjaan, frasa pengenal, aturan panggilan awalan, kamus hubungan), `test_characters_ai.py` (24: satu permintaan per buku, pembersihan isian, id tak dikenal diabaikan, `safe` tidak pernah melempar), `test_characters_flow.py` (25: penyimpanan dan urutan id relasi, deteksi ulang idempoten tanpa baris ganda, hasil lama tidak rusak bila deteksi gagal, status done/partial/failed/running, kunci anti paralel, pemulihan saat server menyala, endpoint, cascade hapus). **Bug ditemukan dan diperbaiki:** `character_ai.safe()` tidak menangkap `AttributeError`, sehingga jawaban Gemini berupa JSON valid berbentuk salah (mis. daftar, bukan objek) membuat seluruh deteksi tokoh berstatus `failed` dan hasilnya dibatalkan, padahal seharusnya `partial` dengan tokoh dasar tersimpan. Perbaikan satu kata di `services/character_ai.py` setelah tes merah. Catatan perilaku (bukan bug): nama tampilan mempertahankan gelar bila itu bentuk yang paling sering muncul ("Mr Budi"); frasa deskripsi berlanjut sampai tanda baca ("a quiet girl who loved books"). Belum teruji: NER nyata pada teks bahasa Indonesia, dan Gemini nyata untuk biodata |
| 2026-10-27 | **Irisan 6: seri (UC-02) dan pembayaran (UC-07, UC-08) diperiksa terhadap SPEC bagian 4 dan 9 (F-SERI, F-BAYAR).** 135 tes baru, total backend 453. `test_collections.py` (34: urutan baca dan posisi, nama dirapikan 1 sampai 150 karakter, 2 sampai 50 buku, buku ganda 400, buku orang lain 404 tanpa menyimpan apa pun, buku berpindah dari seri lama, seri kosong dihapus tetapi seri dengan satu buku tersisa bertahan, ubah dan bubarkan, buku tidak terhapus saat seri dibubarkan, menghapus buku merapikan seri, seri tidak memakai kuota analisis), `test_billing.py` (93: ringkasan kuota dan harga, checkout upgrade dan pay-per-check untuk keempat bank, validasi pesanan, larangan membeli paket lebih rendah dan analisis tambahan bagi High, pembayaran simulasi mengaktifkan paket 30 hari, perpanjangan menambah dari tanggal berakhir, kenaikan paket memulai periode baru dari sekarang, analisis tambahan, invoice email sekali per pembayaran, pembayaran ganda 409, pesanan lewat batas menjadi kedaluwarsa, riwayat terbaru dulu dan milik sendiri, pembatalan termasuk ke gateway, checkout Midtrans (permata, penolakan gateway, gateway mati), klien gateway (sandbox dan produksi, otentikasi Basic, kunci tidak bocor ke galat), webhook (tanda tangan sha512 dan nominal, settlement dan capture, notifikasi berulang diterapkan sekali, status lain, notifikasi kedaluwarsa tidak membatalkan pembayaran), kalender kuota bulanan), `test_mailer.py` (8: hanya dicatat tanpa SMTP, pengiriman di thread latar, kegagalan tidak sampai ke pemanggil, kata sandi SMTP tidak masuk log). Tidak ada bug ditemukan dan tidak ada perubahan pada kode aplikasi. Perilaku yang tercatat tetapi belum diputuskan: (a) naik dari Middle ke High saat Middle masih berlaku memulai periode 30 hari baru dari sekarang, sisa hari Middle tidak ditambahkan; (b) notifikasi settlement Midtrans yang datang setelah pesanan kedaluwarsa atau dibatalkan tetap diterapkan (uang sudah diterima); (c) tanpa `MIDTRANS_SERVER_KEY`, setiap pengguna dapat membayar pesanannya sendiri lewat mode simulasi sehingga paket berbayar gratis, aman hanya selama prototipe berjalan di localhost (bagian 11). Belum teruji: Midtrans sandbox nyata, SMTP nyata, dan tampilan `CheckoutDialog`, `SeriesDialog`, serta halaman Berlangganan di frontend |
| 2026-10-27 | **Irisan 7: aturan pembayaran R5 (keputusan pemilik proyek atas perilaku (a) sampai (c) irisan 6).** Tes dulu (6 merah), lalu kode, total backend 466 lulus. (a) `billing.settle`: paket berbayar yang masih berlaku, apa pun jenisnya, membuat masa baru dimulai dari tanggal berakhir lama (+30 hari), jadi sisa hari Middle ikut terbawa saat naik ke High; paket yang sudah berakhir mulai dari sekarang. (b) Settlement Midtrans terlambat setelah expired atau cancelled tetap diterapkan, kini dikunci dengan tes. (c) `payments.provider()` mengembalikan `unavailable` bila kunci Midtrans kosong dan ada `CORS_ORIGINS` selain localhost, 127.0.0.1, [::1]; `create_va` melempar `PaymentUnavailable`, checkout membalas 503 "Pembayaran belum tersedia.", simulate-pay 403, dan `CheckoutDialog` menampilkan pesan serta menonaktifkan tombol. Perubahan: `services/billing.py`, `services/payments.py`, `api/routers/billing.py`, `components/CheckoutDialog.vue`. Belum teruji: Midtrans sandbox nyata, SMTP nyata |
| 2026-10-27 | **Irisan 8: hapus berantai (ON DELETE CASCADE).** Menghapus akun langsung di MySQL gagal dengan error 1451 karena `documents.user_id`, `chapters.document_id`, dan `paragraphs.document_id` tidak punya cascade. Tes dulu (`test_cascade_delete.py`, 5 merah: tiga FK dan dua penghapusan langsung dengan `PRAGMA foreign_keys=ON`), lalu `ondelete="CASCADE"` di `models.py` dan migrasi `0017_hapus_berantai_milik_pengguna.py` (mencari nama FK lewat inspector, drop, lalu buat ulang dengan CASCADE; downgrade mengembalikan tanpa cascade). Total backend 476 lulus. Migrasi BELUM dijalankan terhadap MySQL oleh agen (perintah DROP FOREIGN KEY tidak ada di SQLite); pemilik proyek menjalankan `python -m alembic upgrade head` dan memeriksanya |
| 2026-10-27 | **Uji manual oleh pemilik proyek (registrasi dan pembayaran).** Berhasil, menurut pemilik proyek: migrasi 0017 dan hapus berantai di MySQL; registrasi dengan kode 6 angka yang dikirim lewat SMTP sungguhan (Gmail dengan App password); checkout dan pembayaran lewat Midtrans sandbox (Payment Simulator) dengan webhook lewat ngrok mengaktifkan paket otomatis; invoice masuk ke inbox; kenaikan Middle ke High membawa sisa hari. Ini menutup bagian "belum teruji" untuk SMTP nyata dan Midtrans sandbox nyata pada irisan 1, 6, dan 7. Masih belum teruji: Midtrans produksi, pengiriman dari domain sendiri, dan deploy publik |
| 2026-10-27 | **Irisan 9: ganti cover (UC-17) dan ganti foto tokoh (UC-18), khusus High (R6).** Tes dulu (`test_images.py`, 42 merah dari 48), lalu kode, lalu tes frontend. Backend: `services/images.py` (jenis dari magic bytes JPG/PNG/WebP, 2 MB, simpan, muat, hapus), `api/routers/images.py` (enam endpoint), `documents.cover_path` (migrasi `0018_tambah_cover_dokumen.py`), properti `has_cover` dan `has_photo`, pembersihan file saat e-book dihapus atau tokoh dideteksi ulang. Frontend: `AuthImage.vue`, `PictureControls.vue`, dipakai di `HasilAnalisisPage`, `TokohPage`, dan `BookCard`. Tes: 49 backend baru (total backend 525 lulus) dan 11 frontend baru (total 37 lulus). Belum teruji: tampilan di browser sungguhan dan migrasi 0018 di MySQL. Keterbatasan: isi gambar tidak didekode (tanpa Pillow) sehingga file rusak berawalan benar tetap tersimpan; foto tokoh hilang saat tokoh dideteksi ulang. `views/WorkspaceNav.vue` dan `views/DocumentView.vue` (tidak terpasang di rute) masih memuat tombol "Ganti cover" lama dan tidak diubah |
