import numpy as np, rasterio
from pathlib import Path
from rasterio.transform import from_origin
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
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

def test_proses_baris_copy_rgb_dan_legend(tmp_path):
    """Bila sumber punya .rgb.tif + .legend.png (pola app), rgb di-crop apa adanya & legend disalin."""
    t = from_origin(300000, 9960000, 1, 1)
    src = tmp_path / "ndre2.data.tif"
    rng = np.random.default_rng(5)
    with rasterio.open(src, "w", driver="GTiff", width=200, height=200, count=1,
                       dtype="float32", crs="EPSG:32749", transform=t) as ds:
        ds.write(rng.random((1, 200, 200)).astype("float32") * 0.8)
    rgb_src = tmp_path / "ndre2.rgb.tif"
    xs = np.arange(200, dtype="uint8")[None, :].repeat(200, 0)
    ys = np.arange(200, dtype="uint8")[:, None].repeat(200, 1)
    pola = np.stack([xs, ys, np.full((200, 200), 128, "uint8")])
    rgba = np.concatenate([pola, np.full((1, 200, 200), 255, "uint8")])
    with rasterio.open(rgb_src, "w", driver="GTiff", width=200, height=200, count=4,
                       dtype="uint8", crs="EPSG:32749", transform=t,
                       compress="jpeg", interleave="pixel") as ds:
        ds.write(rgba)
    legend = tmp_path / "ndre2.legend.png"
    legend.write_bytes(b"isi-legend-palsu")
    d = tmp_path / "out2" / "DIV" / "FLG01_DIV-D02"
    row = {"layer": "ndre", "src_data": str(src),
           "geom": "POLYGON((300025 9959940, 300085 9959940, 300085 9959980, 300025 9959980, 300025 9959940))",
           "dst_data": str(d / "NDRE.data.tif"), "dst_rgb": str(d / "NDRE.rgb.tif"),
           "dst_legend": str(d / "NDRE.legend.png"),
           "src_rgb": str(rgb_src), "src_legend": str(legend)}
    crop_engine.proses_baris(row, "data/palet")
    with rasterio.open(d / "NDRE.rgb.tif") as ds:
        assert ds.count == 4 and ds.profile.get("compress") == "jpeg"
        out = ds.read()
        win = from_bounds(*ds.bounds, transform=t).round_offsets().round_lengths()
        win = rasterio.windows.Window(int(win.col_off), int(win.row_off), int(win.width), int(win.height))
    with rasterio.open(rgb_src) as rs:
        asli = rs.read(window=win)
        inti = (slice(None), slice(8, -8), slice(8, -8))        # hindari piksel tepi mask
        assert np.abs(out[inti].astype("int16") - asli[inti].astype("int16")).mean() < 8  # toleransi re-JPEG q85
    assert (d / "NDRE.legend.png").read_bytes() == b"isi-legend-palsu"

def test_crop_uint8_data_tif_dipaksa_deflate(tmp_path):
    """N-2: sumber uint8 untuk berkas .data.tif tidak boleh di-JPEG (lossy) — paksa DEFLATE."""
    t = from_origin(300000, 9960000, 1, 1)
    src = tmp_path / "kelas_src.tif"
    arr = np.random.default_rng(11).integers(1, 200, (1, 200, 200), dtype="uint8")
    with rasterio.open(src, "w", driver="GTiff", width=200, height=200, count=1,
                       dtype="uint8", crs="EPSG:32749", transform=t) as ds:
        ds.write(arr)
    geom = "POLYGON((300025 9959940, 300085 9959940, 300085 9959980, 300025 9959980, 300025 9959940))"
    dst = tmp_path / "Kelas.data.tif"
    crop_engine.crop_layer(src, geom, dst)
    with rasterio.open(dst) as ds:
        assert ds.profile.get("compress") == "deflate"
        assert ds.dtypes[0] == "uint8"
        out = ds.read(1)
        win = from_bounds(*ds.bounds, transform=t).round_offsets().round_lengths()
        win = rasterio.windows.Window(int(win.col_off), int(win.row_off), int(win.width), int(win.height))
    with rasterio.open(src) as rs:
        asli = rs.read(1, window=win)
    m = out != 0                                          # 0 = nodata di luar poligon
    assert m.any()
    assert np.array_equal(out[m], asli[m])                # salinan eksak (lossless)

def test_render_ortho_rgb_abaikan_nodata_saat_stretch(tmp_path):
    """Nodata -10000 tidak boleh masuk hitungan persentil → blok bertepi nodata
    tidak boleh tersaturasi putih."""
    t = from_origin(300000, 9960000, 1, 1)
    rng = np.random.default_rng(13)
    arr = rng.random((5, 200, 200)).astype("float32") * 0.01
    arr[:, :30, :] = -10000.0                     # 15% nodata: p2 akan jatuh ke -10000
    arr[4, 30:, :] = 255.0
    src = tmp_path / "ortho5.tif"
    with rasterio.open(src, "w", driver="GTiff", width=200, height=200, count=5,
                       dtype="float32", crs="EPSG:32749", transform=t,
                       nodata=-10000.0) as ds:
        ds.write(arr)
    dst = tmp_path / "ortho5.rgb.tif"
    crop_engine.render_ortho_rgb(src, dst, chunk=64)
    with rasterio.open(dst) as ds:
        out = ds.read()
    berdata = out[:, 30:, :]
    assert np.unique(berdata[0]).size > 20
    assert berdata.mean() < 200


def test_overview_data_tidak_membaurkan_nodata(tmp_path):
    """N-3 (data): GDAL average menghormati nodata → overview tepi footprint bersih."""
    t = from_origin(300000, 9960000, 1, 1)
    src = tmp_path / "kelas_nodata.tif"
    arr = np.full((1, 200, 200), -10000.0, "float32")
    arr[:, 101:200, 101:200] = 7.5                        # batas ganjil → blok overview campuran
    with rasterio.open(src, "w", driver="GTiff", width=200, height=200, count=1,
                       dtype="float32", crs="EPSG:32749", transform=t,
                       nodata=-10000.0) as ds:
        ds.write(arr)
    geom = "POLYGON((300099 9959801, 300199 9959801, 300199 9959901, 300099 9959901, 300099 9959801))"
    dst = tmp_path / "Kelas2.data.tif"
    crop_engine.crop_layer(src, geom, dst)
    with rasterio.open(dst) as ds:
        ov = ds.read(1, out_shape=(ds.height // 2, ds.width // 2),
                     resampling=Resampling.nearest)
    vals = set(np.unique(ov).tolist())
    assert vals <= {-10000.0, 7.5}                        # tak ada nilai campuran di tepi
