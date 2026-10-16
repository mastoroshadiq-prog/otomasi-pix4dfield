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


def _ortho(path, alpha_kanan_nol, h=200, w=200, res=5.0):
    arr = np.full((5, h, w), 100.0, dtype="float32")
    arr[4] = 255.0
    if alpha_kanan_nol:
        arr[4, :, w // 2:] = 0.0
    with rasterio.open(path, "w", driver="GTiff", width=w, height=h, count=5,
                       dtype="float32", crs="EPSG:32749",
                       transform=rasterio.transform.from_origin(300000, 9960000, res, res)) as ds:
        ds.write(arr)
    return path


def test_luas_footprint_ha_setengah_alpha(tmp_path):
    """200×200 px @5 m = 100 ha bbox; separuh ber-alpha → footprint ±50 ha."""
    p = _ortho(tmp_path / "ortho5.tif", alpha_kanan_nol=True)
    assert abs(layer_scan.luas_footprint_ha(p) - 50.0) < 1.0


def test_luas_footprint_ha_alpha_penuh(tmp_path):
    p = _ortho(tmp_path / "ortho5.tif", alpha_kanan_nol=False)
    assert abs(layer_scan.luas_footprint_ha(p) - 100.0) < 1.0


def test_estimasi_byte_output_terkalibrasi_gate2():
    """Angka Gate 2 (RINGKASAN): sumber 38.287.432.957 B, footprint 257,9 ha,
    blok 197,63 ha → output nyata 24.708.559.348 B; toleransi ±15%."""
    est = layer_scan.estimasi_byte_output(38_287_432_957, 197.63, 257.9)
    nyata = 24_708_559_348
    assert abs(est - nyata) / nyata < 0.15


def test_estimasi_byte_output_tolak_footprint_nol():
    with pytest.raises(ValueError):
        layer_scan.estimasi_byte_output(1_000_000, 10.0, 0.0)


# --- S-1: layer ber-footprint parsial → baris "dilewati" ---

def _blok(kode="D01", x=300000, y=9960000, sisi=400):
    return {"type": "Feature",
            "properties": {"kode": kode, "divisi": "AME III", "luas_ha": 16.0},
            "geometry": {"type": "Polygon",
                         "coordinates": [[[x, y], [x + sisi, y], [x + sisi, y + sisi],
                                          [x, y + sisi], [x, y]]]}}


def test_rencana_output_layer_footprint_parsial_dilewati():
    layers = {"ortho": {"data": "o.tif", "bounds": (300000, 9959000, 301000, 9961000)},
              "ndre": {"data": "n.tif", "bounds": (305000, 9959000, 306000, 9961000)},
              "dsm": {"data": "d.tif", "bounds": (300200, 9960000, 300300, 9960100)}}  # parsial → tetap proses
    rows = layer_scan.rencana_output([_blok()], layers, r"F:\\keluar", "FLG03")
    st = {(r["layer"]): r.get("status", "pending") for r in rows}
    assert st == {"ortho": "pending", "ndre": "dilewati", "dsm": "pending"}
    r_ndre = [r for r in rows if r["layer"] == "ndre"][0]
    assert "di luar cakupan" in r_ndre["error"]


def test_rencana_output_tanpa_bounds_tetap_pending():
    """Layer tanpa info bounds (mis. hasil scan lama) dianggap mencakup — tidak dilewati."""
    layers = {"ortho": {"data": "o.tif"}, "ndre": {"data": "n.tif"}}
    rows = layer_scan.rencana_output([_blok()], layers, r"F:\\keluar", "FLG03")
    assert all(r.get("status", "pending") == "pending" for r in rows)


# --- Saringan blok berdata: blok dianggap berdata bila ≥25% luasnya tertutup footprint ---

def test_topeng_footprint_grid_dan_luas(tmp_path):
    p = _ortho(tmp_path / "ortho5.tif", alpha_kanan_nol=True)
    t = layer_scan.topeng_footprint(p)
    assert t["mask"].shape == (200, 200)
    assert abs(t["luas_ha"] - 50.0) < 1.0
    assert abs(t["px_m2"] - 25.0) < 0.01


def test_saring_blok_berdata_ambang_25(tmp_path):
    """Footprint = separuh kiri (x < 300500): 100%/50% disimpan, 20%/0% dibuang."""
    p = _ortho(tmp_path / "ortho5.tif", alpha_kanan_nol=True)
    topeng = layer_scan.topeng_footprint(p)
    fitur = [_blok("KIRI", x=300000, y=9959500, sisi=400),     # 100% di dalam → simpan
             _blok("TEPI", x=300250, y=9959500, sisi=500),     # 50% di dalam → simpan
             _blok("SEMPIT", x=300420, y=9959500, sisi=400),   # 20% → buang
             _blok("KANAN", x=300600, y=9959500, sisi=300)]    # 0% → buang
    simpan, buang = layer_scan.saring_blok_berdata(fitur, topeng)
    assert [f["properties"]["kode"] for f in simpan] == ["KIRI", "TEPI"]
    assert [b["kode"] for b in buang] == ["SEMPIT", "KANAN"]
    assert abs(buang[0]["cakupan_persen"] - 20.0) < 0.1
    assert buang[1]["cakupan_persen"] < 0.1


# --- Poligon footprint (bahan "bentang" untuk mode kartu blok penuh / opsi B) ---

def test_poligon_footprint_margin_keluar_kecil(tmp_path):
    from shapely.geometry import Point
    p = _ortho(tmp_path / "ortho5.tif", alpha_kanan_nol=True)
    topeng = layer_scan.topeng_footprint(p)
    pol = layer_scan.poligon_footprint(topeng)
    assert pol.area >= 500_000.0            # area berdata 50 ha — tak pernah terpotong
    assert pol.area < 550_000.0             # margin ke luar tetap tipis
    assert pol.contains(Point(300506, 9959750))       # 6 m di luar tepi mask (margin 7,5 m)
    assert not pol.contains(Point(300520, 9959750))   # 20 m → di luar margin
