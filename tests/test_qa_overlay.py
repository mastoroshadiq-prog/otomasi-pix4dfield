import numpy as np, rasterio
from rasterio.transform import from_origin
from PIL import Image
from core import qa_overlay

def test_overlay_terbentuk(tmp_path):
    t = from_origin(300000, 9960000, 1, 1)
    arr = np.full((3, 100, 100), 200, dtype="uint8")
    rgb = tmp_path / "rgb.tif"
    with rasterio.open(rgb, "w", driver="GTiff", width=100, height=100, count=3,
                       dtype="uint8", crs="EPSG:32749", transform=t) as ds:
        ds.write(arr)
    out = tmp_path / "ov.png"
    qa_overlay.render_blok_overlay(str(rgb),
        "POLYGON((300010 9959960, 300050 9959960, 300050 9959990, 300010 9959990, 300010 9959960))",
        str(out))
    assert out.exists() and out.stat().st_size > 0
    a = np.array(Image.open(out))
    assert a.shape == (100, 100, 3)
    merah = (a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] < 60)
    assert merah.sum() > 100          # garis overlay benar-benar tergambar


def test_overlay_kartu_besar_terdownsample(tmp_path):
    """Kartu besar (4000×2000) harus dibaca turun-sampel ≤1600 px agar tidak memuat
    ratusan MB; garis blok tetap terbaca."""
    t = from_origin(300000, 9960000, 1, 1)
    arr = np.full((3, 2000, 4000), 200, dtype="uint8")
    rgb = tmp_path / "rgb_besar.tif"
    with rasterio.open(rgb, "w", driver="GTiff", width=4000, height=2000, count=3,
                       dtype="uint8", crs="EPSG:32749", transform=t) as ds:
        ds.write(arr)
    out = tmp_path / "ov_besar.png"
    qa_overlay.render_blok_overlay(str(rgb),
        "POLYGON((301000 9958500, 303000 9958500, 303000 9959500, 301000 9959500, 301000 9958500))",
        str(out))
    a = np.array(Image.open(out))
    assert max(a.shape[:2]) <= 1600
    merah = (a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] < 60)
    assert merah.sum() > 100
