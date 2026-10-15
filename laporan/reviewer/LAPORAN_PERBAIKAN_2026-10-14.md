# Laporan Perbaikan — Respons atas Review Independen Kedua

**Untuk:** agent AI reviewer independen (verifikasi perbaikan)
**Dari:** pihak pelaksana (implementer tool)
**Tanggal:** 2026-10-14
**Proyek:** Ekspor Blok Otomatis (Pix4DField) — `D:\pix4dfield_exporting_tools`
**Masukan yang direspons:** `laporan/reviewer/Review-Independen-2-Ekspor-Blok-Otomatis-2026-10-14.md`
(verdict tertulis di review: "PERLU PERBAIKAN — 0 KRITIS, 3 TINGGI, 3 SEDANG, 10 RENDAH";
cakupan yang direspons di sini: T-1..T-3, S-1..S-3, R-1..R-8, dan N-1..N-5 — total 19 temuan bernomor)

> **Catatan kejujuran (baca dulu).** Semua klaim di dokumen ini menunjuk berkas, nama
> fungsi, nama tes, dan angka yang bisa Anda verifikasi langsung di paket. Klaim yang
> tidak terbukti ditulis apa adanya (lihat §5: premis N-3 gugur untuk data, R-8
> dikoreksi presisi). Semua perubahan **belum di-commit**; diff lengkap vs commit
> `65b4b44` disertakan sebagai bukti utama.

---

## 1. Status ringkas

| Kelompok | Temuan | Status |
|---|---|---|
| TINGGI | T-1, T-2, T-3 | Diperbaiki (kode + tes regresi) |
| SEDANG | S-1 | **Diimplementasikan** (keputusan pemilik proyek) |
| SEDANG | S-2 | **De-scope eksplisit di spec** (keputusan pemilik proyek) — §5.1/§9/§10 |
| SEDANG | S-3 | Diperbaiki (whitelist `.gitignore`) |
| RENDAH | R-1, R-2, R-3, R-4, R-5, R-6, R-7 | Diperbaiki (kode/skrip + tes) |
| RENDAH | R-8 | **Diverifikasi ulang + didokumentasikan** (bukan bug tool; bukti baru disertakan) |
| BARU | N-1, N-2, N-4, N-5 | Diperbaiki (kode + tes) |
| BARU | N-3 | **Diselesaikan sebagian via bukti**: premis gugur untuk `.data.tif` (diuji), sisa untuk `.rgb.tif` didokumentasikan sebagai keterbatasan tampilan |

Suite tes: **40 → 68 tes, semuanya lulus** (`pytest tests/ -q` → `68 passed`).
Perubahan: 16 berkas, +681/−65 baris (lihat `BUKTI_diff_vs_commit.txt`). Catatan privasi (repo GitHub publik): `laporan/gate1/blok.geojson` (koordinat blok nyata) dan `laporan/gate1/qa_overlay_peta.png` (peta kebun nyata) **tidak dilacak** — tetap lokal.

**Verifikasi ulang pada data nyata (batch Gate 2, 24,7 GB di `F:`):**

- Resume aman: `run_gate2.py` dijalankan ulang → **0 detik kerja, 40/40 tetap
  "selesai", 0 crop ulang**; `state.json` termigrasi v1 → v2 (lengkap dengan
  `kode_flight` + `geom_blok` 8 blok). Log: `logs/run_20261014_171634.log`
  berisi `Batch mulai: 0 item`.
- `verify_gate2.py` (versi baru) atas seluruh batch → **40/40 item ok;
  max|diff| data = 0,0 (salinan piksel eksak); 0 piksel bocor di luar poligon;
  rgb rata-rata 0,628/255; 23.027.446.780 B data / 197,63 ha; VERIFIKASI: LOLOS**.
  Output lengkap: `verify_gate2_run_20261014.txt`; ringkasan mesin:
  `gate2_verifikasi.json`.

---

## 2. Perbaikan per temuan

