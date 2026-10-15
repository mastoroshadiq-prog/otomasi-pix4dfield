# Ringkasan validasi sumber uji nyata (2026-10-13)

Sumber: `F:\dataset\Pix4DField-export-Fligh01\AME III - Test OtoExport` (read-only).

## 1. Gate 0 — format ekspor penuh aplikasi TERKONFIRMASI

13 file: 5 lapisan, tiap lapisan `<Nama>.data.tif` + `<Nama>.rgb.tif`;
legend png ada untuk NDRE / NIR / RedEdge / Surface model (ortho tanpa legend,
sesuai perilaku aplikasi lama).

- `*.data.tif`: float32, nodata = -10000, LZW, berubin, ~5 overview
- `*.rgb.tif`: uint8 RGBA (JPEG), band-4 alpha = penutup wilayah valid
- `*.legend.png`: palet tiap layer
- **Catatan NIR = RedEdge (diverifikasi 2026-10-14):** `AME III NIR.data.tif` dan
  `AME III RedEdge.data.tif` berukuran sama persis (4.874.415.646 B) dan **checksum
  band GDAL identik (20064)** — data piksel kembar. md5 berkas berbeda
  (struktur biner TIFF), jadi "identik bitwise" hanya benar di level piksel,
  bukan berkas. Konsekuensi: output crop NIR & RedEdge flight ini memang sama
  isinya; bukan bug tool, tetapi perlu dicek di flight berikutnya apakah
  aplikasi benar-benar mengekspor band berbeda.

## 2. Adaptasi alat + verifikasi E2E pada data nyata (D17, NDRE)

`core.crop_engine.proses_baris` dijalankan langsung atas ekspor penuh:

| output | hasil vs ekstraksi jendela acuan dari sumber |
|---|---|
| `NDRE.data.tif` (18,0 MB float) | **max\|diff\| = 0,000000 — identik piksel** |
| `NDRE.rgb.tif` (4 kanal, JPEG) | rata2 \|diff\| = 0,77 (derau re-encode JPEG; tepi antialias alpha wajar) |
| `NDRE.legend.png` | md5 **identik** (salin byte) |

Suite tes: 33/33 lolos.

## 3. TEMUAN PENTING — "Test OtoExport" ≠ akuisisi ekspor manual lama

Ekspor manual pembanding (`AME III/D17/Flight 01 - AME IV&AME III_250226 006-008_ameIII`)
berasal dari **proyek/akuisisi berbeda**, meski kebun sama:

- offset georeferensi antar keduanya ~2 m (phase correlation + NCC)
- korelasi piksel RGB maksimum **0,317** (Spearman 0,304 — bukan sekadar beda tone)
- korelasi NDRE maksimum **0,558**; distribusi NDRE mirip (median 0,400 vs 0,389)
- posisi pohon & jalan sama, tetapi detail frond/shadow per pohon berbeda
- TIFFTAG_DATETIME: uji `2026:02:26 02:55` vs manual `2026:02:25 06:37`

**Konsekuensi:** nilai piksel TIDAK bisa dibandingkan langsung dengan ekspor
manual lama sebagai uji ekivalensi radiometrik. Sebaliknya ekivalensi jalur
potong terbukti kuat dari uji E2E di atas (salin piksel apa adanya).

## 4. Cakupan batch yang mungkin (DIKOREKSI 2026-10-13 v2)

Catatan koreksi: klaim awal "22 blok" SALAH metodologi — itu hanya blok yang
poligonnya menyentuh kotak pembatas TIFF. Versi ini memakai irisan geometri
murni (poligon blok ∩ footprint dari topeng alpha), tanpa penyebut raster
yang terpotong:

- **8 blok AME III tercakup 100,0%** — cocok dengan hitungan manual pengguna:
  D13 (24,59 ha), D14 (24,20 ha), D15 (23,71 ha), D16 (26,97 ha),
  E13 (23,63 ha), E14 (25,31 ha), E15 (24,01 ha), E16 (25,23 ha) — total ±197,6 ha
- parsial: F13 OLE II 41,1%, E17 AME III 33,4%, D17 AME III 31,3%
- 12 blok lain hanya bercak pinggiran 1–9% (D09–D12, E09–E12 AME II; C15/C16
  AME IV; F09 AME II, F17 OLE II)
- luas wilayah berdata total 257,9 ha; 239,7 ha di antaranya jatuh di dalam blok
- grid ukur 1,057 m dari band alpha `Orthomosaic.rgb.tif`
- overlay: `overlay_blok_test_otoexport.png` (hijau = 8 blok 100%)

