from pathlib import Path
import numpy as np
import pymupdf
from PIL import Image, ImageDraw

MAKS_DIM_OVERLAY = 1600


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
