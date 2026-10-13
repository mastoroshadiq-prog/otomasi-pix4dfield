import math
import pytest
from pathlib import Path
from core import pdf_blok

PDF = Path(__file__).resolve().parent.parent / "data" / "sumber" / "peta_blok.pdf"

@pytest.fixture(scope="module")
def kal():
    return pdf_blok.kalibrasi_pdf(PDF)

def test_lolos_gate(kal):
    assert kal["ok"] is True
    assert kal["residual_max_m"] < 1.0        # gate sesungguhnya 3 m

def test_titik_kontrol(kal):
    assert kal["titik_kontrol"] == 16

def test_skala_dan_rotasi(kal):
    assert abs(kal["skala_m_per_pt"] - 5.973) < 0.05
    assert abs(kal["rotasi_deg"]) < 0.1

def test_transform_titik_potong_grid(kal):
    E, N = pdf_blok.pdf_to_utm(kal, 913.2, 705.83)
    E0, N0 = pdf_blok.lonlat_to_utm(109.216667, -0.400000)
    assert math.hypot(E - E0, N - N0) < 1.5   # toleransi 1,5 m

def test_simpan_muat(tmp_path, kal):
    p = tmp_path / "kalibrasi.json"
    pdf_blok.simpan_kalibrasi(kal, p)
    assert pdf_blok.muat_kalibrasi(p)["residual_max_m"] == kal["residual_max_m"]
