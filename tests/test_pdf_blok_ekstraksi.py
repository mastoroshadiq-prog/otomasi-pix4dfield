import json
import pytest
import pymupdf
import shapefile
from pathlib import Path
from shapely.geometry import shape as shp_shape
from shapely.ops import unary_union
from core import blok_geom, pdf_blok

PDF = Path(__file__).resolve().parent.parent / "data" / "sumber" / "peta_blok.pdf"
SHP = Path(r"E:\2. Tanam Inti\2_Tanam_Inti.shp")

# Label berpoligon yang duduk di luar bbox garis grid DMS (mis. seluruh kolom A
# di kiri x=913,2 pt; A10 di x≈826 pt) — dulu dibuang filter "luar area peta".
KODE_LUAR_GRID = ("A01", "A02", "A03", "A04", "A05", "A06", "A07",
                  "A10", "A11", "A12", "A13", "A14", "A18", "A19", "A20", "A21",
                  "B21", "S03B", "S04B")

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


def test_blok_di_luar_bbox_grid_terekstrak(hasil):
    """Filter bbox grid (x 913,2–4174,5 pt dari kalibrasi) dulu membuang SEMUA
    sel berlabel di luar grid sebagai 'legenda/luar area peta' — padahal peta
    menjangkau lebih kiri (kolom A) dan lebih tepi. Filter itu harus tidak ada."""
    _, qa = hasil
    hilang = [k for k in KODE_LUAR_GRID if k not in qa["kode_berlabel"]]
    assert not hilang, f"kode berlabel di luar bbox grid hilang: {hilang}"
    sisa = [k for k in KODE_LUAR_GRID if k in qa["kode_tanpa_poligon"]]
    assert not sisa, f"kode berpoligon tapi masih dianggap tanpa poligon: {sisa}"


# ---------- ekstraksi multi-ring (sel seperti G29: beberapa ring per path) ----------

def _drawing(items, fill=(1, 0, 0)):
    return {"items": items, "fill": fill, "rect": pymupdf.Rect(0, 0, 80, 80)}


def _garis(pts):
    return [("l", pymupdf.Point(*a), pymupdf.Point(*b)) for a, b in zip(pts, pts[1:])]


