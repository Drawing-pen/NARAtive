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
1. **Dokumen bukan novel (artikel, dll).** Usul: tambah field `jenis_dokumen` pada panggilan LLM potongan pertama; bila bukan fiksi, tolak dengan pesan jelas (atau peringatan; pemilik belum memutuskan, saya condong menolak).
2. **OCR dengan mata bor yang bisa diganti.** Antarmuka engine: terima gambar halaman, kembalikan teks dan keyakinan. Engine: `tesseract` (sudah ada, ind+eng) dan `router_vision` (BARU, lewat 9router; cadangannya Gemini langsung). Pemilih `OCR_ENGINE=tesseract|router|auto` (auto: Tesseract dulu, halaman berkeyakinan rendah ke vision). Pemeriksaan kualitas OCR; bila sebagian besar halaman gagal, tolak dokumen dengan pesan ramah. Batas jumlah halaman untuk jalur vision, gambar diperkecil (sisi panjang ±1600 px, JPEG). LANGKAH PERTAMA: skrip uji sekali pakai di scratchpad untuk membuktikan 9router meneruskan gambar (`image_url` base64) ke model vision. Temannya memakai Gemini untuk OCR tulisan tangan dan hasilnya baik.
   Masukan dari teman pemilik (memakai Gemini untuk OCR tulisan tangan): kirim per kelompok, bukan per halaman. Dia mengirim satu grup (5 berkas, maksimal 10 MB) per panggilan; sarannya bila satu dokumen terlalu berat, pecah per 5 sampai 10 halaman. Jadi `router_vision` memakai batch 5 sampai 10 halaman per panggilan (gambar diperkecil, potong batch agar payload dan `ROUTER_TIMEOUT` aman; angka pastinya dari skrip uji), halaman diberi nomor agar keluaran bisa dipecah kembali per halaman. Engine vision HANYA mentranskrip; teksnya lalu masuk ke `llm_analyzer` seperti biasa (jangan menggabung OCR dan penilaian dalam satu panggilan, karena penyamaran konten eksplisit dan pemetaan paragraf harus tetap jalan).
3. Uji empat dokumen: PDF novel biasa, artikel ilmiah PDF, OCR novel scan bagus, PDF scan tulisan tangan tugas kuliah (butuh tampilan teks hasil ekstraksi bila ingin menunjukkan OCR-nya, karena tugas kuliah akan ditolak sebagai bukan novel).
4. Progres analisis di UI plus estimasi realistis (0,5 detik per paragraf jadi ±0,3).
5. Setel ambang rating untuk LLM (Frankenstein 2,2% kekerasan jatuh General padahal diharapkan Teen/Mature); uji Alice dan Crime and Punishment.

### B. Pembayaran
6. Invoice baru (pemilik punya format yang lebih proper; minta formatnya) dan di Riwayat tombol lihat dan unduh invoice.
7. Harga paket yang lebih proper (angka dari pemilik; SPEC dan tes tier ikut berubah).
8. Pembayaran tanpa pindah ke halaman Midtrans: Snap embed (`snap.embed`) menampilkan semua metode di dalam halaman sendiri. Baca dulu cara pembayaran sekarang sebelum memperkirakan besar perubahan.
9. Hapus email tagihan; ganti dengan email pengingat langganan hampir habis. Butuh penjadwal harian: endpoint yang dipanggil cron eksternal gratis (disukai) atau Fly scheduled machine, karena mesin backend bisa tidur.

### C. Admin dan poles
10. UC-16 (suspend akun) saja; UC-15 (daftar akun) dibatalkan. Rancangan: cari lewat email persis, info disamarkan, alasan wajib, tabel audit log (migrasi baru), email pemberitahuan, reaktivasi, halaman kebijakan privasi. Pemilik menyesuaikan SRS/SDD/UC sendiri.
11. Filter bulan/tahun di dashboard admin.
12. Animasi lebih menarik dan tampilan mobile (kerjakan terakhir, beri batas waktu).

### D. Setelah fitur beku
13. Tes white box (pytest, pytest-cov, radon: cakupan, kompleksitas siklomatik, basis path) dan black box API (pytest: partisi ekivalen, nilai batas) dan black box UI (Playwright dengan server LLM palsu dan pembayaran tersimulasi). Dokumen md/pdf.
14. Sinkron SRS/SDD/diagram (tanpa XLM, UC-15 dicabut, UC-16 ditambah, invoice, pengingat, filter).
15. Deploy akhir: redeploy backend, build ulang frontend Netlify bila UI berubah (Make public), admin di Fly, URL notifikasi Midtrans, latihan presentasi, lalu kembalikan Fly ke hemat.

## Keputusan yang masih ditunggu dari pemilik
- Format invoice dan daftar harga baru.
- Dokumen bukan novel: ditolak atau diberi peringatan.
- Tanggal presentasi baru dan apakah dosen menilai PDF scan/OCR.
