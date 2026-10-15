# Laporan Review Independen — Tool "Ekspor Blok Otomatis"

**Tanggal review:** 2026-10-14
**Reviewer:** Senior Code Reviewer independen (bukan implementer; falsification mindset)
**Repo:** `D:\pix4dfield_exporting_tools`
**Rentang commit dinilai:** `118ae92..65b4b44` — 12 commit, 31 file, +2.305 baris (`git diff --stat 118ae92..65b4b44`)
**Snapshot dinilai:** HEAD `65b4b4448530f1a24d0b5569511d1e715e9a3bb0`, dibaca langsung dari working tree (`git status` bersih; review tidak mengubah repo)
**Kontrak:** `docs/superpowers/specs/2026-10-13-ekspor-blok-otomatis-design.md`; rencana: `docs/superpowers/plans/2026-10-13-ekspor-blok-otomatis-implementasi.md`
**Metode:** pembacaan penuh kode pada HEAD, eksekusi tes resmi, audit angka klaim dengan pengukuran ulang independen (rasterio; GDAL CLI tidak tersedia). Tidak menjalankan batch/GUI/server; seluruh akses `F:\dataset` dan `E:\` read-only. Satu-satunya berkas yang ditulis: laporan ini.

---

## 1. Ringkasan & Verdict

**Verdict: PERLU PERBAIKAN** — 0 KRITIS, 3 TINGGI, 3 SEDANG, 8 RENDAH.

Inti teknis tool solid dan terbukti kuat: crop piksel-eksak (`max|diff| = 0,0`) yang saya verifikasi ulang secara independen, folder sumber aman, output selalu ke folder baru `..._auto`, server hanya 127.0.0.1, tanpa otomasi GUI. Seluruh angka utama di `laporan/_uji_d17/RINGKASAN.md` yang saya uji ulang cocok (IoU/geser 8/8 blok, ukuran byte, md5 legend, resolusi, estimasi kompresi). Yang menahan status "siap produksi" adalah tiga masalah TINGGI di jalur operasional: estimasi disk pra-run meleset ±39× (kontrol spec §pra-jalan tidak berfungsi), resume tanpa verifikasi file output (risiko output flight baru dilewati senyap), dan bug logging pada tombol "Ulangi" (log run kedua tidak terbentuk — direproduksi empiris), plus celah kontrak spec (status "dilewati", fallback GCP) dan auditabilitas (bukti gate tidak ter-commit).

Hasil tes resmi yang diwajibkan (dijalankan apa adanya, dua kali dengan hasil sama):

```
$ cd /d/pix4dfield_exporting_tools && .venv/Scripts/python.exe -m pytest tests/ -q
........................................                                 [100%]
40 passed in 4.52s
```

---

## 2. Kekuatan (terverifikasi, bukan sekadar klaim)

1. **Presisi crop piksel-eksak — tahan uji falsifikasi.** Saya menghitung ulang langsung dari sumber: D13/NDRE `max|diff| = 0.0`, 0 piksel non-nodata di luar poligon, jumlah piksel dalam 88.059.114; E13/ortho 5-band `max|diff| = 0.0`, ukuran 1.510.287.972 B persis. Agregat gate2_verifikasi.json: 40/40 item `max_diff_dalam = 0.0` dan `n_luar_bukan_nodata = 0`. Mekanisme benar: `Window(win.col_off - 1, win.row_off - 1, win.width + 2, win.height + 2)` (pad 1 px terdokumentasi, `core/crop_engine.py:18`), `window_transform`, `geometry_mask`, strip `CHUNK_ROWS`.
2. **Georeferensi output konsisten dengan geometri permintaan.** Saya cek independen (bukan memakai transform output sebagai acuan): `dst.transform == window_transform(jendela geometri)` dan `dst.window == jendela geometri −1 px` untuk D13/NDRE dan E13/ortho. Ini menutup blind-spot script verifikasi gate (lihat R-7).
3. **Keselamatan data — folder sumber read-only benar-benar terjaga.** Enumerasi semua jalur tulis di `core/`+`app.py` (open-write/mkdir/copyfile/replace) hanya menuju folder output/log/palet; mtime file sumber 2026-10-13 14:05–14:07 (sebelum batch 15:12); folder arsip lama tidak tersentuh; output mendarat di folder BARU `F:\dataset\Pix4DField-export-FLG01-AMEIII_auto` (total root 24.721.985.387 B).
4. **Kepatuhan kontrak produk terpenuhi.** Server hanya `127.0.0.1` (`app.py:288`), tanpa dependensi otomasi GUI (grep pyautogui/pywinauto/win32com/keyboard/mouse = kosong), UI berbahasa Indonesia, guard path-traversal `/api/kartu/file/<nama>` (`app.py:239-240`) dengan uji pytest (400 untuk `..%5Capp.py`, 404 untuk `..%2F..%2Fapp.py`).
5. **Ketahanan runner bagus untuk jalur normalnya.** `state.json` ditulis atomik (`.tmp` + replace, `core/runner.py:61-67`), resume dilewati-status, retry item 1×, cancel via `threading.Event` aman setelah item berjalan, errno 28 → stop + resume (`core/runner.py:164-168`), CSV ledger + log per run. Ada uji untuk sukses/resume/retry/cancel/disk-full (`tests/test_runner.py`, crop_fn palsu).
6. **Penanganan sel PDF cacat rapi.** `make_valid()` + komponen Polygon terbesar (`core/pdf_blok.py:190-191`) memulihkan D02/D14/F33/F34; angka 459 fitur / 440 kode / 431 divisi konsisten antara `data/qa_pdf_blok.json` dan `data/blok.geojson`; ada tes regresi khusus.
7. **Audit angka RINGKASAN — semua yang diuji ulang cocok.** IoU & geser 8/8 blok persis (recompute mandiri dari `data/blok.geojson` vs `E:\...2_Tanam_Inti.shp`: D13 93,66%/7,50 m, D14 92,27%/9,40 m, D15 94,25%/8,02 m, D16 98,68%/1,47 m, E13 96,91%/3,88 m, E14 96,48%/3,58 m, E15 96,63%/4,16 m, E16 96,72%/4,06 m); state 40/40 selesai; 32/32 legend md5 identik; `total_byte_data` 23.027.446.780 B; rgb 1.426.998.380 B; per blok (data) 2,75–3,14 GB persis; angka per-item persis (D13 rgb rata-rata 0,8404586906169137; `n_dalam` 88.059.114; ukuran 1.510.287.972 B). Klaim kompresi "±20–23% lebih kecil dari LZW" terkonfirmasi: 18,1→≈14,0 (−22,7%), 80,9→≈63,9 (−21,0%), 12,4→9,7 (−21,8%).
8. **`verify_gate2.py` bukan bias konfirmasi.** Ia merekomputasi dari SUMBER (bukan dari output), punya kriteria gagal keras (`sys.exit(1)`, baris 157–160), dan hasilnya konsisten dengan pengukuran ulang saya. Kelemahan kecil ada di R-7.
9. **Diferensiasi DEFLATE+PREDICTOR=3 vs JPEG Q85 benar per tipe data.** Terverifikasi via `tags(ns='IMAGE_STRUCTURE')`, termasuk `predictor` dibuang dari profil sebelum set ulang (`core/crop_engine.py:26-30`) — detail yang mudah salah.

---

## 3. Temuan

### KRITIS

**Tidak ada temuan tingkat KRITIS.** Tidak ditemukan: penulisan ke folder sumber/arsip, hasil yang salah secara sistematis, kehilangan data, pelanggaran batas server, atau klaim gate yang palsu. Semua temuan di bawah adalah perbaikan mutu/operasional, bukan kegagalan total.

### TINGGI

**T-1. Estimasi kebutuhan disk pra-run meleset ±39× → kontrol "disk cukup" praktis tidak berfungsi**

- Bukti, `app.py:72-75`:
  ```python
  luas_semua = sum(f["properties"]["luas_ha"] for f in gj["features"]) or 1.0
  luas_blok = sum(f["properties"]["luas_ha"] for f in blok)
  ukuran_src = sum(Path(v["data"]).stat().st_size for v in hasil["layers"].values())
  estimasi = int(ukuran_src * (luas_blok / luas_semua) * 0.6)   # faktor konservatif vs rekompresi
  ```
- Pengukuran ulang saya: `ukuran_src` = 38.287.432.957 B (5 layer data sumber); `luas_semua` = 7.225,2 ha (seluruh fitur peta, bukan wilayah yang diekspor) vs `luas_blok` = 197,63 ha → rasio 2,7353% → `estimasi` = **628.365.192 B (0,63 GB)**. Output nyata batch: **24.708.559.348 B (24,71 GB)** → meleset **±39,3×** (angka output konsisten dengan tabel RINGKASAN).
- Ambang penolakan, `app.py:159`: `if bebas < info["estimasi_byte"] * 1.2:` → hanya menuntut bebas > 754 MB. Praktis semua disk lolos.
- Dampak: kontrak spec baris 135 ("Pra-jalan … disk < perkiraan kebutuhan → Run ditolak; pesan spesifik di UI") tidak terlaksana. Batch dapat mengisi disk hingga penuh; mitigasi hanya errno 28 di `core/runner.py:164-168` (berhenti setelah berjam-jam kerja, item sisa `pending`). Gate 2 dijalankan via `run_gate2.py` (tanpa pra-cek UI) sehingga bug ini tidak pernah teruji pada jalur nyata.
- Usul perbaikan: ganti basis estimasi ke luas yang benar-benar dicetak terhadap cakupan sumber. Dua opsi konkret: (a) kalibrasi Gate 2 — 24.708.559.348 B / 197,63 ha ≈ **125 MB/ha** pada GSD 5,28 cm → `estimasi = 125 MB/ha × luas_blok × margin (1,3–1,5)` + koreksi GSD; atau (b) `luas_semua` diganti luas wilayah berdata footprint sumber (∝ luas alpha>0, mis. 257,9 ha) sehingga rasionya ±76,6% dan hasilnya dekat aktual. Tambahkan tes unit angka estimasi dan tampilkan juga di log.

**T-2. Resume berbasis `(kode, layer)` tanpa verifikasi file output dan tanpa penjagaan folder `_auto` baru → risiko output flight baru dilewati senyap**

- Bukti, `core/runner.py:73-80`:
  ```python
  lama = {(it["kode"], it["layer"]): it for it in data.get("items", [])}
  ...
      prev = lama.get((it.kode, it.layer))
      if prev and prev["status"] in ("selesai", "dilewati"):
          it.status = prev["status"]
  ```
  Kunci resume tidak memuat kode flight maupun path tujuan; `state.json` hidup di dalam folder output (`core/runner.py:43`). `app.py:162-166` membuat Runner dengan `KONFIG.folder_output` apa pun tanpa memvalidasi bahwa folder itu baru/`_auto`/milik flight yang sama.
- Skenario dampak konkret: pengguna mengganti `kode_flight` (mis. FLG01→FLG02) tetapi menunjuk folder output yang sama (atau folder `..._auto` yang pernah dipakai). Nama file output memuat kode flight (`{FLGxx}_{DIVISI}-{BLOK}`, `core/layer_scan.py:76-93`; spec §6) sehingga file FLG02 belum ada — namun semua item `(kode, layer)` yang sama akan ditandai `selesai` dari state lama dan **dilewati tanpa pesan**; output flight baru hilang secara senyap. Sebaliknya, file output yang terhapus manual juga tidak terdeteksi (tidak ada cek `Path(prev["dst_data"]).exists()`).
- Kontrak D3 spec ("Folder BARU (`..._auto`) — arsip lama tidak pernah ditimpa", spec baris 25) saat ini hanya dijamin oleh isi `config.json` manual; tidak ada validasi di kode.
- Usul perbaikan: (a) saat resume, verifikasi `dst_data`/`dst_rgb`/`dst_legend` benar-benar ada dan ukurannya cocok dengan state; jika tidak → kembalikan ke `pending`; (b) simpan `kode_flight` (dan `output_root`) di dalam `state.json` dan tolak/labeli resume bila berbeda (atau jadikan path tujuan bagian dari kunci); (c) validasi di `/api/jalankan`: folder output wajib berakhiran `_auto` dan, bila `state.json` lama berisi flight berbeda, minta folder baru; (d) uji unit skenario "ganti flight, folder sama" dan "file output dihapus".

**T-3. Bug logging tombol "Ulangi": log run kedua tidak terbentuk, panel log UI kosong, handle file bocor (direproduksi)**

- Bukti, `core/runner.py:105-113`:
  ```python
  self.log_path = self.folder_log / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"
  self._logger = logging.getLogger(f"runner_{id(self)}")
  self._logger.setLevel(logging.INFO)
  if not self._logger.handlers:
      fh = logging.FileHandler(self.log_path, encoding="utf-8")
  ```
  `retry()` (`core/runner.py:93-102`) memanggil `self.start()` → `run()` lagi pada objek yang sama. Karena `handlers` sudah terisi dari run pertama, FileHandler BARU untuk `log_path` baru tidak pernah dibuat: semua baris run kedua masuk ke file log pertama, dan file yang ditunjuk `log_path` tidak pernah ada.
- Jalur nyata yang memicunya: `app.py:191-194` endpoint `/api/ulangi` → `RUNNER["obj"].retry(kode)` (dipakai tombol "Coba ulang blok", spec baris 136); `app.py:176-179` `/api/status` membaca `r.log_path` → `log_tail = ""` sehingga **panel log UI kosong** setelah retry; `/api/unduh/log` (`app.py:215-220`) menyajikan file yang tidak ada.
- Reproduksi empiris (tanpa batch nyata, crop_fn palsu): setelah `retry()`, `r.log_path.name == "run_20261014_152419.log"` dengan `exists: False`; baris run kedua tercatat di file log pertama; saat pembersihan muncul `PermissionError: [WinError 32]` karena FileHandler lama masih menggenggam file (handle bocor — di Windows ini juga mengunci penghapusan/pemindahan log).
- Dampak: pada jalur pemulihan kegagalan — justru saat bukti paling dibutuhkan — log hilang dan UI tampak "tidak ada aktivitas"; diagnosis lapangan (mis. error disk/driver) menjadi sulit. `tests/test_runner.py` menguji `retry()` tetapi tidak memeriksa file log, sehingga bug lolos.
- Usul perbaikan: bersihkan handler sebelum memasang yang baru:
  ```python
  for h in list(self._logger.handlers):
      h.close(); self._logger.removeHandler(h)
  ```
  lalu tambahkan FileHandler baru (atau logger unik per run + tutup handler di akhir `run()`). Tambahkan uji regresi: dua run berturutan pada objek yang sama → file log kedua ada dan berisi; `log_path` konsisten.

### SEDANG

**S-1. Status "dilewati (tanpa data)" tidak pernah diproduksi (kontrak spec tidak terpenuhi)**

- Spec baris 97 mencantumkan status `pending / berjalan / selesai / gagal / dilewati (tanpa data)` dan baris 129: "Blok tanpa cakupan raster → status 'dilewati (tanpa data)', tercatat di CSV/log". Di kode, status ini hanya **dibaca** saat resume (`core/runner.py:70,78`); tidak ada satu pun tempat yang menetapkannya (grep seluruh `core/` + `app.py`: tidak ada `status = "dilewati"`).
- Akar masalah: blok disaring hanya terhadap bounds ortho (`app.py:64` → `layer_scan.blok_dalam_cakupan(..., hasil["layers"]["ortho"]["bounds"])`), sedangkan `rencana_output` membuat baris untuk SEMUA layer per blok (`core/layer_scan.py:83`). Bila ada layer berfootprint lebih kecil (umum di flight besar: NDRE/DSM diproses sebagian wilayah), baris untuk blok di luar cakupan layer tersebut tetap dijadwalkan → perilaku aktual: jendela kosong → error → `gagal`, atau tumpang tindih sebagian → file seluruh-nodata berstatus `selesai` (menyesatkan). Kasus ini tidak muncul pada flight uji karena kelima layer menutupi 8 blok 100%, dan tidak ada tesnya.
- Usul: uji irisan geometri blok ∩ bounds per layer saat membangun rows (metodologi alpha-footprint seperti RINGKASAN §4) lalu set `dilewati` di runner (atau eksklusi bertanda di UI); tambah tes unit sintetis dengan layer ber-footprint parsial.

**S-2. Fallback kalibrasi GCP manual tidak diimplementasikan**

- Spec baris 79: "Fallback bila grid tidak terdeteksi: file GCP manual (3–4 pasangan titik PDF↔UTM) yang diisi pengguna…"; baris 160: "Gate 1 + fallback GCP manual". Implementasi hanya jalur otomatis least-squares dengan ambang `AMBANG_RESIDUAL_M = 3.0` (`core/pdf_blok.py:7,78,108`); tidak ada jalur input manual.
- Cross-check `bdr_*.zip` (spec baris 81/144) juga tidak diimplementasikan; praktiknya digantikan kartu PDF vs `2_Tanam_Inti.shp` (`core/kartu.py`) — pembanding yang berbeda dari spec.
- Dampak: bila PDF baru tidak memuat grid kontrol atau residual >3 m, proses berhenti di Gate 1 tanpa jalur lanjut di dalam tool; kontingensi operasional harus dikerjakan manual di luar tool. Bukan kesalahan hasil — celah kontrak/kontingensi.
- Usul: minimal sediakan `data/gcp_manual.json` opsional (bila ada → dipakai untuk membangun affine, dengan validasi residual); bila memang di-descope, tandai eksplisit di spec + RINGKASAN agar tidak dianggap ada.

**S-3. Bukti Gate 1/2 tidak ter-commit ke git — lubang auditabilitas**

- `.gitignore` memuat `logs/` dan `laporan/`; akibatnya `git ls-files laporan` = **0 file**: `RINGKASAN.md`, `verify_gate2.py`, `gate2_verifikasi.json`, `run_gate2.log`, kartu uji, dan seluruh bukti gate hanya ada di working tree mesin ini. Klaim Gate 2 tidak dapat direproduksi dari clone repo.
- Dampak: reviewer/auditor lain harus memercayai mesin lokal; tidak ada jejak bukti per commit; risiko bukti hilang bila mesin dibersihkan. (Saya dapat mengauditnya hanya karena kebetulan bekerja di mesin ini.)
- Usul: whitelist artefak kunci, mis.:
  ```gitignore
  laporan/*
  !laporan/_uji_d17/RINGKASAN.md
  !laporan/_uji_d17/verify_gate2.py
  !laporan/_uji_d17/gate2_verifikasi.json
  !laporan/_uji_d17/run_gate2.py
  ```
  (atau pindahkan ke `tests/artifacts/`). Untuk run besar, commit checksum + ringkasan JSON saja.

### RENDAH

**R-1. Artefak Gate 1 basi.** `laporan/gate1/qa_pdf_blok.json` masih `n_berlabel = 455` (436 kode, 427 divisi), sedangkan kondisi berjalan adalah 459/440/431 (`data/qa_pdf_blok.json`) — artefak tidak diregenerasi setelah perbaikan make_valid. Tidak memengaruhi jalur produksi, tetapi menyesatkan audit. Usul: regenerasi + masuk whitelist repo (lihat S-3).

**R-2. Footer kartu validasi di-hardcode.** `core/kartu.py:173-174`:
```python
"konteks: residual kalibrasi PDF 0,49 m; GSD 5,28 cm/px; "
"garis digambar apa adanya tanpa penyesuaian"
```
Nilai residual & GSD khusus flight uji; pada flight lain keterangan kartu akan salah. Usul: parameterisasi dari `data/kalibrasi.json` dan transform raster; untuk GSD ambil `abs(transform.a)` dari ortho blok.

**R-3. `innerHTML` dengan data dari server.** `static/app.js:31,69-70` menyematkan `${b.kode}`, `${it.divisi}`, `${it.error}` ke `innerHTML`. Semua lokal (127.0.0.1) dan data milik pengguna, sehingga risiko rendah (self-XSS), tetapi pesan error rasterio dapat memuat string eksternal (path/nama file). Usul: bangun lewat `textContent`/DOM API atau escape sebelum interpolasi.

**R-4. Race `/api/jalankan`.** `app.py:150-166` memeriksa `RUNNER["obj"].snapshot()["aktif"]`, lalu (setelah `_bangun_rows()` yang tidak instan) menimpa `RUNNER["obj"]` tanpa kunci; Flask dev server threaded → dua POST beruntun dapat lolos keduanya → dua Runner menulis folder/nama file yang sama. Usul: `threading.Lock` atau penanda status atomic sebelum membangun rows.

**R-5. `_port_bebas` mengembalikan 0.** `app.py:17-22`: bila 5000–5049 semuanya terpakai, fungsi mengembalikan 0 → Flask memilih port acak yang tidak tercatat, dan `webbrowser.open(f"http://127.0.0.1:{port}")` (`app.py:287`) membuka URL salah. Usul: return None → tampilkan pesan gagal, atau lebarkan rentang dan laporkan port aktual dari server.

**R-6. Daftar blok pada respons pindai dipotong 500.** `app.py:147`: `"blok": info["blok"][:500]`. Untuk peta >500 blok, tabel pratinjau tidak lengkap (jalankan tetap memakai daftar penuh → tampilan vs eksekusi bisa berbeda). Usul: paginasi atau hilangkan potongan (respons JSON kecil).

**R-7. Blind-spot kecil di `verify_gate2.py`.** `laporan/_uji_d17/verify_gate2.py:36-37` hanya meng-assert `ss.transform.a/.e` (ukuran piksel) — bukan origin (`c`,`f`) atau CRS penuh; seluruh cek geometri memakai `dd.bounds`/`dd.window_transform` (referensinya transform output sendiri). Pola ini tidak bias konfirmasi terhadap konten (`cek_data` merekomputasi dari sumber), tetapi pergeseran output sebesar bilangan bulat piksel bisa lolos script. Saya kompensasi dengan pengukuran independen (dst transform == window_transform dari jendela geometri; pad −1 px) untuk D13/NDRE dan E13/ortho — benar. Usul: tambah assert origin & CRS, atau bandingkan `dst.transform` dengan `window_transform` yang dihitung dari sumber. (Catatan mutu verifikasi, bukan cacat produk.)

**R-8. Pada ekspor uji, NIR ≡ RedEdge (piksel identik).** Saat verifikasi independen terlihat isi `NIR.data.tif` dan `RedEdge.data.tif` identik bitwise (palet/mtime berbeda). Bukan bug tool (salin apa adanya), tetapi: (a) klaim "5 layer" secara konten hanya 4 layer unik pada flight uji; (b) verifikasi silang NIR vs RedEdge jadi redundan. Usul: catat di RINGKASAN dan uji ulang dengan flight nyata yang membedakan keduanya; tidak ada perubahan kode.

---

## 4. Rekomendasi

1. **Sebelum pemakaian rutin flight berikutnya:** perbaiki T-1 (estimasi disk basis MB/ha dari Gate 2) dan T-2 (verifikasi file output saat resume + state memuat flight + validasi folder `_auto`). Dua ini berdampak langsung keselamatan operasional.
2. **Segera setelahnya:** perbaiki T-3 (bersihkan FileHandler sebelum run baru) + uji regresi log ganda.
3. **Kontrak spec:** implementasikan S-1 ("dilewati") atau de-scope eksplisit di spec+RINGKASAN; putuskan S-2 (fallback GCP manual) — implementasi minimal atau tandai descope.
4. **Auditabilitas:** S-3 — whitelist artefak gate agar klaim Gate 1/2 dapat direview dari repo.
5. **Cepat & murah:** R-2 (footer kartu diparameterisasi), R-3 (`textContent`), R-4 (lock), R-5 (port), R-6 (potongan 500), R-1 (regenerasi artefak gate1), R-7 (assert transform script verifikasi).
6. **Tambahan uji yang disarankan:** (a) dua run berturutan pada satu objek → file log kedua ada; (b) resume dengan file output dihapus / kode flight berbeda → item kembali `pending`; (c) blok di luar cakupan sebagian layer → `dilewati`; (d) regresi angka estimasi disk terhadap ukuran nyata.

---

## 5. Penilaian Akhir

**Perlu perbaikan.** Inti teknis (presisi crop, keamanan folder sumber, struktur output, pemisahan kompresi per tipe data) solid, terverifikasi kuat, dan layak dipertahankan; namun tiga temuan TINGGI menyentuh keselamatan operasional (pra-cek disk tidak berfungsi, resume lintas-flight dapat melewatkan output baru, log retry hilang) sehingga belum layak dipakai rutin tanpa perbaikan tersebut.

---

## 6. Daftar "Diperiksa & Lolos" (Cakupan)

- **A. Kesesuaian spec/rencana:** folder output BARU `..._auto` (D3) terpenuhi pada jalur riil; naming `{DIVISI}\{FLGxx}_{DIVISI}-{BLOK}` sesuai spec §6 (14 file/folder blok: 5 data + 5 rgb + 4 legend; ortho tanpa legend); struktur UI 4 tab berbahasa Indonesia; pra-cek disk ada implementasinya — tetapi tidak efektif (T-1) dan penjagaan folder baru tidak di kode (T-2).
- **B. Geometri & piksel:** pad 1 px + `window_transform` (bukan asumsi y-flip manual) — terverifikasi D13/NDRE & E13/ortho; 40/40 file `max|diff|=0,0`, 0 piksel non-nodata di luar poligon; make_valid D14/D02/F33/F34 + tes regresi; IoU/geser recompute = tabel RINGKASAN.
- **C. Keselamatan data:** tanpa tulis ke folder sumber (enumerasi jalur tulis + mtime); arsip lama utuh; `state.json` atomik; CSV 40 baris; errno 28 stop; cancel aman.
- **D. Concurrency/memori:** baca raster per jendela/strip (`CHUNK_ROWS=2048`), tidak ada muat penuh raster dalam jalur produksi; lock status; Event cancel; satu Runner per sesi normal (race dua-Runner pada R-4).
- **E. Keamanan web:** bind 127.0.0.1 (app.py:288); traversal `/api/kartu/file` guarded + diuji; `/api/buka-folder` hanya `os.startfile` folder output; tanpa otomasi GUI; tanpa dependensi jaringan keluar.
- **F. Kualitas tes:** `40 passed` (4,52 detik); cakupan inti baik (crop, kalibrasi PDF, ekstraksi sel cacat, runner resume/retry/cancel/disk-full, traversal, kartu). Celah: log retry (T-3), estimasi disk (T-1), resume lintas-flight (T-2), "dilewati" (S-1).
- **G. Audit RINGKASAN:** ≥2 angka diverifikasi independen — jauh lebih dari cukup: `max_diff=0,0`, `n_luar=0`, `rgb_mean` per-item & agregat, ukuran byte per file, IoU/geser 8/8, per-blok data 2,75–3,14 GB, kompresi ±20–23%, luas 197,63 ha, state 40/40, durasi 827 s (log) / Σdur 806 s. `verify_gate2.py` self-konsisten, mampu gagal, merekomputasi dari sumber (blind-spot origin di R-7).
- **H. Kasus tepi:** sel PDF cacat (diuji), filter area 0,2–400 ha, RGBA 4-band (band 1–3) + fix palet, layer parsial (tidak tercakup — S-1), NIR≡RedEdge pada data uji (R-8).

## 7. Klaim yang Tidak (Sepenuhnya) Dapat Diverifikasi

- **Kualitas visual** (palet "setara"/enak dilihat, inspeksi kartu "diperiksa mata") — saya verifikasi numerik (statistik, md5, IoU) tetapi tidak melihat gambar sebagai penilai visual; tidak ada temuan yang bergantung pada ini.
- **Asal-usul Pix4DField** dari ekspor full-extent (Gate 0 "terkonfirmasi dari aplikasi") — saya verifikasi konsistensi internal sumber (13 file, LZW, nodata −10000, alpha), bukan proses pembuatannya di Pix4DField.
- **Uji browser E2E tab 1–4 (task 24)** — tidak dijalankan ulang (aturan review melarang membuka server); digantikan pembacaan kode + tes endpoint. Interaksi UI nyata (klik/drag viewer) tidak diverifikasi.
- **Resume setelah interupsi nyata** (Ctrl+C / disk penuh di tengah batch) — hanya dibuktikan oleh uji unit dengan `crop_fn` palsu; tidak ada bukti dari run nyata yang terinterupsi.
- **"Grid ukur 1,057 m"** (RINGKASAN §4) — skrip pembuatnya tidak disertakan; ukuran saya dari band alpha: piksel 5,28 cm × 20 = 1,056 m (konsisten bila dimaksud langkah sampling). Luas berdata total saya 256,1 ha vs klaim 257,9 ha (selisih 0,7%, wajar karena ambang alpha) — batas presisi klaim, bukan temuan.
- **Rincian total 24,71 GB** — total benar (folder "AME III" = 24.708.559.348 B), tetapi rincian kurung RINGKASAN tidak menjumlah ke total karena `qa_overlay.png` E14/E15 (129.690.543 + 124.226.757 B ≈ 0,25 GB) tidak disebut; "per blok 2,75–3,14 GB" ternyata benar hanya untuk file data (total folder 2,92–3,34 GB). Nitpick dokumentasi, bukan kesalahan angka.
