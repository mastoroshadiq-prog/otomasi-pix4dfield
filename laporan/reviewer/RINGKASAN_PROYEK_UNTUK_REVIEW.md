# Ringkasan Proyek untuk Review — Tool "Ekspor Blok Otomatis" (Pix4DField)

**Dibuat:** 2026-10-14 | **Oleh:** agen pelaksana (deep) | **Untuk:** agent AI reviewer independen

> Dokumen ini adalah konteks pekerjaan yang diminta direview. Ia ditulis oleh pihak
> yang mengerjakan — anggap SEMUA klaim di sini sebagai **hipotesis yang harus
> diverifikasi**, bukan kebenaran. Aturan main dan format laporan ada di `BRIEF.md`
> (wajib dibaca; checklist A–H di sana). Reviewer tidak boleh mencukupkan diri pada
> dokumen ini.

## 1. Latar belakang & tujuan

Pengguna adalah pengelola kebun sawit yang memakai Pix4DField untuk mengolah hasil
foto drone. Masalah: Pix4DField hanya mengekspor **full extent** (seluruh terbang)
atau per blok secara manual — menggambar boundary dan mengekspor satu per satu untuk
puluhan blok per flight itu lambat dan rawan salah.

Solusi yang dibangun: tool lokal yang **memotong otomatis** ekspor full-extent
Pix4DField menjadi layer per blok, memakai poligon blok dari Peta Informasi Tanam
(PDF). Pekerjaan ini menggantikan langkah manual tersebut.

## 2. Ruang lingkup yang diminta direview

- **Repo:** `D:\pix4dfield_exporting_tools` — repo git lokal (tanpa remote),
  HEAD `65b4b44` (2026-10-13), working tree bersih saat paket dibuat.
- **Rentang:** seluruh kode commit `3158105` … `65b4b44` (14 commit; daftar lengkap
  via `git log --oneline`). Dokumen kontrak:
  `docs/superpowers/specs/2026-10-13-ekspor-blok-otomatis-design.md`.
- Yang diminta: review kebenaran teknis, kesesuaian dengan spec, kualitas tes,
  keselamatan data, dan audit klaim (checklist A–H di `BRIEF.md`).

## 3. Kontrak yang mengikat (dari spec — pelanggaran = temuan)

1. **Opsi A:** pengguna mengekspor full-extent satu kali per project secara manual
   di Pix4DField; tool mengerjakan sisanya otomatis. Tool TIDAK mengotomasi GUI
   Pix4DField dalam bentuk apa pun (tanpa klik otomatis).
2. **Output selalu folder BARU** `F:\dataset\Pix4DField-export-<kode>_auto`;
   arsip lama tidak pernah ditimpa.
3. **Folder sumber read-only** — tool tidak boleh menulis/mengubah apa pun di sana.
4. Server web **lokal 127.0.0.1** saja; UI berbahasa Indonesia; dijalankan via
   `jalankan.bat`.
5. Verifikasi bertahap **Gate 0–3**: (0) konfirmasi dukungan export full-extent;
   (1) overlay kalibrasi disetujui; (2) banding 1 project kecil vs ekspor manual;
   (3) batch penuh satu flight.

## 4. Arsitektur (ringkas)

```
PDF peta blok ──core/pdf_blok.py──► data/blok.geojson (poligon + divisi + label)
                    │  kalibrasi affine PDF→UTM (least squares, cache)
                    ▼
Folder sumber (ekspor Pix4DField full-extent, read-only)
   └─core/layer_scan.py──► rencana item per blok×layer (folder {DIVISI}\{FLG}-{BLOK})
        └─core/crop_engine.py──► crop window-based per blok (+ legend, palet, overview)
             └─core/runner.py──► batch: state.json / resume / retry / cancel / CSV / log
                  └─► F:\dataset\Pix4DField-export-<FLG>_auto\...  (folder BARU)

UI: app.py + templates/index.html + static/app.js — 4 tahap:
   Setup → Pindai → Jalankan (progress/batalkan/ulangi/unduh) → Validasi (kartu per blok)
```

## 5. Peta modul (1 baris masing-masing)

| Berkas | Tanggung jawab |
|---|---|
| `app.py` | Server Flask lokal + endpoint API (config, pindai, jalankan, status, ulangi, batalkan, unduh, buka folder, kartu) |
| `core/config.py` | Dataclass konfigurasi + simpan/muat `data/config.json` |
| `core/pdf_blok.py` | Kalibrasi affine PDF→UTM; ekstraksi sel blok → geojson + QA; repair sel cacat |
| `core/layer_scan.py` | Klasifikasi layer sumber; blok dalam cakupan; rencana output; penamaan folder |
| `core/crop_engine.py` | Crop 1 layer (window + mask, pad 1 px); kompresi per tipe; overviews; legend |
| `core/palet.py` | Palet warna NIR/RedEdge/DSM (sampling/ramp) + pembuatan legend |
| `core/qa_overlay.py` | Overlay blok hasil crop untuk QA visual |
| `core/runner.py` | Orkestrasi batch: state.json, resume, retry, cancel, disk penuh, CSV, log |
| `core/kartu.py` | Kartu validasi per blok (strip + 6 inset + footer luas/IoU/geser) + index.json |
| `templates/index.html`, `static/app.js`, `static/style.css` | UI 4 tahap + viewer kartu |
| `tests/` (11 berkas) | 40 tes: kalibrasi, ekstraksi, scan, crop, palet, runner, qa, app, e2e sintetis, kartu |

