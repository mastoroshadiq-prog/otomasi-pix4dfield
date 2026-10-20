import json
import numpy as np
import rasterio
import shapefile
from PIL import Image
from rasterio.transform import from_origin
from shapely.geometry import shape as shp_shape

from core import kartu

POLY = [[300000.0, 9959400.0], [300200.0, 9959400.0], [300200.0, 9960000.0],
        [300000.0, 9960000.0], [300000.0, 9959400.0]]
POLY_GESER = [[x + 900.0, y] for x, y in POLY]
POLY_D14 = [[x + 200.0, y] for x, y in POLY]
POLY_SETENGAH = [[300000.0, 9959400.0], [300100.0, 9959400.0],
                 [300100.0, 9960000.0], [300000.0, 9960000.0],
                 [300000.0, 9959400.0]]


def _tulis_shp(path, records):
    w = shapefile.Writer(str(path), shapeType=shapefile.POLYGON)
    w.field("No_Block", "C")
    w.field("BLOK_Baru", "C")
    for poly, no, baru in records:
        w.poly([poly])
        w.record(no, baru)
    w.close()


def _buat_raster(path, h=600, w=200):
    t = from_origin(300000, 9960000, 1, 1)
    arr = np.zeros((4, h, w), dtype="uint8")
    arr[0] = 60
    arr[1] = 140
    arr[2] = 70
    arr[3] = 255
    with rasterio.open(path, "w", driver="GTiff", width=w, height=h, count=4,
                       dtype="uint8", crs="EPSG:32749", transform=t) as ds:
        ds.write(arr)


def _siapkan_output(tmp_path, kode="D13", divisi="AME III", kode_flight="TST01"):
    out = tmp_path / "out"
    dir_blok = out / divisi / f"{kode_flight}_{divisi.replace(' ', '')}-{kode}"
    dir_blok.mkdir(parents=True)
    _buat_raster(dir_blok / f"Orthomosaic - {dir_blok.name}.rgb.tif")
    return out


def _buat_raster_warna(path, x0, warna, h=600, w=200):
    t = from_origin(x0, 9960000, 1, 1)
    arr = np.zeros((4, h, w), dtype="uint8")
    arr[0], arr[1], arr[2] = warna
    arr[3] = 255
    with rasterio.open(path, "w", driver="GTiff", width=w, height=h, count=4,
                       dtype="uint8", crs="EPSG:32749", transform=t) as ds:
        ds.write(arr)


def _siapkan_output_dua(tmp_path, divisi="AME III", kode_flight="TST01"):
    out = tmp_path / "out"
    for kode, x0, warna in (("D13", 300000, (60, 140, 70)),
                            ("D14", 300200, (180, 40, 40))):
        dir_blok = out / divisi / f"{kode_flight}_{divisi.replace(' ', '')}-{kode}"
        dir_blok.mkdir(parents=True)
        _buat_raster_warna(dir_blok / f"Orthomosaic - {dir_blok.name}.rgb.tif", x0, warna)
    return out


def _tulis_geojson(path, fitur):
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": p,
         "geometry": {"type": "Polygon", "coordinates": [POLY]}} for p in fitur]}
    path.write_text(json.dumps(gj), encoding="utf-8")
    return path


def _tulis_state(out, geom_blok):
    st = {"versi": 2,
          "geom_blok": {k: (g if isinstance(g, str) else g.wkt)
                        for k, g in geom_blok.items()}}
    (out / "state.json").write_text(json.dumps(st), encoding="utf-8")


def test_kartu_dan_index_terbentuk(tmp_path):
    out = _siapkan_output(tmp_path)
    gj = _tulis_geojson(tmp_path / "blok.geojson", [
        {"kode": "D13", "divisi": "AME III"},
        {"kode": "D99", "divisi": "AME III"},          # folder tidak ada → dilewati
    ])
    h = kartu.buat_kartu(str(out), str(gj), "TST01", path_shp=None, dest=str(tmp_path / "kartu"))
    assert h["kartu"] == 1
    assert [d["kode"] for d in h["dilewati"]] == ["D99"]
    png = tmp_path / "kartu" / "kartu_D13.png"
    assert png.exists()
    a = np.array(Image.open(png))
    assert a.shape[0] > 1000 and a.shape[1] > 1000
    hijau = (a[..., 0] == 60) & (a[..., 1] == 140) & (a[..., 2] == 70)
    assert hijau.sum() > 1000                        # citra benar-benar tertempel di kartu
    idx = json.loads((tmp_path / "kartu" / "index.json").read_text(encoding="utf-8"))
    k = idx["kartu"][0]
    assert k["kode"] == "D13" and k["file"] == "kartu_D13.png"
    assert abs(k["luas_pdf_ha"] - 12.0) < 0.01
    assert abs(k["luas_ekspor_ha"] - 12.0) < 0.01   # fallback PDF saat state belum ada
    assert k["iou"] is not None and k["iou"] > 99.0
    assert k["luas_shp_ha"] is None
    assert not (tmp_path / "kartu" / "kartu_gabungan.png").exists()


