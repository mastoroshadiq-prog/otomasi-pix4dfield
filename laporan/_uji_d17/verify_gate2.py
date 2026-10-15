"""Verifikasi pasca-batch Gate 2 (FLG01-AMEIII_auto).

Cek per item: data piksel-eksak di dalam poligon & nodata di luarnya,
rgb mendekati sumber (derau JPEG) + alpha 0 di luar, legend md5 identik,
overview ada. Output: gate2_verifikasi.json + montase pratinjau.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds
from shapely import wkt

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
OUT = Path(r"F:\dataset\Pix4DField-export-FLG01-AMEIII_auto")
HASIL = Path(__file__).resolve().parent / "gate2_verifikasi.json"


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for blok in iter(lambda: f.read(1 << 20), b""):
            h.update(blok)
    return h.hexdigest()


def _cek_grid(ss, dd, src, dst):
    """Grid output harus sama dengan jendela sumber: CRS + transform penuh (a..f)."""
    assert ss.crs == dd.crs, f"CRS beda: {src} vs {dst}"
    win = from_bounds(*dd.bounds, transform=ss.transform)
    t_harap = ss.window_transform(win)
    for at in "abcdef":
        a, b = getattr(t_harap, at), getattr(dd.transform, at)
        assert abs(a - b) < 1e-6, f"grid beda: {src} vs {dst} (transform.{at}: {a} vs {b})"


def cek_data(src, dst, geom_wkt):
    """float32: di dalam poligon identik dgn sumber; di luar = nodata."""
    g = wkt.loads(geom_wkt)
    with rasterio.open(src) as ss, rasterio.open(dst) as dd:
        _cek_grid(ss, dd, src, dst)
        win = from_bounds(*dd.bounds, transform=ss.transform)
        col, row0 = round(win.col_off), round(win.row_off)
        nod = dd.nodata if dd.nodata is not None else -10000.0
        maks = 0.0
        n_in = n_out_buruk = 0
        for row in range(0, dd.height, 2048):
            h = min(2048, dd.height - row)
            w = Window(0, row, dd.width, h)
            a = dd.read(window=w)
            b = ss.read(window=Window(col, row0 + row, dd.width, h))
            m = geometry_mask([g], out_shape=(h, dd.width),
                              transform=dd.window_transform(w), invert=True)
            d = np.abs(a.astype("float64") - b.astype("float64"))
            if m.any():
                maks = max(maks, float(d[:, m].max()))
                n_in += int(m.sum())
            luar = ~m
            n_out_buruk += int(((a != nod) & luar[None, :, :]).any(axis=0).sum())
        n_over = len(dd.overviews(1))
        comp = dd.compression.value if dd.compression else "none"
    return {"max_diff_dalam": maks, "n_piksel_dalam": n_in,
            "n_luar_bukan_nodata": n_out_buruk, "n_overview": n_over,
            "compression": comp, "ukuran": Path(dst).stat().st_size}


def cek_rgb_sederhana(src, dst, geom_wkt):
    g = wkt.loads(geom_wkt)
    with rasterio.open(src) as ss, rasterio.open(dst) as dd:
        _cek_grid(ss, dd, src, dst)
        px = abs(dd.transform.a)
        buf = 3 * px
        win = from_bounds(*dd.bounds, transform=ss.transform)
        col, row0 = round(win.col_off), round(win.row_off)
        luar_ge = g.buffer(buf)
        dalam_ge = g.buffer(-buf)
        n_luar = n_luar_buruk = 0
        maks_luar_alpha = 0
        s_jml, s_n, s_maks = 0.0, 0, 0
        for row in range(0, dd.height, 2048):
            h = min(2048, dd.height - row)
            w = Window(0, row, dd.width, h)
            a = dd.read(window=w).astype("int16")
            b = ss.read(window=Window(col, row0 + row, dd.width, h)).astype("int16")
            tr = dd.window_transform(w)
            m_luar = ~geometry_mask([luar_ge], out_shape=(h, dd.width), transform=tr, invert=True)
            m_dalam = geometry_mask([dalam_ge], out_shape=(h, dd.width), transform=tr, invert=True)
            al = a[3][m_luar]
            if al.size:
                maks_luar_alpha = max(maks_luar_alpha, int(al.max()))
                n_luar += al.size
                n_luar_buruk += int((al > 8).sum())
            d = np.abs(a[:3][:, m_dalam] - b[:3][:, m_dalam])
            if d.size:
                s_jml += float(d.sum())
                s_n += d.size
                s_maks = max(s_maks, int(d.max()))
    return {"alpha_luar_max": maks_luar_alpha, "n_luar": n_luar,
            "n_luar_alpha_gt8": n_luar_buruk,
            "rgb_dalam_mean": (s_jml / s_n) if s_n else 0.0,
            "rgb_dalam_max": s_maks, "ukuran_rgb": Path(dst).stat().st_size}


def main():
    state = json.loads((OUT / "state.json").read_text(encoding="utf-8"))
    items = state["items"]
    geom_blok = state.get("geom_blok", {})     # state v2; state lama menyimpan geom per item
    hasil = {"n_item": len(items),
             "selesai": sum(1 for i in items if i["status"] == "selesai"),
             "gagal": [(i["kode"], i["layer"], i["error"]) for i in items if i["status"] == "gagal"],
             "per_item": {}, "legend_gagal": [], "ringkas": {}}
    print(f"state: {hasil['selesai']}/{hasil['n_item']} selesai, gagal: {hasil['gagal']}")

    for i, it in enumerate(items):
        k, lay = it["kode"], it["layer"]
        rec = hasil["per_item"].setdefault(k, {})
        rec[lay] = {"ukuran": it["size"], "dur_s": round(it["dur_s"], 1)}
        g = geom_blok.get(k) or it.get("geom", "")
        assert g, f"geom tidak ditemukan untuk {k} (state v2 tanpa geom_blok?)"
        try:
            rec[lay].update(cek_data(it["src_data"], it["dst_data"], g))
            src_rgb = it.get("src_rgb")
            if src_rgb:
                rec[lay].update(cek_rgb_sederhana(src_rgb, it["dst_rgb"], g))
            if it.get("dst_legend"):
                if not Path(it["dst_legend"]).exists():
                    hasil["legend_gagal"].append((k, lay, "hilang"))
                elif md5(it["src_legend"]) != md5(it["dst_legend"]):
                    hasil["legend_gagal"].append((k, lay, "beda byte"))
        except Exception as e:
            rec[lay]["error_verifikasi"] = str(e)
        print(f"  [{i+1}/{len(items)}] {k}/{lay} ok", flush=True)

    # ringkasan angka
    luas = {}
    gj = json.loads((ROOT / "data" / "blok.geojson").read_text(encoding="utf-8"))
    for f in gj["features"]:
        luas[f["properties"]["kode"]] = f["properties"]["luas_ha"]
    tmax_dalam = 0.0
    t_luar = 0
    t_dalam_mean = 0.0
    n_dalam = 0
    tot = 0
    n_err = 0
    for k, rec in hasil["per_item"].items():
        for lay, v in rec.items():
            if "error_verifikasi" in v:
                n_err += 1
                continue
            tot += v.get("ukuran", 0)
            tmax_dalam = max(tmax_dalam, v.get("max_diff_dalam", 0.0))
            t_luar += v.get("n_luar_bukan_nodata", 0)
            if "rgb_dalam_mean" in v:
                t_dalam_mean += v["rgb_dalam_mean"] * max(v.get("n_piksel_dalam", 1), 1)
                n_dalam += max(v.get("n_piksel_dalam", 1), 1)
    hasil["ringkas"] = {"n_error_verifikasi": n_err,
                        "max_diff_data_semua": tmax_dalam,
                        "n_luar_bukan_nodata": t_luar,
                        "rgb_mean_tertimbang": (t_dalam_mean / n_dalam) if n_dalam else None,
                        "total_byte_data": tot,
                        "luas_ha": sum(luas.get(k, 0) for k in hasil["per_item"])}
    HASIL.write_text(json.dumps(hasil, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\nRINGKASAN:", json.dumps(hasil["ringkas"], indent=1))
    ok = hasil["selesai"] == hasil["n_item"] and not hasil["gagal"] and not hasil["legend_gagal"] \
        and n_err == 0 and tmax_dalam == 0.0 and t_luar == 0
    print("VERIFIKASI:", "LOLOS" if ok else "PERIKSA DETAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
