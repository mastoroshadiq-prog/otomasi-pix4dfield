# Laporan Review Independen (Kedua) — Tool "Ekspor Blok Otomatis" (Pix4DField)

**Tanggal review:** 2026-10-14
**Reviewer:** Muse (independen; bukan implementer; bukan reviewer pertama)
**Bahan:** `paket_review_ekspor_blok_2026-10-14.zip` (36 berkas: kode, tes, spec, rencana, bukti teks, git log, hasil pytest) + `RINGKASAN_PROYEK_UNTUK_REVIEW.md` + `BRIEF.md` + `PANDUAN_REVIEW_AGENT_LAIN.md`
**Batasan bahan:** paket TIDAK memuat raster maupun `data/blok.geojson`/`data/kalibrasi.json` (koordinat blok disensor). Konsekuensinya: verifikasi angka geometri (K2, K4, K9) tidak dapat dihitung ulang; review ini bertumpu pada pembacaan kode, logika, tes, dan bukti teks. Tes tidak dijalankan ulang (dependensi rasterio dkk. tidak tersedia di lingkungan ini); klaim "40/40 lulus" diambil dari `BUKTI_tes_pytest.txt` apa adanya.
**Keterbukaan metode:** reviewer pertama (`LAPORAN_REVIEW_2026-10-14.md`) sudah kubaca sebelum paket ini datang, sehingga aturan "abaikan review lain agar tidak ter-anker" tidak dapat kupenuhi penuh. Sebagai gantinya: setiap temuan di bawah kuverifikasi ulang langsung ke kode di paket ini (jalur `path:baris` kuperiksa sendiri), dan §8 mencatat eksplisit mana yang konvergen, mana yang kupersempit, dan mana yang baru.

---

## 1. Ringkasan & Verdict

**Verdict: PERLU PERBAIKAN** — 0 KRITIS, 3 TINGGI, 3 SEDANG, 10 RENDAH.

Inti teknis tool ini benar dan dikerjakan dengan hati-hati: geometri crop (pad 1 px + `window_transform` + `geometry_mask` per chunk), kalibrasi affine PDF→UTM, keselamatan folder sumber, dan ketahanan runner semuanya *sound* secara logika kode. Tidak kutemukan bug yang merusak/menghilangkan data, tidak ada jalur tulis ke folder sumber, tidak ada otomasi GUI. Yang menahan status "siap produksi" sama seperti temuan reviewer pertama: tiga masalah operasional (estimasi disk, resume, logging retry) — ketiganya **kukonfirmasi independen dari kode**, dengan dua penguat tambahan (§3).

Perbedaan utama dari review pertama: (a) R-7 kupersempit — celah asersinya nyata tetapi dampak praktisnya jauh lebih kecil dari yang tertulis, karena cek konten `verify_gate2.py` berjangkar pada geometri; (b) R-1 dan R-8 **tidak dapat kuterima/ditolak** dari paket ini (bukti datanya tidak disertakan); (c) lima temuan RENDAH baru, satu di antaranya relevan untuk Gate 3 (pembengkakan `state.json`/`snapshot` oleh WKT geometri).

---

## 2. Kekuatan (terverifikasi dari kode, bukan dari klaim dokumen)

