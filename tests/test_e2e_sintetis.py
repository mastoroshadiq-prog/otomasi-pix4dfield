import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import shape
from core import layer_scan
from core.runner import Runner


def _buat_sumber(folder):
    t = from_origin(300000, 9960000, 1, 1)
    prof = dict(driver="GTiff", width=300, height=300, crs="EPSG:32749", transform=t,
                tiled=True, blockxsize=256, blockysize=256, BIGTIFF="YES")
    rng = np.random.default_rng(1)
    with rasterio.open(folder / "Orthomosaic.tif", "w", count=5, dtype="float32", **prof) as ds:
        ds.write((rng.random((5, 300, 300)) * 100).astype("float32"))
    with rasterio.open(folder / "NDRE.tif", "w", count=1, dtype="float32", **prof) as ds:
        ds.write((rng.random((1, 300, 300)) * 0.8).astype("float32"))


def test_e2e_satu_blok(tmp_path):
    sumber = tmp_path / "sumber"
    sumber.mkdir()
    _buat_sumber(sumber)
    feats = [{"type": "Feature",
              "properties": {"kode": "D01", "divisi": "AME II", "luas_ha": 1.0},
              "geometry": {"type": "Polygon", "coordinates": [[
                  [300050, 9959950], [300150, 9959950], [300150, 9960050],
                  [300050, 9960050], [300050, 9959950]]]}}]
    layers = layer_scan.scan_folder(sumber)["layers"]
    rows = layer_scan.rencana_output(feats, layers, str(tmp_path / "keluar"), "FLG03")
    wkt = shape(feats[0]["geometry"]).wkt
    for r in rows:
        r["geom"] = wkt
    runner = Runner(rows, tmp_path / "keluar", tmp_path / "log",
                    folder_palet=str(Path(__file__).resolve().parent.parent / "data" / "palet"))
    runner.run()
    assert all(it["status"] == "selesai" for it in runner.snapshot()["items"])
    base = tmp_path / "keluar" / "AME II" / "FLG03_AMEII-D01"
    for nama in ("NDRE.data.tif", "NDRE.rgb.tif", "NDRE.legend.png",
                 "Orthomosaic - FLG03_AMEII-D01.data.tif",
                 "Orthomosaic - FLG03_AMEII-D01.rgb.tif"):
        assert (base / nama).exists(), nama
    assert (tmp_path / "keluar" / "hasil_per_blok.csv").exists()
    assert (tmp_path / "keluar" / "state.json").exists()
    data = json.loads((tmp_path / "keluar" / "state.json").read_text(encoding="utf-8"))
    assert len(data["items"]) == len(rows) == 2
    assert (base / "qa_overlay.png").exists()   # overlay QA blok ortho pertama