def test_kartu_dengan_shp_menghitung_iou(tmp_path):
    out = _siapkan_output(tmp_path)
    gj = _tulis_geojson(tmp_path / "blok.geojson", [{"kode": "D13", "divisi": "AME III"}])
    shp_p = tmp_path / "kebun.shp"
    w = shapefile.Writer(str(shp_p), shapeType=shapefile.POLYGON)
    w.field("No_Block", "C")
    w.field("BLOK_Baru", "C")
    w.poly([POLY])
    w.record("D13", "D013A")
    w.close()
    kartu.buat_kartu(str(out), str(gj), "TST01", path_shp=str(shp_p), dest=str(tmp_path / "kartu"))
    idx = json.loads((tmp_path / "kartu" / "index.json").read_text(encoding="utf-8"))
    k = idx["kartu"][0]
    assert k["iou"] is not None and k["iou"] > 99.0
    assert k["kode_shp"] == "D013A"
    assert abs(k["luas_shp_ha"] - 12.0) < 0.01


def test_baris_konteks_dari_nilai_bukan_hardcode():
    """R-2: footer kartu tidak lagi hardcode nilai flight uji."""
    s = kartu._baris_konteks(5.28, 0.4913572)
    assert s == ("konteks: residual kalibrasi PDF 0,49 m; GSD 5,28 cm/px; "
                 "garis digambar apa adanya tanpa penyesuaian")
    s2 = kartu._baris_konteks(3.0, None)                 # tanpa kalibrasi
    assert s2 == ("konteks: GSD 3,00 cm/px; "
                  "garis digambar apa adanya tanpa penyesuaian")


def test_kartu_metadata_gsd_dan_residual(tmp_path):
    """R-2: index.json memuat GSD ortho nyata + residual dari kalibrasi.json."""
    out = _siapkan_output(tmp_path)
    gj = _tulis_geojson(tmp_path / "blok.geojson", [{"kode": "D13", "divisi": "AME III"}])
    kal = tmp_path / "kalibrasi.json"
    kal.write_text(json.dumps({"residual_max_m": 0.123}), encoding="utf-8")
    kartu.buat_kartu(str(out), str(gj), "TST01", dest=str(tmp_path / "kartu"),
                     path_kalibrasi=str(kal))
    idx = json.loads((tmp_path / "kartu" / "index.json").read_text(encoding="utf-8"))
    k = idx["kartu"][0]
    assert abs(k["gsd_cm"] - 100.0) < 0.01               # raster uji 1 m/px
    assert abs(k["residual_m"] - 0.123) < 1e-9
    idx2_dir = tmp_path / "kartu2"
    kartu.buat_kartu(str(out), str(gj), "TST01", dest=str(idx2_dir),
                     path_kalibrasi=str(tmp_path / "tidak_ada.json"))
    k2 = json.loads((idx2_dir / "index.json").read_text(encoding="utf-8"))["kartu"][0]
    assert k2["gsd_cm"] is not None and k2["residual_m"] is None


def test_muat_shp_menyimpan_semua_record_duplikat(tmp_path):
    """BUG nyata: No_Block duplikat di shp (fragmen utuh + fragmen bergeser)
    dulu saling menimpa (yang terakhir menang) sehingga kartu memakai fragmen salah."""
    p = tmp_path / "kebun.shp"
    _tulis_shp(p, [(POLY, "D13", "D013A"), (POLY_GESER, "D13", "D013A")])
    h = kartu.muat_shp(p)
    assert set(h) == {"D13"}
    assert isinstance(h["D13"], list)                # RED bersih sebelum perbaikan
    assert len(h["D13"]) == 2                        # kedua record tersimpan