1. **Logika geometri crop benar.** `core/crop_engine.py:12-24`: `from_bounds` → `round_offsets/round_lengths` → pad 1 px → `intersection` dengan raster → `window_transform(win)` sebagai transform output. Ini pola yang tepat (bukan y-flip manual), dan `geometry_mask(..., invert=True)` per chunk di `crop_engine.py:40-43` memastikan piksel di luar poligon = nodata. Pembacaan windowed (`CHUNK_ROWS=2048`) membuat konsumsi memori aman untuk raster besar — klaim "aman memori" di RINGKASAN berdasar.
2. **Kalibrasi PDF metodologinya jujur.** `core/pdf_blok.py:56-106`: 16 titik kontrol dari perpotongan grid (4×4), *least squares*, residual dihitung terhadap titik yang sama (in-sample — sedikit optimistis, tetapi wajar untuk gate <3 m). Ambang `AMBANG_RESIDUAL_M = 3.0` eksplisit; kegagalan melempar `KalibrasiError` yang ditangkap UI (`app.py:44-45`).
3. **Repair sel cacat + tes regresi adalah praktik yang baik.** `pdf_blok.py:156-166` (`make_valid` → ambil Polygon terbesar) beserta `tests/test_pdf_blok_ekstraksi.py::test_sel_cacat_direparasi_bukan_dibuang` menunjukkan bug D14/D02/F33/F34 ditangani secara sistematis, bukan tambal sulam.
4. **Keselamatan data terstruktur benar.** Enumerasi jalur tulis: `crop_engine`/`palet`/`kartu`/`qa_overlay` hanya menulis ke `dst_*` (folder output), `folder_log`, `folder_palet`; `runner._tulis_state` atomik (`.tmp` + `replace`, `runner.py:61-67`); `errno 28` → stop + cancel (`runner.py:164-168`); cancel via `threading.Event` dicek antar-item (aman setelah item berjalan). Tidak ada `shutil.rmtree`/hapus di seluruh `core/`.
5. **Kontrak produk inti dipatuhi.** Bind `127.0.0.1` (`app.py:288`); tidak ada dependensi otomasi GUI (grep `pyautogui|pywinauto|win32com` nihil — satu-satunya hit "keyboard" adalah `KeyboardInterrupt`); guard path traversal `/api/kartu/file/<nama>` (`app.py:239-240`) + diuji (`test_app.py`).
6. **Kejujuran dokumen pelaksana meningkatkan kepercayaan.** `RINGKASAN.md` §3 mengakui perbandingan ekspor-manual cacat metodologi (akuisisi berbeda), §4 mengakui klaim "22 blok" SALAH dan mengoreksinya, §5 mengakui putaran 1 `verify_gate2.py` salah deteksi. Dokumen yang berani mengoreksi diri sendiri lebih dapat dipercaya daripada yang hanya memuji.
7. **Tes menguji perilaku nyata, bukan tautologi.** `test_crop_engine.py` membangun raster sintetis float32 dan mengasert dimensi/jendela/kompresi; `test_e2e_sintetis.py` menjalankan pipeline penuh (scan → rencana → runner → file output + CSV + state.json + overlay QA); `test_runner.py` memakai `crop_fn` palsu untuk mengisolasi logika resume/retry/cancel/disk-full. Ini unit test yang dirancang benar.

---

## 3. Temuan TINGGI (ketiganya kukonfirmasi independen dari kode)

### T-1. Estimasi disk pra-run salah basis — kontrol "disk cukup" tidak berfungsi (TERKONFIRMASI + penguat)

`app.py:72-75`:
```python
luas_semua = sum(f["properties"]["luas_ha"] for f in gj["features"]) or 1.0
luas_blok = sum(f["properties"]["luas_ha"] for f in blok)
ukuran_src = sum(Path(v["data"]).stat().st_size for v in hasil["layers"].values())
estimasi = int(ukuran_src * (luas_blok / luas_semua) * 0.6)
```
`luas_semua` adalah luas **seluruh fitur peta** (±7.225 ha), bukan luas wilayah berdata sumber (±258 ha). Rasio yang benar harusnya memakai luas footprint sumber. Faktor `0.6` ("konservatif vs rekompresi") arbitrer tanpa kalibrasi. Dampak: `if bebas < info["estimasi_byte"] * 1.2` (`app.py:159`) hampir selalu lolos.

**Dua penguat dari bahan ini:** (1) `run_gate2.py` menjalankan batch via `Runner` **langsung**, melewati `/api/jalankan` — artinya jalur pra-cek disk UI **tidak pernah** dieksekusi pada data nyata; bug ini lolos tanpa pernah diuji di jalur produksinya. (2) **Nol** tes menyentuh `/api/pindai` maupun `/api/jalankan` (`tests/test_app.py` hanya menguji halaman utama, config, status, unduh, kartu) — tidak ada jaring pengaman regresi untuk logika ini.

