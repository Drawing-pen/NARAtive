# Daftar perubahan SRS dan SDD agar sesuai sistem saat ini

Dibuat 2026-11-03 dengan membaca SRS (22 September 2026, 35 halaman) dan SDD (22 September 2026, 40 halaman, termasuk diagram DFD, activity, dan sequence) lalu membandingkannya dengan `docs/SPEC.md` dan kode. SRS dan SDD adalah dokumen milikmu; berkas ini hanya daftar kerja, tidak mengubah keduanya. Rujukan kode yang menjadi acuan ada di `docs/SPEC.md` dan riwayatnya di `docs/CHANGELOG.md`.

**Cara memakai:** kerjakan dari prioritas A ke C. Prioritas A adalah isi dokumen yang sekarang BERTENTANGAN dengan sistem (dosen bisa menemukannya saat demo). B adalah hal baru yang belum ada di dokumen. C adalah istilah dan kerapian. Teks bercetak miring pada kolom "ubah menjadi" siap ditempel dan boleh kamu perhalus.

**Yang belum bisa saya pastikan dari PDF:** isi diagram SDD hanya saya periksa pada DFD (halaman 12), activity diagram unggah (13), dan sequence diagram unggah dan hasil analisis (28). Diagram lain saya simpulkan dari judulnya; periksa sendiri sebelum mengubahnya. Use case diagram di SRS (Gambar 4.1.1) adalah gambar yang tidak terbaca sebagai teks, jadi tidak saya periksa.

---

## SRS

### Prioritas A: bertentangan dengan sistem

