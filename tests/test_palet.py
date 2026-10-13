import numpy as np, rasterio
from core import palet

def _pasangan(tmp_path):
    h = w = 64
    t = rasterio.transform.from_origin(300000, 9960000, 1, 1)
    prof = dict(driver="GTiff", width=w, height=h, crs="EPSG:32749", transform=t)
    arr = np.linspace(0, 100, h * w, dtype="float32").reshape(h, w)
    with rasterio.open(tmp_path / "d.tif", "w", count=1, dtype="float32", **prof) as ds:
        ds.write(arr, 1)
    r = (np.clip(arr / 100 * 255, 0, 255)).astype("uint8")
    rgb = np.stack([r, np.zeros_like(r), np.zeros_like(r)])
    with rasterio.open(tmp_path / "r.tif", "w", count=3, dtype="uint8", **prof) as ds:
        ds.write(rgb)
    return tmp_path / "d.tif", tmp_path / "r.tif"

def test_sampling_dan_apply(tmp_path):
    d, r = _pasangan(tmp_path)
    pal = palet.sample_palette(d, r)
    assert pal["vmin"] == 0 and abs(pal["vmax"] - 100) < 1
    out = palet.apply_palette(np.array([[0.0, 50.0, 100.0]], dtype="float32"), pal)
    assert out.shape == (3, 1, 3)
    assert out[0, 0, 0] < 10 and out[0, 0, 2] > 245          # R rendah di vmin, tinggi di vmax
    assert abs(int(out[0, 0, 1]) - 127) < 15                  # R≈127 di tengah

def test_sampling_rgb_4_band_alpha(tmp_path):
    """Rgb app = 4 band (RGBA JPEG); sampling harus baca band 1-3 saja."""
    h = w = 64
    t = rasterio.transform.from_origin(300000, 9960000, 1, 1)
    prof = dict(driver="GTiff", width=w, height=h, crs="EPSG:32749", transform=t)
    arr = np.linspace(0, 1, h * w, dtype="float32").reshape(h, w)
    with rasterio.open(tmp_path / "d4.tif", "w", count=1, dtype="float32", **prof) as ds:
        ds.write(arr, 1)
    g = (np.clip(arr * 255, 0, 255)).astype("uint8")
    rgba = np.stack([np.zeros_like(g), g, np.zeros_like(g), np.full_like(g, 255)])
    with rasterio.open(tmp_path / "r4.tif", "w", count=4, dtype="uint8", **prof) as ds:
        ds.write(rgba)
    pal = palet.sample_palette(tmp_path / "d4.tif", tmp_path / "r4.tif")
    assert len(pal["colors"]) == 256
    out = palet.apply_palette(np.array([[0.0, 1.0]], dtype="float32"), pal)
    assert out[0, 0, 0] < 10 and out[0, 0, 1] < 10            # R dan B ≈ 0 di mana pun
    assert out[1, 0, 1] > 245 and out[1, 0, 0] < 10           # G: 0 di vmin, ≈255 di vmax

def test_ramp_bawaan_dan_muat(tmp_path):
    pal = palet.ramp_bawaan()
    assert pal["bawaan"] is True and len(pal["colors"]) == 256
    palet.simpan_palet(pal, tmp_path / "bawaan.json")
    assert palet.muat_palet("nir", tmp_path)["bawaan"] is True
    pal2 = palet.palet_untuk_data(pal, _pasangan(tmp_path)[0])
    assert pal2["vmax"] > pal2["vmin"] and pal2["vmin"] >= 0
