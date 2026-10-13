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