| # | Lokasi | Isi sekarang | Ubah menjadi |
|---|---|---|---|
| A1 | 2.3 Tabel karakteristik pengguna, Standard | "terbatas 3 upload dokumen dan 50 halaman per dokumen" | *Standard (Free): maksimal 3 analisis per bulan, 3 e-book aktif, 50 halaman per unggahan.* |
| A2 | 2.3, Middle Tier | "tanpa batas upload, maksimal 300 halaman per dokumen" | *Middle: 15 analisis per bulan, 50 e-book aktif, maksimal 300 halaman per unggahan.* (Kode memang membatasi kuota Middle; angka ada di `backend/app/core/plans.py`.) |
| A3 | 2.3, High Tier | "tanpa batasan halaman/kuota" | Sesuai. Tambahkan: *tanpa batas analisis bulanan dan e-book aktif.* |
| A4 | FR-04 | "menerima unggahan dokumen e-book berformat PDF" | *...berformat PDF atau EPUB, termasuk PDF hasil scan.* (UC-01 sudah menyebut EPUB; FR-04 belum.) |
| A5 | FR-05 dan UC-02 (Purpose, Overview, Typical Course) | Dokumen digabung menjadi satu koleksi yang "dianalisis sebagai satu kesatuan alur cerita" | Sistem membuat **seri**: tiap buku tetap dianalisis sendiri-sendiri; seri hanya mengelompokkan dan mengurutkan buku untuk tampilan dan navigasi baca. Lihat teks UC-02 baru di bawah. |
| A6 | FR-13 dan UC-10 (judul, Overview, Post-Condition, Typical Course) | "biodata tokoh secara lengkap", "lengkap dengan peran serta biodata", "daftar biodata tokoh beserta peran dan frekuensi kemunculan" | Kartu tokoh hanya memuat **foto atau inisial, nama, nama lain, dan satu deskripsi** (siapa tokoh itu dan perannya dalam cerita). **Tidak ada** label peran (utama atau pendukung), usia, pekerjaan, atau kepribadian. Ganti istilah "biodata tokoh" menjadi "deskripsi tokoh" di seluruh dokumen (2.1, 2.2 poin 4, FR-13, 2.3 Middle, UC-10, UC-18 Overview). |
| A7 | UC-11 Overview, "(akrab/konflik)" | Dua jenis hubungan | Enam jenis: *pasangan, sahabat, teman, keluarga, musuh, kenalan.* Hubungan dibaca model bahasa dari isi cerita dan hanya ditampilkan bila ada kutipan teks yang mendukungnya; pengguna memilih "Semua bab" atau satu bab. |
| A8 | UC-13 Overview dan FR-16 | PDF memuat "rating konten, rangkuman cerita, dan highlight paragraf sensitif" | **Sudah sesuai (R17, 2026-11-09).** PDF kini memuat rangkuman keseluruhan dan rangkuman per bab bila rangkuman sudah dibuat (tanpa placeholder bila belum ada). Tidak perlu diubah di SRS; keputusan nomor 2 di bagian akhir berkas ini sudah selesai. |
| A9 | UC-03 Overview (rincian per dimensi dan alasan rating untuk Middle ke atas) | Dinyatakan tersedia | **Sudah dibangun (R16, 2026-11-09).** Rincian per dimensi (persen dan jumlah paragraf) dan alasan rating tersedia untuk Middle ke atas. Alasan disusun dari angka dan aturan rating (bukan dari LLM): mis. "Kekerasan 4,2% paragraf (9 paragraf) mencapai batas Teen: minimal 3% dan 2 paragraf." Tidak perlu diubah di SRS selain bila ingin menyebut bahwa alasan berbasis aturan. |
| A10 (KEPUTUSAN 2026-11-10: ditunda ke pengembangan lanjutan, tidak dibangun) | FR-17, FR-18, FR-19 dan UC-14, UC-15, UC-16; 2.2 poin 12; 2.3 baris Admin | Dashboard Admin dinyatakan ada | **Belum dibangun.** Pindahkan ke bagian "Pengembangan lanjutan" atau tandai "belum diimplementasikan". Kolom `users.role` dan `users.is_active` sudah ada (akun tidak aktif ditolak saat masuk), tetapi belum ada halaman atau endpoint admin. |
| A11 | 2.4 Server environment: RAM 1 sampai 2 GB, storage 1 GB | Spesifikasi minimum server | Terlalu kecil: berkas model saja 1,1 GB dan PyTorch beserta transformers dimuat ke memori. Pemakaian memori sebenarnya belum saya ukur; usulan sementara untuk rilis ini: *CPU saja cukup (tanpa GPU), RAM minimal 4 GB (disarankan 8 GB), storage minimal 10 GB.* Sesuaikan setelah kamu mengukur sendiri. |
| A12 | 3.3 butir 3 (Integrasi layanan eksternal): "Midtrans dan Gemini API" | Dua layanan | Tambahkan: *9router (penyedia model bahasa utama, dijalankan sebagai layanan terpisah), Gemini API sebagai cadangan, dan layanan email (SMTP) untuk kode verifikasi, atur ulang kata sandi, dan invoice.* Model bahasa dipakai untuk bobot cerita, rangkuman, serta deteksi tokoh dan relasi. |

### Prioritas B: ada di sistem, belum ada di dokumen

**Persyaratan fungsional baru (tambahkan ke Tabel 4.1):**

| ID usulan | Requirement |
|---|---|
| FR-01 (ubah) | *Sistem harus bisa mendaftarkan akun User baru dengan verifikasi alamat email lewat kode 6 angka.* |
| FR-27 | *Sistem harus memungkinkan User yang lupa kata sandi mengatur ulang kata sandi lewat kode yang dikirim ke emailnya.* |
| FR-28 | *Sistem harus memungkinkan User melihat profil akun (nama, email, paket, pemakaian kuota, riwayat pembayaran), mengubah nama, mengganti kata sandi, dan menghapus akun beserta seluruh datanya.* |
| FR-29 | *Sistem harus memungkinkan User memulai ulang deteksi tokoh dan membuat rangkuman atas permintaan.* (opsional; sudah tersirat di FR-12 dan FR-13) |

**Use case baru (tambahkan setelah UC-19):**

*UC-20 Mendaftar dengan Verifikasi Email* (Actor: calon pengguna; Cross Ref: FR-01, FR-03, NRF-03, NRF-07). Alur: pengguna mengisi nama, email, kata sandi (minimal 8 karakter); sistem mengirim kode 6 angka ke email (berlaku 10 menit, kirim ulang setelah 60 detik); pengguna memasukkan kode; sistem membuat akun Free dan langsung memasukkan pengguna. Alternatif: email sudah terdaftar; kode salah (maksimal 5 kali); kode kedaluwarsa.

