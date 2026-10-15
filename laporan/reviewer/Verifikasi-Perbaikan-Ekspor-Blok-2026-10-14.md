# Laporan Verifikasi Perbaikan — Tool "Ekspor Blok Otomatis" (Pix4DField)

**Tanggal verifikasi:** 2026-10-14
**Verifikator:** Muse (independen; penulis review kedua yang direspons)
**Bahan:** `paket_verifikasi_perbaikan_2026-10-14.zip` (54 berkas: kode hasil perbaikan, `BUKTI_diff_vs_commit.txt` = diff lengkap vs commit `65b4b44`, `bukti_daftar_tes.txt`, bukti data nyata, kedua laporan review) + `PAKET_VERIFIKASI_PERBAIKAN.md` (berisi `LAPORAN_PERBAIKAN_2026-10-14.md`)
**Metode:** (1) baca diff per temuan dan nilai kebenaran logika perbaikan; (2) hitung ulang angka klaim (T-1); (3) install dependensi (rasterio 1.5.2 dkk.) dan **jalankan sendiri** 56 dari 68 tes — 12 tes PDF dikecualikan karena fixture `data/sumber/peta_blok.pdf` memang disensor dari paket (gagal dengan `FileNotFoundError`, bukan karena perbaikan); (4) bukti data nyata (resume batch, verifikasi piksel, md5, NIR/RedEdge) dinilai dari artefak yang disertakan — tidak dihitung ulang karena raster tidak ada di paket.
**Batasan:** perubahan belum di-commit (sesuai pernyataan implementer); yang diverifikasi adalah working tree di paket.

---

## 1. Verdict

**PERBAIKAN DINYATAKAN SELESAI — LAYAK LANJUT KE GATE 3**, dengan 3 nit dokumentasi kecil (§4) yang tidak menyentuh kode.

Dari 19 temuan bernomor pada review kedua (3 TINGGI, 3 SEDANG, 13 RENDAH incl. 5 temuan baru N-1..N-5): **18 diperbaiki dan terverifikasi** (kode + tes regresi), **1 di-de-scope eksplisit** atas keputusan pemilik proyek (S-2, tercatat di spec §5.1/§9/§10). Tidak ditemukan perbaikan yang setengah jalan, tidak ditemukan regresi pada perilaku yang sudah benar (penjaga: `test_proses_baris_copy_rgb_dan_legend` masih menegaskan rgb = JPEG; verifikasi piksel batch 24,7 GB tetap `max|diff| = 0,0`).

---

## 2. Status per temuan (hasil verifikasi independen)

### TINGGI — ketiganya TERPERBAIKI dan terverifikasi

**T-1 (estimasi disk).** Rumus diganti `estimasi = byte_src / luas_footprint × luas_blok × 0,84` (`core/layer_scan.py`: `luas_footprint_ha` dari maska alpha ortho ter-desimasi ≤1024 px, `estimasi_byte_output`, `RASIO_KOMPRESI_GATE2 = 0.84`). Hitung ulangku: 38.287.432.957 / 256,47 × 197,63 × 0,84 ≈ **24,78 GB vs aktual 24,71 GB → selisih 0,30%** ✓ (klaim 0,30% benar). Rumus ini menjawab keberatanku soal hardcode: hanya rasio kompresi 0,84 yang dikalibrasi dari Gate 2 (wajar — setting kompresi sama antar flight), sedangkan byte/ha diturunkan dari data aktual tiap flight. Dipakai di `app.py` (`/api/pindai`); `ValueError` untuk footprint nol ditangani sebagai 400. Tes: `test_estimasi_byte_output_terkalibrasi_gate2` (±15% thd angka nyata), `test_pindai_estimasi_berbasis_footprint` (endpoint — menutup celah "nol tes untuk /api/pindai" yang kutemukan).

