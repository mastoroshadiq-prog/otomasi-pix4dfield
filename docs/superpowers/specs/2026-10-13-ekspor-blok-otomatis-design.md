# Ekspor Blok Otomatis — Desain Teknis

- **Tanggal:** 2026-10-13
- **Status:** disetujui 2026-10-13 — implementasi dimulai (rencana: `docs/superpowers/plans/2026-10-13-ekspor-blok-otomatis-implementasi.md`)
- **Revisi 2026-10-14:** hasil review independen kedua — fallback GCP manual di-de-scope eksplisit (§5.1, §9); status `dilewati (tanpa data)` benar-benar diproduksi (§5.2/§5.4); resume diverifikasi terhadap file & kode flight (§5.4); estimasi disk berbasis footprint sumber (§5.5); justifikasi keputusan ada di komit pesan terkait.
- **Konteks sesi:** hasil brainstorming opsi A (export full-extent manual 1× per project, sisanya otomatis) dengan Web UI lokal.

## 1. Ringkasan & Tujuan

Menggantikan alur manual Pix4DField (menggambar boundary per blok lalu mengekspor layer per blok) dengan tool lokal:

> Untuk setiap project/flight → crop otomatis semua layer per blok memakai peta blok PDF sebagai geometri acuan → tulis ke folder BARU terkompresi → tanpa menyentuh GUI Pix4DField.

**Kriteria sukses:**
1. Posisi & cakupan hasil sama dengan ekspor manual (diverifikasi visual + statistik pada gate verifikasi).
2. Ukuran file lebih kecil dari referensi (rekompresi LZW→DEFLATE/LERC).
3. Progress, error, dan log terlihat jelas di UI saat proses berjalan.
4. Dapat dipakai berulang untuk setiap flight baru dengan langkah manual minimal (1× export full-extent dari app).

## 2. Keputusan yang Terkunci

| # | Keputusan | Nilai |
|---|---|---|
| D1 | Alur sumber data | Opsi A — pengguna export layer full-extent sekali per project dari Pix4DField; seluruh crop dilakukan tool |
| D2 | UI | Web lokal (Flask), dibuka via double-click `jalankan.bat` |
| D3 | Lokasi output | Folder BARU (`..._auto`) — arsip lama tidak pernah ditimpa |
| D4 | Bahasa UI & dokumen | Indonesia |
| D5 | Peta blok acuan | PDF "Peta Informasi Tanam Tahun Inti" (vektor, UTM 49S) |
| D6 | Opsi B (baca cache app) | Cadangan, di luar scope iterasi ini |

## 3. Fakta & Aset (hasil investigasi, terverifikasi)

| Aset | Fakta | Peran di desain |
|---|---|---|
| PDF peta blok | 56.703 path, 2.520 poligon kandidat, 1.054 label, ~657 kandidat kode blok, grid UTM, WKT UTM 49S terembed | Sumber geometri blok + kode |
| `F:\dataset\Pix4DField-export-Fligh01` | BigTIFF tiled; Ortho 5-band float32 LZW 2,2 GB; RGB uint8 JPEG 44 MB; NDRE float32 LZW 496 MB; DSM float32 LZW 352 MB | Referensi struktur+nama+kompresi |
| `F:\Pix4DField\Data\bdr_*.zip` (8) | `boundaries.shp` + dbf (`name` mis. "AME II F08", "FLG02_AME II - D01"), WGS84 | Validator akurasi & cross-check |
| `E:\2. Tanam Inti\2_Tanam_Inti.shp` | 1.162 poligon; atribut No_Block, Divisi, ESTATE, BLOK_Baru, Tahun_Tana; UTM 49S | Lookup divisi & validasi kode |
| XMP band | Green/Red/RedEdge/NIR/Alpha (560/650/730/860 nm) | Identifikasi band & NDRE |
| Cache app | 148 tif: 57 ortho 5-band + 91 single-band | (Opsi B — cadangan) |
| Toolchain | Python 3.14 + venv `.venv`; rasterio 1.5.2 (GDAL ter-bundel), PyMuPDF 1.28.2, Flask 3.1.3 (terpasang 2026-10-13); CLI GDAL tidak ada di PATH | Dasar implementasi |
| Kalibrasi PDF | 16 titik kontrol dari grid DMS 3'30" (4×4); residual maks 0,67 m; skala 5,973 m/pt; rotasi 0,014° | Ambang Gate 1 (<3 m) sudah terlampaui baik |

## 4. Arsitektur

Root proyek = `D:\pix4dfield_exporting_tools` (repo git terpisah; dipindah dari workspace Qoder 2026-10-13).

