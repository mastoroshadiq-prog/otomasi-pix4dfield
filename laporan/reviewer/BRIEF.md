# Brief Review Independen — Ekspor Blok Otomatis (Pix4DField)

Brief ini untuk SEMUA agent AI (sesi baru, model lain, tool lain) yang diminta
me-review hasil pekerjaan tool ini secara independen. Brief bersifat mandiri:
cukup baca berkas ini + repo, tanpa perlu konteks sesi pembuatnya.

## Ringkasan proyek

- Tool lokal Python (Flask + rasterio) di `D:\pix4dfield_exporting_tools`.
- Fungsi: memotong (crop) ekspor Pix4DField full-extent per blok kebun memakai
  peta blok PDF; UI web lokal 4 tahap (Setup / Pindai / Jalankan / Validasi),
  bahasa Indonesia.
- Status saat brief dibuat (2026-10-14): Gate 0–2 selesai & terverifikasi
  (batch 8 blok `FLG01-AMEIII`); Gate 3 (flight penuh) belum dijalankan.
  HEAD = `65b4b44`. Belum pernah di-review pihak independen.
- Dokumen kontrak: spec `docs/superpowers/specs/2026-10-13-ekspor-blok-otomatis-design.md`,
  rencana `docs/superpowers/plans/2026-10-13-ekspor-blok-otomatis-implementasi.md`.

## Aturan main (wajib dipatuhi reviewer)

1. **Read-only.** Satu-satunya berkas yang boleh kamu tulis adalah laporanmu
   sendiri di `laporan/reviewer/`. Jangan ubah kode, jangan `git commit`,
   jangan pindahkan HEAD.
2. **Jangan jalankan hal berat/berisiko:** dilarang menjalankan batch ekspor
   (`run_gate2.py`, `core/runner.py` sebagai proses nyata), membuka server
   Flask, atau menyentuh/menulis apa pun di `F:\dataset`, `E:\`, dan folder
   sumber data produksi. Baca daftar file boleh, menulis tidak.
3. **Boleh & dianjurkan:** membaca seluruh berkas repo, `git log/show/diff`,
   dan menjalankan tes otomatis.
4. **Setiap temuan wajib berbukti:** `path/berkas.py:baris` + kutipan kode
   atau keluaran perintah yang bisa direproduksi + dampak + usul perbaikan.
   Jangan percaya dokumen — verifikasi ke kode.
5. **Jangan dispatch subagent.** Kerjakan seluruh review sendiri, boleh
   beberapa pass.
6. Artefak biner besar (GeoTIFF/PNG/log di `laporan/`) jangan dibaca mentah —
   pakai skrip kecil untuk sampel bila perlu.
7. **Abaikan hasil review yang sudah ada.** Jika menemukan berkas
   `LAPORAN_REVIEW_*.md` (review dari reviewer lain), jangan membacanya — buat
   penilaianmu sendiri agar tidak ter-anker.

## Lingkungan

- Windows + Git Bash. cwd shell reset tiap perintah → awali setiap perintah
  dengan `cd /d/pix4dfield_exporting_tools &&`.
- Python venv: `.venv/Scripts/python.exe`. Set `PYTHONIOENCODING=utf-8` bila
  menjalankan skrip.
- Tes: `cd /d/pix4dfield_exporting_tools && .venv/Scripts/python.exe -m pytest tests/ -q`
  (harus lulus; laporkan jumlah tes lulus/gagal).
- GDAL CLI **tidak tersedia** (tidak ada `gdalwarp`/`gdalinfo` di PATH) —
  semua I/O raster lewat rasterio. Jangan sarankan solusi yang butuh CLI GDAL
  kecuali sebagai opsi pemasangan baru.

## Bahan wajib dibaca

1. `laporan/reviewer/RINGKASAN_PROYEK_UNTUK_REVIEW.md` — ringkasan pekerjaan dari
   pihak pelaksana (SEMUA klaim di dalamnya wajib diverifikasi ke kode/bukti).
2. Spec + rencana (path di atas) — spec adalah kontrak perilaku.
3. `README.md`.
4. Kode: `app.py`, `core/*.py` (`pdf_blok`, `layer_scan`, `crop_engine`,
   `palet`, `qa_overlay`, `runner`, `config`, `kartu`), `static/app.js`,
   `templates/index.html`.
5. Bukti gate: `laporan/_uji_d17/RINGKASAN.md`, `laporan/_uji_d17/verify_gate2.py`,
   `laporan/_uji_d17/gate2_verifikasi.json`, `laporan/gate1/`.
6. Riwayat: `git log --oneline` (kode mulai commit `3158105`).

## Sudut review (mode falsifikasi, jangan sekadar mengiyakan)

A. **Kesesuaian spec:** baca tiap requirement spec → tunjukkan lokasi
   implementasinya di kode, atau tandai GAP.
B. **Kebenaran geometri:** kalibrasi affine PDF→UTM (`core/pdf_blok.py`),
   transformasi crop (`core/crop_engine.py`), transformasi kartu validasi
   (`core/kartu.py`). Cari off-by-one, y-flip (north-up vs baris array),
   pembulatan piksel.
C. **Keselamatan data:** buktikan tidak ada jalur kode yang menulis ke folder
   sumber; perilaku bila folder output sudah berisi arsip lama (spesifikasi:
   arsip lama tidak pernah ditimpa); mekanisme resume `state.json`.
D. **Konkurensi & ketahanan:** thread Runner vs request Flask, tombol
   Batalkan, retry; konsumsi memori untuk raster besar (windowed read?).
E. **Keamanan web:** path traversal di endpoint unduh/file kartu, escaping
   template (XSS via nama file/geojson?), binding hanya 127.0.0.1.
F. **Kualitas tes:** tes menguji perilaku nyata atau hanya smoke test? Celah
   penting yang tidak tercakup?
G. **Audit angka klaim** (sumber: `RINGKASAN.md`): tabel luas/IoU 8 blok,
   40/40 item batch, `max|diff| = 0`, derau JPEG ±0,63/255, rasio kompresi
   ±20–23% vs LZW. Bisakah direproduksi dari artefak yang ada? Periksa apakah
   `verify_gate2.py` self-konsisten atau bias konfirmasi (mis. membandingkan
   data dengan dirinya sendiri). Cek minimal 2 angka.
H. **Edge case:** sel PDF cacat/self-intersecting (sudah ada 1 perbaikan
   `make_valid`), path Windows, blok tanpa shp, ekspor parsial.

## Format laporan

- Struktur: Ringkasan & verdict → Kekuatan (spesifik) → Temuan
  (KRITIS / TINGGI / SEDANG / RENDAH; tiap temuan: bukti `path:baris`,
  dampak, usul perbaikan) → Rekomendasi → Penilaian akhir
  (siap produksi / perlu perbaikan / belum siap).
- Bahasa Indonesia. Sertakan cakupan "diperiksa dan lolos" agar jelas apa
  yang sudah dicek.
- Simpan ke `laporan/reviewer/LAPORAN_REVIEW_<tanggal>.md` (satu-satunya
  penulisan yang diizinkan).