### T-1 (TINGGI) — Rumus estimasi disk salah

- **Tindakan:** rumus diganti estimasi berbasis footprint layer sumber:
  `estimasi = byte_src / luas_footprint × luas_blok × 0,84`, dengan
  `luas_footprint` dihitung dari maska band terakhir (alpha) terdesimasi 1024 px
  dan `0,84 = RASIO_KOMPRESI_GATE2` (hasil kalibrasi batch Gate 2).
  Berkas: `core/layer_scan.py` (`luas_footprint_ha`, `estimasi_byte_output`,
  `RASIO_KOMPRESI_GATE2`); pemakaian di `app.py` (`/api/pindai`).
- **Bukti angka (data nyata, dihitung ulang 2026-10-14):** byte sumber 5 layer
  = 38.287.432.957 B; footprint ortho = 256,47 ha; luas 8 blok = 197,63 ha →
  **estimasi 24.783.255.904 B (24,78 GB) vs aktual 24.708.559.348 B (24,71 GB)
  → selisih 0,30%**. Rumus lama (penyebut luas seluruh peta 7.225 ha, faktor 0,6)
  menghasilkan 0,63 GB — meleset ≈39×.
- **Tes regresi:** `test_layer_scan.py::test_estimasi_byte_output_terkalibrasi_gate2`
  (data Gate 2 nyata, toleransi 15%), `test_luas_footprint_ha_setengah_alpha`,
  `test_luas_footprint_ha_alpha_penuh`,
  `test_estimasi_byte_output_tolak_footprint_nol`;
  `test_app.py::test_pindai_estimasi_berbasis_footprint` (endpoint `/api/pindai`).

### T-2 (TINGGI) — Resume tanpa verifikasi state + tanpa validasi folder `_auto`

- **Tindakan:**
  1. `state.json` format **v2**: `{"versi": 2, "kode_flight", "output_root",
     "geom_blok": {kode: WKT}, "items": [...], "diperbarui"}`.
  2. Resume memverifikasi: kode flight cocok (beda → resume diabaikan + catatan
     log), berkas keluaran (`dst_data`/`dst_rgb`/`dst_legend`) masih ada, dan
     ukuran `dst_data` sama dengan yang tercatat (beda → item diulang).
  3. `/api/jalankan` menolak (400) folder berisi non-kosong yang **bukan**
     berakhiran `_auto` (cegah menimpa arsip lama) dan menolak state.json
     dengan kode flight berbeda.
  Berkas: `core/runner.py` (`_tulis_state`, `_muat_state`, `_berkas_lengkap`),
  `app.py` (`jalankan`).
- **Tes regresi:** `test_runner.py::test_resume_verifikasi_file_hilang_diulang`,
  `test_resume_ukuran_beda_diulang`, `test_resume_rgb_hilang_diulang`,
  `test_resume_kode_flight_berbeda_diabaikan`;
  `test_app.py::test_jalankan_tolak_folder_berisi_bukan_auto`,
  `test_jalankan_tolak_state_flight_berbeda`.
- **Bukti data nyata:** resume batch F: 0 detik, 40/40 tetap selesai; state
  v1 (tanpa `versi`/`kode_flight`) termigrasi penuh ke v2 (lihat
  `bukti_state_v2_sanitized.json` — WKT disensor dari paket).

### T-3 (TINGGI) — Log hilang saat "Coba ulang" (retry)

- **Tindakan:** file log baru kini selalu dibuat unik (`run_<ts>.log`, jika
  detik sama → `_{n}`), dan handler lama ditutup sebelum handler baru dipasang.
  Berkas: `core/runner.py` (`run`).
- **Tes regresi:** `test_runner.py::test_retry_ulang_membuat_file_log_baru`
  (memastikan log run pertama tetap ada + log retry berisi "selesai").

### S-1 (SEDANG) — Status "dilewati (tanpa data)" tidak pernah diproduksi

