import numpy as np
import rasterio
import pytest
from pathlib import Path
from core import layer_scan

def _tif(path, count, dtype, desc=None):
    data = np.zeros((count, 20, 20), dtype=dtype)
    with rasterio.open(path, "w", driver="GTiff", width=20, height=20, count=count,
                       dtype=dtype, crs="EPSG:32749", transform=rasterio.transform.from_origin(300000, 9960000, 1, 1)) as ds:
        ds.write(data)
    return path

@pytest.fixture
def folder(tmp_path):
    _tif(tmp_path / "Orthomosaic.data.tif", 5, "float32")
    _tif(tmp_path / "Orthomosaic.rgb.tif", 4, "uint8")
    _tif(tmp_path / "NDRE.data.tif", 1, "float32")
    _tif(tmp_path / "NDRE.rgb.tif", 4, "uint8")
    (tmp_path / "NDRE.legend.png").write_bytes(b"png-palsu")
    _tif(tmp_path / "NIR.tif", 1, "float32")
    _tif(tmp_path / "RedEdge.tif", 1, "float32")
    _tif(tmp_path / "Surface model.data.tif", 1, "float32")
    (tmp_path / "Surface model.legend.png").write_bytes(b"png-palsu")
    (tmp_path / "catatan.txt").write_text("bukan raster")
    return tmp_path

def test_klasifikasi_lengkap(folder):
    hasil = layer_scan.scan_folder(folder)
    assert set(hasil["layers"]) == {"ortho", "ndre", "nir", "rededge", "dsm"}
    assert hasil["layers"]["ortho"]["bands"] == 5
    assert hasil["layers"]["ndre"]["rgb"].endswith("NDRE.rgb.tif")
    assert hasil["layers"]["ndre"]["legend"].endswith("NDRE.legend.png")
    assert hasil["layers"]["dsm"]["legend"].endswith("Surface model.legend.png")
    assert hasil["layers"]["nir"]["rgb"] is None and hasil["layers"]["nir"]["legend"] is None
    assert any("catatan.txt" in d["file"] for d in hasil["ditolak"])
    assert not any(".rgb.tif" in d["file"] or ".legend.png" in d["file"] for d in hasil["ditolak"])

def test_file_satu_band_asing_ditolak(tmp_path):
    _tif(tmp_path / "aneh.tif", 1, "float32")
    hasil = layer_scan.scan_folder(tmp_path)
    assert "ortho" not in hasil["layers"]
    assert len(hasil["ditolak"]) == 1

def test_rencana_output_naming():
    feats = [{"type": "Feature",
              "properties": {"kode": "D01", "divisi": "AME II", "luas_ha": 30.0},
              "geometry": {"type": "Polygon", "coordinates": [[[300000, 9960000], [300400, 9960000], [300400, 9960400], [300000, 9960400], [300000, 9960000]]]}}]
    layers = {"ortho": {"data": "x.tif"}, "ndre": {"data": "y.tif"}}
    rows = layer_scan.rencana_output(feats, layers, r"F:\\keluar", "FLG03")
    r0 = [r for r in rows if r["kode"] == "D01" and r["layer"] == "ortho"][0]
    assert r0["dst_dir"].replace("\\", "/").endswith("AME II/FLG03_AMEII-D01")
    assert Path(r0["dst_data"]).name == "Orthomosaic - FLG03_AMEII-D01.data.tif"
    assert Path(r0["dst_rgb"]).name == "Orthomosaic - FLG03_AMEII-D01.rgb.tif"
    assert r0["dst_legend"] is None
    r1 = [r for r in rows if r["kode"] == "D01" and r["layer"] == "ndre"][0]
    assert Path(r1["dst_data"]).name == "NDRE.data.tif"
    assert Path(r1["dst_rgb"]).name == "NDRE.rgb.tif"
    assert Path(r1["dst_legend"]).name == "NDRE.legend.png"