*UC-21 Mengatur Ulang Kata Sandi* (Actor: pengguna terdaftar; Cross Ref: FR-27, NRF-03, NRF-07). Alur: pengguna memilih "Lupa kata sandi" di halaman masuk, mengisi email; sistem mengirim kode 6 angka bila akun ada (jawaban sistem selalu sama agar keberadaan akun tidak bocor); pengguna memasukkan kode dan kata sandi baru; sistem mengganti kata sandi dan langsung memasukkan pengguna. Alternatif: kode salah atau kedaluwarsa (pesan sama), 5 kesalahan menghanguskan kode.

*UC-22 Mengelola Profil Akun* (Actor: pengguna; Cross Ref: FR-28, FR-11). Alur: pengguna membuka halaman profil; melihat informasi akun dan pemakaian; mengubah nama; mengganti kata sandi (kata sandi lama wajib benar); melihat dan melanjutkan pembayaran yang menunggu; menghapus akun dengan konfirmasi kata sandi. Catatan: **riwayat pembayaran (UC-08) sekarang berada di halaman Profil**, bukan halaman terpisah.

**Perubahan alur pada use case yang sudah ada:**

- **UC-01 Typical Course dan Alternative Flow:** (a) tambahkan "sistem memeriksa batas e-book aktif" bersama halaman dan kuota; (b) urutan sebenarnya: sistem membaca isi file lalu memeriksa batas (bukan memeriksa halaman sebelum membaca); (c) "menyimpan dokumen" → *sistem menyimpan hanya teksnya, file asli tidak disimpan*; (d) Exceptional Flow baru: *PDF rusak atau terkunci kata sandi ditolak saat unggah*, *PDF yang tetap tanpa teks atau teksnya tidak terbaca berstatus gagal dengan alasan* (PDF hasil scan dibaca otomatis), dan *EPUB berDRM ditolak*; (d2) *PDF dibaca di latar dengan status "membaca" dan progres per halaman, kuota baru terpakai setelah berhasil dibaca*; (e) memilih beberapa file sekaligus mengunggahnya berurutan lalu menawarkan membuat seri; (f) analisis berjalan di latar dan halaman memperbarui status otomatis.
- **UC-02 (teks baru yang disarankan):** *Purpose: mengelompokkan beberapa e-book yang saling berkaitan menjadi satu seri agar mudah dikenali dan dibaca berurutan. Overview: pengguna memilih dua atau lebih e-book miliknya, memberi nama seri, dan menentukan urutannya. Tiap e-book tetap dianalisis dan dihitung kuotanya sendiri; seri tidak menggabungkan hasil analisis. Pengguna dapat mengubah nama, urutan, dan isi seri, atau membubarkannya (e-book tidak ikut terhapus).*
- **UC-04:** tambahkan bahwa teks EPUB tampil dengan format yang dibaca (judul, cetak tebal, miring); mode baca mengikuti pembagian bab.
- **UC-07:** tambahkan *mode simulasi bila kunci Midtrans tidak diatur (nomor VA contoh, tombol "simulasikan pembayaran")*, pembayaran yang menunggu dapat dilanjutkan dari halaman Profil, dan pay-per-check berupa paket 1, 3, atau 5 analisis tambahan.
- **UC-09:** rangkuman **tidak otomatis**; pengguna menekan "Buat rangkuman" dan prosesnya berjalan di latar. Paragraf seksual tidak dikirim ke model bahasa (diganti penanda). Bila model bahasa gagal, bab dirangkum sederhana tanpa AI.
- **UC-10:** deteksi tokoh berjalan otomatis setelah analisis selesai (Middle ke atas) dan bisa diulang lewat tombol "Deteksi ulang"; butuh layanan model bahasa.
- **UC-17 dan UC-18:** sudah sesuai (JPG, PNG, WebP; maksimal 2 MB; dikecilkan; berkas ikut terhapus). Tidak perlu diubah.

