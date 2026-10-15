"""Generator kartu validasi per blok: citra hasil crop + batas PDF (merah, dipakai crop)
vs batas shp kebun (biru), plus inset resolusi asli di titik-titik batas.

Output: <dest>/kartu_<KODE>.png + <dest>/index.json (metadata untuk UI).
Default dest: <folder_output>/_validasi.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import rasterio
from PIL import Image, ImageDraw, ImageFont
from rasterio.windows import Window
from shapely.geometry import LineString
from shapely.geometry import shape as shp_shape

WINS, HINS = 430, 300          # ukuran inset (px resolusi asli)
HSTRIP = 960
FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
FONT_REG = "C:/Windows/Fonts/arial.ttf"


def _font(ukuran, bold):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, ukuran)
    except OSError:
        return ImageFont.load_default()


def _baris_konteks(gsd_cm, residual_m):
    def _id(v):
        return f"{v:.2f}".replace(".", ",")
    sisa = f"residual kalibrasi PDF {_id(residual_m)} m; " if residual_m is not None else ""
    return (f"konteks: {sisa}GSD {_id(gsd_cm)} cm/px; "
            "garis digambar apa adanya tanpa penyesuaian")


def muat_shp(path_shp):
    import shapefile
    r = shapefile.Reader(str(path_shp))
    fields = [f[0] for f in r.fields[1:]]
    hasil = {}
    for rec, sh in zip(r.records(), r.shapes()):
        d = dict(zip(fields, rec))
        k = str(d.get("No_Block") or "").strip().upper().replace(" ", "")
        if k:
            hasil[k] = {"geom": shp_shape(sh.__geo_interface__),
                        "kode_shp": str(d.get("BLOK_Baru") or "")}
    return hasil


def komposit(arr):
    rgb = arr[:3].transpose(1, 2, 0).astype("float64")
    if arr.shape[0] >= 4:
        a = arr[3:4].transpose(1, 2, 0) / 255.0
        rgb = rgb * a + 255 * (1 - a)
    return rgb.astype("uint8")


def _titik(g):
    if g.is_empty:
        return []
    if g.geom_type == "Point":
        return [g]
    return [p for p in getattr(g, "geoms", []) if p.geom_type == "Point"]


def titik_timur_barat(g, yu):
    """Potongan garis horizontal y=yu dengan batas poligon: (x paling barat, x paling timur)."""
    minx, miny, maxx, maxy = g.bounds
    ln = LineString([(minx - 100, yu), (maxx + 100, yu)])
    xs = sorted(p.x for p in _titik(ln.intersection(g.boundary)))
    return (xs[0], xs[-1]) if len(xs) >= 2 else None


def titik_utara_selatan(g, xv):
    """Potongan garis vertikal x=xv dengan batas poligon: (y selatan, y utara)."""
    minx, miny, maxx, maxy = g.bounds
    ln = LineString([(xv, miny - 100), (xv, maxy + 100)])
    ys = sorted(p.y for p in _titik(ln.intersection(g.boundary)))
    return (ys[0], ys[-1]) if len(ys) >= 2 else None


def _ke_px(inv, g, off=(0, 0), skala=None):
    rings = []
    parts = g.geoms if g.geom_type == "MultiPolygon" else [g]
    for pt in parts:
        ring = []
        for x, y in pt.exterior.coords:
            c, r = inv @ (x, y)
            ring.append(((c - off[0]) * skala, (r - off[1]) * skala) if skala
                        else (c - off[0], r - off[1]))
        rings.append(ring)
    return rings


def _render_kartu(kode, divisi, g_pdf, info_shp, rgb_path, out_png, font_b, font_m, font_s,
                  residual_m=None):
    g_shp = info_shp["geom"] if info_shp else None
    iou = g_pdf.intersection(g_shp).area / g_pdf.union(g_shp).area * 100 if g_shp else None
    geser = g_pdf.centroid.distance(g_shp.centroid) if g_shp else None

    minx, miny, maxx, maxy = g_pdf.bounds
    cx = (minx + maxx) / 2
    y25 = maxy - (maxy - miny) * 0.25
    y75 = maxy - (maxy - miny) * 0.75
    xb25 = titik_timur_barat(g_pdf, y25) or (minx, maxx)
    xb75 = titik_timur_barat(g_pdf, y75) or (minx, maxx)
    yns = titik_utara_selatan(g_pdf, cx) or (miny, maxy)
    spec = [
        (xb25[0], y25, "1 - tepi barat atas (25%)"),
        (xb25[1], y25, "3 - tepi timur atas (25%)"),
        (xb75[0], y75, "2 - tepi barat bawah (75%)"),
        (xb75[1], y75, "4 - tepi timur bawah (75%)"),
        (cx, yns[1], "5 - tepi utara (tengah)"),
        (cx, yns[0], "6 - tepi selatan (tengah)"),
    ]

    with rasterio.open(rgb_path) as ds:
        inv = ~ds.transform
        gsd_cm = abs(ds.transform.a) * 100
        W = max(1, round(HSTRIP * ds.width / ds.height))
        strip = komposit(ds.read(out_shape=(min(4, ds.count), HSTRIP, W)))
        s = W / ds.width
        ww, hh = min(WINS, ds.width), min(HINS, ds.height)

        insets = []
        for xb, yb, nama in spec:
            col, row = inv @ (xb, yb)
            col = max(0, min(int(round(col - WINS / 2)), ds.width - ww))
            row = max(0, min(int(round(row - HINS / 2)), ds.height - hh))
            img = Image.fromarray(komposit(ds.read(window=Window(col, row, ww, hh))))
            d = ImageDraw.Draw(img)
            if g_shp:
                for ring in _ke_px(inv, g_shp, (col, row)):
                    d.line(ring, fill=(0, 90, 255), width=3)
            for ring in _ke_px(inv, g_pdf, (col, row)):
                d.line(ring, fill=(255, 0, 0), width=3)
            d.rectangle([0, 0, ww - 1, hh - 1], outline=(40, 40, 40), width=2)
            d.text((10, 6), nama, font=font_m, fill=(255, 255, 255),
                   stroke_width=2, stroke_fill=(0, 0, 0))
            insets.append(img)

    strip_img = Image.fromarray(strip)
    dstrip = ImageDraw.Draw(strip_img)
    if g_shp:
        for ring in _ke_px(inv, g_shp, skala=s):
            dstrip.line(ring, fill=(0, 90, 255), width=3)
    for ring in _ke_px(inv, g_pdf, skala=s):
        dstrip.line(ring, fill=(255, 0, 0), width=3)
    for xb, yb, nama in spec:
        c, r = inv @ (xb, yb)
        px, py = c * s, r * s
        dstrip.ellipse([px - 7, py - 7, px + 7, py + 7], fill=(255, 210, 0),
                       outline=(0, 0, 0), width=2)
        dstrip.text((px + 9, py - 22), nama.split(" ")[0], font=font_m,
                    fill=(255, 210, 0), stroke_width=2, stroke_fill=(0, 0, 0))
    dstrip.rectangle([0, 0, strip_img.width - 1, strip_img.height - 1],
                     outline=(30, 30, 30), width=1)

    pad, top = 16, 76
    grid_h = 3 * HINS + 2 * 30
    Wc = pad * 2 + strip_img.width + 20 + 2 * WINS + 14 + 8
    Hc = top + max(strip_img.height, grid_h) + 78
    cv = Image.new("RGB", (Wc, Hc), (248, 248, 248))
    dr = ImageDraw.Draw(cv)
    dr.text((pad, 14), f"Kartu validasi blok {kode} - div {divisi}", font=font_b, fill=(15, 15, 15))
    dr.text((pad, 46), "merah = batas ekstraksi peta PDF (dipakai crop)  |  "
                       "biru = batas shp Tanam Inti (No_Block)", font=font_s, fill=(60, 60, 60))
    cv.paste(strip_img, (pad, top))
    gx = pad + strip_img.width + 20
    for i, img in enumerate(insets):
        rr, cc = divmod(i, 2)
        cv.paste(img, (gx + cc * (WINS + 14), top + rr * (HINS + 30)))
    if g_shp:
        kaki = (f"luas PDF {g_pdf.area/1e4:.2f} ha vs shp {g_shp.area/1e4:.2f} ha  |  "
                f"IoU {iou:.1f}%  |  geser titik tengah {geser:.1f} m  |  shp: {info_shp['kode_shp']}")
    else:
        kaki = (f"luas PDF {g_pdf.area/1e4:.2f} ha  |  "
                f"shp tidak ditemukan untuk No_Block={kode}")
    dr.text((pad, Hc - 46), kaki, font=font_m, fill=(20, 20, 20))
    dr.text((pad, Hc - 23), _baris_konteks(gsd_cm, residual_m), font=font_s, fill=(90, 90, 90))
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    cv.save(out_png)

    return {"kode": kode, "divisi": divisi, "file": Path(out_png).name,
            "luas_pdf_ha": round(g_pdf.area / 1e4, 2),
            "luas_shp_ha": round(g_shp.area / 1e4, 2) if g_shp else None,
            "iou": round(iou, 1) if iou is not None else None,
            "geser_m": round(geser, 1) if geser is not None else None,
            "kode_shp": info_shp["kode_shp"] if info_shp else None,
            "gsd_cm": round(gsd_cm, 2),
            "residual_m": residual_m}


def buat_kartu(output_root, geojson_path, kode_flight, path_shp=None,
               hanya=None, dest=None, progress=None, path_kalibrasi=None):
    """Buat kartu untuk setiap blok yang folder hasilnya ada di output_root.

    hanya: set kode blok yang dibatasi (opsional). progress: callback(i, n, kode).
    """
    from core.layer_scan import folder_blok
    gj = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    shp_map = muat_shp(path_shp) if path_shp and Path(path_shp).exists() else {}
    residual_m = None
    if path_kalibrasi and Path(path_kalibrasi).exists():
        kal = json.loads(Path(path_kalibrasi).read_text(encoding="utf-8"))
        if kal.get("residual_max_m") is not None:
            residual_m = float(kal["residual_max_m"])
    dest = Path(dest) if dest else Path(output_root) / "_validasi"
    dest.mkdir(parents=True, exist_ok=True)
    font_b, font_m, font_s = _font(24, True), _font(18, True), _font(16, False)

    dipilih, dilewati = [], []
    for f in gj["features"]:
        p = f["properties"]
        kode = p["kode"]
        if hanya and kode not in hanya:
            continue
        divisi = p.get("divisi") or "TANPA_DIVISI"
        dir_blok = folder_blok(output_root, kode_flight, divisi, kode)
        rgb = next(iter(sorted(dir_blok.glob("Orthomosaic - *.rgb.tif"))), None) \
            if dir_blok.exists() else None
        if rgb is None:
            dilewati.append({"kode": kode, "alasan": "folder hasil / Orthomosaic rgb tidak ada"})
            continue
        dipilih.append((kode, divisi, f, rgb))

    dipilih.sort(key=lambda t: (t[1], t[0]))
    kartu_list = []
    for i, (kode, divisi, f, rgb) in enumerate(dipilih, 1):
        if progress:
            progress(i, len(dipilih), kode)
        entri = _render_kartu(kode, divisi, shp_shape(f["geometry"]),
                              shp_map.get(kode.upper().strip()), rgb,
                              dest / f"kartu_{kode}.png", font_b, font_m, font_s,
                              residual_m=residual_m)
        kartu_list.append(entri)

    idx = {"dibuat": datetime.now().isoformat(timespec="seconds"),
           "kode_flight": kode_flight, "sumber_output": str(output_root),
           "shp": str(path_shp) if shp_map else None,
           "kartu": kartu_list, "dilewati": dilewati}
    (dest / "index.json").write_text(json.dumps(idx, indent=1, ensure_ascii=False),
                                     encoding="utf-8")
    return {"dest": str(dest), "kartu": len(kartu_list), "dilewati": dilewati}


def main():
    from core.config import ROOT
    ap = argparse.ArgumentParser(description="Buat kartu validasi per blok")
    ap.add_argument("--output", required=True, help="folder output hasil ekspor")
    ap.add_argument("--geojson", default=str(ROOT / "data" / "blok.geojson"))
    ap.add_argument("--kode-flight", required=True)
    ap.add_argument("--shp", default=None, help="path shp kebun (opsional)")
    ap.add_argument("--kode", default=None, help="batasi ke kode tertentu, dipisah koma")
    ap.add_argument("--dest", default=None, help="folder kartu (default: <output>/_validasi)")
    ap.add_argument("--kalibrasi", default=str(ROOT / "data" / "kalibrasi.json"),
                    help="kalibrasi.json untuk footer konteks (residual)")
    a = ap.parse_args()
    hanya = {x.strip() for x in a.kode.split(",")} if a.kode else None
    hasil = buat_kartu(a.output, a.geojson, a.kode_flight, path_shp=a.shp,
                       hanya=hanya, dest=a.dest, path_kalibrasi=a.kalibrasi,
                       progress=lambda i, n, k: print(f"[{i}/{n}] kartu {k}"))
    print(f"selesai: {hasil['kartu']} kartu -> {hasil['dest']}; dilewati {len(hasil['dilewati'])}")
    for d in hasil["dilewati"][:10]:
        print(f"  dilewati {d['kode']}: {d['alasan']}")


if __name__ == "__main__":
    main()