Usul: `estimasi = (byte_per_ha_terkalibrasi × luas_blok × margin)` dengan byte_per_ha diturunkan dari footprint aktual × byte/piksel sumber × faktor kompresi terukur Gate 2 — sebagai **rumus**, bukan konstanta hardcode (125 MB/ha spesifik GSD 5,28 cm & komposisi layer flight ini). Tambahkan tes unit untuk angka estimasi.

### T-2. Resume tanpa verifikasi — skenario pemicunya realistis, bukan teoretis (TERKONFIRMASI + penguat)

`core/runner.py:69-80`: kunci resume hanya `(kode, layer)`; tidak ada cek `kode_flight`, tidak ada cek path output, tidak ada cek keberadaan file. `state.json` tinggal di dalam folder output.

**Penguat:** alur UI membuat skenario pemicu menjadi *user error* yang wajar, bukan kasus buatan. Pengguna mengisi `folder_output` manual di Setup (mis. `..._auto` flight sebelumnya) lalu mengganti `kode_flight` — tidak ada satu baris kode pun yang memvalidasi folder output baru/berakhiran `_auto`/milik flight yang sama (`app.py:150-166`). Kontrak D3 ("arsip lama tidak pernah ditimpa") saat ini hanya dijaga oleh kedisiplinan pengguna. Akibatnya: seluruh item `(kode, layer)` yang sama ditandai `selesai` dari state lama dan **output flight baru hilang senyap** — tanpa pesan apa pun di UI.

Usul: (a) saat resume, verifikasi `dst_data`/`dst_rgb`/`dst_legend` ada (dan ukurannya cocok bila murah); yang hilang → `pending`; (b) simpan `kode_flight` + `output_root` di `state.json`, tolak resume bila berbeda; (c) validasi di `/api/jalankan`: folder output wajib kosong/baru atau berakhiran `_auto`; (d) uji skenario "ganti flight, folder sama".

### T-3. Bug logging pada `retry()` — mekanisme terkonfirmasi penuh dari kode (TERKONFIRMASI)

`core/runner.py:105-113`: `run()` membuat `log_path` baru setiap dipanggil, tetapi `FileHandler` baru hanya dipasang `if not self._logger.handlers`. `retry()` (`runner.py:93-102`) memanggil `start()` → `run()` pada **objek yang sama** → handler sudah ada → file log baru tidak pernah dibuat; semua baris run kedua masuk ke file log pertama; `/api/status` membaca `r.log_path` yang tidak ada → `log_tail = ""`; `/api/unduh/log` → 404. Handler lama juga tidak pernah ditutup (bocor; di Windows mengunci file).

**Penguat:** tidak ada satu pun tes yang memanggil `Runner.retry()` — `tests/test_runner.py` hanya menguji retry *otomatis di dalam loop* (`for percobaan in (1, 2)`), bukan retry via tombol UI. Jalur yang rusak adalah jalur yang tidak teruji.

Usul: tutup & lepas handler lama sebelum memasang FileHandler baru (atau logger unik per run); uji regresi: dua `run()` pada objek yang sama → file log kedua ada dan terisi.

---

## 4. Temuan SEDANG (ketiganya terkonfirmasi)

### S-1. Status `dilewati (tanpa data)` tidak pernah diproduksi (TERKONFIRMASI via grep)

`grep -rn '"dilewati"'` pada `core/`+`app.py`: satu-satunya *pembacaan* di `runner.py:78` (resume); **nol** penugasan status di seluruh kode produksi. (Kemunculan lain hanya di `kartu.py` — fitur kartu validasi yang berbeda.) Akar masalah terkonfirmasi di `layer_scan.py`: `blok_dalam_cakupan()` (`layer_scan.py:66-69`) hanya memfilter terhadap bounds **ortho**, sedangkan `rencana_output()` (`layer_scan.py:77-93`) membuat baris untuk **semua layer × semua blok** hasil filter ortho. Pada flight dengan layer ber-footprint lebih kecil (kasus umum: NDRE/DSM sebagian wilayah), blok di luar cakupan layer itu akan berakhir `gagal` (jendela kosong → error tulis raster 0×0) atau `selesai` dengan file seluruh-nodata (menyesatkan) — bukan `dilewati` seperti kontrak spec §5.4/§6. Tidak muncul di Gate 2 karena kelima layer menutupi 8 blok 100%.

