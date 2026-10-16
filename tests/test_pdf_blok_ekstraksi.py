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

def test_sel_cacat_direparasi_bukan_dibuang(hasil):
    """Sel berpotongan-diri (mis. jarum 0,3 pt di tepi D14) harus diperbaiki make_valid."""
    _, qa = hasil
    for kode in ("D14", "D02", "F33", "F34"):
        assert kode in qa["kode_berlabel"], f"{kode} hilang dari hasil ekstraksi"
        assert kode not in qa["kode_tanpa_poligon"]

def test_d14_luas_masuk_akal(hasil):
    tmp, _ = hasil
    gj = json.loads((tmp / "blok.geojson").read_text(encoding="utf-8"))
    d14 = [f for f in gj["features"] if f["properties"]["kode"] == "D14"]
    assert len(d14) == 1
    assert 20.0 <= d14[0]["properties"]["luas_ha"] <= 30.0
    xs = [c[0] for c in d14[0]["geometry"]["coordinates"][0]]
    assert 303380 <= min(xs) <= 303460 and 303620 <= max(xs) <= 303700  # celah D13–D15


def test_label_plasma_tidak_diassign_via_kedekatan(hasil):
    """Label blok plasma (suffix P) berbaris di koridor dashed tanpa sel sendiri.
    Jalur kedekatan ≤60 pt pernah menempelkan G24P ke sel magenta di DBE I
    (blok fantom 97% tertutup data — harus eksklusif via containment)."""
    _, qa = hasil
    fantom = {"C24P", "D24P", "E24P", "E26P", "E43P", "F24P", "F25P", "F45P",
              "G24P", "G41P", "H23P", "H24P", "I23P", "I24P", "L41P", "N43PA",
              "N44P", "O42P", "O43P"}
    assert fantom.isdisjoint(qa["kode_berlabel"])
    for k in ("G25A", "G25B", "G26", "G27", "G28"):
        assert k in qa["kode_berlabel"], f"{k} hilang dari hasil ekstraksi"


def test_pola_kode_plasma():
    for k in ("G24P", "N43PA", "CC2P", "L41P", "H57P"):
        assert pdf_blok._kode_plasma(k), k
    for k in ("G25A", "BAN2", "C04A", "D14", "J44B", "K16", "G15"):
        assert not pdf_blok._kode_plasma(k), k
