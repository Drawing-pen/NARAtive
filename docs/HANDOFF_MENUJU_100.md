# Handoff: menuju 100% (per 2026-11-24)

Presentasi diundur, tetapi proyek harus 100% minggu depan. Tes white/black box baru dikerjakan SETELAH semua fitur dinyatakan 100% oleh pemilik.

## Aturan kerja (wajib)
- Siklus per irisan: aturan SPEC dulu, tes gagal, implementasi minimal, laporan jujur, sinkronkan `docs/SPEC.md` dan `docs/CHANGELOG.md`.
- Jangan membangun di luar SPEC tanpa bertanya. Tidak ada komentar kode baru.
- Jangan commit atau push (pemilik yang push). Jangan cetak isi `backend/.env` atau `.env` root.
- Berkas asli SRS/SDD/drawio tidak disentuh; perubahan hanya ke berkas `UPDATE_*`.
- Jangan menyentuh deploy Fly tanpa izin pemilik.
- Bahasa Indonesia, ringkas, perintah untuk Windows. Pemilik suka satu langkah per kali.

## Catatan tentang docs/CLAUDE.md
- Berkas itu sebagian sudah usang: masih menyebut model xlm-roberta dengan 4 kepala, bobot cerita 0,7 LLM + 0,3 emosi, dan `app/ml/model.py`. Sejak R24 analisis 100% LLM (`services/llm_analyzer.py`), emosi dihapus, `model.py` dihapus. Yang berlaku adalah `docs/SPEC.md` (R21 sampai R25) dan `docs/CHANGELOG.md`.
- Aturan CLAUDE.md yang tetap berlaku untuk pekerjaan OCR: tidak ada pilihan atau istilah OCR di UI (pemilih engine hanya di backend/env), semua tier menerima semua jenis PDF, tes tidak boleh memanggil layanan nyata (pakai fake seperti `tests/router_fake.py`), dan rancang untuk semua jenis buku, bukan satu dua contoh.
- Pemilik belum meminta CLAUDE.md diperbarui; tanyakan dulu.

## Keadaan terakhir
- R24 (analisis 100% LLM via 9router, XLM dihapus, tanpa emosi) dan R25 (timeout 9router 300 dan coba ulang sekali) selesai. Perbaikan merge tokoh selesai. Semua belum di-commit.
- Tes terakhir: backend 1276 lulus, frontend 303 lulus.
- Deploy Fly perlu redeploy untuk membawa perbaikan merge tokoh. Backend Fly sedang menyala terus; kembalikan ke hemat (`'stop'`, `0`) setelah presentasi selesai.
- Jadikan admin: `python -m app.tools.jadikan_admin email [cabut]` (lokal lewat docker compose exec backend, di Fly lewat `flyctl ssh console -a narative-api-ipl26 -C "..."`).

## Daftar kerja (usulan urutan)
### A. Keandalan analisis
1. **Dokumen bukan novel (artikel, dll).** SELESAI KODE 2026-11-24 (R28, irisan 44): diputuskan pemilik, bukan ditolak melainkan status `not_novel` (tanpa rating, tanpa kuota, menu terkunci, halaman awal menyatakan bukan novel). Sisa: uji dengan LLM nyata (DML tulisan tangan dan artikel ilmiah harus `other`, Konspirasi dan Tere Liye harus `novel`), lihat di peramban, redeploy Fly (migrasi 0022).
2. **OCR dengan mata bor yang bisa diganti.** Antarmuka engine: terima gambar halaman, kembalikan teks dan keyakinan. Engine: `tesseract` (sudah ada, ind+eng) dan `router_vision` (BARU, lewat 9router; cadangannya Gemini langsung). Pemilih `OCR_ENGINE=tesseract|router|auto` (auto: Tesseract dulu, halaman berkeyakinan rendah ke vision). Pemeriksaan kualitas OCR; bila sebagian besar halaman gagal, tolak dokumen dengan pesan ramah. Batas jumlah halaman untuk jalur vision, gambar diperkecil (sisi panjang ±1600 px, JPEG). LANGKAH PERTAMA: skrip uji sekali pakai di scratchpad untuk membuktikan 9router meneruskan gambar (`image_url` base64) ke model vision. Temannya memakai Gemini untuk OCR tulisan tangan dan hasilnya baik.
   Masukan dari teman pemilik (memakai Gemini untuk OCR tulisan tangan): kirim per kelompok, bukan per halaman. Dia mengirim satu grup (5 berkas, maksimal 10 MB) per panggilan; sarannya bila satu dokumen terlalu berat, pecah per 5 sampai 10 halaman. Jadi `router_vision` memakai batch 5 sampai 10 halaman per panggilan (gambar diperkecil, potong batch agar payload dan `ROUTER_TIMEOUT` aman; angka pastinya dari skrip uji), halaman diberi nomor agar keluaran bisa dipecah kembali per halaman. Engine vision HANYA mentranskrip; teksnya lalu masuk ke `llm_analyzer` seperti biasa (jangan menggabung OCR dan penilaian dalam satu panggilan, karena penyamaran konten eksplisit dan pemetaan paragraf harus tetap jalan).
   STATUS 2026-11-24: langkah pertama selesai (lihat bagian "Hasil uji OCR vision" di bawah); aturan R26 ditulis; KODE R26 SELESAI (irisan 42: `extraction/vision.py`, `ocr.py`, `summarizer._generate(images=...)`, `reader_jobs`; backend 1356 tes lulus). Sudah diuji ke 9router lokal nyata lewat `prepare_pdf` (DML tulisan tangan terbaca, kualitas 0,98; Tere Liye dan 16 halaman Konspirasi normal; rincian di CHANGELOG irisan 42). Sisa: buku scan utuh lewat vision, scan miring/buram/dua kolom, lalu redeploy Fly.