**T-2 (resume).** `state.json` v2: `{versi, kode_flight, output_root, geom_blok, items}`. `_muat_state` kini: (a) abaikan resume bila flight berbeda (dengan catatan log); (b) verifikasi `dst_data`/`dst_rgb`/`dst_legend` ada + ukuran `dst_data` cocok (`_berkas_lengkap`); (c) `dilewati` dipertahankan tanpa cek berkas (benar — tidak ada berkasnya). `/api/jalankan` menolak folder berisi yang bukan `_auto` (400) dan state flight berbeda (400, pesan jelas menyebut kedua kode flight). Migrasi v1→v2 terbukti di data nyata (state 40 item termigrasi; resume ulang = 0 detik kerja). Tes: 4 skenario resume + 2 skenario endpoint — menutup celah "nol tes" sebelumnya.

**T-3 (log retry).** `run()` kini: nama log unik (`_{n}` bila detik sama) + handler lama **ditutup dan dilepas** sebelum FileHandler baru dipasang (sekaligus menutup kebocoran handle). Tes `test_retry_ulang_membuat_file_log_baru` memakai jalur UI yang sebenarnya (`r.retry("B00")` + join thread): log1 utuh, log2 ada dan berisi "selesai" — persis skenario bug yang dulu kureproduksi dari kode.

### SEDANG

**S-1.** Diimplementasikan (keputusan pemilik): `rencana_output` menandai `dilewati` + alasan bila poligon blok tak beririsan bbox layer; runner melewatinya; resume mempertahankannya. Tes mencakup parsial (dsm beririsan sebagian → tetap diproses ✓) dan defensif (tanpa info bounds → tetap pending, tidak salah dibuang ✓). Catatan jujur: cek memakai bbox, bukan footprint presisi — blok yang menyentuh bbox tapi di luar data aktual masih bisa menghasilkan file seluruh-nodata; sisa edge yang dapat diterima.

**S-2.** De-scope eksplisit di spec (§5.1, §9, §10 + catatan revisi di kepala dokumen). Dinilai sebagai keputusan produk yang sah dan terdokumentasi — kontrak tidak lagi berbohong.

**S-3.** `.gitignore` diganti pola whitelist: 13 berkas laporan inti + berkas bukti paket ini terlacak; raster/artefak besar tetap terabaikan. Klaim `git add -n` = 22 berkas konsisten dengan isi whitelist.

### RENDAH

**R-1.** Diregenerasi; `bukti_gate1_md5.txt`: `blok.geojson`/`qa_pdf_blok.json`/`qa_overlay_peta.png` md5 identik antara `laporan/gate1/` dan `data/`, `n_berlabel=459` ✓ (angka 459 sendiri tak dapat kuhitung ulang tanpa data — konsistensi internalnya yang terverifikasi).
**R-2.** Footer dibangun `_baris_konteks(gsd_cm, residual_m)` — GSD dari `abs(transform.a)`, residual dari `kalibrasi.json` (null-safe); `index.json` memuat keduanya; 8 kartu diregenerasi dengan nilai dari data ✓.
**R-3.** Tiga titik interpolasi → `createElement` + `textContent`; sisa `innerHTML` hanya `= ""` ✓. `node --check` disebut lolos (tidak diverifikasi ulang — node tak tersedia di sini; perubahan JS cukup dibaca).
**R-4.** `JALANKAN_LOCK` non-blocking mencakup seluruh seksi kritis (cek → bangun rows → buat Runner) ✓.
**R-5.** Kembalikan `None` + `SystemExit` berpesan jelas ✓.
**R-6.** `[:500]` dihapus; tes memakai 506 blok sintetis ✓.
**R-7.** `verify_gate2.py` kini `_cek_grid`: CRS sama + transform penuh a..f (tol 1e-6) direkonstruksi dari bounds; baca `geom_blok` (fallback v1). Verifikasi ulang batch nyata: **40/40 ok, VERIFIKASI: LOLOS** ✓.
**R-8.** Bukti baru presisi: ukuran sama (4.874.415.646 B), md5 berkas **berbeda**, SHA-256 piksel **identik** → observasi reviewer pertama terkonfirmasi dan diperhalus ("identik bitwise hanya benar di level piksel, bukan berkas"); didokumentasikan di `RINGKASAN.md` §1 ✓. Bukan bug tool — benar.

### Temuan baru N-1..N-5

