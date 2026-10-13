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