def test_shp_terkait_saring_fragmen_jauh(tmp_path):
    """Fragmen duplikat yang bergeser jauh tidak boleh mengacaukan luas/garis
    shp; fragmen sah di dalam area ekspor tetap digabung."""
    utama = shp_shape({"type": "Polygon",
                       "coordinates": [[[300000.0, 9959400.0], [300300.0, 9959400.0],
                                        [300300.0, 9960000.0], [300000.0, 9960000.0],
                                        [300000.0, 9959400.0]]]})
    kandidat = [{"geom": shp_shape({"type": "Polygon", "coordinates": [POLY_GESER]}),
                 "kode_shp": "JAUH"},
                {"geom": shp_shape({"type": "Polygon", "coordinates": [POLY]}),
                 "kode_shp": "BENAR"},
                {"geom": shp_shape({"type": "Polygon",
                                    "coordinates": [[[300200.0, 9959400.0],
                                                     [300300.0, 9959400.0],
                                                     [300300.0, 9960000.0],
                                                     [300200.0, 9960000.0],
                                                     [300200.0, 9959400.0]]]}),
                 "kode_shp": "BENAR"}]
    g, kode = kartu.shp_terkait(utama, kandidat)
    assert abs(g.area - 18.0 * 1e4) < 1.0        # POLY + fragmen sah, bukan yang jauh
    assert kode == "BENAR"


def test_kartu_abaikan_fragmen_shp_jauh(tmp_path):
    out = _siapkan_output(tmp_path)
    gj = _tulis_geojson(tmp_path / "blok.geojson", [{"kode": "D13", "divisi": "AME III"}])
    shp_p = tmp_path / "kebun.shp"
    _tulis_shp(shp_p, [(POLY, "D13", "D013A"), (POLY_GESER, "D13", "D013A")])
    kartu.buat_kartu(str(out), str(gj), "TST01", path_shp=str(shp_p),
                     dest=str(tmp_path / "kartu"))
    idx = json.loads((tmp_path / "kartu" / "index.json").read_text(encoding="utf-8"))
    k = idx["kartu"][0]
    assert abs(k["luas_shp_ha"] - 12.0) < 0.01     # bukan 24 ha dari duplikat jauh
    assert k["kode_shp"] == "D013A"


def test_kartu_gabungan_untuk_banyak_blok(tmp_path):
    """Kartu besar gabungan: semua blok tersusun pada posisi aslinya,
    tampil pertama di index agar mudah dipakai untuk validasi visual."""
    out = _siapkan_output_dua(tmp_path)
    gj = tmp_path / "blok.geojson"
    gj.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"kode": "D13", "divisi": "AME III"},
         "geometry": {"type": "Polygon", "coordinates": [POLY]}},
        {"type": "Feature", "properties": {"kode": "D14", "divisi": "AME III"},
         "geometry": {"type": "Polygon", "coordinates": [POLY_D14]}},
    ]}), encoding="utf-8")

    h = kartu.buat_kartu(str(out), str(gj), "TST01", dest=str(tmp_path / "kartu"))
    assert h["kartu"] == 3                          # 2 per blok + 1 gabungan
    png = tmp_path / "kartu" / "kartu_gabungan.png"
    assert png.exists()
    a = np.array(Image.open(png))
    assert a.shape[0] >= 1200 and a.shape[1] >= 800
    hijau = (a[..., 0] == 60) & (a[..., 1] == 140) & (a[..., 2] == 70)
    merah = (a[..., 0] == 180) & (a[..., 1] == 40) & (a[..., 2] == 40)
    assert hijau.sum() > 1000 and merah.sum() > 1000   # kedua blok benar-benar tampil

    idx = json.loads((tmp_path / "kartu" / "index.json").read_text(encoding="utf-8"))
    g = idx["kartu"][0]
    assert g["kode"] == "GABUNGAN" and g["jenis"] == "gabungan"
    assert g["file"] == "kartu_gabungan.png" and g["n_blok"] == 2
    assert abs(g["luas_pdf_ha"] - 24.0) < 0.01
    assert abs(g["luas_ekspor_ha"] - 24.0) < 0.01
    assert [k["kode"] for k in idx["kartu"][1:]] == ["D13", "D14"]


def test_gabungan_menampilkan_garis_shp_resmi(tmp_path):
    """Kartu gabungan juga harus memuat garis biru shp Tanam Inti (resmi),
    bukan hanya batas ekspor merah."""
    out = _siapkan_output_dua(tmp_path)
    gj = tmp_path / "blok.geojson"
    gj.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"kode": "D13", "divisi": "AME III"},
         "geometry": {"type": "Polygon", "coordinates": [POLY]}},
        {"type": "Feature", "properties": {"kode": "D14", "divisi": "AME III"},
         "geometry": {"type": "Polygon", "coordinates": [POLY_D14]}},
    ]}), encoding="utf-8")
    shp_p = tmp_path / "kebun.shp"
    _tulis_shp(shp_p, [(POLY, "D13", "D013A"), (POLY_D14, "D14", "D014A")])
    kartu.buat_kartu(str(out), str(gj), "TST01", path_shp=str(shp_p),
                     dest=str(tmp_path / "kartu"))
    a = np.array(Image.open(tmp_path / "kartu" / "kartu_gabungan.png"))
    biru = (a[..., 0] == 0) & (a[..., 1] == 90) & (a[..., 2] == 255)
    assert biru.sum() > 500                          # garis shp benar-benar tergambar