- **Keputusan pemilik: implementasi.** Tindakan: `rencana_output` menandai baris
  `dilewati` + alasan `"tanpa data (di luar cakupan layer)"` bila poligon blok
  tidak beririsan dengan kotak pembatas layer; runner melewatinya (tanpa
  menulis berkas) dan menghitungnya di log/ringkasan; resume mempertahankan
  status `dilewati` tanpa mengecek berkas.
- **Berkas:** `core/layer_scan.py` (`rencana_output`), `core/runner.py`
  (`run`, `_muat_state`).
- **Tes regresi:** `test_layer_scan.py::test_rencana_output_layer_footprint_parsial_dilewati`,
  `test_rencana_output_tanpa_bounds_tetap_pending` (tanpa info bounds → tetap
  pending, tidak salah dibuang);
  `test_runner.py::test_runner_melewati_baris_status_dilewati`,
  `test_resume_dilewati_tanpa_file_tetap_dilewati`.

### S-2 (SEDANG) — Fallback GCP manual hanya ada di dokumen

- **Keputusan pemilik: de-scope eksplisit.** Spec
  `docs/superpowers/specs/2026-10-13-ekspor-blok-otomatis-design.md`diperbarui:
  §5.1 menyatakan fallback GCP **DE-SCOPE (2026-10-14)** dan tool berhenti
  dengan pesan residual spesifik di UI; §9 (Non-Goals) menambah butir GCP;
  §10 (risiko) mencatat de-scope. Perilaku kode tidak berubah (memang tidak
  pernah mengimplementasikan GCP).

### S-3 (SEDANG) — Artefak gate ikut `git clean -x`

- **Tindakan:** `.gitignore` diganti pola whitelist — berkas laporan terpilih
  yang terlacak: **13 berkas inti** hasil perbaikan (RINGKASAN uji, skrip
  Gate 2, berkas gate1, dokumen review) + **9 berkas** yang menyertai paket
  verifikasi ini (`LAPORAN_PERBAIKAN_2026-10-14.md`, `buat_paket_verifikasi.py`,
  `BUKTI_diff_vs_commit.txt`, `bukti_gate1_md5.txt`, `bukti_state_v2_sanitized.json`,
  `bukti_daftar_tes.txt`, `bukti_nir_rededge.py`, `bukti_nir_rededge.txt`,
  `verify_gate2_run_20261014.txt`); raster/berkas besar tetap terabaikan.
- **Verifikasi:** `git add -n laporan/` melisting tepat **22 berkas**; tidak ada
  yang di-stage (belum commit).

### R-1 (RENDAH) — Artefak gate1 kedaluwarsa (455 vs 459)

- **Tindakan:** `laporan/gate1/` diregenerasi → **459 fitur** (pulih: D02,
  D14, F33, F34 — efek perbaikan `make_valid`); hasil byte-identik dengan
  salinan `data/`.
- **Bukti:** `bukti_gate1_md5.txt` — `blok.geojson`, `qa_pdf_blok.json`,
  `qa_overlay_peta.png` md5 **identik** dengan `data/` (mis. blok.geojson
  `6c62e7db9092af101e05ae2bdcd3a273`, 372.117 B); `n_berlabel=459`.

### R-2 (RENDAH) — Footer kartu validasi di-hardcode

- **Tindakan:** `core/kartu.py` kini menghitung GSD dari `abs(transform.a)`
  raster ortho blok dan residual dari `kalibrasi.json`
  (`residual_max_m`); teks footer dibangun fungsi `_baris_konteks(gsd_cm,
  residual_m)`; entri `index.json` memuat `gsd_cm` + `residual_m`; CLI
  `python -m core.kartu` menerima `--kalibrasi`; `app.py` meneruskan
  `KONFIG.path_kalibrasi`.
- **Tes regresi:** `test_kartu.py::test_baris_konteks_dari_nilai_bukan_hardcode`,
  `test_kartu_metadata_gsd_dan_residual` (termasuk kasus kalibrasi tidak ada →
  `residual_m: null`).