Usul: uji irisan blok ∩ bounds **per layer** saat membangun rows → set `dilewati` (atau eksklusi bertanda di UI); tes unit dengan layer ber-footprint parsial; atau de-scope eksplisit di spec.

### S-2. Fallback GCP manual tidak diimplementasikan (TERKONFIRMASI)

Spec §5.1: "Fallback bila grid tidak terdeteksi: file GCP manual (3–4 pasangan titik PDF↔UTM)…". `core/pdf_blok.py` hanya memiliki jalur otomatis (`kalibrasi_pdf`, ambang `AMBANG_RESIDUAL_M = 3.0`); tidak ada parameter/berkas GCP manual di kode, CLI, maupun UI. Bila PDF baru gagal kalibrasi, tool berhenti tanpa jalur lanjut internal. Ini celah kontrak/kontingensi, bukan bug hasil.

Usul: dukung `data/gcp_manual.json` opsional (bangun affine + validasi residual), atau tandai de-scope eksplisit di spec + RINGKASAN.

### S-3. Bukti gate tidak ter-commit (TERKONFIRMASI via dokumen rencana)

`.gitignore` tidak disertakan dalam paket ZIP sehingga tidak dapat kuperiksa langsung; namun `docs/superpowers/plans/.../2026-10-13-ekspor-blok-otomatis-implementasi.md` (Task 1, Step 1) menetapkan isi `.gitignore` mencakup `logs/` dan `laporan/`. Akibatnya seluruh bukti Gate 1/2 hanya ada di working tree mesin pembuat — klaim tidak dapat direproduksi dari clone. Usul: whitelist artefak kunci (`laporan/_uji_d17/RINGKASAN.md`, `verify_gate2.py`, `gate2_verifikasi.json`, `run_gate2.py`) atau pindahkan ke `tests/artifacts/`. Catatan tambahan: aturan brief yang menempatkan laporan reviewer di `laporan/reviewer/` bertabrakan dengan ignore ini — whitelist `laporan/reviewer/` juga.

---

## 5. Temuan RENDAH

**R-2. Footer kartu validasi di-hardcode (TERKONFIRMASI).** `core/kartu.py` (±baris 173): `"konteks: residual kalibrasi PDF 0,49 m; GSD 5,28 cm/px; …"` — nilai spesifik flight uji; pada flight lain keterangan kartu salah. Usul: parameterisasi dari `data/kalibrasi.json` + `abs(transform.a)` ortho.

**R-3. `innerHTML` dengan data server (TERKONFIRMASI).** `static/app.js:31` (`${b.kode}`, `${b.divisi}`) dan `app.js:69-70` (`${it.kode}`, `${it.error}` — pesan error rasterio dapat memuat path/nama file eksternal). Risiko rendah (localhost, data milik pengguna sendiri/self-XSS), tetapi murah diperbaiki via `textContent`/escape.

**R-4. Race `/api/jalankan` (TERKONFIRMASI).** `app.py:150-166`: cek `snapshot()["aktif"]` → `_bangun_rows()` (tidak instan) → timpa `RUNNER["obj"]` tanpa kunci; Flask threaded → dua POST beruntun dapat lolos keduanya. Usul: `threading.Lock` atau tandai status sebelum membangun rows.

**R-5. `_port_bebas` mengembalikan 0 (TERKONFIRMASI).** `app.py:17-22`: bila 5000–5049 penuh → `port=0` → Flask bind acak tetapi `webbrowser.open("http://127.0.0.1:0")` membuka URL salah. Usul: kembalikan `None` → pesan gagal yang jelas.

**R-6. Daftar blok respons pindai dipotong 500 (TERKONFIRMASI).** `app.py:147` (`info["blok"][:500]`) — tampilan vs eksekusi dapat berbeda pada peta >500 blok. Usul: paginasi atau hilangkan potongan.

