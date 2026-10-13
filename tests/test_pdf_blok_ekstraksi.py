import json
import pytest
from pathlib import Path
from core import pdf_blok

PDF = Path(__file__).resolve().parent.parent / "data" / "sumber" / "peta_blok.pdf"
SHP = Path(r"E:\2. Tanam Inti\2_Tanam_Inti.shp")

@pytest.fixture(scope="module")
def hasil(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("blok")
    kal = pdf_blok.kalibrasi_pdf(PDF)
    qa = pdf_blok.ekstrak_blok(PDF, kal, tmp / "blok.geojson", tmp / "qa.json", tmp / "peta.png",
                               shp_path=SHP if SHP.exists() else None)
    return tmp, qa

def test_jumlah_blok_berlabel(hasil):
    _, qa = hasil
    assert 300 <= qa["n_berlabel"] <= 900

def test_kode_tertentu_ada(hasil):
    _, qa = hasil
    assert "C04A" in qa["kode_berlabel"]

def test_geojson_valid_dan_berisi_divisi(hasil):
    tmp, qa = hasil
    gj = json.loads((tmp / "blok.geojson").read_text(encoding="utf-8"))
    assert len(gj["features"]) == qa["n_berlabel"]
    assert sum(1 for f in gj["features"] if f["properties"].get("divisi")) > 0

def test_file_output_ada(hasil):
    tmp, _ = hasil
    assert (tmp / "peta.png").stat().st_size > 10_000

def test_lookup_shp():
    if not SHP.exists():
        pytest.skip("shp tidak ada")
    lookup = pdf_blok.muat_lookup_shp(SHP)
    assert len(lookup) > 500
