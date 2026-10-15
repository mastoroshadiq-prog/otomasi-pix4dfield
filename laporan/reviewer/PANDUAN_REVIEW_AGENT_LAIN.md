# Panduan: Membawa Pekerjaan Ini ke Agent AI Lain untuk Review

Tujuan: review independen dilakukan oleh **agent AI lain** (bukan agent pelaksana
"deep"). Semua bahan sudah disiapkan di folder `laporan/reviewer/`.

## Isi paket

| Berkas | Fungsi |
|---|---|
| `RINGKASAN_PROYEK_UNTUK_REVIEW.md` | Konteks mandiri proyek (mulai dari sini) |
| `BRIEF.md` | Aturan main reviewer + checklist A–H + format laporan |
| `PAKET_KODE_UNTUK_REVIEW.md` (243 KB) | SEMUA kode+tes+spec+bukti dalam 1 berkas — untuk AI chat |
| `paket_review_ekspor_blok_2026-10-14.zip` (86 KB, 36 berkas) | Versi ZIP (dokumen, kode, tes, bukti teks, log git, hasil pytest) |
| `buat_paket_review.py` | Generator ulang paket di atas (jalankan bila kode berubah) |

Catatan privasi: paket **tidak memuat raster maupun koordinat poligon blok**
(`blok.geojson`, `kalibrasi.json` hanya ada di repo lokal). Jangan sertakan
`LAPORAN_REVIEW_2026-10-14.md` (hasil reviewer percobaan) — biarkan reviewer baru
membuat penilaiannya sendiri.

## Opsi A — Agent dengan akses file di komputer ini (paling kuat)

Cocok untuk: sesi Qoder baru yang dibuka pada folder `D:\pix4dfield_exporting_tools`,
Codex CLI, Claude Code, Gemini CLI, atau tool lain yang bisa membaca/menjalankan
perintah. Kelebihan: bisa menjalankan tes dan memverifikasi angka ke data nyata.

Buka tool tersebut dengan folder `D:\pix4dfield_exporting_tools` (beri akses baca;
sebaiknya tanpa izin tulis), lalu tempel prompt ini:

```text
Kamu adalah reviewer independen untuk pekerjaan tool "Ekspor Blok Otomatis" di repo
ini. Jangan mengandalkan konteks/memori agent mana pun selain isi repo. Tugasmu HANYA
me-review (read-only): jangan mengubah kode/berkas apa pun, jangan menjalankan batch
ekspor, jangan membuka server.

Langkah:
1. Baca laporan/reviewer/RINGKASAN_PROYEK_UNTUK_REVIEW.md (konteks pekerjaan).
2. Baca laporan/reviewer/BRIEF.md dan ikuti SEMUA aturan + checklist A–H di dalamnya.
3. Review seluruh pekerjaan sesuai brief (mode falsifikasi: uji klaim, cari kelemahan).
   Jalankan tes otomatis seperti dijelaskan BRIEF.
4. Tulis laporanmu (bahasa Indonesia, format di BRIEF) ke
   laporan/reviewer/LAPORAN_REVIEW_<namamu>_<tanggal>.md — ini satu-satunya berkas
   yang boleh kamu tulis.

Abaikan berkas LAPORAN_REVIEW_*.md yang sudah ada; buat penilaianmu sendiri.
```

## Opsi B — AI berbasis chat/cloud tanpa akses file

Cocok untuk: ChatGPT, Claude web, Gemini, dan sejenisnya. Unggah
`paket_review_ekspor_blok_2026-10-14.zip` (atau tempel isi
`PAKET_KODE_UNTUK_REVIEW.md` bila upload tidak memungkinkan — 243 KB mungkin perlu
dipotong; minimal bagian 0–1 + kode inti), lalu tempel prompt ini:

```text
Lampiran: paket review proyek perangkat lunak "Ekspor Blok Otomatis"
(Python/Flask/rasterio). Paket memuat kode, tes, dokumen kontrak, dan bukti teks;
tidak memuat data raster.

Tugasmu: review independen: mulai dari
laporan/reviewer/RINGKASAN_PROYEK_UNTUK_REVIEW.md, lalu laporan/reviewer/BRIEF.md
dan ikuti aturan + checklist A–H di BRIEF. Verifikasi setiap klaim ke kode/bukti
yang dilampirkan; tandai klaim yang tidak bisa kamu verifikasi. Hasilkan laporan
dalam bahasa Indonesia sesuai format di BRIEF (Kekuatan, Temuan KRITIS/TINGGI/
SEDANG/RENDAH dengan bukti file:baris, Rekomendasi, Penilaian akhir).
```

Keterbatasan Opsi B: reviewer tidak bisa menjalankan tes atau menghitung ulang angka
geometri (tidak ada data mentah) — laporannya terbatas pada pembacaan kode & logika.

## Opsi C — Layanan review pihak ketiga (opsional, hati-hati privasi)

Bila Anda nyaman membawa kode ke cloud, repo bisa diunggah ke GitHub **privat** lalu
direview dengan layanan seperti CodeRabbit (alur pull request). Repo saat ini belum
punya remote, jadi ini butuh langkah tambahan; jangan lakukan tanpa keputusan Anda.

## Aturan keselamatan

- Reviewer WAJIB read-only: jangan beri izin tulis ke repo atau ke data
  (`F:\dataset`, `E:\`), jangan izinkan menjalankan batch ekspor / membuka server.
- Simpan laporan reviewer di `laporan/reviewer/` agar terkumpul.
- Untuk Opsi B, unggah hanya paket yang sudah disiapkan (tanpa raster/koordinat).

## Menilai kualitas review yang kembali

1. Setiap temuan harus berbukti `path:baris` + alasan — tolak yang hanya opini.
2. Cek acak 1–2 temuan ke kode asli; kalau salah baca, minta ulang dengan bukti.
3. Pastikan ada verdict akhir dan daftar "diperiksa & lolos" (cakupan).

## Regenerasi paket (bila kode berubah)

```bash
cd /d/pix4dfield_exporting_tools && .venv/Scripts/python.exe laporan/reviewer/buat_paket_review.py
```

Paket lama akan tertimpa dengan tanggal baru (nama ZIP memuat tanggal).
