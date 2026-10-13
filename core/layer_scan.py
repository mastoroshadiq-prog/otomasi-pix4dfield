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

def nama_base(layer, nama_blok):
    if layer == "ortho": return f"Orthomosaic - {nama_blok}"
    if layer == "dsm": return f"Surface model - {nama_blok}"
    return {"ndre": "NDRE", "nir": "NIR", "rededge": "RedEdge"}[layer]

def folder_blok(output_root, kode_flight, divisi, kode):
    divisi = divisi or "TANPA_DIVISI"
    return Path(output_root) / divisi / f"{kode_flight}_{divisi.replace(' ', '')}-{kode}"

def rencana_output(features, layers, output_root, kode_flight):
    rows = []
    for f in features:
        p = f["properties"]
        divisi = p.get("divisi") or "TANPA_DIVISI"
        dst_dir = folder_blok(output_root, kode_flight, divisi, p["kode"])
        nama_blok = dst_dir.name
        for layer, info in layers.items():
            base = nama_base(layer, nama_blok)
            rows.append({"divisi": divisi, "kode": p["kode"], "layer": layer,
                         "src_data": info["data"], "nama_base": base,
                         "src_rgb": info.get("rgb"), "src_legend": info.get("legend"),
                         "dst_dir": str(dst_dir),
                         "dst_data": str(dst_dir / f"{base}.data.tif"),
                         "dst_rgb": str(dst_dir / f"{base}.rgb.tif"),
                         "dst_legend": None if layer == "ortho"
                                       else str(dst_dir / f"{base}.legend.png")})
    return rows