## 6. Status & klaim angka (WAJIB diverifikasi ulang)

Status yang diklaim: **Gate 0–2 selesai & terverifikasi; Gate 3 (flight penuh) belum
dijalankan.** Hasil batch berasal dari run nyata 2026-10-13.

| # | Klaim | Nilai | Bukti | Cara cek mandiri |
|---|---|---|---|---|
| K1 | Kalibrasi PDF | residual maks 0,49 m (ambang 3 m) | `data/kalibrasi.json`, `laporan/gate1/` | hitung ulang dari tabel kontrol |
| K2 | Geojson blok | 459 fitur; 440 kode unik; 431 berdivisi | `data/blok.geojson`, `data/qa_pdf_blok.json` | hitung dari geojson |
| K3 | Batch Gate 2 | FLG01-AMEIII, 8 blok, 40/40 selesai, 0 gagal, ±827 dtk | `laporan/_uji_d17/run_gate2.log`, `gate2_verifikasi.json` | baca log |
| K4 | Presisi crop | selisih piksel maksimum data-vs-sumber = 0,0 (semua 40 file); 0 piksel bukan-nodata di luar poligon | `laporan/_uji_d17/verify_gate2.py` (rekomputasi dari SUMBER) | jalankan/bedah skrip |
| K5 | Ukuran output | total 24,71 GB (≈23,03 data + 1,43 rgb + legend) | folder `F:\dataset\Pix4DField-export-FLG01-AMEIII_auto` | hitung ulang byte |
| K6 | Kompresi | DEFLATE+predictor ±20–23% lebih kecil dari LZW manual (per-ha, GSD setara) | `laporan/_uji_d17/RINGKASAN.md` | banding ukuran file nyata |
| K7 | rgb JPEG Q85 | derau ±0,63/255 vs sumber | `RINGKASAN.md`, `verify_gate2.py` | ukur ulang |
| K8 | Legend | 32/32 md5 identik dengan ekspor manual | `RINGKASAN.md` | md5sum |
| K9 | Kartu validasi | IoU PDF-vs-shp 92,3–98,7% (8 blok); geser 1,5–9,4 m; selisih sistematis ±8 m di tepi barat (batas PDF mengikuti jalan koleksi) | `F:\..._auto\_validasi\index.json` | hitung ulang geometri |
| K10 | Cakupan sumber | 8 blok 100% (±197,6 ha); parsial F13 41%, E17 33%, D17 31% | `RINGKASAN.md` | metode topeng alpha |
| K11 | Tes otomatis | 40/40 lulus | `tests/` | jalankan pytest |

## 7. Pertanyaan yang diharapkan dijawab reviewer

1. Apakah transformasi geometri crop benar (window, pad 1 px, `window_transform`,
   `geometry_mask`)? Ada off-by-one / y-flip / pembulatan piksel?
2. Apakah ada jalur kode yang bisa menulis/menghapus di folder sumber, atau menimpa
   arsip lama?
3. Apakah resume `state.json` aman terhadap: kode flight berubah, file output
   hilang, folder output diganti?
4. Apakah klaim gate (K1–K11) bisa direproduksi pihak ketiga dari repo ini? Apa
   yang kurang untuk itu?
5. Apakah tes menguji perilaku nyata (bukan tautologi)? Celah tes paling berisiko?
6. Apakah estimasi disk pra-jalan dapat diandalkan? (hitung ulang dengan data nyata)
7. Apakah penanganan sel PDF cacat (`make_valid` → ambil Polygon terbesar) benar
   untuk kasus lain?
8. Apakah UI aman (path traversal, XSS) dan benar-benar hanya lokal?
9. Apakah memori/performa aman untuk raster besar & flight penuh (ratusan blok)?
10. Bagian spec mana yang belum diimplementasikan (gap kontrak)?

## 8. Cara verifikasi cepat (untuk reviewer dengan akses file)

```bash
cd /d/pix4dfield_exporting_tools && .venv/Scripts/python.exe -m pytest tests/ -q
```

Lingkungan: Windows + Git Bash; cwd shell reset tiap perintah → awali tiap perintah
dengan `cd /d/pix4dfield_exporting_tools &&`; GDAL CLI tidak tersedia (semua raster
via rasterio). Detail lain di `BRIEF.md`.

## 9. Catatan privasi & batasan paket

- Paket untuk AI cloud **tidak memuat raster** maupun `data/blok.geojson` /
  `data/kalibrasi.json` (koordinat blok = data lokasi kebun). Verifikasi angka
  geometri penuh (K2, K4, K9) hanya bisa dilakukan reviewer dengan akses file di
  komputer ini (Opsi A di `PANDUAN_REVIEW_AGENT_LAIN.md`).
- Bukti teks memuat path lokal mesin pembuat (mis. `F:\...`) — bukan rahasia, tetapi
  jangan disebar publik.