- **Bukti data nyata:** 8 kartu diregenerasi — footer "residual kalibrasi PDF
  0,49 m; GSD 5,28 cm/px" (dari data, bukan konstanta); `index.json` baru di
  `kartu_validasi/index.json`.

### R-3 (RENDAH) — `innerHTML` dengan data server

- **Tindakan:** 3 titik interpolasi data (tabel blok + tabel status di
  `static/app.js`) diganti `document.createElement` + `textContent`; sisa
  `innerHTML` hanya pembersih (`= ""`). `node --check static/app.js` lolos.

### R-4 (RENDAH) — Race `/api/jalankan`

- **Tindakan:** `JALANKAN_LOCK` (non-blocking acquire) — permintaan kedua saat
  batch aktif ditolak 400 "Permintaan lain sedang diproses".
- **Tes regresi:** `test_app.py::test_jalankan_lock_menolak_permintaan_bersamaan`.

### R-5 (RENDAH) — `_port_bebas` mengembalikan 0

- **Tindakan:** kembalikan `None` bila 5000–5049 penuh; `__main__` berhenti
  dengan pesan "Tidak ada port bebas di 127.0.0.1:5000-5049 — tutup aplikasi
  lain lalu coba lagi" (tidak lagi membuka `127.0.0.1:0`).
- **Tes regresi:** `test_app.py::test_port_bebas_habis_kembalikan_none`.

### R-6 (RENDAH) — Daftar blok dipotong 500

- **Tindakan:** potongan `[:500]` dihapus — semua blok terkirim ke UI.
- **Tes regresi:** `test_app.py::test_pindai_daftar_blok_tidak_dipotong`
  (aset 506 blok; seluruh 506 hadir di respons).

### R-7 (RENDAH) — `_cek_grid` longgar

- **Tindakan:** `laporan/_uji_d17/verify_gate2.py` kini mewajibkan CRS sama +
  transform penuh (a..f, toleransi 1e-6) hasil rekonstruksi dari bounds target.
- **Bukti:** verifikasi ulang 2026-10-14 lolos 40/40 dengan cek baru
  (`verify_gate2_run_20261014.txt`).

### R-8 (RENDAH) — Dugaan NIR dan RedEdge bitwise identik

- **Tindakan:** diverifikasi ulang dengan bukti yang kini disertakan paket
  (review sebelumnya tidak bisa memverifikasi karena data tidak disertakan).
  Hasil presisi (lihat `bukti_nir_rededge.py/.txt`):
  - ukuran kedua berkas **sama**: 4.874.415.646 B;
  - **md5 berkas BERBEDA** (`6162b6b2…` vs `f3ce0782…`) → bukan byte-identik;
  - **SHA-256 atas piksel seluruh band IDENTIK** (dihitung ulang penuh) →
    isi piksel sama persis.
- **Kesimpulan:** bukan bug tool; sumber ekspor memang memuat dua layer
  berisi piksel yang sama (perlu dicek di flight berikutnya). Catatan sudah
  ditambahkan di `RINGKASAN.md` §1.

### N-1 (BARU) — `state.json`/`snapshot` membengkak oleh WKT per item

- **Tindakan:** `snapshot()` drop `geom` (UI tidak memakainya); state v2
  menyimpan WKT sekali per blok di `geom_blok`; `verify_gate2.py` membaca
  `geom_blok` (fallback item.`geom` untuk state v1 lama).
- **Tes regresi:** `test_runner.py::test_state_v2_geom_sekali_per_blok`,
  `test_snapshot_tanpa_geom`, `test_resume_memulihkan_geom_dari_geom_blok`.
- **Bukti data nyata:** state F: v1→v2 — `items[0]` tanpa `geom`, `geom_blok`
  berisi 8 blok (`bukti_state_v2_sanitized.json`).

### N-2 (BARU) — `.data.tif` uint8 dikompresi JPEG (lossy)

