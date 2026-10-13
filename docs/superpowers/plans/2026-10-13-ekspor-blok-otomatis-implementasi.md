# Rencana Implementasi — Tool "Ekspor Blok Otomatis" Pix4DField

> **Untuk agen pelaksana:** SUB-SKILL WAJIB: gunakan `superpowers:executing-plans` (atau `superpowers:subagent-driven-development`) untuk mengeksekusi rencana ini tugas-per-tugas. Langkah memakai checkbox (`- [ ]`).

**Goal:** Tool lokal (Flask + rasterio) yang meng-crop layer full-extent hasil ekspor Pix4DField per blok menggunakan peta blok PDF, dengan UI progres/error/log berbahasa Indonesia, menulis ke folder output BARU terkompresi.

**Architecture:** Pipeline 3 tahap di UI (Setup → Pindai/dry-run → Jalankan). Geometri blok dari PDF via kalibrasi affine (sudah terverifikasi: residual maks 0,67 m). Crop per blok × layer via rasterio (windowed + per-strip), render `.rgb.tif` dari palet hasil sampling referensi, legend digenerate. Orkestrasi batch dengan state.json (resume), retry 1×, cancel aman, CSV + log.

**Tech Stack:** Python 3.14.6 (venv `.venv` di root proyek) — rasterio 1.5.2 (GDAL ter-bundel; CLI GDAL tidak tersedia), PyMuPDF 1.28.2, Flask 3.1.3, Pillow, numpy 2.5, shapely 2.2, pyshp 3.1, tifffile, pytest.

**Spec:** `docs/superpowers/specs/2026-10-13-ekspor-blok-otomatis-design.md`

## Batasan Global (dari spec — berlaku untuk semua task)

- Output HANYA ke folder BARU `F:\dataset\Pix4DField-export-<FLGxx>_auto\`; tidak pernah menulis/menimpa arsip lama.
- CRS kerja: EPSG:32749 (WGS 84 / UTM 49S). Semua geometri & raster internal di CRS ini.
- Bahasa UI & dokumen: Indonesia. Nama variabel/fungsi: bebas (disarankan Indonesia untuk domain).
- Nama folder blok: `<FLGxx>_<DIVISI tanpa spasi>-<BLOK>` (contoh `FLG03_AMEII-D01`); folder divisi tetap berspasi (`AME II`).
- Set file per blok (spec §6): Orthomosaic → `.data.tif` + `.rgb.tif`; NDRE/NIR/RedEdge/Surface model → `.data.tif` + `.rgb.tif` + `.legend.png`.
- Kalibrasi PDF lolos jika residual < 3 m (terukur 0,666 m pada PDF contoh — 16 titik kontrol).
- Semua operasi raster via rasterio API; GTiff `TILED=YES`, blok 256, `BIGTIFF=YES`; float32 → `DEFLATE + PREDICTOR=3` (LERC diuji di Gate 2); rgb uint8 → `JPEG kualitas 85` + overviews.
- Interpretasi peta PDF = sumber kebenaran geometri blok; `2_Tanam_Inti.shp` hanya lookup divisi; `bdr_*.zip` alat validasi.
- Tes dijalankan: `cd /d/pix4dfield_exporting_tools && .venv/Scripts/python.exe -m pytest tests/ -q`.
- Jangan jalankan GUI Pix4DField; jangan otomasi klik.

## Struktur File & Tanggung Jawab

```
D:\pix4dfield_exporting_tools\
  app.py                    # entry Flask + auto-port + auto-buka browser
  jalankan.bat              # double-click untuk mulai
  requirements.txt
  core/
    __init__.py
    config.py               # AppConfig (JSON) + path default proyek
    pdf_blok.py             # kalibrasi affine + ekstraksi poligon blok + geojson + CLI __main__
    layer_scan.py           # klasifikasi layer sumber + filter blok dalam cakupan + rencana output
    palet.py                # sampling palet dari (data,rgb) referensi + apply + legend PNG + ramp bawaan
    crop_engine.py          # crop per blok (strip-wise) + proses_baris (data+rgb+legend)
    runner.py               # orkestrasi batch: state/resume/retry/cancel, CSV, log
    qa_overlay.py           # render PNG overlay (peta PDF & blok hasil crop)
  templates/index.html      # UI satu halaman, 3 tahap
  static/style.css
  static/app.js
  data/
    sumber/peta_blok.pdf    # salinan peta (fixture tes & default)
    config.json             # (generated)
    kalibrasi.json          # (generated)
    blok.geojson            # (generated)
    palet/ndre.json         # (generated dari referensi — Gate 2)
    palet/bawaan.json       # ramp fallback NIR/RedEdge/DSM (di-commit)
  logs/                     # run_<ts>.log (generated)
  laporan/                  # artefak gate (generated)
  tests/