def test_rings_satu_chain_tertutup():
    items = _garis([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    rings = pdf_blok._rings_dari_drawing(_drawing(items))
    assert rings is not None and len(rings) == 1
    assert rings[0][0] == (0.0, 0.0) and rings[0][-1] == (0.0, 0.0)
    assert len(rings[0]) == 5


def test_rings_dua_quad_berjarak_dipisah():
    """Dua ring dalam satu path (dipisah lompatan >0,5 pt) harus jadi 2 ring."""
    a = _garis([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    b = _garis([(20, 5), (30, 5), (30, 15), (20, 15), (20, 5)])
    rings = pdf_blok._rings_dari_drawing(_drawing(a + b))
    assert rings is not None and len(rings) == 2
    assert all(r[0] == r[-1] for r in rings)


def test_rings_tak_tertutup_none():
    items = _garis([(0, 0), (10, 0), (10, 10)])  # celah penutup ~14 pt
    assert pdf_blok._rings_dari_drawing(_drawing(items)) is None


def test_rings_item_quad():
    q = pymupdf.Quad(pymupdf.Point(0, 0), pymupdf.Point(10, 0),
                     pymupdf.Point(10, 10), pymupdf.Point(0, 10))
    rings = pdf_blok._rings_dari_drawing(_drawing([("qu", q)]))
    assert rings is not None and len(rings) == 1
    assert len(rings[0]) == 5 and rings[0][0] == rings[0][-1] == (0.0, 0.0)


def test_poly_dari_rings_lubang_even_odd():
    """Ring terkandung = lubang (aturan even-odd), bukan poligon kedua."""
    luar = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    dalam = [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)]
    g = pdf_blok._poly_dari_rings([luar, dalam])
    assert g.geom_type == "Polygon"
    assert abs(g.area - 96) < 1e-9 and len(g.interiors) == 1


def test_poly_dari_rings_disjoint_digabung():
    a = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    b = [(20, 0), (30, 0), (30, 10), (20, 10), (20, 0)]
    g = pdf_blok._poly_dari_rings([a, b])
    assert g.geom_type == "MultiPolygon"
    assert len(g.geoms) == 2 and abs(g.area - 200) < 1e-9


def test_g29_sel_multi_ring_terekstrak(hasil):
    """Sel G29 di peta = satu path berisi 3 ring (pita jalan tipis memisahkan);
    rantai poligon lama berhenti di lompatan antar-ring → G29 dulu hilang,
    lalu blok G29 tidak pernah jadi kandidat Pindai."""
    tmp, qa = hasil
    assert "G29" in qa["kode_berlabel"]
    assert "G29" not in qa["kode_tanpa_poligon"]
    gj = json.loads((tmp / "blok.geojson").read_text(encoding="utf-8"))
    fitur = [f for f in gj["features"] if f["properties"]["kode"] == "G29"]
    assert len(fitur) == 1
    assert fitur[0]["geometry"]["type"] == "MultiPolygon"
    assert 20.0 <= fitur[0]["properties"]["luas_ha"] <= 30.0


def test_kode_lama_tetap_poligon_biasa(hasil):
    """Sel ring-tunggal harus tetap keluar sebagai Polygon (bukan MultiPolygon)."""
    tmp, _ = hasil
    gj = json.loads((tmp / "blok.geojson").read_text(encoding="utf-8"))
    a10 = [f for f in gj["features"] if f["properties"]["kode"] == "A10"]
    assert len(a10) == 1
    assert a10[0]["geometry"]["type"] == "Polygon"


def test_c07b_menempel_sel_teal_bukan_kotak_anotasi(hasil):
    """Label C07B (font 24 pt) duduk persis di dalam kotak anotasi oranye 0,917 ha,
    padahal sel blok sebenarnya = sel teal 4,046 ha yang batasnya hanya 0,41 pt dari
    pusat label. Penautan harus dikoreksi memakai shp resmi (IoU teal 90,2%,
    kotak anotasi 0,5%)."""
    if not SHP.exists():
        pytest.skip("shp tidak ada")
    tmp, _ = hasil
    gj = json.loads((tmp / "blok.geojson").read_text(encoding="utf-8"))
    f = [x for x in gj["features"] if x["properties"]["kode"] == "C07B"]
    assert len(f) == 1
    g = shp_shape(f[0]["geometry"])
    assert 3.9 <= g.area / 1e4 <= 4.2, \
        f"luas C07B = {g.area / 1e4:.3f} ha (masih kotak anotasi 0,917 ha?)"
    ref = unary_union(blok_geom.frags_dari_shp(SHP)["C07B"])
    iou = g.intersection(ref).area / g.union(ref).area
    assert iou > 0.85, f"IoU C07B vs shp = {iou:.1%}"


# ---------- prioritas klaim label: multi-ring tahan-kedekatan + pass lanjutan ----------

KAL_SINTETIS = {"affine_E": [6.0, 0.0, 300000.0], "affine_N": [0.0, -6.0, 9960000.0],
                "residual_max_m": 0.0}


def _pdf_sintetis(tmp_path):
    """PDF mini skala 6 m/pt:
    - M = drawing multi-ring ber-fill (pita 100×12 pt + strip 40×12 pt, 6,05 ha)
    - S = sel ring-tunggal ber-fill 100×100 pt (36 ha) dgn label X1 di dalamnya
    - X1 juga berada ≤60 pt dari pusat M; Y2 hanya dekat M (jauh dari S).
    Urutan halaman: M diproses sebelum S."""
    doc = pymupdf.open()
    page = doc.new_page(width=800, height=800)
    m = page.new_shape()
    m.draw_polyline([(200, 250), (300, 250), (300, 262), (200, 262), (200, 250)])
    m.draw_polyline([(320, 250), (360, 250), (360, 262), (320, 262), (320, 250)])
    m.finish(color=(0, 0, 0), fill=(1, 0, 0))
    m.commit()
    page.draw_polyline([(200, 270), (300, 270), (300, 370), (200, 370), (200, 270)],
                       color=(0, 0, 0), fill=(0, 0, 1))
    page.insert_text((245, 291), "X1")
    page.insert_text((240, 222), "Y2")
    path = tmp_path / "sintetis.pdf"
    doc.save(str(path))
    return path


def _ekstrak_sintetis(tmp_path):
    pdf = _pdf_sintetis(tmp_path)
    pdf_blok.ekstrak_blok(pdf, KAL_SINTETIS, tmp_path / "b.geojson",
                          tmp_path / "q.json", tmp_path / "p.png")
    return json.loads((tmp_path / "b.geojson").read_text(encoding="utf-8"))


def test_kedekatan_multi_ring_tidak_menyerobot_sel_bertuan(tmp_path):
    """M (multi-ring) diproses lebih dulu dan berada ≤60 pt dari X1; tanpa penahan,
    jalur kedekatannya mencuri X1 dari sel S yang sebenarnya (X1 terkandung S).
    X1 harus tetap geometri S: 36 ha Polygon, bukan 6,05 ha MultiPolygon."""
    gj = _ekstrak_sintetis(tmp_path)
    x1 = [f for f in gj["features"] if f["properties"]["kode"] == "X1"]
    assert len(x1) == 1
    assert x1[0]["geometry"]["type"] == "Polygon"
    assert abs(x1[0]["properties"]["luas_ha"] - 36.0) < 0.1


def test_pass_lanjutan_pulihkan_label_telantar(tmp_path):
    """Y2 tidak terkandung sel mana pun dan hanya M (multi-ring) yang dekat;
    setelah M ditahan di pass utama, pass lanjutan harus menautkan M → Y2
    (6,05 ha MultiPolygon) — tanpa itu blok tsb hilang dari kandidat Pindai."""
    gj = _ekstrak_sintetis(tmp_path)
    y2 = [f for f in gj["features"] if f["properties"]["kode"] == "Y2"]
    assert len(y2) == 1
    assert y2[0]["geometry"]["type"] == "MultiPolygon"
    assert abs(y2[0]["properties"]["luas_ha"] - 6.048) < 0.15


# ---------- koreksi penautan label dgn shp resmi (label besar vs sel blok) ----------

def _pdf_label_di_kotak_kecil(tmp_path):
    """Kotak anotasi kecil (12×8,4 pt ≈ 0,36 ha) memuat label Z1, sementara
    sel blok sebenarnya (100×100 pt = 36 ha) tepat 0,5 pt di atas label —
    label besar ini dulu menempel ke kotak anotasi via containment."""
    doc = pymupdf.open()
    page = doc.new_page(width=800, height=800)
    page.insert_text((320, 320), "Z1", fontsize=24)
    w = [x for x in page.get_text("words") if x[4].strip() == "Z1"]
    assert len(w) == 1
    cx, cy = (w[0][0] + w[0][2]) / 2, (w[0][1] + w[0][3]) / 2
    page.draw_polyline([(cx - 6, cy + 0.5), (cx + 94, cy + 0.5), (cx + 94, cy + 100.5),
                        (cx - 6, cy + 100.5), (cx - 6, cy + 0.5)],
                       color=(0, 0, 0), fill=(0, 0.5, 0.4))
    page.draw_polyline([(cx - 6, cy - 8), (cx + 6, cy - 8), (cx + 6, cy + 0.4),
                        (cx - 6, cy + 0.4), (cx - 6, cy - 8)],
                       color=(0, 0, 0), fill=(1, 0.667, 0))
    path = tmp_path / "label_besar.pdf"
    doc.save(str(path))
    return path, cx, cy


def _poly_utm(pts):
    return [[6.0 * x + 300000.0, -6.0 * y + 9960000.0] for x, y in pts]


def test_label_besar_ambigu_dikoreksi_dengan_shp(tmp_path):
    """Tanpa koreksi shp, Z1 = kotak anotasi 0,36 ha; sel blok 36 ha yang
    tidak memuat pusat label (jarak 0,5 pt) harus dipulihkan."""
    pdf, cx, cy = _pdf_label_di_kotak_kecil(tmp_path)
    besar = _poly_utm([(cx - 6, cy + 0.5), (cx + 94, cy + 0.5),
                       (cx + 94, cy + 100.5), (cx - 6, cy + 100.5),
                       (cx - 6, cy + 0.5)])
    shp_p = tmp_path / "kebun.shp"
    w = shapefile.Writer(str(shp_p), shapeType=shapefile.POLYGON)
    w.field("No_Block", "C")
    w.field("BLOK_Baru", "C")
    w.poly([besar])
    w.record("Z1", "Z1")
    w.close()
    pdf_blok.ekstrak_blok(pdf, KAL_SINTETIS, tmp_path / "b.geojson",
                          tmp_path / "q.json", tmp_path / "p.png", shp_path=str(shp_p))
    gj = json.loads((tmp_path / "b.geojson").read_text(encoding="utf-8"))
    z1 = [f for f in gj["features"] if f["properties"]["kode"] == "Z1"]
    assert len(z1) == 1
    assert 35.0 <= z1[0]["properties"]["luas_ha"] <= 37.0, \
        f"luas Z1 = {z1[0]['properties']['luas_ha']:.3f} ha (masih kotak anotasi?)"
    ref = shp_shape({"type": "Polygon", "coordinates": [besar]})
    g = shp_shape(z1[0]["geometry"])
    iou = g.intersection(ref).area / g.union(ref).area
    assert iou > 0.95