### Bug ekstraksi D14 ditemukan & diperbaiki (2026-10-13)

D14 hilang dari `data/blok.geojson` v1 (455 fitur). Penyebab: sel D14 di PDF
mengandung jarum balik 0,3 pt di tepi kiri, urutan titik
`(1229,1668.9) → (1229.3,1668.9) → (1229,1668.9)`, sehingga poligon shapely
tidak valid dan filter `if not poly_pt.is_valid: continue` membuangnya.

Perbaikan di `core/pdf_blok.py`: `shapely.validation.make_valid()` lalu ambil
komponen Polygon terbesar (hasil repair D14 = GeometryCollection berisi
Polygon 6781,1 pt² utuh + LineString artefak 0,3 pt). Regenerasi menghasilkan
**459 fitur** (+4 sel cacat pulih: D02 AME II 24,45 ha, D14 AME III 24,20 ha,
F33 & F34 DBE I 27,06/30,73 ha), 440 kode unik, 431 berdivisi.
Tes regresi: `tests/test_pdf_blok_ekstraksi.py::test_sel_cacat_direparasi_bukan_dibuang`.

## 5. Gate 2 — batch 8 blok `FLG01-AMEIII` (2026-10-13)

Dijalankan via Runner langsung (skrip `run_gate2.py`), sumber
`AME III - Test OtoExport` (read-only, tidak tersentuh), output ke folder BARU
`F:\dataset\Pix4DField-export-FLG01-AMEIII_auto`.

- **40/40 item selesai, 0 gagal**, 827 detik (±14 menit) kerja; semua status
  "selesai" di `hasil_per_blok.csv` + `state.json`