**Persyaratan non-fungsional baru (tambahkan ke Tabel 5.1):**

| ID usulan | Requirement |
|---|---|
| NRF-18 | *Paragraf bermuatan seksual tidak boleh dikirim ke layanan model bahasa pihak ketiga.* |
| NRF-19 | *Kegagalan layanan model bahasa tidak boleh menggagalkan analisis inti (rating dan Safe Mode); fitur yang bergantung padanya menampilkan hasil sebagian atau pesan yang jelas.* |
| NRF-20 | *Kode verifikasi dan atur ulang kata sandi disimpan sebagai hash, berlaku 10 menit, dan dibatasi 5 kali percobaan.* |

### Prioritas C: kerapian

- **1.3 butir 2** ("registrasi dan login"): tambahkan verifikasi email, lupa kata sandi, dan profil.
- **1.4 Tabel istilah:** tambahkan *Seri*, *Analisis tambahan (pay-per-check)* (sudah ada), *9router*, dan *Kode verifikasi*. Perbaiki ejaan "diigtal" dan "eletronik" pada istilah E-book.
- **2.2 poin 7** ("deskripsi lengkap dari novel EBook"): saya tidak menemukan fitur ini di sistem; hapus atau jelaskan maksudnya.
- **2.5 Batasan:** tambahkan *PDF yang dikunci kata sandi atau rusak ditolak*, *ukuran unggahan maksimal 100 MB*, dan catatan bahwa PDF hasil scan dibaca otomatis (pengenalan teks/OCR berjalan di server, tanpa pilihan di antarmuka); mutu hasil scan yang buruk membuat berkas gagal diproses dengan pesan yang jelas.
- **Pengujian yang belum terbukti:** NRF-01 (5 detik), NRF-02 (2 detik), NRF-11 (10 detik) belum diukur, dan NRF-14 (backup berkala) belum diimplementasikan. Jangan mengklaimnya selesai di laporan tanpa pengukuran.
- **Tanggal dan versi** di sampul: perbarui sebagai revisi.

---

## SDD

### Prioritas A: bertentangan dengan sistem

| # | Lokasi | Isi sekarang | Ubah menjadi |
|---|---|---|---|
| D1 | 2.3 paragraf terakhir: "biodata tokoh dan progres relasi ... diekstraksi menggunakan pendekatan Named Entity Recognition dan analisis kemunculan bersama (Amalvy et al., 2024)" | Pendekatan NER | Sistem **tidak lagi memakai NER**. *Tokoh dan relasi dibaca oleh model bahasa generatif per potongan bab (hingga sekitar 40.000 karakter), lalu digabungkan; jumlah kemunculan dan bobot hubungan dihitung oleh sistem, dan hubungan hanya ditampilkan bila kutipan buktinya ada di teks.* Rujukan Amalvy dkk. boleh tetap sebagai landasan, tetapi jangan ditulis sebagai metode yang dipakai. |
| D2 | 3.3 Basis data: daftar 12 tabel | `user`, `ebooks`, `analysis_results`, `chapters`, `characters`, `characters_relations`, `sensitive_paragraphs`, `subscriptions`, `transactions`, `payment_methods`, `usage_quota`, `sensitivity_profiles` | Lihat tabel padanan di bawah. |
| D3 | 4.1 DFD Level 0 dan Level 1 | Entitas eksternal: User, Admin, Payment Gateway; penyimpan data D1 sampai D6 | Tambahkan entitas eksternal **Layanan Model Bahasa (9router/Gemini)** dan **Layanan Email**; tandai alur Admin sebagai belum diimplementasikan; perbarui penyimpan data (lihat di bawah). |
| D4 | 4.2a Activity "Mengunggah Dokumen E-Book" | Setelah analisis, cabang "User Premium": deteksi tokoh, ekstraksi relasi, rangkuman per bab dan keseluruhan, otomatis | Rangkuman **tidak otomatis**. Setelah analisis selesai: Middle ke atas → deteksi tokoh dan relasi otomatis (model bahasa); rangkuman dibuat hanya bila pengguna menekan "Buat rangkuman". Tambahkan langkah *periksa kuota bulanan dan batas e-book aktif* dan cabang *PDF tanpa teks atau EPUB berDRM ditolak*. Sistem juga menambah langkah *penilaian bobot cerita oleh model bahasa dipadukan dengan sinyal model (0,7 dan 0,3)* dan analisis berjalan di antrean latar. |
| D5 | 4.3a Sequence "Mengunggah Dokumen E-Book" | Pengguna → Halaman → Sistem → Database; hasil dikembalikan setelah analisis | Unggah dijawab segera (status "diantre"); analisis berjalan di latar dan halaman memeriksa status berkala. Tambahkan peserta **Antrean/Pekerja analisis**, **Layanan Model Bahasa** (bobot cerita), dan langkah pemeriksaan kuota. |
| D6 | Abstrak dan 2.1, 2.2 | "biodata tokoh", "progres relasi antar tokoh" | Ganti ke *deskripsi tokoh* dan *relasi antar tokoh per bab*. |
| D7 | 3.1 Perangkat keras server: 2 vCPU, RAM 1 sampai 2 GB, storage 1 GB | Spesifikasi | Sama dengan A11 di SRS (berkas model 1,1 GB; usulan RAM minimal 4 GB, disarankan 8 GB; storage minimal 10 GB). |

