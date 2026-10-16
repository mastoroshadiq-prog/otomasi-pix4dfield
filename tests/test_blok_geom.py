"""Tes geometri kartu mode blok penuh (opsi B): union pecahan shp + tambal celah."""
import shapefile
from shapely.geometry import box
from core import blok_geom


def test_union_pecahan_dan_isian_midline():
    """Dua blok 45 ha berjarak 100 m: celah dibagi rata di garis tengah → 50 + 50 ha."""
    bentang = box(0, 0, 1000, 1000)
    frags = {"D01": [box(0, 0, 450, 1000)], "D02": [box(550, 0, 1000, 1000)]}
    g = blok_geom.geometri_kartu(bentang, frags, ["D01", "D02"])
    assert abs(g["D01"].area - 500_000) < 100
    assert abs(g["D02"].area - 500_000) < 100
    assert g["D01"].intersection(g["D02"]).area < 1     # hanya berbatasan


def test_kode_tanpa_fragmen_dikembalikan_none():
    frags = {"D01": [box(0, 0, 10, 10)]}
    g = blok_geom.geometri_kartu(box(0, 0, 100, 100), frags, ["D01", "X99"])
    assert g["X99"] is None and g["D01"] is not None


def test_fragmen_di_luar_bentang_dipotong():
    frags = {"D01": [box(0, 0, 200, 100)]}
    g = blok_geom.geometri_kartu(box(0, 0, 100, 100), frags, ["D01"])
    assert abs(g["D01"].area - 10_000) < 1


def test_batas_tambal_dihormati():
    bentang = box(0, 0, 1000, 1000)
    frags = {"D01": [box(0, 0, 450, 1000)], "D02": [box(550, 0, 1000, 1000)]}
    g = blok_geom.geometri_kartu(bentang, frags, ["D01", "D02"], maks_tambal=10)
    assert abs(g["D01"].area - 460_000) < 100
    assert abs(g["D02"].area - 460_000) < 100


def test_union_multi_fragmen_tanpa_tambalan():
    frags = {"X": [box(0, 0, 100, 100), box(200, 0, 300, 100)]}
    g = blok_geom.geometri_kartu(box(0, 0, 400, 100), frags, ["X"], maks_tambal=0)
    assert g["X"].geom_type == "MultiPolygon"
    assert abs(g["X"].area - 20_000) < 1


def test_frags_dari_shp_normalisasi_dan_duplikat(tmp_path):
    p = tmp_path / "kebun.shp"
    w = shapefile.Writer(str(p), shapeType=shapefile.POLYGON)
    w.field("No_Block", "C")
    w.field("BLOK_Baru", "C")
    w.poly([[[0, 0], [0, 100], [100, 100], [100, 0], [0, 0]]])
    w.record(" g25 a", "X1")
    w.poly([[[200, 0], [200, 100], [300, 100], [300, 0], [200, 0]]])
    w.record("G25A", "X2")
    w.close()
    frags = blok_geom.frags_dari_shp(p)
    assert set(frags) == {"G25A"}                       # dinormalisasi (spasi/huruf kecil)
    assert len(frags["G25A"]) == 2                      # dua fragmen dipertahankan
    assert abs(frags["G25A"][0].area - 10_000) < 1