- struktur: `AME III\FLG01-AMEIII_AMEIII-<KODE>\` berisi 5 × `.data.tif` +
  5 × `.rgb.tif` + 4 × `.legend.png` (ortho tanpa legend — sesuai perilaku app);
  E14 & E15 dapat tambahan `qa_overlay.png` (sampel QA otomatis)
- total **24,71 GB** (data 23,03 GB + rgb 1,43 GB + legend 0,2 MB); per blok
  2,75–3,14 GB

### Verifikasi piksel (`verify_gate2.py`; putaran 1 salah deteksi ortho 5-band, diperbaiki lalu diulang)

- **data: max|diff| = 0,0 di SEMUA 40 file** (termasuk 8 ortho 5-band) terhadap
  jendela sumber — salinan eksak, tanpa interpolasi
- di luar poligon blok: **0 piksel** bukan nodata (−10000) di seluruh batch;
  rgb di luar poligon transparan (ring JPEG ≤ 23/255 hanya di ±1.000 piksel
  tepi dari ±89 juta piksel/layer)
- rgb di dalam: rata-rata beda kanal **0,63/255** (derau re-encode JPEG Q85)
- legend: **32/32 md5 identik** dengan file sumber (salin byte)
- overview [2,4,8,16] terbentuk di semua file data & rgb

### Kompresi vs ekspor manual lama (D17, LZW) — akuisisi berbeda, angka indikatif

GSD kedua pihak setara (5,28 vs 5,37 cm/px), jadi per-ha masih sebanding:

| layer | batch ini (DEFLATE+predictor) | manual D17 (LZW) |
|---|---|---|
| NDRE | 14,0 MB/ha | 18,1 MB/ha |
| Orthomosaic | 63,9 MB/ha | 80,9 MB/ha |
| Surface model | 9,7 MB/ha | 12,4 MB/ha |
| rgb NDRE / Ortho / DSM | 1,9 / 2,5 / 0,9 MB/ha (JPEG Q85) | 1,5 / 1,7 / 0,7 MB/ha |

→ data float ±20–23% lebih kecil dari LZW. rgb sedikit lebih besar (Q85 +
kanal alpha). Ekspor manual lama hanya 3 layer; batch ini 5 layer
(+NIR, +RedEdge yang sebelumnya tidak pernah diekspor).

## Validasi silang PDF vs shp kebun (kartu per blok)

Pembanding independen: `E:\2. Tanam Inti\2_Tanam_Inti.shp` (1162 poligon, UTM 49S,
field `No_Block`). Generator: `core/kartu.py` — dipakai tombol "Buat/Perbarui Kartu
Validasi" di tab 4 UI dan CLI `python -m core.kartu`; hasil kerja di
`<folder_output>\_validasi\`, salinan uji di `kartu_validasi/kartu_<KODE>.png`.
Isi kartu: strip penuh blok + garis batas **merah = ekstraksi PDF (dipakai crop)**
dan **biru = shp Tanam Inti**; 6 inset resolusi asli (4 tepi panjang, utara, selatan)
di titik bernomor kuning; putih = area di luar poligon crop (nodata).

| blok | luas PDF (ha) | luas shp (ha) | beda | IoU | geser titik tengah |
|---|---|---|---|---|---|
| D13 | 24,59 | 24,39 | +0,20 | 93,7% | 7,5 m |
| D14 | 24,20 | 24,08 | +0,11 | 92,3% | 9,4 m |
| D15 | 23,71 | 22,36 | +1,35 | 94,2% | 8,0 m |
| D16 | 26,97 | 26,71 | +0,25 | 98,7% | 1,5 m |
| E13 | 23,63 | 23,74 | −0,11 | 96,9% | 3,9 m |
| E14 | 25,31 | 24,46 | +0,85 | 96,5% | 3,6 m |
| E15 | 24,01 | 23,93 | +0,08 | 96,6% | 4,2 m |
| E16 | 25,23 | 24,92 | +0,31 | 96,7% | 4,1 m |

Temuan dari inset (diperiksa mata pada D14 & D16): selisih utama ada di sisi
barat — batas PDF (merah) berjalan di tepi barat jalan koleksi (jalan ikut
masuk blok), batas shp (biru) berjalan ~8 m di tepi timurnya. Tepi utara/selatan
divergensi tipis (0,5–2,5 m). Semua garis digambar apa adanya tanpa penyesuaian.

## 6. Perbaikan pasca review independen kedua (2026-10-14)

Menindaklanjuti `laporan/reviewer/Review-Independen-2-Ekspor-Blok-Otomatis-2026-10-14.md`
(0 KRITIS, 3 TINGGI, 3 SEDANG, 10 RENDAH) — semua temuan diperbaiki, tiap
perbaikan disertai tes regresi (suite 40 → 68 tes, semua lulus):

- **T-1 (estimasi disk salah rumus):** diganti estimasi berbasis footprint layer:
  `estimasi = byte_src / luas_footprint × luas_blok × 0,84` (rasio kalibrasi dari
  batch Gate 2). Validasi data nyata: ortho footprint 256,5 ha → estimasi 8 blok
  = **24,78 GB vs aktual 24,71 GB (selisih 0,3%)**; rumus lama (penyebut luas
  seluruh peta 7.225 ha, faktor 0,6) menghasilkan 0,63 GB — meleset ~39×.
- **T-2 (state.json tidak terverifikasi saat resume):** format baru **v2** —
  `{"versi":2, "kode_flight", "output_root", "geom_blok":{kode:wkt}, "items":[…]}`.
  Resume kini memverifikasi: kode flight cocok (beda → item diulang + log),
  berkas keluaran masih ada, dan ukurannya sama. `/api/jalankan` menolak folder
  berisi bukan `_auto` (cegah timpa arsip lama) dan state dengan flight berbeda.
- **T-3 (log hilang saat retry):** file log baru dibuat unik per run (`_{n}` bila
  detik sama), handler lama ditutup sebelum diganti — log run pertama tetap utuh.
- **N-1 (geom disimpan per item = duplikasi):** snapshot() tidak lagi menyimpan
  geom per item; geom disimpan sekali per blok di `geom_blok`; `verify_gate2.py`
  membaca `geom_blok` (fallback v1 tetap jalan).
- **S-1 (status "dilewati" tidak pernah diproduksi):** `rencana_output` menandai
  baris `dilewati` + alasan "tanpa data (di luar cakupan layer)" bila poligon blok
  tidak menyentuh kotak pembatas layer; runner melewatinya (tanpa file, tetap
  dilewati saat resume).
- **S-2 (fallback GCP hanya di dokumen):** **de-scope eksplisit** atas keputusan
  pengguna — spec §5.1/§9/§10 diperbarui: tool berhenti dengan pesan residual
  spesifik di UI, tidak ada jalur GCP manual.
- **S-3 (folder laporan ikut git clean -x):** `.gitignore` diganti pola whitelist —
  22 berkas laporan terpilih yang terlacak (13 inti: RINGKASAN, skrip Gate 2, gate1,
  review; + 9 berkas bukti/fix paket verifikasi), artefak besar tetap terabaikan.
- **R-1 (artefak gate1 kedaluwarsa 455):** diregenerasi → **459 fitur** (D02, D14,
  F33, F34 pulih via `make_valid`), md5 identik dengan salinan `data/`.
- **R-7 (`_cek_grid` longgar):** kini mewajibkan CRS sama + transform penuh
  (a..f, toleransi 1e-6) hasil rekonstruksi dari bounds.
- **R-8 (NIR vs RedEdge):** diverifikasi ulang — ukuran sama 4.874.415.646 B,
  **checksum band GDAL identik (20064) = piksel identik**; md5 berkas berbeda
  (struktur biner), bukan bug tool.
- **N-2 (.data.tif uint8 di-JPEG lossy):** `crop_layer` memaksa DEFLATE untuk
  semua berkas `*.data.tif` (predictor 3 float / 2 uint8); rgb tetap JPEG Q85.
  Tes: uint8 → `.data.tif` salinan piksel eksak.
- **N-3 (overview merata-ratakan nodata):** *diverifikasi empiris* — untuk
  `.data.tif` premis tidak terbukti: GDAL `average` menghormati nodata
  (−10000 tidak pernah membaur); dijaga tes regresi. Untuk `.rgb.tif` ada bauran
  tepi tipis di overview karena JPEG menggeser piksel 0 → 1–3 (tampilan saja,
  bukan data) — diterima sebagai keterbatasan tampilan, bukan artefak data.
- **N-4 (requirements tidak di-pin):** `pip freeze` dari venv teruji →
  24 paket terkunci; `pip install --dry-run` memverifikasi semuanya cocok.
- **N-5 (field `workers` mati):** dihapus dari `core/config.py`; config.json lama
  yang masih memuatnya tetap termuat (field asing diabaikan).
- **R-2 (footer kartu hardcode):** `core/kartu.py` kini membaca residual dari
  `kalibrasi.json` + GSD dari `abs(transform.a)` ortho; entri `index.json`
  memuat `gsd_cm`/`residual_m`.
- **R-3 (innerHTML berdata server):** 3 titik di `static/app.js` diganti
  `textContent`/createElement (tabel blok, tabel status); `node --check` lolos.
- **R-4 (race /api/jalankan):** kunci non-blocking — permintaan kedua ditolak 400.
- **R-5 (`_port_bebas` → 0):** mengembalikan `None`; aplikasi berhenti dengan
  pesan jelas bila 5000–5049 penuh.
- **R-6 (daftar blok dipotong 500):** potongan dihapus; semua blok terkirim ke UI.

### Verifikasi ulang pada data nyata pasca perbaikan (2026-10-14)

- **Resume Gate 2:** `run_gate2.py` dijalankan ulang atas folder batch F: yang
  sama → **0 detik kerja, 40/40 tetap selesai, 0 crop ulang** (resume aman);
  `state.json` termigrasi v1 → **v2** dengan `kode_flight` + `geom_blok` 8 blok
  lengkap, item tidak lagi menyimpan WKT (N-1).
- **`verify_gate2.py` (versi baru, R-7 + N-1):** **40/40 item ok** — max|diff|
  data **0,0** di semua layer, 0 piksel bocor di luar poligon; rgb 0,628/255;
  `total_byte_data` 23.027.446.780 B / 197,63 ha. **VERIFIKASI: LOLOS**.
- **Kartu validasi (R-2):** 8 kartu diregenerasi via CLI — footer kini memakai
  GSD nyata ortho (5,28 cm/px) + residual dari `kalibrasi.json` (0,49 m);
  `index.json` memuat `gsd_cm`/`residual_m`; salinan diperbarui di
  `kartu_validasi/`.

## Artefak

- `banding_3jendela.png` — ortho full-extent vs manual D17, 3 jendela
- `zoom_hires.png` — zoom 35 m berwarna, registrasi terbaik
- `anaglyph_teregistrasi.png` — fusi merah(F)/hijau(M)
- `e2e/` — hasil proses_baris nyata D17/NDRE
- `overlay_blok_test_otoexport.png` — cakupan 8 blok 100% (versi terkoreksi)
- `gate2_pratinjau_8blok.png` — montase ortho RGB 8 blok hasil batch
- `kartu_validasi/kartu_<KODE>.png` (8 file) — kartu validasi PDF vs shp per blok
- `run_gate2.py`, `verify_gate2.py`, `gate2_verifikasi.json`, `run_gate2.log` — skrip + bukti Gate 2
- Kartu juga tersedia di `F:\dataset\Pix4DField-export-FLG01-AMEIII_auto\_validasi\` (dibaca tab 4 UI; dibuat `core/kartu.py`)