**R-7. Blind-spot `verify_gate2.py` — DIPERSEMPIT.** Klaim reviewer pertama benar secara teknis: `verify_gate2.py:36-37` hanya meng-assert `(crs, transform.a, transform.e)` — bukan origin (`c`, `f`). Namun dampak praktisnya **jauh lebih kecil** dari yang tersirat: `cek_data` membandingkan konten piksel memakai `geometry_mask` yang berjangkar pada **geometri asli** (`g`, independen dari `dd.transform`). Pergeseran output sebesar bilangan bulat piksel akan membuat maska vs konten tidak selaras → `max_diff > 0` (kecuali raster lokal konstan). Yang benar-benar bisa lolos hanyalah kasus degeneratif. Tetap layak ditambahkan assert origin/CRS penuh sebagai higiene verifikasi — tetapi ini bukan lubang yang berarti.

**R-1 & R-8. TIDAK DAPAT DIVERIFIKASI dari paket ini.** R-1 (artefak gate1 basi: `n_berlabel` 455 vs 459) dan R-8 (NIR ≡ RedEdge bitwise) keduanya membutuhkan berkas data yang disensor dari paket. Tidak kutolak, tidak kukonfirmasi — butuh akses mesin.

**N-1 (BARU). Pembengkakan `snapshot()`/`state.json` oleh WKT geometri — relevan untuk Gate 3.** `runner.snapshot()` (`runner.py:48-56`) mengembalikan `asdict(it)` **termasuk `geom` WKT** per item, dan `app.js polling()` tidak pernah memakai `it.geom` — setiap poll 1 detik mengirim ribuan string WKT sia-sia. Lebih berat: `state.json` menyimpan `geom` **per item** (5× duplikat per blok, satu per layer) dan `_tulis_state()` menulis ulang seluruh berkas **setelah setiap item**. Pada flight penuh (ratusan blok × 5 layer), ini menjadi I/O JSON puluhan MB yang diulang ratusan kali + respons `/api/status` multi-MB per detik. Pada 40 item Gate 2 tidak terasa; pada Gate 3 akan terasa. Usul: keluarkan `geom` dari `snapshot()`; di `state.json` simpan geometri sekali per kode blok (perhatikan: `verify_gate2.py` membaca `it["geom"]` dari state — jaga kompatibilitas atau sesuaikan skrip).

**N-2 (BARU). `crop_layer` mengompresi `.data.tif` uint8 dengan JPEG (lossy).** `crop_engine.py:28-31`: `float32 → DEFLATE+predictor`, else → `JPEG Q85` — berlaku untuk **data**, bukan hanya rgb. Praktiknya sumber selalu float32 sehingga belum menggigit, tetapi tidak ada penjaga: satu layer sumber uint8 akan terkompresi lossy secara diam-diam. Usul: paksa DEFLATE untuk seluruh `.data.tif` (atau tolak dengan pesan jelas).

**N-3 (BARU). Overview memakai `Resampling.average` tanpa maska nodata.** `crop_engine.py:47-49` (dan `_render_uint8`): piksel tepi overview merata-ratakan nodata (−10000) ke dalam — artefak tampilan pada overview saja, bukan data. Sekali jalan: teruskan `overview_resampling` yang sadar-nodata atau terima sebagai keterbatasan tampilan.

**N-4 (BARU). `requirements.txt` tidak di-pin.** `flask>=3.1`, `rasterio>=1.5`, dst. — pembuatan ulang venv di mesin lain (mis. laptop lapangan) dapat menarik versi berbeda. Murah: `pip freeze > requirements.txt` dari venv teruji.

**N-5 (BARU). Konfigurasi `workers` mati.** `core/config.py:14` menerima `workers`, `Runner.__init__` menerimanya, tetapi tidak pernah dipakai (single-thread). Opsi yang tidak berfungsi sebaiknya dihapus atau diimplementasikan, agar tidak menyesatkan.

---

## 6. Kesesuaian kontrak spec (sudut A, ringkas)

