import numpy as np, rasterio
from rasterio.transform import from_origin
from core import crop_engine

def _sumber(tmp_path):
    t = from_origin(300000, 9960000, 1, 1)
    arr = np.random.default_rng(7).random((3, 200, 200)).astype("float32") * 100
    with rasterio.open(tmp_path / "src.tif", "w", driver="GTiff", width=200, height=200,
                       count=3, dtype="float32", crs="EPSG:32749", transform=t,
                       compress="DEFLATE", predictor=3, tiled=True, blockxsize=256, blockysize=256,
                       BIGTIFF="YES") as ds:
        ds.write(arr)
    return tmp_path / "src.tif", t

def test_crop_luas_dan_nodata(tmp_path):
    src, t = _sumber(tmp_path)
    # kotak 60x40 m pada koordinat (300025..300085, 9959940..9959980)
    geom = "POLYGON((300025 9959940, 300085 9959940, 300085 9959980, 300025 9959980, 300025 9959940))"
    dst = tmp_path / "out.tif"
    stat = crop_engine.crop_layer(src, geom, dst)
    with rasterio.open(dst) as ds:
        assert ds.count == 3 and ds.crs.to_epsg() == 32749
        assert 58 <= ds.width <= 64 and 38 <= ds.height <= 44
        assert ds.profile.get("compress") == "deflate"
    assert stat["piksel"] > 0 and stat["ukuran"] > 0

def test_proses_baris_lengkap(tmp_path):
    t = from_origin(300000, 9960000, 1, 1)
    src = tmp_path / "ndre_src.tif"
    arr = np.random.default_rng(3).random((1, 60, 60)).astype("float32") * 0.8
    with rasterio.open(src, "w", driver="GTiff", width=60, height=60, count=1,
                       dtype="float32", crs="EPSG:32749", transform=t) as ds:
        ds.write(arr)
    d = tmp_path / "out" / "DIV" / "FLG03_DIV-D01"
    row = {"layer": "ndre", "src_data": str(src),
           "geom": "POLYGON((300010 9959960, 300050 9959960, 300050 9959990, 300010 9959990, 300010 9959960))",
           "dst_data": str(d / "NDRE.data.tif"), "dst_rgb": str(d / "NDRE.rgb.tif"),
           "dst_legend": str(d / "NDRE.legend.png")}
    stat = crop_engine.proses_baris(row, "data/palet")
    assert stat["ukuran"] > 0
    assert (d / "NDRE.rgb.tif").exists() and (d / "NDRE.legend.png").exists()