**Padanan tabel basis data (untuk 3.3):**

| Di SDD | Di sistem sekarang | Catatan |
|---|---|---|
| `user` | `users` | Tambahan kolom: `tier`, `tier_expires_at`, `extra_checks`, `role`, `is_active` |
| `ebooks` | `documents` | Hasil agregat analisis (rating, persentase, bobot cerita) ada di tabel yang sama; ada `cover_path`, status rangkuman dan tokoh, `collection_id` |
| `analysis_results` | (tidak ada) | Digabung ke `documents` |
| `chapters` | `chapters` | Memuat judul dan rangkuman per bab |
| `sensitive_paragraphs` | `paragraphs` | Semua paragraf disimpan dengan skor bahasa kasar, seksual, kekerasan, emosi; ada kolom `markdown` dan `kind` |
| `characters` | `characters` | Berisi nama, nama lain (`aliases`), deskripsi (`biodata`), `mention_count`, `photo_path`; kolom peran, jenis kelamin, usia, pekerjaan, kepribadian, latar tidak lagi dipakai |
| `characters_relations` | `character_relations` | Per pasangan per bab: jenis hubungan dan bobot |
| `subscriptions` | (tidak dibuat) | Status langganan di `users.tier` dan `users.tier_expires_at` |
| `payment_methods` | (tidak dibuat) | Daftar bank didukung ada di konfigurasi |
| `transactions` | `transactions` | Sesuai |
| `usage_quota` | `usage_quota` | Sesuai |
| `sensitivity_profiles` | `sensitivity_profiles` | Sesuai |
| (baru) | `collections` | Seri e-book (UC-02) |
| (baru) | `email_verifications` | Pendaftaran tertunda dan kode verifikasi |
| (baru) | `password_resets` | Kode atur ulang kata sandi |

**Perubahan DFD (D3) yang konkret:** ganti D2 "ebooks" menjadi "documents (termasuk hasil analisis)", hapus D3 "analysis_results", ganti D4 menjadi "characters dan character_relations" (sudah sesuai), dan tambahkan penyimpan *collections*, *usage_quota*, *email_verifications*, serta *password_resets*. Proses "Manajemen Autentikasi" (daftar, verifikasi, masuk, atur ulang sandi) belum tampil di Level 1 dan sebaiknya ditambahkan. Proses "Manajemen Admin" ditandai belum diimplementasikan.

### Prioritas B: diagram baru atau diperbarui