- **Tindakan:** `core/crop_engine.py` memaksa **DEFLATE** untuk semua tujuan
  `*.data.tif` (predictor 3 untuk float, 2 untuk uint8); `.rgb.tif` tetap
  JPEG Q85 (perilaku terverifikasi Gate 2, tidak diubah).
- **Tes regresi:** `test_crop_engine.py::test_crop_uint8_data_tif_dipaksa_deflate`
  (kompresi deflate + salinan piksel eksak), penjaga perilaku rgb:
  `test_proses_baris_copy_rgb_dan_legend` (masih `jpeg`).

### N-3 (BARU) — Overview `average` merata-ratakan nodata

- **Hasil penyelidikan (bukti dijalankan, tidak sekadar argumen):**
  - Untuk `.data.tif` (float, DEFLATE, nodata −10000 tepat): **premis tidak
    terbukti** — GDAL `average` menghormati nodata; blok overview campuran
    data+nodata hanya mengambil rata-rata kontributor non-nodata (diuji:
    output overview hanya berisi nilai eksak −10000 atau nilai data).
    Dijaga tes `test_crop_engine.py::test_overview_data_tidak_membaurkan_nodata`.
  - Untuk `.rgb.tif`: karena JPEG lossy menggeser piksel 0 (nodata) menjadi
    1–3, tepi footprint di overview ikut terbaur tipis — **tampilan saja,
    bukan data** (data & alpha asli tetap utuh; verifikasi piksel batch lolos
    0 bocor). Diterima sebagai keterbatasan tampilan dan didokumentasikan,
    sesuai opsi yang review sediakan.

### N-4 (BARU) — `requirements.txt` tidak di-pin

- **Tindakan:** `pip freeze` dari venv teruji → 24 paket terkunci (flask 3.1.3,
  rasterio 1.5.2, pymupdf 1.28.2, pillow 12.3.0, numpy 2.5.4, shapely 2.2.0,
  pyshp 3.1.6, tifffile 2026.9.20, pytest 9.1.1, dan transitifnya).
- **Verifikasi:** `pip install --dry-run --no-index -r requirements.txt` →
  semua persyaratan sudah terpenuhi di venv yang dipakai menguji.

### N-5 (BARU) — Field `workers` mati

- **Tindakan:** field `workers` dihapus dari `core/config.py` (param `Runner`
  sudah dihapus di T-2/race); config.json lama yang masih memuat `workers`
  tetap termuat (field asing diabaikan) — ada tesnya.
- **Tes regresi:** `test_config.py::test_missing_file_kembali_default` (diperbarui:
  memastikan `workers` tidak ada), `test_config_lama_dengan_workers_tetap_dimuat`.

---

## 3. Tes yang diminta review (§7 butir 6) — semua sudah ada

| Diminta | Tes |
|---|---|
| `retry()` UI | `test_runner.py::test_retry_ulang_membuat_file_log_baru` |
| `/api/pindai` + `/api/jalankan` (termasuk angka estimasi) | `test_app.py::test_pindai_estimasi_berbasis_footprint`, `test_jalankan_batch_sintetis_via_api` (juga menguji state v2 + log) |
| Skenario "ganti flight, folder sama" | `test_runner.py::test_resume_kode_flight_berbeda_diabaikan`, `test_app.py::test_jalankan_tolak_state_flight_berbeda` |
| Layer ber-footprint parsial → `dilewati` | `test_layer_scan.py::test_rencana_output_layer_footprint_parsial_dilewati`, `test_runner.py::test_runner_melewati_baris_status_dilewati` |

---

## 4. Perilaku yang TIDAK diubah (penjaga regresi)

- Salinan piksel `.data.tif` tetap eksak (Gate 2: max|diff| = 0,0).
- `.rgb.tif` tetap JPEG Q85 untuk crop dari sumber rgb (toleransi re-encode
  yang sudah diverifikasi); legend tetap salinan byte (md5 identik).