```

## Konstanta Terverifikasi (PDF contoh — dipakai di kode & tes)

| Konstanta | Nilai |
|---|---|
| Halaman | 5669,26 × 4251,74 pt (1 halaman) |
| Area peta (grid) | x ∈ [913,20 … 4174,46], y ∈ [705,83 … 3945,43] pt |
| Garis grid H (y pt) | 705,83 / 1785,70 / 2865,57 / 3945,43 |
| Garis grid V (x pt) | 913,20 / 2000,29 / 3087,37 / 4174,46 |
| Label | lat 0°24'0"S … 0°34'30"S; lon 109°13'0"E … 109°23'30"E; 16 label DMS (8 lat + 8 lon) |
| Affine (dari prototipe) | E = 5,973385·x + 0,001505·y + 296076,3575 ; N = 0,001505·x − 5,973348·y + 9959980,7236 |
| Residual | maks 0,666 m; rata-rata 0,293 m |
| Skala / rotasi | 5,973 m/pt; 0,014° |
| path PDF | 56.703 drawing; 2.520 poligon >3 item; tipe item `l` + `qu`; swatch legenda besar-item di x≈4888–5027 (dikecualikan filter area) |

---

### Task 1: Kerangka proyek + konfigurasi

**Files:**
- Create: `core/__init__.py` (kosong), `core/config.py`, `tests/__init__.py` (kosong), `tests/test_config.py`, `requirements.txt`, `.gitignore`
- Create: `data/sumber/peta_blok.pdf` (salin dari `C:\Users\IKINAI\Downloads\Peta Informasi Tanam Tahun Inti (1).pdf`)

**Interfaces:**
- Produces: `core.config.ROOT: Path`; `AppConfig` (dataclass) dengan field: `folder_sumber, folder_output, pdf_peta, kode_flight, workers, port, path_kalibrasi, path_blok, folder_palet, folder_log` (semua `str`, `workers: int = 1`, `port: int = 0`); `load_config(path=None) -> AppConfig`; `save_config(cfg, path=None) -> None`.

- [ ] **Step 1: Salin PDF + buat .gitignore & requirements.txt**

```bash
cd /d/pix4dfield_exporting_tools && mkdir -p data/sumber core tests templates static data/palet logs laporan
cp "/c/Users/IKINAI/Downloads/Peta Informasi Tanam Tahun Inti (1).pdf" data/sumber/peta_blok.pdf
```

`.gitignore`:
```
.venv/
__pycache__/
*.pyc
logs/
laporan/
data/config.json
data/kalibrasi.json
data/blok.geojson
data/qa_pdf_blok.json
data/qa_overlay_peta.png
data/palet/*.json
!data/palet/bawaan.json
```

`requirements.txt`:
```
flask>=3.1
rasterio>=1.5
pymupdf>=1.28
pillow>=12
numpy>=2.5
shapely>=2.2
pyshp>=3.1
tifffile>=2026
pytest>=8
```

- [ ] **Step 2: Tulis tes gagal `tests/test_config.py`**

```python
from core.config import AppConfig, load_config, save_config

def test_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = AppConfig(folder_sumber="F:/sumber", folder_output="F:/keluar", kode_flight="FLG03")
    save_config(cfg, p)
    assert load_config(p) == cfg

def test_missing_file_kembali_default(tmp_path):
    cfg = load_config(tmp_path / "belum_ada.json")
    assert cfg.kode_flight == ""
    assert cfg.pdf_peta.endswith("peta_blok.pdf")
    assert cfg.workers == 1

def test_abaikan_field_asing(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"kode_flight": "FLG09", "field_asing": 1}', encoding="utf-8")
    assert load_config(p).kode_flight == "FLG09"
```

- [ ] **Step 3: Jalankan tes — harus GAGAL**

Run: `.venv/Scripts/python.exe -m pytest tests/test_config.py -q` → Expected: FAIL (`ModuleNotFoundError: core.config`).

- [ ] **Step 4: Implementasi `core/config.py`**

```python
import json
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

@dataclass
class AppConfig:
    folder_sumber: str = ""
    folder_output: str = ""
    pdf_peta: str = str(ROOT / "data" / "sumber" / "peta_blok.pdf")
    kode_flight: str = ""
    workers: int = 1
    port: int = 0
    path_kalibrasi: str = str(ROOT / "data" / "kalibrasi.json")
    path_blok: str = str(ROOT / "data" / "blok.geojson")
    folder_palet: str = str(ROOT / "data" / "palet")
    folder_log: str = str(ROOT / "logs")

def _path(path) -> Path:
    return Path(path) if path else ROOT / "data" / "config.json"

def load_config(path=None) -> AppConfig:
    p = _path(path)
    if not p.exists():
        return AppConfig()
    data = json.loads(p.read_text(encoding="utf-8"))
    return AppConfig(**{k: v for k, v in data.items() if k in AppConfig.__dataclass_fields__})

def save_config(cfg: AppConfig, path=None) -> None:
    p = _path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 5: Jalankan tes — harus LULUS** (perintah Step 3, expected PASS 3 items)

- [ ] **Step 6: Commit**

```bash
git add .gitignore requirements.txt core/ tests/ data/sumber/peta_blok.pdf
git commit -m "feat(core): kerangka proyek + konfigurasi + fixture peta PDF"
```

---

### Task 2: Kalibrasi PDF → affine pt→UTM

**Files:**
- Create: `core/pdf_blok.py` (bagian kalibrasi), `tests/test_pdf_blok_kalibrasi.py`

**Interfaces:**
- Produces: `KalibrasiError`; `lonlat_to_utm(lon, lat, zone=49) -> (E, N)`; `kalibrasi_pdf(pdf_path) -> dict` dengan kunci: `ok: bool`, `affine_E: [a,b,c]`, `affine_N: [a,b,c]`, `titik_kontrol: int`, `residual_max_m: float`, `residual_mean_m: float`, `skala_m_per_pt: float`, `rotasi_deg: float`, `grid: {"y": [...], "x": [...]}`, `sumber: {"pdf": str, "ukuran": int, "mtime": float}`; `pdf_to_utm(kal, x, y) -> (E, N)`; `simpan_kalibrasi(kal, path)`; `muat_kalibrasi(path)`.

- [ ] **Step 1: Tulis tes gagal dengan angka acuan terverifikasi**

```python
import math
import pytest
from pathlib import Path
from core import pdf_blok

PDF = Path(__file__).resolve().parent.parent / "data" / "sumber" / "peta_blok.pdf"

@pytest.fixture(scope="module")
def kal():
    return pdf_blok.kalibrasi_pdf(PDF)

def test_lolos_gate(kal):
    assert kal["ok"] is True
    assert kal["residual_max_m"] < 1.0        # gate sesungguhnya 3 m

def test_titik_kontrol(kal):
    assert kal["titik_kontrol"] == 16

def test_skala_dan_rotasi(kal):
    assert abs(kal["skala_m_per_pt"] - 5.973) < 0.05
    assert abs(kal["rotasi_deg"]) < 0.1

def test_transform_titik_potong_grid(kal):
    E, N = pdf_blok.pdf_to_utm(kal, 913.2, 705.83)
    E0, N0 = pdf_blok.lonlat_to_utm(109.216667, -0.400000)
    assert math.hypot(E - E0, N - N0) < 1.5   # toleransi 1,5 m

def test_simpan_muat(tmp_path, kal):
    p = tmp_path / "kalibrasi.json"
    pdf_blok.simpan_kalibrasi(kal, p)
    assert pdf_blok.muat_kalibrasi(p)["residual_max_m"] == kal["residual_max_m"]
```

- [ ] **Step 2: Jalankan — harus GAGAL** (`AttributeError`/`ModuleNotFoundError`)

- [ ] **Step 3: Implementasi (port dari prototipe tervalidasi di `C:\Users\IKINAI\AppData\Local\Temp\pdf_calib_proto.py`)**

Inti yang WAJIB ada di `core/pdf_blok.py`:

```python
import json, math, re
from pathlib import Path
import numpy as np
import pymupdf

DMS_RE = re.compile(r'^(\d+)°(\d+)\'([\d.]+)"([NSEW])$')
AMBANG_RESIDUAL_M = 3.0

class KalibrasiError(Exception):
    pass

def lonlat_to_utm(lon, lat, zone=49):
    """WGS84 → UTM (formula seri standar; akurasi mm). 49S: lat<0 → +10.000.000."""
    a = 6378137.0; f = 1 / 298.257223563
    e2 = f * (2 - f); ep2 = e2 / (1 - e2); k0 = 0.9996
    lon0 = math.radians(zone * 6 - 183)
    phi = math.radians(lat); lam = math.radians(lon)
    N = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    T = math.tan(phi) ** 2
    C = ep2 * math.cos(phi) ** 2
    A = math.cos(phi) * (lam - lon0)
    M = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi
             - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * phi)
             + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * phi)
             - (35 * e2 ** 3 / 3072) * math.sin(6 * phi))
    E = k0 * N * (A + (1 - T + C) * A ** 3 / 6
                  + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5 / 120) + 500000
    Nn = k0 * (M + N * math.tan(phi) * (A * A / 2
              + (5 - T + 9 * C + 4 * C * C) * A ** 4 / 24
              + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6 / 720))
    if lat < 0:
        Nn += 10000000
    return E, Nn

def _label_dms(page):
    """-> (list lat [(val, cx, cy)], list lon [(val, cx, cy)])."""
    lat, lon = [], []
    for w in page.get_text("words"):
        m = DMS_RE.match(w[4].strip())
        if not m:
            continue
        v = int(m[1]) + int(m[2]) / 60 + float(m[3]) / 3600
        if m[4] in "SW":
            v = -v
        item = (v, (w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
        (lat if m[4] in "NS" else lon).append(item)
    return lat, lon

def _cluster(vals, tol=2.0):
    """Gabung nilai berdekatan; -> list posisi tengah cluster."""
    out = []
    for v in sorted(vals):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]

def _garis_grid(page):
    """Deteksi garis grid panjang; -> (y_clusters, x_clusters) dalam pt."""
    pw, ph = page.rect.width, page.rect.height
    ys, xs = [], []
    for d in page.get_drawings():
        r = d["rect"]
        if r.width > 0.5 * pw and r.height < 3:
            ys.append((r.y0 + r.y1) / 2)
        elif r.height > 0.5 * ph and r.width < 3:
            xs.append((r.x0 + r.x1) / 2)
    return _cluster(ys), _cluster(xs)

def _fit_affine(pt):
    """pt: list (x, y, E, N) -> (affine_E, affine_N) via least squares."""
    A = np.array([[p[0], p[1], 1.0] for p in pt])
    coefE, *_ = np.linalg.lstsq(A, np.array([p[2] for p in pt]), rcond=None)
    coefN, *_ = np.linalg.lstsq(A, np.array([p[3] for p in pt]), rcond=None)
    return coefE.tolist(), coefN.tolist()

def kalibrasi_pdf(pdf_path) -> dict:
    doc = pymupdf.open(str(pdf_path))
    page = doc[0]
    lat, lon = _label_dms(page)
    y_cls, x_cls = _garis_grid(page)
    if len(lat) < 4 or len(lon) < 4 or len(y_cls) < 2 or len(x_cls) < 2:
        raise KalibrasiError(f"Grid/label tidak cukup: lat={len(lat)} lon={len(lon)} Y={len(y_cls)} X={len(x_cls)}")
    # petakan tiap nilai unik label → posisi garis terdekat
    def match(pairs, axis_val):
        hasil = {}
        for val, cx, cy in pairs:
            pos = cx if axis_val else cy
            cls = x_cls if axis_val else y_cls
            nearest = min(cls, key=lambda c: abs(c - pos))
            if abs(nearest - pos) > 30:
                raise KalibrasiError(f"Label di {pos:.1f} tidak menemukan garis grid (selisih > 30 pt)")
            hasil[val] = nearest
        return hasil
    map_lat = match(lat, False)   # nilai lat → y garis
    map_lon = match(lon, True)    # nilai lon → x garis
    pt = []
    for latv, y in map_lat.items():
        for lonv, x in map_lon.items():
            E, N = lonlat_to_utm(lonv, latv)
            pt.append((x, y, E, N))
    affine_E, affine_N = _fit_affine(pt)
    res = [math.hypot(affine_E[0] * x + affine_E[1] * y + affine_E[2] - E,
                      affine_N[0] * x + affine_N[1] * y + affine_N[2] - N)
           for x, y, E, N in pt]
    kal = {
        "ok": max(res) < AMBANG_RESIDUAL_M,
        "affine_E": affine_E, "affine_N": affine_N,
        "titik_kontrol": len(pt),
        "residual_max_m": max(res), "residual_mean_m": sum(res) / len(res),
        "skala_m_per_pt": math.hypot(affine_E[0], affine_N[0]),
        "rotasi_deg": math.degrees(math.atan2(affine_N[0], affine_E[0])),
        "grid": {"y": y_cls, "x": x_cls},
        "sumber": {"pdf": str(pdf_path), "ukuran": Path(pdf_path).stat().st_size,
                   "mtime": Path(pdf_path).stat().st_mtime},
    }
    return kal

def pdf_to_utm(kal, x, y):
    return (kal["affine_E"][0] * x + kal["affine_E"][1] * y + kal["affine_E"][2],
            kal["affine_N"][0] * x + kal["affine_N"][1] * y + kal["affine_N"][2])

def simpan_kalibrasi(kal, path):
    Path(path).write_text(json.dumps(kal, indent=2, ensure_ascii=False), encoding="utf-8")

def muat_kalibrasi(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
```

- [ ] **Step 4: Jalankan tes — harus LULUS** (5 items)

- [ ] **Step 5: Commit** — `git add core/pdf_blok.py tests/test_pdf_blok_kalibrasi.py && git commit -m "feat(pdf_blok): kalibrasi affine PDF→UTM 49S (residual maks 0,67 m)"`

---

### Task 3: Ekstraksi poligon blok + label + blok.geojson + overlay peta

**Files:**
- Modify: `core/pdf_blok.py` (tambah fungsi ekstraksi + `__main__`)
- Create: `core/qa_overlay.py` (bagian `render_pdf_overlay`), `tests/test_pdf_blok_ekstraksi.py`

**Interfaces:**
- Consumes: `kalibrasi_pdf`, `pdf_to_utm` (Task 2).
- Produces: `KODE_RE`; `KATA_BUKAN_BLOK: set[str]`; `_poligon_dari_drawing(d) -> list[tuple] | None`; `ekstrak_blok(pdf_path, kal, out_geojson, out_qa_json, out_overlay_png, shp_path=None) -> dict` (kembalian = isi QA json); `muat_lookup_shp(shp_path) -> dict[str, str]` (kode_norm → divisi); `core.qa_overlay.render_pdf_overlay(pdf_path, features_pt, out_png) -> None`.

- [ ] **Step 1: Tulis tes gagal `tests/test_pdf_blok_ekstraksi.py`**

```python
import json
import pytest
from pathlib import Path
from core import pdf_blok

PDF = Path(__file__).resolve().parent.parent / "data" / "sumber" / "peta_blok.pdf"
SHP = Path(r"E:\2. Tanam Inti\2_Tanam_Inti.shp")

@pytest.fixture(scope="module")
def hasil(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("blok")
    kal = pdf_blok.kalibrasi_pdf(PDF)
    qa = pdf_blok.ekstrak_blok(PDF, kal, tmp / "blok.geojson", tmp / "qa.json", tmp / "peta.png")
    return tmp, qa

def test_jumlah_blok_berlabel(hasil):
    _, qa = hasil
    assert 300 <= qa["n_berlabel"] <= 900

def test_kode_tertentu_ada(hasil):
    _, qa = hasil
    assert "C04A" in qa["kode_berlabel"]

def test_geojson_valid_dan_berisi_divisi(hasil):
    tmp, qa = hasil
    gj = json.loads((tmp / "blok.geojson").read_text(encoding="utf-8"))
    assert len(gj["features"]) == qa["n_berlabel"]
    assert sum(1 for f in gj["features"] if f["properties"].get("divisi")) > 0

def test_file_output_ada(hasil):
    tmp, _ = hasil
    assert (tmp / "peta.png").stat().st_size > 10_000

def test_lookup_shp():
    if not SHP.exists():
        pytest.skip("shp tidak ada")
    lookup = pdf_blok.muat_lookup_shp(SHP)
    assert len(lookup) > 500
```

- [ ] **Step 2: Jalankan — GAGAL** (fungsi belum ada)

- [ ] **Step 3: Implementasi ekstraksi di `core/pdf_blok.py`**

```python
KODE_RE = re.compile(r'^[A-Za-z]{1,4}-?\d{1,2}[A-Za-z]?\d{0,2}[A-Za-z]?$')
KATA_BUKAN_BLOK = {"BLOCK", "BATAS", "HA", "LUAS", "SUMATERA", "KALIMANTAN", "BARAT", "TIMUR",
                   "PETA", "INFORMASI", "TANAM", "INTI", "TAHUN", "LEGENDA", "SKALA"}

def _poligon_dari_drawing(d):
    """Rantai item 'l'/'qu' → daftar titik; None bila bukan satu poligon tertutup."""
    pts = []
    for it in d["items"]:
        if it[0] == "l":
            p1, p2 = it[1], it[2]
            if not pts:
                pts.append((p1.x, p1.y))
            elif abs(pts[-1][0] - p1.x) > 0.5 or abs(pts[-1][1] - p1.y) > 0.5:
                return None  # banyak sub-path terpisah
            pts.append((p2.x, p2.y))
        elif it[0] == "qu":
            q = it[1]
            quad = [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]
            if pts and (abs(pts[-1][0] - quad[0][0]) > 0.5 or abs(pts[-1][1] - quad[0][1]) > 0.5):
                return None
            pts.extend(quad)
        else:
            return None
    if len(pts) < 4:
        return None
    return pts

def _tertutup(pts, tol=1.0):
    return math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) <= tol

def ekstrak_blok(pdf_path, kal, out_geojson, out_qa_json, out_overlay_png, shp_path=None):
    from shapely.geometry import Polygon, Point
    doc = pymupdf.open(str(pdf_path))
    page = doc[0]
    # kata kode blok
    kata = []
    for w in page.get_text("words"):
        s = w[4].strip()
        if KODE_RE.match(s) and s.upper() not in KATA_BUKAN_BLOK and not s.isdigit():
            kata.append((s.upper(), (w[0] + w[2]) / 2, (w[1] + w[3]) / 2))
    x_min, x_max = kal["grid"]["x"][0], kal["grid"]["x"][-1]
    y_min, y_max = kal["grid"]["y"][0], kal["grid"]["y"][-1]
    lookup = muat_lookup_shp(shp_path) if shp_path and Path(shp_path).exists() else {}
    fitur, dipakai, fitur_pt = [], set(), []
    n_kandidat = 0
    for d in page.get_drawings():
        pts = _poligon_dari_drawing(d)
        if not pts:
            continue
        n_kandidat += 1
        if d.get("fill") is None and not _tertutup(pts):
            continue
        cx0 = sum(p[0] for p in pts[:-1]) / (len(pts) - 1)
        cy0 = sum(p[1] for p in pts[:-1]) / (len(pts) - 1)
        if not (x_min - 5 <= cx0 <= x_max + 5 and y_min - 5 <= cy0 <= y_max + 5):
            continue  # legenda / luar area peta
        poly_pt = Polygon(pts)
        if not poly_pt.is_valid or poly_pt.area <= 0:
            continue
        poly_utm = Polygon([pdf_to_utm(kal, x, y) for x, y in pts])
        luas_ha = poly_utm.area / 10000.0
        if not (0.2 <= luas_ha <= 400):
            continue
        # tautkan label: di dalam poligon dulu, lalu terdekat ≤ 60 pt
        kode, idx = None, None
        for i, (s, lx, ly) in enumerate(kata):
            if i in dipakai:
                continue
            if poly_pt.contains(Point(lx, ly)):
                kode, idx = s, i
                break
        if kode is None:
            best = None
            for i, (s, lx, ly) in enumerate(kata):
                if i in dipakai:
                    continue
                dist = abs(lx - cx0) + abs(ly - cy0)
                if dist < 60 and (best is None or dist < best):
                    best, idx = dist, i
            if idx is not None:
                kode = kata[idx][0]
        if kode is None:
            continue
        dipakai.add(idx)
        koord = [[round(x, 2), round(y, 2)] for x, y in poly_utm.exterior.coords]
        fitur.append({"type": "Feature",
                      "properties": {"kode": kode, "divisi": lookup.get(kode, ""),
                                     "luas_ha": round(luas_ha, 3), "sumber": "pdf"},
                      "geometry": {"type": "Polygon", "coordinates": [koord]}})
        fitur_pt.append((poly_pt, kode))
    gj = {"type": "FeatureCollection", "crs": "EPSG:32749", "features": fitur}
    Path(out_geojson).write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    luas = sorted(f["properties"]["luas_ha"] for f in fitur)
    qa = {"n_poligon_kandidat": n_kandidat,
          "n_berlabel": len(fitur),
          "kode_berlabel": sorted({f["properties"]["kode"] for f in fitur}),
          "n_divisi_terisi": sum(1 for f in fitur if f["properties"]["divisi"]),
          "kode_tanpa_poligon": sorted({s for s, _, _ in kata} - {f["properties"]["kode"] for f in fitur}),
          "luas_ha": {"min": luas[0], "median": luas[len(luas) // 2], "max": luas[-1]} if luas else {},
          "kalibrasi_residual_max_m": kal["residual_max_m"]}
    Path(out_qa_json).write_text(json.dumps(qa, indent=2, ensure_ascii=False), encoding="utf-8")
    from core import qa_overlay
    qa_overlay.render_pdf_overlay(pdf_path, fitur_pt, out_overlay_png)
    return qa

def muat_lookup_shp(shp_path):
    """2_Tanam_Inti.shp → {kode_norm: divisi}. Coba BLOK_Baru lalu No_Block."""
    import shapefile
    r = shapefile.Reader(str(shp_path))
    fields = [f[0] for f in r.fields[1:]]
    hasil = {}
    for rec in r.records():
        d = dict(zip(fields, rec))
        for kol in ("BLOK_Baru", "No_Block"):
            v = str(d.get(kol) or "").strip().upper().replace(" ", "")
            if v:
                hasil.setdefault(v, str(d.get("Divisi") or "").strip())
    return hasil

if __name__ == "__main__":
    import sys
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/sumber/peta_blok.pdf")
    kal = kalibrasi_pdf(p)
    simpan_kalibrasi(kal, "data/kalibrasi.json")
    qa = ekstrak_blok(p, kal, "data/blok.geojson", "data/qa_pdf_blok.json",
                      "data/qa_overlay_peta.png", shp_path=r"E:\2. Tanam Inti\2_Tanam_Inti.shp")
    print(json.dumps(qa, indent=2, ensure_ascii=False))
```

`core/qa_overlay.py` — bagian PDF (bagian blok di Task 7):

```python
from pathlib import Path
import numpy as np
import pymupdf
from PIL import Image, ImageDraw

def render_pdf_overlay(pdf_path, fitur_pt, out_png, zoom=0.5):
    """fitur_pt: list (shapely Polygon dalam pt PDF, kode)."""
    doc = pymupdf.open(str(pdf_path))
    pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    dr = ImageDraw.Draw(img)
    for poly, kode in fitur_pt:
        xy = [(x * zoom, y * zoom) for x, y in poly.exterior.coords]
        dr.line(xy, fill=(255, 0, 0), width=2)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
```

- [ ] **Step 4: Jalankan tes — LULUS.** Jika rentang jumlah berlabel tidak tercapai, JANGAN longgarkan tes: periksa `qa.json` (berapa label tak tertaut), catat temuan di commit, sesuaikan HANYA bila ada bukti kuat (mis. label ganda).
- [ ] **Step 5: Jalankan CLI sekali pada PDF asli** untuk menghasilkan artefak nyata:

Run: `.venv/Scripts/python.exe -m core.pdf_blok data/sumber/peta_blok.pdf`
Expected: `data/blok.geojson`, `data/qa_pdf_blok.json`, `data/qa_overlay_peta.png` terbentuk; cetak statistik.

- [ ] **Step 6: Commit** — `git commit -am "feat(pdf_blok): ekstraksi poligon blok + label + geojson + overlay QA"`

---

### Task 4: layer_scan — klasifikasi layer + cakupan blok + rencana output

**Files:**
- Create: `core/layer_scan.py`, `tests/test_layer_scan.py`

**Interfaces:**
- Produces: `ROLE_LAYER = ("ortho", "ndre", "nir", "rededge", "dsm")`; `scan_folder(folder) -> dict` = `{"layers": {role: {"data": path, "bands": int, "dtype": str, ...}}, "ditolak": [{"file","alasan"}]}`; `baca_meta(path) -> dict`; `blok_dalam_cakupan(geojson, bounds) -> list[feature]`; `rencana_output(features, layers, output_root, kode_flight) -> list[dict]` dengan item: `{divisi, kode, layer, src_data, dst_dir, dst_data, dst_rgb, dst_legend, nama_base}`.

- [ ] **Step 1: Tulis tes gagal (sintetik, tidak butuh file nyata)**

```python
import numpy as np
import rasterio
import pytest
from pathlib import Path
from core import layer_scan

def _tif(path, count, dtype, desc=None):
    data = np.zeros((count, 20, 20), dtype=dtype)
    with rasterio.open(path, "w", driver="GTiff", width=20, height=20, count=count,
                       dtype=dtype, crs="EPSG:32749", transform=rasterio.transform.from_origin(300000, 9960000, 1, 1)) as ds:
        ds.write(data)
    return path

@pytest.fixture
def folder(tmp_path):
    _tif(tmp_path / "Orthomosaic.tif", 5, "float32")
    _tif(tmp_path / "NDRE.tif", 1, "float32")
    _tif(tmp_path / "NIR.tif", 1, "float32")
    _tif(tmp_path / "RedEdge.tif", 1, "float32")
    _tif(tmp_path / "Surface model.tif", 1, "float32")
    (tmp_path / "catatan.txt").write_text("bukan raster")
    return tmp_path

def test_klasifikasi_lengkap(folder):
    hasil = layer_scan.scan_folder(folder)
    assert set(hasil["layers"]) == {"ortho", "ndre", "nir", "rededge", "dsm"}
    assert hasil["layers"]["ortho"]["bands"] == 5
    assert any("catatan.txt" in d["file"] for d in hasil["ditolak"])

def test_file_satu_band_asing_ditolak(tmp_path):
    _tif(tmp_path / "aneh.tif", 1, "float32")
    hasil = layer_scan.scan_folder(tmp_path)
    assert "ortho" not in hasil["layers"]
    assert len(hasil["ditolak"]) == 1

def test_rencana_output_naming():
    feats = [{"type": "Feature",
              "properties": {"kode": "D01", "divisi": "AME II", "luas_ha": 30.0},
              "geometry": {"type": "Polygon", "coordinates": [[[300000, 9960000], [300400, 9960000], [300400, 9960400], [300000, 9960400], [300000, 9960000]]]}}]
    layers = {"ortho": {"data": "x.tif"}, "ndre": {"data": "y.tif"}}
    rows = layer_scan.rencana_output(feats, layers, r"F:\\keluar", "FLG03")
    r0 = [r for r in rows if r["kode"] == "D01" and r["layer"] == "ortho"][0]
    assert r0["dst_dir"].replace("\\", "/").endswith("AME II/FLG03_AMEII-D01")
    assert Path(r0["dst_data"]).name == "Orthomosaic - FLG03_AMEII-D01.data.tif"
    assert Path(r0["dst_rgb"]).name == "Orthomosaic - FLG03_AMEII-D01.rgb.tif"
    assert r0["dst_legend"] is None
    r1 = [r for r in rows if r["kode"] == "D01" and r["layer"] == "ndre"][0]
    assert Path(r1["dst_data"]).name == "NDRE.data.tif"
    assert Path(r1["dst_rgb"]).name == "NDRE.rgb.tif"
    assert Path(r1["dst_legend"]).name == "NDRE.legend.png"
```

- [ ] **Step 2: Jalankan — GAGAL**

- [ ] **Step 3: Implementasi `core/layer_scan.py`**

```python
import re
from pathlib import Path
import rasterio

ROLE_LAYER = ("ortho", "ndre", "nir", "rededge", "dsm")

def baca_meta(path):
    with rasterio.open(path) as ds:
        return {"data": str(path), "bands": ds.count, "dtype": ds.dtypes[0],
                "crs": str(ds.crs), "bounds": tuple(ds.bounds), "nodata": ds.nodata}

def _peran_dari_nama(nama):
    n = nama.lower()
    if "ndre" in n: return "ndre"
    if "rededge" in n or "red_edge" in n or "red-edge" in n: return "rededge"
    if re.search(r'(^|[^a-z])nir([^a-z]|$)', n): return "nir"
    if "surface" in n or "dsm" in n or "dtm" in n: return "dsm"
    if "ortho" in n: return "ortho"
    return None

def scan_folder(folder):
    hasil = {"layers": {}, "ditolak": []}
    for f in sorted(Path(folder).glob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".tif", ".tiff"):
            hasil["ditolak"].append({"file": str(f), "alasan": "bukan raster tif"})
            continue
        try:
            meta = baca_meta(f)
        except Exception as e:
            hasil["ditolak"].append({"file": str(f), "alasan": f"gagal dibaca: {e}"})
            continue
        peran = _peran_dari_nama(f.name)
        if peran is None:
            if meta["bands"] == 5:
                peran = "ortho"
            else:
                hasil["ditolak"].append({"file": str(f), "alasan": f"tidak dikenali (band={meta['bands']}, dtype={meta['dtype']})"})
                continue
        if peran in hasil["layers"]:
            hasil["ditolak"].append({"file": str(f), "alasan": f"duplikat layer '{peran}' (sudah: {hasil['layers'][peran]['data']})"})
            continue
        hasil["layers"][peran] = meta
    return hasil

def blok_dalam_cakupan(geojson, bounds):
    from shapely.geometry import shape, box
    b = box(*bounds)
    return [f for f in geojson["features"] if shape(f["geometry"]).intersects(b)]

def nama_base(layer, nama_blok):
    if layer == "ortho": return f"Orthomosaic - {nama_blok}"
    if layer == "dsm": return f"Surface model - {nama_blok}"
    return {"ndre": "NDRE", "nir": "NIR", "rededge": "RedEdge"}[layer]

def rencana_output(features, layers, output_root, kode_flight):
    rows = []
    for f in features:
        p = f["properties"]
        divisi = p.get("divisi") or "TANPA_DIVISI"
        nama_blok = f"{kode_flight}_{divisi.replace(' ', '')}-{p['kode']}"
        dst_dir = Path(output_root) / divisi / nama_blok
        for layer, info in layers.items():
            base = nama_base(layer, nama_blok)
            rows.append({"divisi": divisi, "kode": p["kode"], "layer": layer,
                         "src_data": info["data"], "nama_base": base,
                         "dst_dir": str(dst_dir),
                         "dst_data": str(dst_dir / f"{base}.data.tif"),
                         "dst_rgb": str(dst_dir / f"{base}.rgb.tif"),
                         "dst_legend": None if layer == "ortho"
                                       else str(dst_dir / f"{base}.legend.png")})
    return rows
```

Catatan (spec §6): semua layer punya `.rgb.tif`; `.legend.png` hanya untuk layer indeks (ndre/nir/rededge/dsm) — ortho tanpa legend.

- [ ] **Step 4: Jalankan — LULUS** (3 items)
- [ ] **Step 5: Commit** — `git commit -am "feat(layer_scan): klasifikasi layer + cakupan blok + rencana output"`

---

### Task 5: palet + crop_engine (crop, rgb, legend)

**Files:**
- Create: `core/palet.py`, `core/crop_engine.py`, `tests/test_palet.py`, `tests/test_crop_engine.py`
- Create: `data/palet/bawaan.json` (generated — Step 5)

**Interfaces:**
- Produces (palet): `sample_palette(data_tif, rgb_tif, out_json=None) -> dict` (`{"vmin","vmax","colors": [[r,g,b]×256]}`); `ramp_bawaan(n=256) -> dict` (dengan flag `bawaan: True`); `simpan_palet(pal, path)`; `muat_palet(role, folder_palet) -> dict`; `palet_untuk_data(pal, data_tif) -> dict`; `apply_palette(arr_2d, pal) -> np.uint8 (3,h,w)`; `make_legend(pal, out_png, satuan="")`.
- Produces (crop): `crop_layer(src_path, geom_wkt, dst_path) -> dict` (`{"piksel": int, "ukuran": int}`); `proses_baris(row, folder_palet) -> dict`; `render_ortho_rgb(src_data_tif, dst_rgb)`; `render_rgb(src_data_tif, dst_rgb, pal)`.

- [ ] **Step 1: Tulis tes gagal palet (sintetik) `tests/test_palet.py`**

```python
import numpy as np, rasterio
from core import palet

def _pasangan(tmp_path):
    h = w = 64
    t = rasterio.transform.from_origin(300000, 9960000, 1, 1)
    prof = dict(driver="GTiff", width=w, height=h, crs="EPSG:32749", transform=t)
    arr = np.linspace(0, 100, h * w, dtype="float32").reshape(h, w)
    with rasterio.open(tmp_path / "d.tif", "w", count=1, dtype="float32", **prof) as ds:
        ds.write(arr, 1)
    r = (np.clip(arr / 100 * 255, 0, 255)).astype("uint8")
    rgb = np.stack([r, np.zeros_like(r), np.zeros_like(r)])
    with rasterio.open(tmp_path / "r.tif", "w", count=3, dtype="uint8", **prof) as ds:
        ds.write(rgb)
    return tmp_path / "d.tif", tmp_path / "r.tif"

def test_sampling_dan_apply(tmp_path):
    d, r = _pasangan(tmp_path)
    pal = palet.sample_palette(d, r)
    assert pal["vmin"] == 0 and abs(pal["vmax"] - 100) < 1
    out = palet.apply_palette(np.array([[0.0, 50.0, 100.0]], dtype="float32"), pal)
    assert out.shape == (3, 1, 3)
    assert out[0, 0, 0] < 10 and out[0, 0, 2] > 245          # R rendah di vmin, tinggi di vmax
    assert abs(int(out[0, 0, 1]) - 127) < 15                  # R≈127 di tengah

def test_ramp_bawaan_dan_muat(tmp_path):
    pal = palet.ramp_bawaan()
    assert pal["bawaan"] is True and len(pal["colors"]) == 256
    palet.simpan_palet(pal, tmp_path / "bawaan.json")
    assert palet.muat_palet("nir", tmp_path)["bawaan"] is True
    pal2 = palet.palet_untuk_data(pal, _pasangan(tmp_path)[0])
    assert pal2["vmax"] > pal2["vmin"] and pal2["vmin"] >= 0
```

- [ ] **Step 2: Jalankan — GAGAL**, lalu implementasi `core/palet.py`:

```python
import json, math
from pathlib import Path
import numpy as np
import rasterio
from PIL import Image, ImageDraw

def sample_palette(data_tif, rgb_tif, out_json=None, max_px=300_000):
    with rasterio.open(data_tif) as ds, rasterio.open(rgb_tif) as rs:
        step = max(1, int(math.sqrt(ds.width * ds.height / max_px)))
        h2, w2 = max(1, ds.height // step), max(1, ds.width // step)
        a = ds.read(1, out_shape=(h2, w2)).astype("float64").ravel()
        rgb = rs.read(out_shape=(3, h2, w2)).reshape(3, -1)
        nod = ds.nodata
    if nod is not None:
        keep = a != nod
        a, rgb = a[keep], rgb[:, keep]
    order = np.argsort(a)
    a, rgb = a[order], rgb[:, order]
    vmin, vmax = float(a[0]), float(a[-1])
    if vmax - vmin < 1e-9:
        vmax = vmin + 1.0
    bins = np.linspace(vmin, vmax, 257)
    idx = np.clip(np.digitize(a, bins) - 1, 0, 255)
    warna = np.zeros((256, 3), dtype="float64")
    for i in range(256):
        m = idx == i
        warna[i] = rgb[:, m].mean(axis=1) if m.any() else np.nan
    for c in range(3):
        col = warna[:, c]
        good = ~np.isnan(col)
        if good.sum() >= 2:
            col[~good] = np.interp(np.flatnonzero(~good), np.flatnonzero(good), col[good])
        else:
            col[:] = 0
    pal = {"vmin": vmin, "vmax": vmax,
           "colors": np.clip(warna, 0, 255).astype(int).tolist()}
    if out_json:
        simpan_palet(pal, out_json)
    return pal

def ramp_bawaan(n=256):
    """Gradien biru→sian→kuning→merah untuk layer tanpa referensi (NIR/RedEdge/DSM)."""
    anchors = np.array([[0, 0, 255], [0, 200, 255], [255, 220, 0], [255, 0, 0]], dtype="float64")
    pos = np.linspace(0, len(anchors) - 1, n)
    c = np.stack([np.interp(pos, np.arange(len(anchors)), anchors[:, k]) for k in range(3)], axis=1)
    return {"vmin": 0.0, "vmax": 1.0, "bawaan": True, "colors": c.astype(int).tolist()}

def simpan_palet(pal, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(pal), encoding="utf-8")

def muat_palet(role, folder_palet):
    """Cari {role}.json; fallback bawaan.json; fallback ramp bawaan in-memory."""
    folder = Path(folder_palet)
    for nama in (f"{role}.json", "bawaan.json"):
        p = folder / nama
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return ramp_bawaan()

def palet_untuk_data(pal, data_tif):
    """Palet bawaan (vmin/vmax 0..1) diskalakan ke persentil 2–98 data aktual."""
    if not pal.get("bawaan"):
        return pal
    with rasterio.open(data_tif) as ds:
        a = ds.read(1, out_shape=(min(64, ds.height), min(64, ds.width))).astype("float64")
        nod = ds.nodata
    if nod is not None:
        a = a[a != nod]
    if a.size == 0:
        return {**pal, "vmin": 0.0, "vmax": 1.0}
    lo, hi = np.percentile(a, (2, 98))
    return {**pal, "vmin": float(lo), "vmax": float(hi if hi > lo else lo + 1e-6)}

def apply_palette(arr, pal):
    warna = np.array(pal["colors"], dtype="float64")
    t = np.clip((arr.astype("float64") - pal["vmin"]) / max(pal["vmax"] - pal["vmin"], 1e-12), 0, 1) * 255.0
    i0 = np.clip(np.floor(t).astype(int), 0, 255)
    i1 = np.clip(i0 + 1, 0, 255)
    frac = (t - i0)[..., None]
    rgb = warna[i0] * (1 - frac) + warna[i1] * frac     # (h, w, 3)
    return np.clip(rgb, 0, 255).astype("uint8").transpose(2, 0, 1)

def make_legend(pal, out_png, satuan="", tinggi=260, lebar=90):
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (lebar, tinggi + 40), "white")
    dr = ImageDraw.Draw(img)
    warna = np.array(pal["colors"], dtype="uint8")
    for y in range(tinggi):
        c = tuple(int(v) for v in warna[255 - int(y / tinggi * 255)])
        dr.line([(10, y + 10), (40, y + 10)], fill=c, width=1)
    dr.text((8, 2), f"{pal['vmax']:.2f} {satuan}", fill="black")
    dr.text((8, tinggi + 16), f"{pal['vmin']:.2f} {satuan}", fill="black")
    img.save(out_png)
```

- [ ] **Step 3: Tes crop gagal dulu `tests/test_crop_engine.py`:**

```python
import numpy as np, rasterio
from rasterio.transform import from_origin
from core import crop_engine

def _sumber(tmp_path):
    t = from_origin(300000, 9960000, 1, 1)
    arr = np.random.default_rng(7).random((3, 200, 200)).astype("float32") * 100
    with rasterio.open(tmp_path / "src.tif", "w", driver="GTiff", width=200, height=200,
                       count=3, dtype="float32", crs="EPSG:32749", transform=t,
                       compress="DEFLATE", predictor=3, tiled=True, blockxsize=256, blockysize=256,
                       BIGTIFF="YES") as ds:
        ds.write(arr)
    return tmp_path / "src.tif", t

def test_crop_luas_dan_nodata(tmp_path):
    src, t = _sumber(tmp_path)
    # kotak 60x40 m pada koordinat (300025..300085, 9959940..9959980)
    geom = "POLYGON((300025 9959940, 300085 9959940, 300085 9959980, 300025 9959980, 300025 9959940))"
    dst = tmp_path / "out.tif"
    stat = crop_engine.crop_layer(src, geom, dst)
    with rasterio.open(dst) as ds:
        assert ds.count == 3 and ds.crs.to_epsg() == 32749
        assert 58 <= ds.width <= 64 and 38 <= ds.height <= 44
        assert ds.profile.get("compress") == "deflate"
    assert stat["piksel"] > 0 and stat["ukuran"] > 0

def test_proses_baris_lengkap(tmp_path):
    t = from_origin(300000, 9960000, 1, 1)
    src = tmp_path / "ndre_src.tif"
    arr = np.random.default_rng(3).random((1, 60, 60)).astype("float32") * 0.8
    with rasterio.open(src, "w", driver="GTiff", width=60, height=60, count=1,
                       dtype="float32", crs="EPSG:32749", transform=t) as ds:
        ds.write(arr)
    d = tmp_path / "out" / "DIV" / "FLG03_DIV-D01"
    row = {"layer": "ndre", "src_data": str(src),
           "geom": "POLYGON((300010 9959960, 300050 9959960, 300050 9959990, 300010 9959990, 300010 9959960))",
           "dst_data": str(d / "NDRE.data.tif"), "dst_rgb": str(d / "NDRE.rgb.tif"),
           "dst_legend": str(d / "NDRE.legend.png")}
    stat = crop_engine.proses_baris(row, "data/palet")
    assert stat["ukuran"] > 0
    assert (d / "NDRE.rgb.tif").exists() and (d / "NDRE.legend.png").exists()
```

- [ ] **Step 4: Jalankan — GAGAL**, lalu implementasi `core/crop_engine.py`:

```python
from pathlib import Path
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds
from shapely import wkt

CHUNK_ROWS = 2048

def crop_layer(src_path, geom_wkt, dst_path):
    geom = wkt.loads(geom_wkt)
    with rasterio.open(src_path) as ds:
        minx, miny, maxx, maxy = geom.bounds
        win = from_bounds(minx, miny, maxx, maxy, transform=ds.transform)
        win = win.round_offsets().round_lengths()
        win = Window(win.col_off - 1, win.row_off - 1, win.width + 2, win.height + 2)
        win = win.intersection(Window(0, 0, ds.width, ds.height))
        win = Window(int(win.col_off), int(win.row_off), int(win.width), int(win.height))
        profile = ds.profile.copy()
        profile.update(driver="GTiff", width=int(win.width), height=int(win.height),
                       transform=ds.window_transform(win), tiled=True,
                       blockxsize=256, blockysize=256, BIGTIFF="YES", num_threads="ALL_CPUS")
        float32 = np.issubdtype(np.dtype(ds.dtypes[0]), np.floating)
        profile.update(compress="DEFLATE", **(dict(predictor=3) if float32 else {}))
        nodata = ds.nodata if ds.nodata is not None else (0.0 if float32 else 0)
        profile["nodata"] = nodata
        Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
        total = int(win.width) * int(win.height)
        with rasterio.open(dst_path, "w", **profile) as out:
            for row in range(0, int(win.height), CHUNK_ROWS):
                h = min(CHUNK_ROWS, int(win.height) - row)
                winr = Window(int(win.col_off), int(win.row_off) + row, int(win.width), h)
                arr = ds.read(window=winr)
                mask = geometry_mask([geom], out_shape=(h, int(win.width)),
                                     transform=ds.window_transform(winr), invert=True)
                arr = np.where(mask[None, ...], arr, nodata)
                out.write(arr, window=Window(0, row, int(win.width), h))
    return {"piksel": total, "ukuran": Path(dst_path).stat().st_size}

def proses_baris(row, folder_palet):
    """Satu baris rencana output: crop data → render rgb → legend."""
    from core import palet
    stat = crop_layer(row["src_data"], row["geom"], row["dst_data"])
    if row.get("dst_rgb"):
        if row["layer"] == "ortho":
            render_ortho_rgb(row["dst_data"], row["dst_rgb"])
        else:
            pal = palet.palet_untuk_data(palet.muat_palet(row["layer"], folder_palet), row["dst_data"])
            render_rgb(row["dst_data"], row["dst_rgb"], pal)
            if row.get("dst_legend"):
                palet.make_legend(pal, row["dst_legend"], satuan=row["layer"].upper())
    return stat

def render_ortho_rgb(src_data_tif, dst_rgb, peta_band=None, chunk=CHUNK_ROWS):
    """Ortho 5-band (band1=Green, 2=Red, 3=RedEdge, 4=NIR, 5=Alpha) → rgb uint8 JPEG.
    peta_band default R←2, G←1, B←3 (diverifikasi vs referensi di Gate 2)."""
    peta_band = peta_band or {1: 2, 2: 1, 3: 3}
    _render_uint8(src_data_tif, dst_rgb, None, peta_band, chunk=chunk)

def render_rgb(src_data_tif, dst_rgb, pal, chunk=CHUNK_ROWS):
    _render_uint8(src_data_tif, dst_rgb, pal, None, chunk=chunk)

def _render_uint8(src, dst, pal, peta_band, chunk):
    from core import palet
    with rasterio.open(src) as ds:
        profile = dict(driver="GTiff", width=ds.width, height=ds.height, count=3,
                       dtype="uint8", crs=ds.crs, transform=ds.transform,
                       compress="JPEG", JPEG_QUALITY=85, tiled=True,
                       blockxsize=256, blockysize=256, BIGTIFF="YES",
                       nodata=0, photometric="YCBCR")
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        lo = hi = None
        if pal is None:
            samp = ds.read(out_shape=(ds.count, min(256, ds.height), min(256, ds.width)))
            vals = np.stack([samp[peta_band[k] - 1] for k in (1, 2, 3)]).astype("float64")
            lo, hi = np.percentile(vals, (2, 98))
        with rasterio.open(dst, "w", **profile) as out:
            for row in range(0, ds.height, chunk):
                h = min(chunk, ds.height - row)
                win = Window(0, row, ds.width, h)
                if pal is not None:
                    rgb = palet.apply_palette(ds.read(1, window=win), pal)
                else:
                    bands = [ds.read(b, window=win).astype("float64")
                             for b in (peta_band[1], peta_band[2], peta_band[3])]
                    rgb = np.stack(bands)
                    rgb = np.clip((rgb - lo) / max(hi - lo, 1e-9) * 255, 0, 255).astype("uint8")
                out.write(rgb, window=win)
        with rasterio.open(dst, "r+") as ds2:
            ds2.build_overviews([2, 4, 8, 16], Resampling.average)
```

- [ ] **Step 5: Generate `data/palet/bawaan.json`**

```bash
.venv/Scripts/python.exe -c "from core import palet; palet.simpan_palet(palet.ramp_bawaan(), 'data/palet/bawaan.json')"
```

- [ ] **Step 6: Jalankan semua tes — LULUS**, commit — `git commit -am "feat(core): palet (sampling/ramp/legend) + crop engine (crop/rgb/overviews)"`

---

### Task 6: runner — orkestrasi batch

**Files:**
- Create: `core/runner.py`, `tests/test_runner.py`

**Interfaces:**
- Produces: `Item` (dataclass: `divisi, kode, layer, src_data, dst_dir, dst_data, dst_rgb, dst_legend, nama_base, geom, status, error, dur_s, size`) dengan status `pending/berjalan/selesai/gagal/dilewati`; `Runner(rows, output_root, folder_log, workers=1, crop_fn=None, qa_sample=2, folder_palet=None)`; metode `start()`, `run()`, `cancel()`, `retry(kode)`, `snapshot() -> dict`; properti `state_path = output_root/state.json`; CSV `output_root/hasil_per_blok.csv`.
- Default `crop_fn` = `crop_engine.proses_baris(row, folder_palet)` (crop + rgb + legend). Untuk unit test, `crop_fn` palsu.

- [ ] **Step 1: Tulis tes gagal (crop_fn palsu) `tests/test_runner.py`**

```python
from pathlib import Path
from core.runner import Runner

def _baris(tmp_path, n=3):
    rows = []
    for i in range(n):
        d = tmp_path / "out" / "DIV" / f"FLG01_DIV-B{i:02d}"
        rows.append({"divisi": "DIV", "kode": f"B{i:02d}", "layer": "ndre",
                     "src_data": "x.tif", "dst_dir": str(d), "nama_base": "NDRE",
                     "dst_data": str(d / "NDRE.data.tif"), "dst_rgb": None, "dst_legend": None})
    return rows

def test_sukses_dan_csv(tmp_path):
    rows = _baris(tmp_path)
    def crop(row):
        Path(row["dst_data"]).parent.mkdir(parents=True, exist_ok=True)
        Path(row["dst_data"]).write_bytes(b"x" * 10)
        return {"piksel": 100, "ukuran": 10}
    r = Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop)
    r.run()
    snap = r.snapshot()
    assert all(it["status"] == "selesai" for it in snap["items"])
    csv = (tmp_path / "out" / "hasil_per_blok.csv").read_text(encoding="utf-8")
    assert "B00" in csv and "selesai" in csv

def test_resume_melewati_selesai(tmp_path):
    rows = _baris(tmp_path)
    calls = []
    def crop(row):
        calls.append(row["kode"])
        Path(row["dst_data"]).parent.mkdir(parents=True, exist_ok=True)
        Path(row["dst_data"]).write_bytes(b"x")
        return {"piksel": 1, "ukuran": 1}
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop).run()
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop).run()
    assert calls == ["B00", "B01", "B02"]      # run kedua tak mengulang

def test_gagal_retry_sekali_lalu_lanjut(tmp_path):
    rows = _baris(tmp_path, 2)
    state = {"n": 0}
    def crop(row):
        if row["kode"] == "B00":
            state["n"] += 1
            if state["n"] <= 2:                 # gagal di percobaan + retry
                raise RuntimeError("disk penuh")
        Path(row["dst_data"]).parent.mkdir(parents=True, exist_ok=True)
        Path(row["dst_data"]).write_bytes(b"x")
        return {"piksel": 1, "ukuran": 1}
    r = Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop)
    r.run()
    snap = {it["kode"]: it["status"] for it in r.snapshot()["items"]}
    assert snap["B00"] == "gagal" and snap["B01"] == "selesai"   # batch lanjut

def test_cancel_stop_aman(tmp_path):
    rows = _baris(tmp_path, 3)
    r = None
    def crop(row):
        Path(row["dst_data"]).parent.mkdir(parents=True, exist_ok=True)
        Path(row["dst_data"]).write_bytes(b"x")
        if row["kode"] == "B00":
            r.cancel()           # pengguna menekan Batalkan saat blok pertama selesai
        return {"piksel": 1, "ukuran": 1}
    r = Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop)
    r.run()
    snap = {it["kode"]: it["status"] for it in r.snapshot()["items"]}
    assert snap["B00"] == "selesai"
    assert snap["B01"] == "pending" and snap["B02"] == "pending"

def test_disk_penuh_hentikan_batch(tmp_path):
    rows = _baris(tmp_path, 3)
    def crop(row):
        if row["kode"] == "B01":
            raise OSError(28, "No space left on device")
        Path(row["dst_data"]).parent.mkdir(parents=True, exist_ok=True)
        Path(row["dst_data"]).write_bytes(b"x")
        return {"piksel": 1, "ukuran": 1}
    r = Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop)
    r.run()
    snap = {it["kode"]: it["status"] for it in r.snapshot()["items"]}
    assert snap["B00"] == "selesai" and snap["B01"] == "gagal" and snap["B02"] == "pending"
```

- [ ] **Step 2: Jalankan — GAGAL**, lalu implementasi `core/runner.py`:

```python
import csv, json, logging, threading, time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

@dataclass
class Item:
    divisi: str
    kode: str
    layer: str
    src_data: str
    dst_dir: str
    dst_data: str
    dst_rgb: str | None
    dst_legend: str | None
    nama_base: str = ""
    geom: str = ""
    status: str = "pending"
    error: str = ""
    dur_s: float = 0.0
    size: int = 0

class Runner:
    def __init__(self, rows, output_root, folder_log, workers=1, crop_fn=None,
                 qa_sample=2, folder_palet=None):
        from core import config as cfg_mod
        self.items = [Item(**r) for r in rows]
        self.output_root = Path(output_root)
        self.folder_log = Path(folder_log)
        if crop_fn is None:
            from core import crop_engine
            fp = folder_palet or str(cfg_mod.ROOT / "data" / "palet")
            crop_fn = lambda row: crop_engine.proses_baris(row, fp)
        self.crop_fn = crop_fn
        self.qa_sample = qa_sample
        self._batal = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._logger = None
        self._qa_dibuat = 0
        self.state_path = self.output_root / "state.json"
        self.csv_path = self.output_root / "hasil_per_blok.csv"
        self.log_path = None

    def _log(self, msg):
        if self._logger:
            self._logger.info(msg)

    def snapshot(self):
        with self._lock:
            items = [asdict(it) for it in self.items]
        return {"aktif": bool(self._thread and self._thread.is_alive()),
                "total": len(items),
                "selesai": sum(1 for it in items if it["status"] == "selesai"),
                "gagal": sum(1 for it in items if it["status"] == "gagal"),
                "items": items,
                "log_file": str(self.log_path) if self.log_path else ""}

    def _tulis_state(self):
        with self._lock:
            data = {"items": [asdict(it) for it in self.items],
                    "diperbarui": datetime.now().isoformat(timespec="seconds")}
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.state_path)

    def _muat_state(self):
        """Resume: item selesai/dilewati dari run sebelumnya dilewati."""
        if not self.state_path.exists():
            return
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        lama = {(it["kode"], it["layer"]): it for it in data.get("items", [])}
        with self._lock:
            for it in self.items:
                prev = lama.get((it.kode, it.layer))
                if prev and prev["status"] in ("selesai", "dilewati"):
                    it.status = prev["status"]
                    it.size = prev.get("size", 0)
                    it.dur_s = prev.get("dur_s", 0.0)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._batal.clear()
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._batal.set()

    def retry(self, kode):
        with self._lock:
            ada = False
            for it in self.items:
                if it.kode == kode and it.status == "gagal":
                    it.status = "pending"
                    it.error = ""
                    ada = True
        if ada:
            self.start()

    def run(self):
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.folder_log.mkdir(parents=True, exist_ok=True)
        self.log_path = self.folder_log / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"
        self._logger = logging.getLogger(f"runner_{id(self)}")
        self._logger.setLevel(logging.INFO)
        if not self._logger.handlers:
            fh = logging.FileHandler(self.log_path, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self._logger.addHandler(fh)
        self._muat_state()
        with self._lock:
            todo = [it for it in self.items if it.status == "pending"]
        self._log(f"Batch mulai: {len(todo)} item")
        for it in todo:
            if self._batal.is_set():
                self._log("Dibatalkan — item tersisa tetap pending")
                break
            self._proses(it)
            self._tulis_state()
            self._tulis_csv()
        self._tulis_state()
        self._tulis_csv()
        self._log("Batch selesai")

    def _proses(self, it):
        row = {"divisi": it.divisi, "kode": it.kode, "layer": it.layer, "src_data": it.src_data,
               "dst_dir": it.dst_dir, "dst_data": it.dst_data, "dst_rgb": it.dst_rgb,
               "dst_legend": it.dst_legend, "nama_base": it.nama_base, "geom": it.geom}
        for percobaan in (1, 2):      # retry otomatis 1×
            t0 = time.time()
            it.status = "berjalan"
            it.error = ""
            self._log(f"{it.kode}/{it.layer}: mulai (percobaan {percobaan})")
            try:
                stat = self.crop_fn(row)
                it.size = stat.get("ukuran", 0)
                it.dur_s = time.time() - t0
                it.status = "selesai"
                self._log(f"{it.kode}/{it.layer}: selesai {it.size} B dalam {it.dur_s:.1f}s")
                return
            except KeyboardInterrupt:
                it.status = "pending"
                self.cancel()
                return
            except Exception as e:
                it.error = str(e)
                it.dur_s = time.time() - t0
                self._log(f"{it.kode}/{it.layer}: gagal ({e})")
                if getattr(e, "errno", None) == 28:
                    self._log("Disk penuh — batch dihentikan; item tersisa tetap pending")
                    it.status = "gagal"
                    self.cancel()
                    return
        it.status = "gagal"

    def _tulis_csv(self):
        with self._lock:
            items = [asdict(it) for it in self.items]
        cols = ["divisi", "kode", "layer", "status", "size", "dur_s", "dst_data", "error"]
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=cols)
            wr.writeheader()
            for it in items:
                wr.writerow({k: it[k] for k in cols})
```

- [ ] **Step 3: Jalankan — LULUS** (5 items), commit — `git commit -am "feat(runner): orkestrasi batch + resume + retry + cancel + csv/log"`

---

### Task 7: qa_overlay — overlay blok hasil crop + integrasi runner

**Files:**
- Modify: `core/qa_overlay.py` (tambah `render_blok_overlay`), `core/runner.py` (hook QA di `_proses`), `tests/test_qa_overlay.py`

**Interfaces:**
- Produces: `render_blok_overlay(rgb_tif, geom_wkt, out_png) -> None`.

- [ ] **Step 1: Tes gagal** (rgb sintetik 100×100 @1m + kotak 40×30):

```python
import numpy as np, rasterio
from rasterio.transform import from_origin
from core import qa_overlay

def test_overlay_terbentuk(tmp_path):
    t = from_origin(300000, 9960000, 1, 1)
    arr = np.full((3, 100, 100), 200, dtype="uint8")
    rgb = tmp_path / "rgb.tif"
    with rasterio.open(rgb, "w", driver="GTiff", width=100, height=100, count=3,
                       dtype="uint8", crs="EPSG:32749", transform=t) as ds:
        ds.write(arr)
    out = tmp_path / "ov.png"
    qa_overlay.render_blok_overlay(str(rgb),
        "POLYGON((300010 9959960, 300050 9959960, 300050 9959990, 300010 9959990, 300010 9959960))",
        str(out))
    assert out.stat().st_size > 1000
```

- [ ] **Step 2: Implementasi `render_blok_overlay` di `core/qa_overlay.py`:**

```python
def render_blok_overlay(rgb_tif, geom_wkt, out_png):
    import rasterio
    from shapely import wkt
    geom = wkt.loads(geom_wkt)
    with rasterio.open(rgb_tif) as ds:
        arr = ds.read([1, 2, 3])
        inv = ~ds.transform
    img = Image.fromarray(np.transpose(arr, (1, 2, 0)))
    dr = ImageDraw.Draw(img)
    px = [inv * (x, y) for x, y in geom.exterior.coords]
    dr.line(px, fill=(255, 0, 0), width=2)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
```

- [ ] **Step 3: Integrasi runner + jalankan tes**

Ganti blok sukses di `Runner._proses` (bagian `try` setelah `stat = self.crop_fn(row)`) menjadi:

```python
            try:
                stat = self.crop_fn(row)
                it.size = stat.get("ukuran", 0)
                it.dur_s = time.time() - t0
                it.status = "selesai"
                self._log(f"{it.kode}/{it.layer}: selesai {it.size} B dalam {it.dur_s:.1f}s")
                if (it.layer == "ortho" and self._qa_dibuat < self.qa_sample
                        and it.dst_rgb and it.geom):
                    try:
                        from core import qa_overlay
                        qa_overlay.render_blok_overlay(
                            it.dst_rgb, it.geom, str(Path(it.dst_dir) / "qa_overlay.png"))
                        self._log(f"{it.kode}: overlay QA → qa_overlay.png")
                    except Exception as e:
                        self._log(f"{it.kode}: overlay QA gagal ({e})")
                    self._qa_dibuat += 1
                return
```

Run: `.venv/Scripts/python.exe -m pytest tests/test_qa_overlay.py tests/test_runner.py -q` — Expected: PASS (tes runner tetap lolos karena `dst_rgb=None` di baris palsu → hook dilewati).
Commit — `git commit -am "feat(qa_overlay): overlay blok hasil crop + integrasi runner (2 blok pertama)"`

---

### Task 8: Web UI (Flask) + launcher

**Files:**
- Create: `app.py`, `templates/index.html`, `static/style.css`, `static/app.js`, `jalankan.bat`, `tests/test_app.py`

**Interfaces:**
- Consumes: semua modul core.
- Produces (rute): `GET /`; `GET|POST /api/config`; `GET /api/blok`; `POST /api/blok/divisi`; `POST /api/pindai`; `POST /api/jalankan`; `GET /api/status`; `POST /api/batalkan`; `POST /api/ulangi`; `POST /api/buka-folder`; `GET /api/unduh/hasil`; `GET /api/unduh/log`.

- [ ] **Step 1: Tes gagal `tests/test_app.py`**

```python
def test_halaman_utama():
    import app as aplikasi
    c = aplikasi.app.test_client()
    r = c.get("/")
    assert r.status_code == 200 and "Ekspor Blok" in r.get_data(as_text=True)

def test_config_roundtrip(tmp_path, monkeypatch):
    import app as aplikasi
    from core import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "ROOT", tmp_path)
    c = aplikasi.app.test_client()
    r = c.post("/api/config", json={"folder_sumber": str(tmp_path), "kode_flight": "FLG03"})
    assert r.status_code == 200
    assert c.get("/api/config").get_json()["kode_flight"] == "FLG03"

def test_status_tanpa_run():
    import app as aplikasi
    c = aplikasi.app.test_client()
    j = c.get("/api/status").get_json()
    assert j["aktif"] is False and j["total"] == 0

def test_unduh_belum_ada(tmp_path, monkeypatch):
    import app as aplikasi
    monkeypatch.setattr(aplikasi.KONFIG, "folder_output", str(tmp_path / "kosong"))
    c = aplikasi.app.test_client()
    assert c.get("/api/unduh/hasil").status_code == 404
```

- [ ] **Step 2: Implementasi `app.py`**

```python
import json, shutil, socket, threading, webbrowser
from dataclasses import asdict, fields
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from core import config as cfg_mod
from core import layer_scan, pdf_blok
from core.runner import Runner

app = Flask(__name__)
KONFIG = cfg_mod.load_config()
RUNNER = {"obj": None}
SHP_DIVISI = r"E:\2. Tanam Inti\2_Tanam_Inti.shp"


def _port_bebas(mulai=5000, akhir=5050):
    for p in range(mulai, akhir):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return 0


def _free_bytes(path):
    p = Path(path or ".").resolve()
    while not p.exists() and p.parent != p:
        p = p.parent
    return shutil.disk_usage(str(p)).free


def _muat_geojson():
    """Muat blok.geojson; bila belum ada: kalibrasi + ekstraksi dari PDF (sekali)."""
    gj_path = Path(KONFIG.path_blok)
    if not gj_path.exists():
        pdf = Path(KONFIG.pdf_peta)
        if not pdf.exists():
            raise ValueError(f"PDF peta tidak ditemukan: {pdf}")
        kal_path = Path(KONFIG.path_kalibrasi)
        if kal_path.exists():
            kal = pdf_blok.muat_kalibrasi(kal_path)
        else:
            kal = pdf_blok.kalibrasi_pdf(pdf)
            pdf_blok.simpan_kalibrasi(kal, kal_path)
        if not kal["ok"]:
            raise ValueError(f"Kalibrasi PDF gagal (residual maks {kal['residual_max_m']:.2f} m)")
        pdf_blok.ekstrak_blok(pdf, kal, gj_path, gj_path.with_name("qa_pdf_blok.json"),
                              gj_path.with_name("qa_overlay_peta.png"),
                              shp_path=SHP_DIVISI if Path(SHP_DIVISI).exists() else None)
    return json.loads(gj_path.read_text(encoding="utf-8"))


def _bangun_rows():
    gj = _muat_geojson()
    if not KONFIG.folder_sumber:
        raise ValueError("Folder sumber belum diisi")
    if not KONFIG.folder_output:
        raise ValueError("Folder output belum diisi")
    if not KONFIG.kode_flight:
        raise ValueError("Kode flight belum diisi (mis. FLG03)")
    hasil = layer_scan.scan_folder(KONFIG.folder_sumber)
    if "ortho" not in hasil["layers"]:
        raise ValueError("Layer Orthomosaic (5-band) tidak ditemukan di folder sumber")
    blok = layer_scan.blok_dalam_cakupan(gj, hasil["layers"]["ortho"]["bounds"])
    if not blok:
        raise ValueError("Tidak ada blok peta yang beririsan dengan cakupan ortho")
    rows = layer_scan.rencana_output(blok, hasil["layers"], KONFIG.folder_output, KONFIG.kode_flight)
    from shapely.geometry import shape
    wkt_map = {f["properties"]["kode"]: shape(f["geometry"]).wkt for f in blok}
    for r in rows:
        r["geom"] = wkt_map[r["kode"]]
    luas_semua = sum(f["properties"]["luas_ha"] for f in gj["features"]) or 1.0
    luas_blok = sum(f["properties"]["luas_ha"] for f in blok)
    ukuran_src = sum(Path(v["data"]).stat().st_size for v in hasil["layers"].values())
    estimasi = int(ukuran_src * (luas_blok / luas_semua) * 0.6)   # faktor konservatif vs rekompresi
    kal = None
    kal_path = Path(KONFIG.path_kalibrasi)
    if kal_path.exists():
        k = pdf_blok.muat_kalibrasi(kal_path)
        kal = {"residual_max_m": k["residual_max_m"], "titik_kontrol": k["titik_kontrol"]}
    return {"rows": rows, "layers": {k: str(v["data"]) for k, v in hasil["layers"].items()},
            "ditolak": hasil["ditolak"], "n_blok": len(blok), "estimasi_byte": estimasi,
            "blok": [{"kode": f["properties"]["kode"],
                      "divisi": f["properties"].get("divisi", ""),
                      "luas_ha": f["properties"].get("luas_ha")} for f in blok],
            "kalibrasi": kal}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/config")
def get_config():
    return jsonify(asdict(KONFIG))


@app.post("/api/config")
def post_config():
    data = request.get_json(force=True)
    for f in fields(KONFIG):
        if f.name in data:
            setattr(KONFIG, f.name, data[f.name])
    cfg_mod.save_config(KONFIG)
    return jsonify({"ok": True})


@app.get("/api/blok")
def get_blok():
    try:
        gj = _muat_geojson()
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True,
                    "blok": [{"kode": f["properties"]["kode"],
                              "divisi": f["properties"].get("divisi", ""),
                              "luas_ha": f["properties"].get("luas_ha")} for f in gj["features"]]})


@app.post("/api/blok/divisi")
def post_blok_divisi():
    data = request.get_json(force=True)
    kode, divisi = data["kode"], data["divisi"]
    gj_path = Path(KONFIG.path_blok)
    gj = json.loads(gj_path.read_text(encoding="utf-8"))
    n = 0
    for f in gj["features"]:
        if f["properties"]["kode"] == kode:
            f["properties"]["divisi"] = divisi
            n += 1
    gj_path.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    return jsonify({"ok": n > 0, "diubah": n})


@app.post("/api/pindai")
def pindai():
    try:
        info = _bangun_rows()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    bebas = _free_bytes(KONFIG.folder_output)
    return jsonify({"ok": True, "n_blok": info["n_blok"], "layers": info["layers"],
                    "ditolak": info["ditolak"], "n_baris": len(info["rows"]),
                    "estimasi_byte": info["estimasi_byte"], "disk_bebas_byte": bebas,
                    "cukup_disk": bebas > info["estimasi_byte"] * 1.2,
                    "blok": info["blok"][:500], "kalibrasi": info["kalibrasi"]})


@app.post("/api/jalankan")
def jalankan():
    if RUNNER["obj"] and RUNNER["obj"].snapshot()["aktif"]:
        return jsonify({"ok": False, "error": "Batch sedang berjalan"}), 400
    try:
        info = _bangun_rows()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    bebas = _free_bytes(KONFIG.folder_output)
    if bebas < info["estimasi_byte"] * 1.2:
        return jsonify({"ok": False, "error": "Ruang disk tidak cukup: estimasi %.1f GB, bebas %.1f GB"
                        % (info["estimasi_byte"] / 1e9, bebas / 1e9)}), 400
    r = Runner(info["rows"], KONFIG.folder_output, KONFIG.folder_log,
               folder_palet=KONFIG.folder_palet)
    RUNNER["obj"] = r
    r.start()
    return jsonify({"ok": True})


@app.get("/api/status")
def status():
    r = RUNNER["obj"]
    if r is None:
        return jsonify({"aktif": False, "items": [], "total": 0, "selesai": 0,
                        "gagal": 0, "log_tail": ""})
    snap = r.snapshot()
    log_tail = ""
    if r.log_path and Path(r.log_path).exists():
        log_tail = "\n".join(Path(r.log_path).read_text(encoding="utf-8", errors="replace").splitlines()[-80:])
    snap["log_tail"] = log_tail
    return jsonify(snap)


@app.post("/api/batalkan")
def batalkan():
    if RUNNER["obj"]:
        RUNNER["obj"].cancel()
    return jsonify({"ok": True})


@app.post("/api/ulangi")
def ulangi():
    kode = request.get_json(force=True)["kode"]
    if RUNNER["obj"]:
        RUNNER["obj"].retry(kode)
    return jsonify({"ok": True})


@app.post("/api/buka-folder")
def buka_folder():
    import os
    if KONFIG.folder_output and Path(KONFIG.folder_output).exists():
        os.startfile(KONFIG.folder_output)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Folder output belum ada"}), 400


@app.get("/api/unduh/hasil")
def unduh_hasil():
    p = Path(KONFIG.folder_output) / "hasil_per_blok.csv"
    if not p.exists():
        return jsonify({"ok": False, "error": "CSV belum ada"}), 404
    return send_file(p, as_attachment=True)


@app.get("/api/unduh/log")
def unduh_log():
    r = RUNNER["obj"]
    if r is None or not r.log_path or not Path(r.log_path).exists():
        return jsonify({"ok": False, "error": "Log belum ada"}), 404
    return send_file(r.log_path, as_attachment=True)


if __name__ == "__main__":
    port = KONFIG.port or _port_bebas()
    threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host="127.0.0.1", port=port, debug=False)
```

- [ ] **Step 3: `templates/index.html`** (satu halaman, 3 kartu):

```html
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<title>Ekspor Blok Otomatis — Pix4DField</title>
<link rel="stylesheet" href="/static/style.css">
</head>
<body>
<h1>Ekspor Blok Otomatis — Pix4DField</h1>

<section class="kartu" id="tahap-setup">
  <h2>1. Setup</h2>
  <label>Folder sumber (hasil ekspor full-extent dari app): <input id="folder_sumber" size="60"></label>
  <label>Folder output (BARU, mis. F:\dataset\Pix4DField-export-FLG03_auto): <input id="folder_output" size="60"></label>
  <label>Peta blok PDF: <input id="pdf_peta" size="60"></label>
  <label>Kode flight (mis. FLG03): <input id="kode_flight" size="10"></label>
  <button id="btn-simpan">Simpan Konfigurasi</button>
  <span id="status-simpan"></span>
</section>

<section class="kartu" id="tahap-pindai">
  <h2>2. Pindai (dry-run)</h2>
  <button id="btn-pindai">Pindai Folder Sumber</button>
  <div id="hasil-pindai"></div>
  <table id="tabel-blok">
    <thead><tr><th>Kode</th><th>Divisi</th><th>Luas (ha)</th><th>Koreksi divisi</th></tr></thead>
    <tbody></tbody>
  </table>
</section>

<section class="kartu" id="tahap-jalankan">
  <h2>3. Jalankan</h2>
  <button id="btn-jalankan">Jalankan Ekspor</button>
  <button id="btn-batalkan">Batalkan</button>
  <button id="btn-buka">Buka Folder Hasil</button>
  <a id="unduh-csv" href="/api/unduh/hasil">Unduh CSV</a>
  &nbsp;<a id="unduh-log" href="/api/unduh/log">Unduh Log</a>
  <div>Progress: <span id="progress-teks">0/0</span></div>
  <div id="progress-bar"><div id="progress-isi"></div></div>
  <table id="tabel-status">
    <thead><tr><th>Blok</th><th>Layer</th><th>Status</th><th>Ukuran</th><th>Error</th><th></th></tr></thead>
    <tbody></tbody>
  </table>
  <pre id="log"></pre>
</section>
<script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: `static/app.js`**

```js
const $ = (id) => document.getElementById(id);
const KUNCI = ["folder_sumber", "folder_output", "pdf_peta", "kode_flight"];

async function muatConfig() {
  const c = await (await fetch("/api/config")).json();
  for (const k of KUNCI) $(k).value = c[k] ?? "";
}

async function simpanConfig() {
  const body = {};
  for (const k of KUNCI) body[k] = $(k).value.trim();
  const r = await (await fetch("/api/config", {method: "POST",
    headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)})).json();
  $("status-simpan").textContent = r.ok ? "Tersimpan." : "Gagal menyimpan.";
}

async function pindai() {
  $("hasil-pindai").textContent = "Memindai…";
  const r = await (await fetch("/api/pindai", {method: "POST"})).json();
  if (!r.ok) { $("hasil-pindai").textContent = "GAGAL: " + r.error; return; }
  const nLayer = Object.keys(r.layers).length;
  $("hasil-pindai").textContent =
    `${r.n_blok} blok × ${nLayer} layer = ${r.n_baris} file; ` +
    `estimasi ${(r.estimasi_byte / 1e9).toFixed(1)} GB; ` +
    `disk bebas ${(r.disk_bebas_byte / 1e9).toFixed(1)} GB` +
    (r.cukup_disk ? "" : " — PERINGATAN: disk mungkin tidak cukup");
  const tb = $("tabel-blok").querySelector("tbody");
  tb.innerHTML = "";
  for (const b of r.blok) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${b.kode}</td><td>${b.divisi || "-"}</td><td>${b.luas_ha ?? ""}</td>`;
    const td = document.createElement("td");
    const inp = document.createElement("input");
    inp.value = b.divisi || "";
    const btn = document.createElement("button");
    btn.textContent = "Simpan";
    btn.onclick = async () => {
      await fetch("/api/blok/divisi", {method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({kode: b.kode, divisi: inp.value.trim()})});
      btn.textContent = "Tersimpan";
    };
    td.append(inp, btn);
    tr.append(td);
    tb.append(tr);
  }
}

async function jalankan() {
  const r = await (await fetch("/api/jalankan", {method: "POST"})).json();
  if (!r.ok) { alert("Gagal: " + r.error); return; }
  setTimeout(polling, 500);
}

function warna(status) {
  return {selesai: "#c8f7c5", gagal: "#f7c5c5", berjalan: "#fff3b0",
          dilewati: "#e0e0e0", pending: "#ffffff"}[status] || "#fff";
}

async function polling() {
  const s = await (await fetch("/api/status")).json();
  $("progress-teks").textContent = `${s.selesai}/${s.total} (gagal ${s.gagal})`;
  $("progress-isi").style.width = s.total ? `${Math.round(s.selesai / s.total * 100)}%` : "0%";
  const tb = $("tabel-status").querySelector("tbody");
  tb.innerHTML = "";
  for (const it of s.items) {
    const tr = document.createElement("tr");
    tr.style.background = warna(it.status);
    tr.innerHTML = `<td>${it.divisi} ${it.kode}</td><td>${it.layer}</td><td>${it.status}</td>` +
                   `<td>${(it.size / 1e6).toFixed(1)} MB</td><td>${it.error}</td>`;
    const td = document.createElement("td");
    if (it.status === "gagal") {
      const b = document.createElement("button");
      b.textContent = "Coba ulang";
      b.onclick = () => {
        fetch("/api/ulangi", {method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({kode: it.kode})});
        setTimeout(polling, 500);
      };
      td.append(b);
    }
    tr.append(td);
    tb.append(tr);
  }
  $("log").textContent = s.log_tail || "";
  if (s.aktif) setTimeout(polling, 1000);
}

$("btn-simpan").onclick = simpanConfig;
$("btn-pindai").onclick = pindai;
$("btn-jalankan").onclick = jalankan;
$("btn-batalkan").onclick = () => fetch("/api/batalkan", {method: "POST"});
$("btn-buka").onclick = () => fetch("/api/buka-folder", {method: "POST"});
muatConfig().then(polling);
```

- [ ] **Step 5: `static/style.css`**

```css
body { font-family: "Segoe UI", sans-serif; margin: 20px; color: #222; }
h1 { font-size: 20px; }
h2 { font-size: 15px; margin: 0 0 8px; }
.kartu { border: 1px solid #ccc; border-radius: 8px; padding: 14px; margin-bottom: 16px; }
label { display: block; margin: 6px 0; }
input { padding: 4px; }
button { padding: 5px 12px; margin-right: 6px; cursor: pointer; }
table { border-collapse: collapse; width: 100%; margin-top: 8px; font-size: 13px; }
th, td { border: 1px solid #bbb; padding: 3px 6px; text-align: left; }
#log { background: #111; color: #ddd; padding: 8px; max-height: 240px; overflow: auto; font-size: 12px; }
#progress-bar { background: #eee; height: 14px; border-radius: 7px; margin: 6px 0; width: 400px; }
#progress-isi { background: #3a7; height: 14px; border-radius: 7px; width: 0; }
```

- [ ] **Step 6: `jalankan.bat`**

```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Ekspor Blok Otomatis
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
```

- [ ] **Step 7: Jalankan tes — LULUS.** Lalu uji manual dengan browser:

Run (background): `cd /d/pix4dfield_exporting_tools && .venv/Scripts/python.exe app.py` — catat port dari output `Running on http://127.0.0.1:<port>`.
Buka via browser-use MCP (`navigate_page`) → verifikasi: judul "Ekspor Blok Otomatis — Pix4DField" tampil, tiga kartu tahap terlihat, tombol "Simpan Konfigurasi" mengembalikan "Tersimpan", tidak ada error konsol. Screenshot. Hentikan server.
Commit — `git commit -am "feat(ui): web lokal 3 tahap (setup/pindai/jalankan) + jalankan.bat"`

---

### Task 9: Integrasi end-to-end (sintetis) + artefak Gate 1 + README

**Files:**
- Create: `tests/test_e2e_sintetis.py`, `README.md`

- [ ] **Step 1: Tes e2e sintetis `tests/test_e2e_sintetis.py`** (folder sumber palsu 2 layer menutupi 1 blok sintetik; runner dengan crop_fn nyata):

```python
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import shape
from core import layer_scan
from core.runner import Runner


def _buat_sumber(folder):
    t = from_origin(300000, 9960000, 1, 1)
    prof = dict(driver="GTiff", width=300, height=300, crs="EPSG:32749", transform=t,
                tiled=True, blockxsize=256, blockysize=256, BIGTIFF="YES")
    rng = np.random.default_rng(1)
    with rasterio.open(folder / "Orthomosaic.tif", "w", count=5, dtype="float32", **prof) as ds:
        ds.write((rng.random((5, 300, 300)) * 100).astype("float32"))
    with rasterio.open(folder / "NDRE.tif", "w", count=1, dtype="float32", **prof) as ds:
        ds.write((rng.random((1, 300, 300)) * 0.8).astype("float32"))


def test_e2e_satu_blok(tmp_path):
    sumber = tmp_path / "sumber"
    sumber.mkdir()
    _buat_sumber(sumber)
    feats = [{"type": "Feature",
              "properties": {"kode": "D01", "divisi": "AME II", "luas_ha": 1.0},
              "geometry": {"type": "Polygon", "coordinates": [[
                  [300050, 9959950], [300150, 9959950], [300150, 9960050],
                  [300050, 9960050], [300050, 9959950]]]}}]
    layers = layer_scan.scan_folder(sumber)["layers"]
    rows = layer_scan.rencana_output(feats, layers, str(tmp_path / "keluar"), "FLG03")
    wkt = shape(feats[0]["geometry"]).wkt
    for r in rows:
        r["geom"] = wkt
    runner = Runner(rows, tmp_path / "keluar", tmp_path / "log",
                    folder_palet=str(Path(__file__).resolve().parent.parent / "data" / "palet"))
    runner.run()
    assert all(it["status"] == "selesai" for it in runner.snapshot()["items"])
    base = tmp_path / "keluar" / "AME II" / "FLG03_AMEII-D01"
    for nama in ("NDRE.data.tif", "NDRE.rgb.tif", "NDRE.legend.png",
                 "Orthomosaic - FLG03_AMEII-D01.data.tif",
                 "Orthomosaic - FLG03_AMEII-D01.rgb.tif"):
        assert (base / nama).exists(), nama
    assert (tmp_path / "keluar" / "hasil_per_blok.csv").exists()
    assert (tmp_path / "keluar" / "state.json").exists()
    data = json.loads((tmp_path / "keluar" / "state.json").read_text(encoding="utf-8"))
    assert len(data["items"]) == len(rows) == 2
    assert (base / "qa_overlay.png").exists()   # overlay QA blok ortho pertama
```

- [ ] **Step 2: Jalankan semua tes**

Run: `.venv/Scripts/python.exe -m pytest tests/ -q` — Expected: semua LULUS.

- [ ] **Step 3: Salin artefak Gate 1** (hasil Task 3 Step 5):

```bash
mkdir -p laporan/gate1
cp data/blok.geojson data/qa_pdf_blok.json data/qa_overlay_peta.png laporan/gate1/
```

- [ ] **Step 4: Tulis `README.md`**

```markdown
# Ekspor Blok Otomatis — Pix4DField

Tool lokal untuk memotong (crop) layer hasil ekspor Pix4DField per blok kebun
memakai peta blok PDF, lalu menulisnya ke folder output BARU.

## Cara Pakai

1. Di Pix4DField: ekspor semua layer untuk 1 project sebagai **full extent** (satu kali per project, bukan per blok) ke satu folder.
2. Double-click `jalankan.bat` — server lokal mulai, browser terbuka otomatis (`http://127.0.0.1:<port>`).
3. **Tahap 1 (Setup):** isi folder sumber, folder output BARU (mis. `F:\dataset\Pix4DField-export-FLG03_auto`), peta blok PDF, kode flight → Simpan.
4. **Tahap 2 (Pindai):** periksa jumlah blok × layer, estimasi disk, koreksi divisi bila perlu → Pindai.
5. **Tahap 3 (Jalankan):** mulai batch; pantau progress/log; tombol Batalkan / Coba ulang / Buka folder / Unduh CSV / Unduh log tersedia.

## Verifikasi (gate)

- **Gate 0:** konfirmasi app mendukung export full-extent (sekali per project).
- **Gate 1:** overlay peta `laporan/gate1/qa_overlay_peta.png` di-ACC (posisi batas blok vs peta).
- **Gate 2:** 1 project kecil — bandingkan hasil vs ekspor manual (posisi, cakupan, ukuran file, palet); ukur rasio kompresi.
- **Gate 3:** batch penuh 1 flight ke folder `..._auto`; verifikasi visual beberapa blok.

## Catatan

- Output SELALU ke folder baru `..._auto`; arsip lama tidak pernah disentuh.
- Geometri blok dari PDF "Peta Informasi Tanam Tahun Inti" — kalibrasi affine residual ≈ 0,67 m; CRS EPSG:32749.
- Palet NIR/RedEdge/DSM belum ada referensinya → gradien aproksimasi (`data/palet/bawaan.json`) sampai disampel dari ekspor `.rgb` app di Gate 2.
- Tes: `.venv/Scripts/python.exe -m pytest tests/ -q`
- Rencana & spec: `docs/superpowers/`
```

- [ ] **Step 5: Commit** — `git commit -am "feat: integrasi e2e sintetis + artefak Gate 1 + README"`

---

## Risiko & Item Terbuka (dipantau saat eksekusi)

- **Pola nama file ekspor full-extent dari app belum diketahui** → `layer_scan` punya jalur klasifikasi nama → jumlah band; finalisasi saat Gate 2 (pengguna mengekspor contoh nyata).
- **Palet NIR/RedEdge belum ada referensi** → fallback `data/palet/bawaan.json`; disampel dari ekspor `.rgb` app saat Gate 2.
- **Mapping band ortho→rgb** (R←2, G←1, B←3) diverifikasi terhadap pasangan referensi saat Gate 2; koreksi bila sampel menunjukkan lain.
- **Jumlah blok berlabel (300–900)** dikalibrasi dari hasil nyata; dicatat di `qa_pdf_blok.json`.
- **Gate 0** (dukungan ekspor full-extent di app) tetap perlu konfirmasi pengguna sebelum Gate 2 dijalankan.
- **Label non-blok** (CT-01, Ban1-12) bisa ikut tertangkap `KODE_RE` bila menempel ke poligon; dicek pada ACC Gate 1.