| Kontrak spec | Status |
|---|---|
| D1 tanpa otomasi GUI | ✓ terpenuhi (grep bersih) |
| D2 web lokal 127.0.0.1 | ✓ (`app.py:288`) |
| D3 folder BARU `..._auto`, arsip tak tersentuh | △ hanya konvensi; tanpa validasi kode (lihat T-2) |
| D4 UI Indonesia | ✓ |
| §5.1 kalibrasi + fallback GCP manual | △ kalibrasi ✓; fallback ✗ (S-2) |
| §5.3/§5.4 crop windowed, kompresi per tipe | ✓ |
| §5.4 status `dilewati (tanpa data)` | ✗ (S-1) |
| §5.4 resume/retry-1×/cancel/CSV/log | ✓ dengan catatan T-2, T-3 |
| §6 penamaan output | ✓ sesuai pola |
| §7 pra-jalan: kalibrasi lolos, file lengkap, **disk cukup** | △ dua pertama ✓; disk ✗ efektif (T-1) |
| Non-goals (tanpa otomasi GUI, tanpa timpa arsip) | ✓ |

---

## 7. Rekomendasi (berurutan)

1. **Sebelum flight berikutnya (Gate 3):** perbaiki T-1 (rumus estimasi, bukan konstanta) dan T-2 (verifikasi resume + validasi folder `_auto`). Keduanya menyentuh keselamatan operasional pada skala besar.
2. **Segera setelahnya:** T-3 (perbaikan FileHandler + uji regresi `retry()`), dan N-1 (rampingkan `snapshot`/`state.json` — hambatan Gate 3 yang nyata).
3. **Keputusan produk:** S-1 dan S-2 — implementasi atau de-scope eksplisit di spec. Jangan biarkan kontrak berbohong.
4. **Auditabilitas:** S-3 — whitelist artefak gate + `laporan/reviewer/`.
5. **Cepat & murah:** N-2 (paksa DEFLATE untuk data), N-4 (pin requirements), N-5 (hapus/implementasikan `workers`), R-2 s.d. R-6, R-7 (assert origin di skrip verifikasi).
6. **Tes yang hilang (prioritas):** `retry()` UI, `/api/pindai` + `/api/jalankan` (termasuk angka estimasi), skenario "ganti flight folder sama", layer ber-footprint parsial → `dilewati`.

---

## 8. Catatan konvergensi vs review pertama

| Temuan | Status verifikasiku |
|---|---|
| T-1, T-2, T-3 (TINGGI) | Konvergen penuh — terkonfirmasi dari kode, masing-masing dengan penguat tambahan |
| S-1, S-2, S-3 (SEDANG) | Konvergen (S-3 via dokumen rencana, karena `.gitignore` tak ada di paket) |
| R-2, R-3, R-4, R-5, R-6 | Konvergen |
| R-7 | Konvergen sebagian — celah asersi nyata, tetapi dampak praktis dipersempit (maska geometri menangkap pergeseran) |
| R-1, R-8 | Tidak dapat diverifikasi dari paket ini (data disensor) |
| Baru: N-1 s.d. N-5 | Lima temuan RENDAH tambahan dari pembacaan mandiri |

**Penilaian akhir: PERLU PERBAIKAN.** Tidak ada temuan kritis; tidak ada kehilangan/korupsi data; tidak ada klaim gate yang palsu. Perbaikan bersifat terfokus dan terlokalisasi. Dengan T-1/T-2/T-3 dan N-1 diperbaiki, tool layak lanjut ke Gate 3.

## 9. Cakupan "diperiksa & lolos"

- Seluruh `core/*.py` (8 modul), `app.py`, `static/app.js`, `templates/index.html` (skim), `requirements.txt`, `jalankan.bat` — dibaca penuh.
- Seluruh `tests/` (11 berkas) — dibaca; dinilai menguji perilaku nyata dengan celah terdokumentasi di §7-rekomendasi-6.
- `docs/superpowers/specs` + `plans` (bagian relevan), `README.md`, `laporan/_uji_d17/RINGKASAN.md`, `verify_gate2.py`, `run_gate2.py`, `gate2_verifikasi.json` (struktur), `BUKTI_git_log.txt`, `BUKTI_tes_pytest.txt` — dibaca.
- **Tidak diperiksa** (di luar bahan): angka geometri K2/K4/K9 (butuh raster + geojson), kualitas visual palet/kartu, perilaku UI nyata di browser, `data/blok.geojson`/`kalibrasi.json`.
