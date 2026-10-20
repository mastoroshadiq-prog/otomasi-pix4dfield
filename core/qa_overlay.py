from pathlib import Path
import numpy as np
import pymupdf
from PIL import Image, ImageDraw

MAKS_DIM_OVERLAY = 1600


def _gambar_geom(dr, geom, zoom, warna, lebar):
    for p in (geom.geoms if geom.geom_type == "MultiPolygon" else [geom]):
        xy = [(x * zoom, y * zoom) for x, y in p.exterior.coords]
        if len(xy) >= 2:
            dr.line(xy, fill=warna, width=lebar)


def render_pdf_overlay(pdf_path, fitur_pt, out_png, zoom=0.5, fitur_shp_pt=None):
    """fitur_pt: list (shapely Polygon/MultiPolygon dalam pt PDF, kode).

    fitur_shp_pt (opsional): list (geom pt, kode) batas dari fragmen shp Tanam
    Inti — digambar biru. Dalam mode ini poligon PDF untuk kode yang batasnya
    dari shp dilewati, kode tanpa shp digambar oranye (batas dari peta PDF)."""
    doc = pymupdf.open(str(pdf_path))
    pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    dr = ImageDraw.Draw(img)
    kode_shp = {k for _, k in fitur_shp_pt} if fitur_shp_pt else set()
    for geom, _ in (fitur_shp_pt or []):
        _gambar_geom(dr, geom, zoom, (0, 70, 255), 2)
    for geom, kode in fitur_pt:
        if kode in kode_shp:
            continue
        warna = (255, 130, 0) if fitur_shp_pt is not None else (255, 0, 0)
        _gambar_geom(dr, geom, zoom, warna, 3 if fitur_shp_pt is not None else 2)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)


def render_blok_overlay(rgb_tif, geom_wkt, out_png, maks_dim=MAKS_DIM_OVERLAY):
    """Pratinjau rgb + garis batas blok (merah).

    Kartu blok penuh bisa puluhan–ratusan MP; citra dibaca ter-downsample
    (sisi terpanjang ≤ maks_dim px) agar hemat memori, koordinat blok
    dipetakan ulang lewat bounds.
    """
    import rasterio
    from rasterio.enums import Resampling
    from shapely import wkt
    geom = wkt.loads(geom_wkt)
    with rasterio.open(rgb_tif) as ds:
        f = min(1.0, maks_dim / max(ds.width, ds.height))
        if f < 1.0:
            h, w = max(1, round(ds.height * f)), max(1, round(ds.width * f))
            arr = ds.read([1, 2, 3], out_shape=(3, h, w), resampling=Resampling.average)
        else:
            arr = ds.read([1, 2, 3])
        kiri, atas, kanan, bawah = ds.bounds
    img = Image.fromarray(np.transpose(arr, (1, 2, 0)))
    dr = ImageDraw.Draw(img)
    for pt in (geom.geoms if geom.geom_type == "MultiPolygon" else [geom]):
        px = [((x - kiri) / (kanan - kiri) * img.width,
               (atas - y) / (atas - bawah) * img.height) for x, y in pt.exterior.coords]
        dr.line(px, fill=(255, 0, 0), width=2)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
