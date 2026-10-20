import numpy as np, pymupdf, rasterio
from rasterio.transform import from_origin
from PIL import Image
from core import qa_overlay


def _pdf_kecil(tmp_path):
    doc = pymupdf.open()
    doc.new_page(width=200, height=200)
    p = tmp_path / "mini.pdf"
    doc.save(str(p))
    doc.close()
    return p


def test_render_pdf_overlay_multi_ring(tmp_path):
    """Fitur MultiPolygon (sel peta multi-ring seperti G29) harus tergambar
    semua bagiannya, bukan crash di .exterior."""
    from shapely.geometry import Polygon, MultiPolygon
    pdf = _pdf_kecil(tmp_path)
    m = MultiPolygon([Polygon([(10, 10), (60, 10), (60, 60), (10, 60)]),
                      Polygon([(100, 100), (150, 100), (150, 150), (100, 150)])])
    out = tmp_path / "ov.png"
    qa_overlay.render_pdf_overlay(pdf, [(m, "G29")], str(out), zoom=1.0)
    a = np.array(Image.open(str(out)))
    merah = (a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] < 60)
    assert merah[:80, :80].sum() > 50
    assert merah[90:, 90:].sum() > 50


def test_render_pdf_overlay_biru_shp_oranye_pdf(tmp_path):
    """Mode peta batas: kode ber-fragmen shp digambar biru (batas dipakai crop),
    kode tanpa shp digambar oranye; poligon PDF kode ber-shp tidak digambar ulang."""
    from shapely.geometry import Polygon
    pdf = _pdf_kecil(tmp_path)
    sel_shp = Polygon([(20, 20), (60, 20), (60, 60), (20, 60)])
    sel_pdf_sama_shp = Polygon([(24, 24), (64, 24), (64, 64), (24, 64)])
    sel_pdf_tanpa_shp = Polygon([(100, 100), (140, 100), (140, 140), (100, 140)])
    out = tmp_path / "ov.png"
    qa_overlay.render_pdf_overlay(
        pdf, [(sel_pdf_sama_shp, "X1"), (sel_pdf_tanpa_shp, "X2")],
        str(out), zoom=1.0, fitur_shp_pt=[(sel_shp, "X1")])
    a = np.array(Image.open(str(out)))
    biru = (a[..., 2] > 200) & (a[..., 0] < 60) & (a[..., 1] < 120)
    oranye = (a[..., 0] > 200) & (a[..., 1] > 90) & (a[..., 1] < 170) & (a[..., 2] < 60)
    assert biru.sum() > 50
    assert oranye[90:, 90:].sum() > 50
    assert oranye[:90, :90].sum() == 0


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