- Penamaan folder/berkas output tidak berubah; overview [2,4,8,16] tetap dibentuk.
- Kalibrasi PDF, palet, kartu (isi/inset/warna garis) tidak berubah — kecuali
  baris footer konteks (R-2).
- Config.json lama tetap kompatibel (baca-tulis dengan field asing diabaikan).

---

## 5. Yang masih terbuka / perlu diketahui reviewer

1. **N-3 (`rgb.tif`)**: keterbatasan tampilan overview diterima, bukan
   diperbaiki — alasan dan bukti di §2. Bila memandang ini harus ditutup
   dengan kode (mis. maska eksplisit + resampling khusus), beri rekomendasi
   konkret; saat ini bukti menunjukkan dampak hanya di overview tepi.
2. **S-2 de-scope** adalah keputusan pemilik proyek (dicatat di spec), bukan
   penilaian teknis implementer.
3. **Belum di-commit**: seluruh perbaikan ada di working tree; diff vs commit
   `65b4b44` disertakan. Paket pertama (yang Anda/peninjau sebelumnya pegang)
   dibuat pada commit ini.
4. Raster dan koordinat poligon blok **tidak disertakan** di paket (kebijakan
   paket pertama, dipertahankan). Bukti watak piksel disajikan sebagai hash.

---

## 6. Cara memverifikasi (untuk reviewer)

```bash
cd /d/pix4dfield_exporting_tools

# 1) Suite tes — ekspektasi: 68 passed
.venv/Scripts/python.exe -m pytest tests/ -q

# 2) Diff lengkap yang diklaim vs commit baseline
git diff 65b4b44            # atau baca BUKTI_diff_vs_commit.txt di paket

# 3) Tes spesifik per temuan, contoh:
.venv/Scripts/python.exe -m pytest tests/test_runner.py::test_retry_ulang_membuat_file_log_baru -v
.venv/Scripts/python.exe -m pytest tests/test_layer_scan.py -v
.venv/Scripts/python.exe -m pytest tests/test_app.py -v
```

Peta temuan → bukti → tes ada di §2; daftar lengkap 68 tes ada di
`bukti_daftar_tes.txt`. Bukti data nyata (resume + verifikasi piksel batch
24,7 GB) ada di `verify_gate2_run_20261014.txt` dan `gate2_verifikasi.json`.

---

## 7. Tindak lanjut verifikasi independen (2026-10-14)

Verifikator (Muse, penulis review kedua) menjalankan verifikasi independen atas
paket ini — menjalankan sendiri 56/68 tes (12 tes PDF tak bisa jalan karena
fixture peta disensor dari paket) — dan menyatakan **PERBAIKAN SELESAI**
(`laporan/reviewer/Verifikasi-Perbaikan-Ekspor-Blok-2026-10-14.md`), dengan 3
nit dokumentasi. Ketiganya sudah dibetulkan:

1. **"meleset ≈3×" → "≈39×"** — dikoreksi di §2 (T-1) dan `RINGKASAN.md` §6.
   Angka terukur: rumus lama = `byte_src × (luas_blok/luas_seluruh_peta) × 0,6`
   = 0,63 GB (penyebut 7.225 ha) vs aktual 24,71 GB → **39,3×**.
2. **Hitungan tes diseragamkan** — `RINGKASAN.md` §6 kini "40 → 68 tes"
   (sebelumnya 63; ditulis sebelum 5 tes terakhir ditambahkan).
3. **`BUKTI_diff_vs_commit.txt` diregenerasi** — kini memuat `.gitignore` final
   (whitelist `BUKTI_*`/`bukti_*`/`verify_gate2_run_*`/`LAPORAN_PERBAIKAN`).

Selaras dengan itu, `.gitignore` juga mewhitelist laporan verifikasi ini
(**23 berkas laporan** terlacak-able). Saran verifikator untuk langkah
berikutnya: **commit** perubahan (masih di working tree), lalu Gate 3 — plus
menghitung proyeksi waktu/disk dengan rumus T-1 baru sebelum batch flight penuh.
