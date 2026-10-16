import re
from pathlib import Path
import rasterio

ROLE_LAYER = ("ortho", "ndre", "nir", "rededge", "dsm")

# output/sumber per ha terukur pada batch Gate 2 (lihat laporan/_uji_d17/RINGKASAN.md):
# 24.708.559.348 B / (38.287.432.957 B / 257,9 ha × 197,63 ha) ≈ 0,84
RASIO_KOMPRESI_GATE2 = 0.84

# blok dengan cakupan footprint ortho di bawah ini dianggap tanpa data (mis. hanya
# tersenggol tepi bbox ortho). Bukti: pada flight DBE I, blok tersenggol 0,00–0,01%,
# blok berdata nyata ≥95,9% — jurang lebar, 25% aman dari keduanya.
AMBANG_BLOK_BERDATA = 25.0

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

def _pasangan(f):
    """Untuk <NAME>.data.tif → cek sibling <NAME>.rgb.tif / <NAME>.legend.png (pola ekspor app)."""
    nama = f.name
    base = nama[:-len(".data.tif")] if nama.lower().endswith(".data.tif") else nama.rsplit(".", 1)[0]
    rgb = f.with_name(base + ".rgb.tif")
    legend = f.with_name(base + ".legend.png")
    return (str(rgb) if rgb.exists() else None,
            str(legend) if legend.exists() else None)

def scan_folder(folder):
    hasil = {"layers": {}, "ditolak": []}
    for f in sorted(Path(folder).glob("*")):
        if not f.is_file():
            continue
        low = f.name.lower()
        if low.endswith(".rgb.tif") or low.endswith(".rgb.tiff") or low.endswith(".legend.png"):
            continue        # artefak pendamping ekspor app — bukan layer sumber
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
        rgb, legend = _pasangan(f)
        meta["rgb"] = rgb
        meta["legend"] = legend
        hasil["layers"][peran] = meta
    return hasil

def blok_dalam_cakupan(geojson, bounds):
    from shapely.geometry import shape, box
    b = box(*bounds)
    return [f for f in geojson["features"] if shape(f["geometry"]).intersects(b)]

def topeng_footprint(path_data, maks_dim=1024):
    """Topeng area berdata layer (mask band terakhir > 0) + grid & luasnya.

    Dibaca ter-undersample (sisi terpanjang ≤ maks_dim px) agar murah pada
    file multi-GB; akurasi ±beberapa persen cukup untuk pra-cek disk/blok.
    """
    with rasterio.open(path_data) as ds:
        f = min(1.0, maks_dim / max(ds.width, ds.height))
        h = max(1, round(ds.height * f))
        w = max(1, round(ds.width * f))
        mask = ds.read(ds.count, out_shape=(h, w)) > 0
        transform = ds.transform @ rasterio.Affine.scale(ds.width / w, ds.height / h)
        px_m2 = abs(transform.a * transform.e)
    return {"mask": mask, "transform": transform, "px_m2": px_m2,
            "h": h, "w": w, "luas_ha": float(mask.sum()) * px_m2 / 1e4}


def luas_footprint_ha(path_data, maks_dim=1024):
    return topeng_footprint(path_data, maks_dim)["luas_ha"]


def poligon_footprint(topeng):
    """Poligon area berdata dari topeng (bahan "bentang" kartu mode blok penuh).

    Diberi margin ke luar 1,5 px-topeng agar tepi flight tidak tergunting
    tangga piksel; piksel di luar data memang alpha=0 sehingga tak ikut ter-ekspor.
    """
    from rasterio.features import shapes
    from shapely.geometry import shape
    from shapely.ops import unary_union
    m = topeng["mask"]
    if not m.any():
        return None
    geoms = [shape(g) for g, v in
             shapes(m.astype("uint8"), mask=m, transform=topeng["transform"]) if v]
    if not geoms:
        return None
    return unary_union(geoms).buffer(1.5 * topeng["px_m2"] ** 0.5)


def saring_blok_berdata(features, topeng, ambang=AMBANG_BLOK_BERDATA):
    """Pisahkan blok berdata (≥ ambang % luasnya tertutup footprint) vs diabaikan.

    Return (simpan, buang); buang berisi {"kode", "cakupan_persen"} — blok yang
    hanya tersenggol tepi ortho tanpa piksel berdata nyata (senyap sebelum ini).
    """
    from rasterio.features import geometry_mask
    from shapely.geometry import mapping, shape
    simpan, buang = [], []
    for fb in features:
        geom = shape(fb["geometry"])
        if geom.area <= 0:
            cakupan = 0.0
        else:
            gm = geometry_mask([mapping(geom)], out_shape=(topeng["h"], topeng["w"]),
                               transform=topeng["transform"], invert=True)
            cakupan = float((topeng["mask"] & gm).sum()) * topeng["px_m2"] / geom.area * 100.0
        if cakupan >= ambang:
            simpan.append(fb)
        else:
            buang.append({"kode": fb["properties"]["kode"], "cakupan_persen": round(cakupan, 2)})
    return simpan, buang

def estimasi_byte_output(byte_src, luas_blok_ha, luas_footprint_ha,
                         rasio=RASIO_KOMPRESI_GATE2):
    """Estimasi ukuran output: byte sumber per ha footprint × luas blok × rasio."""
    if luas_footprint_ha <= 0:
        raise ValueError("Luas footprint sumber nol — tidak bisa mengestimasi disk")
    return int(byte_src / luas_footprint_ha * luas_blok_ha * rasio)

def nama_base(layer, nama_blok):
    if layer == "ortho": return f"Orthomosaic - {nama_blok}"
    if layer == "dsm": return f"Surface model - {nama_blok}"
    return {"ndre": "NDRE", "nir": "NIR", "rededge": "RedEdge"}[layer]

def folder_blok(output_root, kode_flight, divisi, kode):
    divisi = divisi or "TANPA_DIVISI"
    return Path(output_root) / divisi / f"{kode_flight}_{divisi.replace(' ', '')}-{kode}"

def rencana_output(features, layers, output_root, kode_flight):
    from shapely.geometry import shape, box
    rows = []
    for f in features:
        p = f["properties"]
        geom = shape(f["geometry"])
        divisi = p.get("divisi") or "TANPA_DIVISI"
        dst_dir = folder_blok(output_root, kode_flight, divisi, p["kode"])
        nama_blok = dst_dir.name
        for layer, info in layers.items():
            base = nama_base(layer, nama_blok)
            row = {"divisi": divisi, "kode": p["kode"], "layer": layer,
                   "src_data": info["data"], "nama_base": base,
                   "src_rgb": info.get("rgb"), "src_legend": info.get("legend"),
                   "dst_dir": str(dst_dir),
                   "dst_data": str(dst_dir / f"{base}.data.tif"),
                   "dst_rgb": str(dst_dir / f"{base}.rgb.tif"),
                   "dst_legend": None if layer == "ortho"
                                 else str(dst_dir / f"{base}.legend.png")}
            b = info.get("bounds")
            if b is not None and not geom.intersects(box(*b)):
                row["status"] = "dilewati"
                row["error"] = "tanpa data (di luar cakupan layer)"
            rows.append(row)
    return rows