**Diagram yang perlu diperbarui (periksa isinya, saya hanya menyimpulkan dari judul kecuali yang disebut di atas):**
- 4.2e dan 4.3e "Membuat Koleksi" → sebut "Membuat Seri"; tiap buku tetap dianalisis sendiri, seri tidak menggabungkan analisis.
- 4.2b, 4.3b "Melihat Hasil Analisis": rincian per dimensi dan alasan rating belum diimplementasikan.
- 4.2f, 4.3f "Membayar Fitur Premium": tambahkan mode simulasi, pembatalan, kedaluwarsa, dan notifikasi dari Payment Gateway (webhook) ke sistem; invoice dikirim lewat Layanan Email.
- 4.2g, 4.3g "Riwayat Pembayaran": sekarang di halaman Profil dan memuat tombol lanjutkan pembayaran untuk transaksi yang menunggu.
- 4.2 dan 4.3 "Melihat Biodata Tokoh" → "Melihat Deskripsi Tokoh": tanpa peran dan rincian; deteksi memakai model bahasa.
- 4.2 dan 4.3 "Melihat Progress Relasi": enam jenis hubungan, pilihan "Semua bab" atau satu bab.
- 4.2 dan 4.3 "Melihat Rangkuman Per Bab": rangkuman dibuat atas permintaan pengguna dan berjalan di latar (status "sedang membuat rangkuman").
- 4.2 dan 4.3 "Mengunduh Hasil Analisis": PDF belum memuat rangkuman (atau sesuaikan setelah keputusan A8).
- Diagram Admin (laporan pendapatan, daftar akun, tangguhkan akun): tandai belum diimplementasikan atau pindahkan ke pengembangan lanjutan.

**Diagram baru yang disarankan** (activity dan sequence): *Mendaftar dengan verifikasi email*, *Mengatur ulang kata sandi*, dan *Mengelola profil akun* (lihat UC-20 sampai UC-22 di atas). Peserta sequence: Pengguna, Halaman, Sistem, Database, **Layanan Email**.

**Peserta tambahan pada sequence diagram yang memakai model bahasa:** pada diagram unggah (bobot cerita), rangkuman, dan tokoh, tambahkan **Layanan Model Bahasa (9router, dengan Gemini sebagai cadangan)**.

### Prioritas C: kerapian

- **3.2 Lingkungan perangkat lunak:** tambahkan MySQL 8, Docker Compose (opsional untuk menjalankan), dan layanan model bahasa 9router. Tidak wajib menulis versi Python atau Node.
- **1.3 Gambaran dokumen:** sebut bahwa UML kini memuat diagram untuk pendaftaran, atur ulang kata sandi, dan profil.
- **Aktor "Payment Gateway":** tetap, tetapi tambahkan aktor eksternal **Layanan Model Bahasa** dan **Layanan Email** di Bab II fungsi.
- **Daftar pustaka:** pertahankan Amalvy dkk. dan Krawczyk dkk. sebagai landasan; tambahkan rujukan untuk pendekatan model bahasa generatif bila dosen meminta metode yang diacu.
- **Tanggal dan versi** di sampul: perbarui sebagai revisi.

---

## Hal yang sudah sesuai (tidak perlu diubah)

UC-05 Safe Mode, UC-06 hapus e-book, UC-12 profil sensitivitas, UC-17 dan UC-18 ganti cover dan foto, UC-19 ubah judul, alur dasar UC-01 sampai UC-04, FR-02, FR-03, FR-06 sampai FR-12, FR-20 sampai FR-26, NRF-03 sampai NRF-10, NRF-12, NRF-13, NRF-15 sampai NRF-17, tabel `transactions`, `usage_quota`, dan `sensitivity_profiles`, serta batas halaman Free (50) dan Middle (300).

## Urutan kerja yang saya sarankan

1. Kerjakan semua prioritas A SRS dan SDD (sekitar 20 butir; sebagian besar mengganti satu atau dua kalimat).
2. Putuskan hal yang mengubah isi dokumen: (a) panel admin: sudah diputuskan ditunda ke pengembangan lanjutan (2026-11-10), jadi cukup pindahkan di dokumen, (b) angka server minimum. (Keputusan PDF unduhan sudah selesai: rangkuman kini masuk PDF.)
3. Tambahkan UC-20 sampai UC-22 beserta diagramnya.
4. Perbarui tabel basis data dan DFD.
5. Terakhir, periksa seluruh diagram activity dan sequence satu per satu terhadap daftar di prioritas B.