3. Uji empat dokumen: PDF novel biasa, artikel ilmiah PDF, OCR novel scan bagus, PDF scan tulisan tangan tugas kuliah (butuh tampilan teks hasil ekstraksi bila ingin menunjukkan OCR-nya, karena tugas kuliah akan ditolak sebagai bukan novel).
4. Progres analisis di UI plus estimasi realistis: SELESAI 2026-11-24 (R27, irisan 43: progres nyata untuk membaca, analisis, rangkuman, tokoh, relasi; komponen `ProgressLoader`; estimasi 0,3 detik per paragraf). Sisa: lihat di peramban, jalankan migrasi 0022 di Postgres, redeploy Fly dan build ulang Netlify.
5. Setel ambang rating untuk LLM (Frankenstein 2,2% kekerasan jatuh General padahal diharapkan Teen/Mature); uji Alice dan Crime and Punishment.

### B. Pembayaran
6. Invoice baru dan di Riwayat tombol lihat dan unduh invoice: SELESAI KODE 2026-11-24 (R29, irisan 45; format acuan dari pemilik, tanpa kode VA). Sisa: lihat di peramban, redeploy. Butir 7 (harga) masih menunggu angka dari pemilik.
7. Harga paket yang lebih proper (angka dari pemilik; SPEC dan tes tier ikut berubah).
8. Pembayaran tanpa pindah ke halaman Midtrans: KODE DITULIS 2026-11-24 (R30, irisan 46, Snap embed). Tes ditulis tetapi belum dijalankan (pemilik yang menjalankan tes sejak 2026-11-24; lihat memori `pemilik-jalankan-tes`). Sisa: pemilik menjalankan tes dan melapor galat, coba dengan akun Midtrans sandbox (isi `MIDTRANS_CLIENT_KEY`, aktifkan Snap), migrasi 0023, redeploy.
9. Hapus email tagihan; ganti dengan email pengingat langganan hampir habis. Butuh penjadwal harian: endpoint yang dipanggil cron eksternal gratis (disukai) atau Fly scheduled machine, karena mesin backend bisa tidur.

### C. Admin dan poles
10. UC-16 (suspend akun) saja; UC-15 (daftar akun) dibatalkan. Rancangan: cari lewat email persis, info disamarkan, alasan wajib, tabel audit log (migrasi baru), email pemberitahuan, reaktivasi, halaman kebijakan privasi. Pemilik menyesuaikan SRS/SDD/UC sendiri.
11. Filter bulan/tahun di dashboard admin: KODE DITULIS 2026-11-24 (R31, irisan 47); tes dijalankan pemilik. Sisa: lihat di peramban.
12. Animasi lebih menarik dan tampilan mobile (kerjakan terakhir, beri batas waktu).