```
app.py                  # entry Flask + launcher browser
jalankan.bat            # double-click: start server + buka browser
core/
  config.py             # muat/simpan konfigurasi (JSON) + path default
  pdf_blok.py           # ekstraksi + kalibrasi peta PDF -> blok.geojson
  layer_scan.py         # deteksi & klasifikasi layer di folder sumber
  crop_engine.py        # gdalwarp cutline per blok x layer + palet rgb/legend
  runner.py             # orkestrasi batch, status, resume, retry, cancel
  qa_overlay.py         # render PNG overlay verifikasi
templates/ static/      # UI web
data/                   # blok.geojson, cache kalibrasi, palet
logs/                   # run_*.log (salinan)
tests/                  # uji komponen
docs/superpowers/specs/ # dokumen ini
```

Alur data:

```
PDF peta ──(sekali)──> pdf_blok ──> blok.geojson (UTM 49S) ──┐
                                                             ▼
Pengguna: export full-extent ──> folder sumber ──> layer_scan ──> runner ──> crop_engine ──> folder output baru
                                                             │              │
                                                             ▼              ▼
                                                       web UI (progress)  qa_overlay (PNG)
```

## 5. Komponen

### 5.1 `pdf_blok` — ekstraksi & kalibrasi (dijalankan sekali per peta, hasil di-cache)
- Kalibrasi: ekstrak label DMS (graticule 3'30") + garis grid dari PDF → titik potong → fit affine `PDF pt → UTM 49S` least-squares → laporkan residual; **lolos jika residual < 3 m** (terukur 0,67 m pada PDF contoh).
- Fallback bila grid tidak terdeteksi: **DE-SCOPE eksplisit (2026-10-14)** — file GCP manual (3–4 pasangan titik PDF↔UTM) TIDAK diimplementasikan pada iterasi ini; bila kalibrasi otomatis gagal, tool berhenti dengan pesan residual spesifik di UI (lihat §9).
- Ekstraksi poligon blok: path fill/stroke ≥3 titik → transform → geometri UTM; label kode blok ditautkan ke poligon via centroid terdekat; filter hanya pola kode blok valid (mis. `A01`, `H31`, `C04A`, `F22D22`).
- Validasi silang: poligon hasil vs `bdr_*.zip` (blok yang punya keduanya) → statistik jarak batas; vs `2_Tanam_Inti.shp` (kode & divisi).
- Output: `data/blok.geojson` + `data/qa_pdf_blok.json` + `data/qa_overlay_peta.png`.

### 5.2 `layer_scan` — deteksi layer sumber
- Scan folder sumber; klasifikasi tiap file: Ortho(data 5-band, rgb), NDRE, NIR, RedEdge, DSM — berdasarkan pola nama + jumlah band + SampleFormat + XMP.
- File tak dikenal / tidak lengkap → dilaporkan sebagai penolakan dengan pesan spesifik (muncul di UI sebelum run).
- Output: daftar layer + preview di halaman Scan.

### 5.3 `crop_engine` — mesin crop
- Per blok × layer: crop via **rasterio API** (setara `gdalwarp -cutline -crop_to_cutline`; CLI GDAL tidak tersedia di PATH) — windowed per-strip agar aman memori; tulis GTiff `TILED=YES`, `BLOCK=256`, `BIGTIFF=YES`.
- Kompresi: float32 → `DEFLATE` (+`PREDICTOR=3`); uint8 RGB → `DEFLATE`; jika GDAL wheel mendukung `LERC` untuk float, jadikan opsi per-layer (diuji pada gate 2 mana yang lebih baik).
- `.rgb` untuk layer indeks (NDRE/NIR/RE/DSM): render warna memakai **palet yang disampel dari file `.rgb.tif` export lama**; `.legend.png` digenerate dari palet yang sama.
- Overviews (`gdaladdo`) untuk rgb agar ringan dibuka.
- Nama file output mengikuti pola referensi: `Orthomosaic - <NAME>.data.tif`, `NDRE.data.tif`, dst.

### 5.4 `runner` — orkestrasi
- Antrian per blok × layer; status: `pending / berjalan / selesai / gagal / dilewati (tanpa data)`.
- `state.json` per run → **resume**: blok selesai dilewati saat run diulang.
- Retry otomatis 1× per blok gagal; error per blok tidak menghentikan batch.
- Cancel: menghentikan setelah file yang sedang berjalan selesai (aman).
- Output buku besar: `hasil_per_blok.csv` (blok, layer, status, ukuran, durasi, error) + `run_<tanggal>.log`.

### 5.5 Web UI (`app.py`)
Halaman tunggal, 3 tahap:
1. **Setup** — pilih folder sumber, folder output, file PDF, kode flight (mis. `FLG03`), konfirmasi mapping divisi.
2. **Pindai (dry-run)** — daftar blok + layer + pra-validasi (kalibrasi PDF ada? file lengkap? disk cukup?) — belum menulis apa pun.
3. **Jalankan** — progress bar total, tabel blok×layer berwarna status, log live, tombol Batalkan / Coba ulang blok, tombol Buka folder hasil, unduh `hasil_per_blok.csv` + log.

Server hanya `127.0.0.1`, auto-pilih port, browser dibuka otomatis.

### 5.6 `qa_overlay`
- Render 2–3 blok sampel per run: ortho RGB + garis batas blok → PNG di folder output/laporan.

## 6. Output & Penamaan

- Root output baru: `F:\dataset\Pix4DField-export-<FLGxx>_auto\`
- Struktur: `{DIVISI}\{FLGxx}_{DIVISI}-{BLOK}\` — contoh `AME II\FLG03_AMEII-D01\`
- Set file per blok (mengikuti pola referensi):

| Layer | File |
|---|---|
| Orthomosaic | `Orthomosaic - <NAME>.data.tif` (5-band float32), `.rgb.tif` |
| NDRE | `NDRE.data.tif`, `NDRE.rgb.tif`, `NDRE.legend.png` |
| NIR | `NIR.data.tif`, `NIR.rgb.tif`, `NIR.legend.png` |
| RedEdge | `RedEdge.data.tif`, `RedEdge.rgb.tif`, `RedEdge.legend.png` |
| Surface model | `Surface model - <NAME>.data.tif`, `.rgb.tif`, `.legend.png` |

- Mapping divisi per blok: lookup dari `2_Tanam_Inti.shp` (Divisi/BLOK_Baru) + koreksi manual di tabel UI sebelum run.
- Blok tanpa cakupan raster → status "dilewati (tanpa data)", tercatat di CSV/log.

## 7. Penanganan Error & Log

| Level | Contoh | Perilaku |
|---|---|---|
| Pra-jalan | Kalibrasi PDF belum lolos; file layer hilang; disk < perkiraan kebutuhan | Run ditolak; pesan spesifik di UI; tidak menulis |
| Per blok | gdalwarp gagal (data nodata/error disk) | Blok → `gagal` + alasan; batch lanjut; tombol "Coba ulang blok" |
| Fatal | Disk penuh saat berjalan; PDF hilang di tengah | Stop aman; state tersimpan; pesan instruksi di UI |

Log: panel live di UI + `run_<tanggal>.log` + `hasil_per_blok.csv` di folder output.

## 8. Verifikasi Bertahap (gate persetujuan pengguna)

1. **Gate 0 (sebelum coding penuh):** konfirmasi dari pengguna bahwa Pix4DField mendukung export layer full-extent; bila tidak, dipakai boundary besar tunggal per project.
2. **Gate 1:** hasil `pdf_blok` — overlay peta + statistik residual + perbandingan vs `bdr_*.zip`; pengguna melihat PNG dan meng-ACC akurasi.
3. **Gate 2:** 1 project kecil (~5–10 blok) → bandingkan hasil vs export manual (posisi, cakupan, ukuran file, palet); ukur rasio kompresi asli (untuk kalibrasi estimasi). Pengguna ACC.
4. **Gate 3:** batch penuh 1 flight ke folder `..._auto`; ringkasan statistik; pengguna verifikasi visual beberapa blok; baru dipakai rutin.

## 9. Non-Goals (iterasi ini)

- Otomasi GUI Pix4DField.
- Menimpa/mengubah arsip lama (semua tulisan ke folder baru).
- Komputasi ulang NDRE dari 5-band (dicatat sebagai opsi masa depan).
- Opsi B (baca cache `img_*.tif`) — cadangan, butuh investigasi lanjutan.
- Multi-user/server jaringan.
- **Fallback GCP manual saat kalibrasi PDF gagal — DE-SCOPE (2026-10-14).** Keputusan pengguna setelah review independen kedua: jalur yang berlaku adalah pesan error residual yang spesifik saja; jalur GCP manual (3–4 pasangan titik PDF↔UTM) dicatat sebagai kandidat iterasi berikutnya, bukan kontrak iterasi ini.

## 10. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Kalibrasi PDF tidak akurat (>3 m) | Gate 1 + cross-check `bdr_*.zip`; fallback GCP manual **di-de-scope** (§9) — jalur gagal = pesan residual spesifik |
| App tidak mendukung export full-extent | Gate 0; alternatif boundary tunggal besar |
| Rasio kompresi nyata belum diketahui | Diukur pada Gate 2 sebelum batch (estimasi awal 30–60% untuk float) |
| Palet Pix4D tidak persis tertiru | Palet disampel dari `.rgb.tif` export lama; legend digenerate konsisten |
| Disk penuh saat batch | Pra-cek disk di Scan; Cancel aman; resume |
| Penamaan blok PDF ↔ folder tidak konsisten (F22D22, C04A/B, NDRE 2/3/4) | Normalisasi terpusat + tabel pemetaan bisa dikoreksi di UI |

## 11. Item Konfirmasi Kecil (dibawa ke review ini)

- Nama folder output `<...>_auto` — atau usulan pengguna lain?
- Format nama blok pada path: `FLG03_AMEII-D01` (padat, mengikuti `FLG01_AMEII-D01`) — setuju?
