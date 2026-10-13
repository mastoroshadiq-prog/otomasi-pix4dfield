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

def test_ramp_bawaan_dan_muat(tmp_path):
    pal = palet.ramp_bawaan()
    assert pal["bawaan"] is True and len(pal["colors"]) == 256
    palet.simpan_palet(pal, tmp_path / "bawaan.json")
    assert palet.muat_palet("nir", tmp_path)["bawaan"] is True
    pal2 = palet.palet_untuk_data(pal, _pasangan(tmp_path)[0])
    assert pal2["vmax"] > pal2["vmin"] and pal2["vmin"] >= 0