### D. Setelah fitur beku
13. Tes white box (pytest, pytest-cov, radon: cakupan, kompleksitas siklomatik, basis path) dan black box API (pytest: partisi ekivalen, nilai batas) dan black box UI (Playwright dengan server LLM palsu dan pembayaran tersimulasi). Dokumen md/pdf.
14. Sinkron SRS/SDD/diagram (tanpa XLM, UC-15 dicabut, UC-16 ditambah, invoice, pengingat, filter).
15. Deploy akhir: redeploy backend, build ulang frontend Netlify bila UI berubah (Make public), admin di Fly, URL notifikasi Midtrans, latihan presentasi, lalu kembalikan Fly ke hemat.

## Hasil uji OCR vision (2026-11-24, butir 2 langkah pertama SELESAI, belum ada kode produksi)
Skrip sekali pakai ada di `C:\Users\Edi AP\AppData\Local\Temp\antigravity\` (`vision_probe.py`, `compare_ocr.py`, `measure_conf.py`), di luar repo. Jalankan dengan `backend\.venv\Scripts\python.exe` dan `$env:PYTHONIOENCODING='utf-8'` (konsol Windows cp1252 gagal mencetak karakter seperti panah). Empat PDF uji ada di `system design/analysis test/` (sudah di `.gitignore`).

**Terbukti:**
- 9router meneruskan `image_url` base64 ke model vision (combo `Narative`, model yang menjawab `gemini-3.8-flash-n`). Gemini langsung tidak perlu sebagai jalur utama.
- Format permintaan: `messages[0].content` berisi satu bagian `text` (instruksi) dan beberapa bagian `image_url`. Instruksi meminta penanda `===HALAMAN k===` di awal tiap halaman. Penanda lengkap dan urut pada semua batch (6 dan 10 halaman pendek, 5 dan 10 halaman padat), panjang keluaran cocok dengan harapan (13.878 dari 13.780; 27.760 dari 27.561), tidak ada halaman terpotong atau tertukar.
- Gambar: sisi panjang ±1600 px, JPEG kualitas 70. Satu halaman padat ±130 sampai 260 KB, 10 halaman padat ±2,6 MB.
- Waktu: 10 halaman padat 54 detik, 8 halaman novel scan 32 detik, 2 halaman tulisan tangan 28 sampai 71 detik (bervariasi). Semua jauh di bawah `ROUTER_TIMEOUT` 300.
- Model memakai ±1.000 token berpikir per panggilan, jadi `max_tokens` harus longgar (kira-kira 1,2 kali panjang teks yang diharapkan ditambah cadangan).

**Perbandingan pada PDF uji:**

| PDF | Halaman | Perlu OCR | Tesseract | Vision |
|---|---|---|---|---|
| Wajib Tulis DML (tulisan tangan, CamScanner) | 2 | 2 | teks kacau, kamus 77% dan 85% | benar, kamus 99% dan 92% |
| Konspirasi Alam Semesta (novel scan) | 246 | 246 | baik, 86 sampai 97%, ±1,3 dtk per halaman, ada salah huruf kecil | baik, 87 sampai 99%, ±4 dtk per halaman |
| Tere Liye | 255 | 4 (sampul dan iklan) | sampah atau kosong | benar |
| Artikel ilmiah Android Malware | 15 | 0 | tidak dipakai | tidak dipakai |

Tere Liye dan artikel ilmiah sebenarnya PDF teks, jalur teksnya sudah cukup.

**Temuan yang mengubah rancangan `auto`:** persentase kata dikenali kamus (pemeriksaan mutu OCR sekarang) TIDAK memisahkan tulisan tangan dari novel (77 sampai 85% lawan 86 sampai 97%, tumpang tindih; ambang tolak sekarang 50% meloloskan tulisan tangan yang kacau). Keyakinan per kata dari Tesseract (kolom `conf` pada keluaran `tsv`) memisahkan dengan bersih pada 13 halaman yang diukur:

| Jenis | Rata-rata `conf` | Porsi kata dengan `conf` ≥ 80 |
|---|---|---|
| Tulisan tangan (2 halaman) | 48,7 dan 57,1 | 17% dan 23% |
| Novel scan (11 halaman) | 88,3 sampai 92,9 | 87 sampai 96% |

Halaman dengan hanya 0 sampai 1 kata (sampul, iklan) tidak punya `conf` yang berarti, jadi aturan perlu jumlah kata minimal. Usul: halaman dikirim ke vision bila rata-rata `conf` di bawah ±75 (jarak aman di tengah celah 57 sampai 88) atau halaman hampir tanpa kata namun berisi gambar. Angka ini diukur pada 13 halaman dari 2 dokumen, belum pada scan miring, buram, atau dua kolom; setel ulang dengan data tambahan sebelum dibekukan di SPEC.

**Belum teruji:** scan miring atau buram, dua kolom, halaman berisi konten eksplisit yang mungkin ditolak model, satu buku utuh lewat vision (246 halaman kira-kira 31 batch dan 430 ribu token), variasi waktu per panggilan (hanya satu atau dua kali jalan per ukuran), dan akurasi vision yang dibandingkan dengan teks acuan (hanya dibaca mata, plus rasio kamus).

**Keputusan pemilik (2026-11-24):** batch `router_vision` 8 halaman per panggilan dengan muatan maksimal ±6 MB, keduanya jadi pengaturan (bukan konstanta), bisa disetel lagi setelah uji scan nyata.

**Urutan berikutnya untuk butir 2:** (1) SELESAI 2026-11-24: aturan R26 ditulis di `docs/SPEC.md` (keputusan pemilik: `conf` 75, batas 60 halaman, bawaan `auto`, gambar boleh ke 9router atau Gemini); (2) tulis tes yang gagal dengan fake seperti `tests/router_fake.py` (perlu diperluas agar memahami bagian `image_url`); (3) implementasi minimal; (4) laporan jujur; (5) sinkron SPEC dan CHANGELOG. Pemeriksaan kualitas mutu OCR yang lama (kamus 50%) tetap dipertahankan sebagai jaring pengaman akhir.

**Catatan keamanan (kesalahan agen, 2026-11-24):** saat memeriksa nama pengaturan, agen mencari di `backend/.env` dengan `grep` yang menampilkan nilai `GEMINI_API_KEY` dan `ROUTER_API_KEY` utuh di riwayat sesi. Tidak ditulis ke berkas mana pun. Pemilik disarankan mengganti kedua kunci bila riwayat sesi bisa dilihat orang lain. Aturan untuk sesi berikutnya: cari nama kunci saja (mis. `grep -c` atau pola yang tidak mencocokkan nilai), jangan pernah tampilkan baris yang memuat nilai.

## Pembayaran yang meragukan (R32, 2026-11-24)
Usulan A (menu admin "Periksa pembayaran") dan B (tombol "Periksa status" di Riwayat plus penelusuran status akhir 7 hari) KODE DITULIS; tes dijalankan pemilik. Usulan C (penyapu berkala lewat cron eksternal yang memanggil endpoint rahasia) dan D (angka "perlu dicek" di dashboard) ditunda dan akan dikerjakan bersama butir pengingat langganan (butir 9 di atas) karena butuh penjadwal yang sama.

## Persiapan deploy berikutnya (disiapkan 2026-11-24, BELUM dijalankan; deploy Fly hanya atas izin pemilik)
Keadaan: semua kode sampai irisan 48 sudah lulus tes backend dan frontend di laptop pemilik; belum ada yang di-deploy ke Fly/Netlify sejak R23.
1. **Commit dan push** (pemilik yang push). Pastikan `backend/.env` dan `.env` tidak ikut; berkas uji buku (FannyHill.epub, Frankenstein.epub) jangan ikut.
2. **Migrasi:** 0022 (progres) dan 0023 (pembayaran Snap) berjalan otomatis lewat `docker-entrypoint.sh` (`alembic upgrade head`) saat backend Fly mulai. 0023 memakai `batch_alter_table` untuk mengubah `bank` dan `va_number` menjadi nullable; BELUM dijalankan di Postgres (hanya diperiksa terbaca sebagai head). Sebelum deploy: buat snapshot volume mesin database, lalu pantau log saat start pertama (`flyctl logs -a narative-api-ipl26`).
3. **Rahasia dan pengaturan baru:** `MIDTRANS_CLIENT_KEY` (salin lewat `deploy/fly/set-secrets.ps1`, yang sudah memuatnya, setelah diisi di `backend/.env`). Bawaan aman tanpa diisi: `OCR_ENGINE=auto`, `DOCUMENT_TYPE_CHECK=true`, `VISION_BATCH_PAGES=8`, `VISION_BATCH_MB=6`, `VISION_MAX_PAGES=60`, `OCR_TIMEOUT=120`. Ganti kunci API yang pernah tercetak di sesi (GEMINI_API_KEY, ROUTER_API_KEY) sebelum atau saat memasukkan rahasia baru.
4. **Midtrans:** aktifkan Snap dan metode yang diinginkan di dashboard; isi URL notifikasi dengan `https://narative-api-ipl26.fly.dev/billing/midtrans/notification` (URL ngrok lama sudah mati); kunci sandbox dan klien harus berpasangan.
5. **9router di Fly** harus bisa dipakai untuk gambar (vision): di laptop terbukti lewat combo `Narative` (model yang menjawab `gemini-3.8-flash-n`); pastikan 9router Fly memakai combo yang sama dan `ROUTER_BASE_URL`/`ROUTER_MODEL` benar. Tanpa vision, PDF tulisan tangan ditolak dengan pesan mutu rendah (tidak rusak).
6. **Backend:** dari folder proyek `flyctl deploy backend --config <jalur lengkap>\deploy\fly\backend.fly.toml --remote-only --ha=false`. Memori 2 GB cukup (Tesseract ada di Dockerfile). Mesin backend sedang diatur menyala terus sampai presentasi.
7. **Frontend:** build dengan `VITE_API_URL=https://narative-api-ipl26.fly.dev` (`npm run build` di folder `frontend`), unggah `frontend/dist` ke Netlify secara manual, pastikan statusnya Make public.
8. **Akun admin di Fly:** `flyctl ssh console -a narative-api-ipl26 -C "python -m app.tools.jadikan_admin email@kamu"` (akun harus sudah terdaftar di Fly; basis datanya terpisah dari lokal).
9. **Uji asap setelah deploy (urut):** daftar atau masuk; unggah EPUB novel lalu lihat progres 0 sampai 100 dan rating; unggah artikel PDF lalu pastikan "Dokumen ini bukan novel" tanpa kuota terpakai; unggah PDF scan atau tulisan tangan; beli paket lalu lihat metode pembayaran muncul di dalam halaman (sandbox), bayar, buka invoice dan unduh PDF, cek email invoice; halaman admin: filter bulan dan tahun, "Periksa pembayaran"; tampilan di HP.
10. **Risiko yang diketahui:** (a) pemeriksaan bukan-novel untuk EPUB sinkron tanpa batas waktu pendek: bila 9router dan Gemini mati, unggahan EPUB bisa menunggu lama (usulan: batas sekitar 20 detik, lewat itu dianggap novel; belum dikerjakan, menunggu persetujuan pemilik); (b) migrasi 0023 belum dicoba di Postgres; (c) Snap embed belum dicoba dengan akun Midtrans sungguhan; (d) semua tampilan baru belum dilihat di peramban dan HP; (e) cold start backend ±10 detik (502 sesaat itu wajar).
11. **Setelah presentasi:** kembalikan Fly ke hemat (`auto_stop_machines='stop'`, `min_machines_running=0`), pertimbangkan menghapus `/data/model` dan `/data/hf` di volume, periksa tagihan Fly (kredit starter kedaluwarsa 28 Nov 2026).
12. **Belum dikerjakan (butir sisa):** harga paket (menunggu brainstorming pemilik), email pengingat langganan beserta penjadwalnya dan penyapu pembayaran (C dan D di R32), UC-16 suspend akun, tampilan mobile (audit), animasi lain, tes white/black box dan dokumennya, sinkron SRS/SDD/diagram.

## Keputusan yang masih ditunggu dari pemilik
- Format invoice dan daftar harga baru.
- Dokumen bukan novel: SUDAH DIJAWAB 2026-11-24 (status `not_novel`, lihat R28).
- Tanggal presentasi baru dan apakah dosen menilai PDF scan/OCR.
- Butir 2: SUDAH DIJAWAB 2026-11-24: `conf` Tesseract ambang 75 jadi sinyal `auto`, batas 60 halaman untuk vision, bawaan `OCR_ENGINE=auto`, gambar halaman boleh dikirim ke 9router atau Gemini (hemat: hanya halaman berkeyakinan rendah). Tercatat di SPEC R26.
- Ganti kunci API yang tercetak di sesi (lihat catatan keamanan).
