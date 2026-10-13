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
