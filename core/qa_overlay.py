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