def test_muat_geom_ekspor_dari_state_json(tmp_path):
    out = _siapkan_output(tmp_path)
    g = shp_shape({"type": "Polygon", "coordinates": [POLY]})
    _tulis_state(out, {"D13": g})
    hasil = kartu.muat_geom_ekspor(out)
    assert set(hasil) == {"D13"}
    assert abs(hasil["D13"].area - g.area) < 1e-6
    assert kartu.muat_geom_ekspor(tmp_path / "tidak_ada") == {}
    (out / "state.json").write_text(json.dumps({"geom_blok": {"D13": "bukan wkt"}}),
                                    encoding="utf-8")
    assert kartu.muat_geom_ekspor(out) == {}


def test_komposit_piksel_nol_jadi_latar_terang():
    """RGB ekspor 3-band memakai 0 sebagai nodata; kartu tidak boleh
    menampilkannya hitam (blok C07B tampak seperti lubang)."""
    arr = np.zeros((3, 4, 4), dtype="uint8")
    out = kartu.komposit(arr)
    assert (out == 235).all()
    arr[:, 1, 1] = (60, 140, 70)
    out = kartu.komposit(arr)
    assert tuple(out[1, 1]) == (60, 140, 70)


def test_kartu_pakai_batas_ekspor_dari_state(tmp_path):
    """Batas merah kartu = geometri ekspor aktual (state.json), bukan sel PDF
    parsial; angka indeks dihitung terhadap geometri ekspor itu."""
    out = _siapkan_output(tmp_path)
    gj = tmp_path / "blok.geojson"
    gj.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"kode": "D13", "divisi": "AME III"},
         "geometry": {"type": "Polygon", "coordinates": [POLY_SETENGAH]}},
    ]}), encoding="utf-8")
    _tulis_state(out, {"D13": shp_shape({"type": "Polygon", "coordinates": [POLY]})})
    kartu.buat_kartu(str(out), str(gj), "TST01", dest=str(tmp_path / "kartu"))
    k = json.loads((tmp_path / "kartu" / "index.json").read_text(encoding="utf-8"))["kartu"][0]
    assert abs(k["luas_ekspor_ha"] - 12.0) < 0.01
    assert abs(k["luas_pdf_ha"] - 6.0) < 0.01
    assert abs(k["iou"] - 50.0) < 0.5
    assert abs(k["geser_m"] - 50.0) < 0.5


def test_gabungan_memakai_batas_ekspor_state(tmp_path):
    """Kartu gabungan harus mengisi citra sampai batas ekspor, bukan berhenti
    di poligon PDF yang hanya separuh blok."""
    out = _siapkan_output_dua(tmp_path)
    gj = tmp_path / "blok.geojson"
    gj.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"kode": "D13", "divisi": "AME III"},
         "geometry": {"type": "Polygon", "coordinates": [POLY_SETENGAH]}},
        {"type": "Feature", "properties": {"kode": "D14", "divisi": "AME III"},
         "geometry": {"type": "Polygon", "coordinates": [POLY_D14]}},
    ]}), encoding="utf-8")
    _tulis_state(out, {"D13": shp_shape({"type": "Polygon", "coordinates": [POLY]}),
                       "D14": shp_shape({"type": "Polygon", "coordinates": [POLY_D14]})})
    kartu.buat_kartu(str(out), str(gj), "TST01", dest=str(tmp_path / "kartu"))
    a = np.array(Image.open(tmp_path / "kartu" / "kartu_gabungan.png"))
    hijau = (a[..., 0] == 60) & (a[..., 1] == 140) & (a[..., 2] == 70)
    xs = np.where(hijau.any(axis=0))[0]
    assert xs.size > 0
    assert xs.max() / a.shape[1] > 0.35      # citra D13 sampai batas ekspor (bukan 25% PDF)
    g = json.loads((tmp_path / "kartu" / "index.json").read_text(encoding="utf-8"))["kartu"][0]
    assert abs(g["luas_ekspor_ha"] - 24.0) < 0.01
    assert abs(g["luas_pdf_ha"] - 18.0) < 0.01
