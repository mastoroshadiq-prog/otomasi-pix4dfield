import json
import numpy as np
import rasterio
import shapefile
from PIL import Image
from rasterio.transform import from_origin

from core import kartu

POLY = [[300000.0, 9959400.0], [300200.0, 9959400.0], [300200.0, 9960000.0],
        [300000.0, 9960000.0], [300000.0, 9959400.0]]


def _buat_raster(path, h=600, w=200):
    t = from_origin(300000, 9960000, 1, 1)
    arr = np.zeros((4, h, w), dtype="uint8")
    arr[0] = 60
    arr[1] = 140
    arr[2] = 70
    arr[3] = 255
    with rasterio.open(path, "w", driver="GTiff", width=w, height=h, count=4,
                       dtype="uint8", crs="EPSG:32749", transform=t) as ds:
        ds.write(arr)


def _siapkan_output(tmp_path, kode="D13", divisi="AME III", kode_flight="TST01"):
    out = tmp_path / "out"
    dir_blok = out / divisi / f"{kode_flight}_{divisi.replace(' ', '')}-{kode}"
    dir_blok.mkdir(parents=True)
    _buat_raster(dir_blok / f"Orthomosaic - {dir_blok.name}.rgb.tif")
    return out


def _tulis_geojson(path, fitur):
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": p,
         "geometry": {"type": "Polygon", "coordinates": [POLY]}} for p in fitur]}
    path.write_text(json.dumps(gj), encoding="utf-8")
    return path


def test_kartu_dan_index_terbentuk(tmp_path):
    out = _siapkan_output(tmp_path)
    gj = _tulis_geojson(tmp_path / "blok.geojson", [
        {"kode": "D13", "divisi": "AME III"},
        {"kode": "D99", "divisi": "AME III"},          # folder tidak ada → dilewati
    ])
    h = kartu.buat_kartu(str(out), str(gj), "TST01", path_shp=None, dest=str(tmp_path / "kartu"))
    assert h["kartu"] == 1
    assert [d["kode"] for d in h["dilewati"]] == ["D99"]
    png = tmp_path / "kartu" / "kartu_D13.png"
    assert png.exists()
    a = np.array(Image.open(png))
    assert a.shape[0] > 1000 and a.shape[1] > 1000
    hijau = (a[..., 0] == 60) & (a[..., 1] == 140) & (a[..., 2] == 70)
    assert hijau.sum() > 1000                        # citra benar-benar tertempel di kartu
    idx = json.loads((tmp_path / "kartu" / "index.json").read_text(encoding="utf-8"))
    k = idx["kartu"][0]
    assert k["kode"] == "D13" and k["file"] == "kartu_D13.png"
    assert abs(k["luas_pdf_ha"] - 12.0) < 0.01
    assert k["iou"] is None and k["luas_shp_ha"] is None


def test_kartu_dengan_shp_menghitung_iou(tmp_path):
    out = _siapkan_output(tmp_path)
    gj = _tulis_geojson(tmp_path / "blok.geojson", [{"kode": "D13", "divisi": "AME III"}])
    shp_p = tmp_path / "kebun.shp"
    w = shapefile.Writer(str(shp_p), shapeType=shapefile.POLYGON)
    w.field("No_Block", "C")
    w.field("BLOK_Baru", "C")
    w.poly([POLY])
    w.record("D13", "D013A")
    w.close()
    kartu.buat_kartu(str(out), str(gj), "TST01", path_shp=str(shp_p), dest=str(tmp_path / "kartu"))
    idx = json.loads((tmp_path / "kartu" / "index.json").read_text(encoding="utf-8"))
    k = idx["kartu"][0]
    assert k["iou"] is not None and k["iou"] > 99.0
    assert k["kode_shp"] == "D013A"
    assert abs(k["luas_shp_ha"] - 12.0) < 0.01


def test_baris_konteks_dari_nilai_bukan_hardcode():
    """R-2: footer kartu tidak lagi hardcode nilai flight uji."""
    s = kartu._baris_konteks(5.28, 0.4913572)
    assert s == ("konteks: residual kalibrasi PDF 0,49 m; GSD 5,28 cm/px; "
                 "garis digambar apa adanya tanpa penyesuaian")
    s2 = kartu._baris_konteks(3.0, None)                 # tanpa kalibrasi
    assert s2 == ("konteks: GSD 3,00 cm/px; "
                  "garis digambar apa adanya tanpa penyesuaian")


def test_kartu_metadata_gsd_dan_residual(tmp_path):
    """R-2: index.json memuat GSD ortho nyata + residual dari kalibrasi.json."""
    out = _siapkan_output(tmp_path)
    gj = _tulis_geojson(tmp_path / "blok.geojson", [{"kode": "D13", "divisi": "AME III"}])
    kal = tmp_path / "kalibrasi.json"
    kal.write_text(json.dumps({"residual_max_m": 0.123}), encoding="utf-8")
    kartu.buat_kartu(str(out), str(gj), "TST01", dest=str(tmp_path / "kartu"),
                     path_kalibrasi=str(kal))
    idx = json.loads((tmp_path / "kartu" / "index.json").read_text(encoding="utf-8"))
    k = idx["kartu"][0]
    assert abs(k["gsd_cm"] - 100.0) < 0.01               # raster uji 1 m/px
    assert abs(k["residual_m"] - 0.123) < 1e-9
    idx2_dir = tmp_path / "kartu2"
    kartu.buat_kartu(str(out), str(gj), "TST01", dest=str(idx2_dir),
                     path_kalibrasi=str(tmp_path / "tidak_ada.json"))
    k2 = json.loads((idx2_dir / "index.json").read_text(encoding="utf-8"))["kartu"][0]
    assert k2["gsd_cm"] is not None and k2["residual_m"] is None