**N-1.** `snapshot()` drop `geom`; state v2 simpan WKT sekali per blok di `geom_blok` ✓ (bukti: `bukti_state_v2_sanitized.json`, 8 blok).
**N-2.** `crop_layer` paksa DEFLATE untuk `*.data.tif` (predictor 3 float / 2 uint8); rgb tetap JPEG ✓ + tes piksel-eksak uint8.
**N-3.** Klaim "GDAL average menghormati nodata" **kuuji ulang independen di mesinku** (rasterio 1.5.2/GDAL ter-bundel, Linux): tes `test_overview_data_tidak_membaurkan_nodata` lolos — overview hanya berisi tepat −10000.0 atau 7.5, tanpa nilai bauran. Premis gugur untuk `.data.tif` ✓. Sisa untuk `.rgb.tif` (bauran tepi tipis akibat JPEG menggeser piksel 0→1–3) diterima sebagai keterbatasan tampilan — penilaian yang proporsional; bukan artefak data (verifikasi piksel batch: 0 bocor).
**N-4.** `requirements.txt` di-pin 24 paket dari venv teruji ✓.
**N-5.** `workers` dihapus dari config + Runner; config lama tetap termuat (ada tes) ✓.

---

## 3. Hasil eksekusi tes independen

```
56 passed in 4.07s   (68 total − 12 tes PDF yang butuh fixture peta_blok.pdf,
                       dikecualikan; di mesin pembuat dilaporkan 68 passed)
```
12 tes PDF gagal di sini murni karena `pymupdf.FileNotFoundError` (fixture disensor dari paket — sesuai kebijakan privasi paket, bukan regresi). Seluruh 28 tes regresi baru untuk temuan T/S/R/N lolos di mesinku, termasuk `test_retry_ulang_membuat_file_log_baru`, `test_jalankan_tolak_folder_berisi_bukan_auto`, dan `test_estimasi_byte_output_terkalibrasi_gate2`.

---

## 4. Nit dokumentasi (tidak memengaruhi kode — sarankan dibetulkan sebelum commit)

1. **"Rumus lama meleset ≈3×"** tertulis di `LAPORAN_PERBAIKAN` §2 dan `RINGKASAN.md` §6 — angka yang terukur adalah **≈39×** (0,63 GB vs 24,71 GB). Kemungkinan typo (angka 9 hilang).
2. **Jumlah tes tidak konsisten:** `LAPORAN_PERBAIKAN` §1 dan `bukti_daftar_tes.txt` = 68, tetapi `RINGKASAN.md` §6 menulis "40 → 63" — RINGKASAN tampaknya ditulis sebelum 5 tes terakhir ditambahkan.
3. **`BUKTI_diff_vs_commit.txt` sedikit basi** untuk `.gitignore`: tidak mencakup baris whitelist `BUKTI_*`/`bukti_*`/`verify_gate2_run_*`/`LAPORAN_PERBAIKAN` yang ada di berkas final. Regenerasi diff sebelum commit.

---

## 5. Sisa pekerjaan menuju Gate 3

1. Betulkan 3 nit di §4, lalu **commit** (perubahan masih di working tree).
2. Sebelum batch flight penuh: hitung proyeksi waktu & disk memakai rumus T-1 yang baru (contoh: 8 blok ≈ 827 dtk untuk 40 item — ekstrapolasi ke N blok).
3. Pada flight berikutnya, verifikasi ulang R-8 (apakah Pix4DField benar-benar mengekspor NIR ≠ RedEdge) — sudah dicatat sebagai catatan di RINGKASAN.
4. Opsional: pertimbangkan cek footprint presisi (bukan bbox) untuk S-1 bila flight besar menunjukkan banyak file seluruh-nodata.

**Penilaian akhir verifikasi: PERBAIKAN SELESAI.** Implementer merespons seluruh 19 temuan bernomor, tiap perbaikan disertai tes regresi yang menguji perilaku nyata (bukan tautologi), menjaga perilaku yang sudah benar, dan jujur soal batasannya (§5 laporan perbaikan: N-3 sebagian, S-2 keputusan pemilik, belum commit). Tidak ada temuan baru dari sisi verifikator pada kode perbaikan ini.
