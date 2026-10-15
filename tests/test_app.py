def test_halaman_utama():
    import app as aplikasi
    c = aplikasi.app.test_client()
    r = c.get("/")
    assert r.status_code == 200 and "Ekspor Blok" in r.get_data(as_text=True)

def test_config_roundtrip(tmp_path, monkeypatch):
    import app as aplikasi
    from core import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "ROOT", tmp_path)
    c = aplikasi.app.test_client()
    r = c.post("/api/config", json={"folder_sumber": str(tmp_path), "kode_flight": "FLG03"})
    assert r.status_code == 200
    assert c.get("/api/config").get_json()["kode_flight"] == "FLG03"

def test_status_tanpa_run():
    import app as aplikasi
    c = aplikasi.app.test_client()
    j = c.get("/api/status").get_json()
    assert j["aktif"] is False and j["total"] == 0

def test_unduh_belum_ada(tmp_path, monkeypatch):
    import app as aplikasi
    monkeypatch.setattr(aplikasi.KONFIG, "folder_output", str(tmp_path / "kosong"))
    c = aplikasi.app.test_client()
    assert c.get("/api/unduh/hasil").status_code == 404

def test_api_kartu_kosong(tmp_path, monkeypatch):
    import app as aplikasi
    monkeypatch.setattr(aplikasi.KONFIG, "folder_output", str(tmp_path / "kosong"))
    c = aplikasi.app.test_client()
    j = c.get("/api/kartu").get_json()
    assert j["ok"] is True and j["kartu"] == []

def test_api_kartu_daftar_dan_file(tmp_path, monkeypatch):
    import json
    import app as aplikasi
    d = tmp_path / "_validasi"
    d.mkdir()
    (d / "kartu_D13.png").write_bytes(b"\x89PNG\r\n\x1a\nisi")
    (d / "index.json").write_text(json.dumps(
        {"kartu": [{"kode": "D13", "file": "kartu_D13.png"}], "dilewati": []}), encoding="utf-8")
    monkeypatch.setattr(aplikasi.KONFIG, "folder_output", str(tmp_path))
    c = aplikasi.app.test_client()
    assert [k["kode"] for k in c.get("/api/kartu").get_json()["kartu"]] == ["D13"]
    assert c.get("/api/kartu/file/kartu_D13.png").status_code == 200
    assert c.get("/api/kartu/file/lain.txt").status_code == 400
    assert c.get("/api/kartu/file/..%5Capp.py").status_code == 400
    assert c.get("/api/kartu/file/..%2F..%2Fapp.py").status_code == 404
    assert c.get("/api/kartu/file/kartu_X.png").status_code == 404

def test_api_kartu_buat_tanpa_output(monkeypatch):
    import app as aplikasi
    monkeypatch.setattr(aplikasi.KONFIG, "folder_output", "")
    c = aplikasi.app.test_client()
    r = c.post("/api/kartu/buat")
    assert r.status_code == 400 and r.get_json()["ok"] is False


def _poligon(x0, y0, sisi):
    return [[x0, y0], [x0 + sisi, y0], [x0 + sisi, y0 + sisi], [x0, y0 + sisi], [x0, y0]]


def _siapkan_sumber_uji(tmp_path):
    """Ortho 5-band 200×200 @5 m: bbox 100 ha, alpha separuh kanan nol → footprint 50 ha."""
    import numpy as np
    import rasterio
    src = tmp_path / "sumber"
    src.mkdir()
    arr = np.full((5, 200, 200), 100.0, dtype="float32")
    arr[4, :, 100:] = 0.0
    with rasterio.open(src / "Orthomosaic.data.tif", "w", driver="GTiff", width=200,
                       height=200, count=5, dtype="float32", crs="EPSG:32749",
                       transform=rasterio.transform.from_origin(300000, 9960000, 5, 5)) as ds:
        ds.write(arr)
    with rasterio.open(src / "NDRE.data.tif", "w", driver="GTiff", width=20, height=20,
                       count=1, dtype="float32", crs="EPSG:32749",
                       transform=rasterio.transform.from_origin(300000, 9960000, 50, 50)) as ds:
        ds.write(np.ones((1, 20, 20), dtype="float32"))
    return src


def _konfig_pindai(tmp_path, monkeypatch, features):
    import json
    import app as aplikasi
    src = _siapkan_sumber_uji(tmp_path)
    gj_path = tmp_path / "blok.geojson"
    gj_path.write_text(json.dumps({"type": "FeatureCollection", "features": features}),
                       encoding="utf-8")
    for k, v in {"folder_sumber": str(src), "folder_output": str(tmp_path / "out"),
                 "kode_flight": "TST01", "path_blok": str(gj_path)}.items():
        monkeypatch.setattr(aplikasi.KONFIG, k, v)
    return aplikasi, src


def test_pindai_estimasi_berbasis_footprint(tmp_path, monkeypatch):
    fitur = [
        {"type": "Feature", "properties": {"kode": "D01", "divisi": "AME III", "luas_ha": 25.0},
         "geometry": {"type": "Polygon", "coordinates": [_poligon(300000, 9959500, 500)]}},
        {"type": "Feature", "properties": {"kode": "X99", "divisi": "LAIN", "luas_ha": 1000.0},
         "geometry": {"type": "Polygon", "coordinates": [_poligon(400000, 9900000, 10000)]}},
    ]
    aplikasi, src = _konfig_pindai(tmp_path, monkeypatch, fitur)
    c = aplikasi.app.test_client()
    j = c.post("/api/pindai").get_json()
    assert j["ok"] is True and j["n_blok"] == 1
    byte_src = sum((src / n).stat().st_size for n in ("Orthomosaic.data.tif", "NDRE.data.tif"))
    assert j["estimasi_byte"] == int(byte_src / 50.0 * 25.0 * 0.84)  # footprint 50 ha, blok 25 ha
    lama = int(byte_src * (25.0 / 1025.0) * 0.6)                     # rumus lama: basis seluruh peta
    assert j["estimasi_byte"] != lama
    assert j["cukup_disk"] is True
    monkeypatch.setattr(aplikasi, "_free_bytes", lambda p: 0)
    j2 = c.post("/api/pindai").get_json()
    assert j2["cukup_disk"] is False


def test_pindai_daftar_blok_tidak_dipotong(tmp_path, monkeypatch):
    fitur = []
    n = 0
    for baris in range(22):
        for kolom in range(23):
            n += 1
            x, y = 300000 + kolom * 42, 9959000 + baris * 42
            fitur.append({"type": "Feature",
                          "properties": {"kode": f"K{n:03d}", "divisi": "UJI", "luas_ha": 0.18},
                          "geometry": {"type": "Polygon", "coordinates": [_poligon(x, y, 40)]}})
    aplikasi, _ = _konfig_pindai(tmp_path, monkeypatch, fitur)
    c = aplikasi.app.test_client()
    j = c.post("/api/pindai").get_json()
    assert j["n_blok"] == n == 506
    assert len(j["blok"]) == n


# --- T-2 di level API: /api/jalankan ---

def _konfig_jalankan(tmp_path, monkeypatch, nama_out="out_auto"):
    fitur = [{"type": "Feature",
              "properties": {"kode": "D01", "divisi": "AME III", "luas_ha": 25.0},
              "geometry": {"type": "Polygon", "coordinates": [_poligon(300000, 9959500, 500)]}}]
    aplikasi, src = _konfig_pindai(tmp_path, monkeypatch, fitur)
    out = tmp_path / nama_out
    for k, v in {"folder_output": str(out), "folder_log": str(tmp_path / "log"),
                 "folder_palet": str(tmp_path / "palet")}.items():
        monkeypatch.setattr(aplikasi.KONFIG, k, v)
    return aplikasi, src, out


def test_jalankan_tolak_folder_berisi_bukan_auto(tmp_path, monkeypatch):
    import app as aplikasi
    aplikasi, src, out = _konfig_jalankan(tmp_path, monkeypatch, nama_out="arsip_lama")
    out.mkdir()
    (out / "file_lama.tif").write_bytes(b"x")
    c = aplikasi.app.test_client()
    r = c.post("/api/jalankan")
    assert r.status_code == 400 and "_auto" in r.get_json()["error"]


def test_jalankan_tolak_state_flight_berbeda(tmp_path, monkeypatch):
    import json
    import app as aplikasi
    aplikasi, src, out = _konfig_jalankan(tmp_path, monkeypatch)
    out.mkdir()
    (out / "state.json").write_text(json.dumps(
        {"versi": 2, "kode_flight": "FLG01", "items": []}), encoding="utf-8")
    monkeypatch.setattr(aplikasi.KONFIG, "kode_flight", "FLG02")
    c = aplikasi.app.test_client()
    r = c.post("/api/jalankan")
    assert r.status_code == 400 and "FLG01" in r.get_json()["error"]


def test_jalankan_batch_sintetis_via_api(tmp_path, monkeypatch):
    import json
    import app as aplikasi
    aplikasi, src, out = _konfig_jalankan(tmp_path, monkeypatch)
    c = aplikasi.app.test_client()
    r = c.post("/api/jalankan")
    assert r.status_code == 200 and r.get_json()["ok"] is True
    rn = aplikasi.RUNNER["obj"]
    rn._thread.join(timeout=60)
    snap = rn.snapshot()
    assert snap["aktif"] is False and snap["total"] == 2 and snap["selesai"] == 2
    dir_blok = out / "AME III" / "TST01_AMEIII-D01"
    dst = dir_blok / "Orthomosaic - TST01_AMEIII-D01.data.tif"
    assert dst.exists() and dst.stat().st_size > 0
    assert (dir_blok / "NDRE.data.tif").exists()
    assert (dir_blok / "NDRE.rgb.tif").exists() and (dir_blok / "NDRE.legend.png").exists()
    st = json.loads((out / "state.json").read_text(encoding="utf-8"))
    assert st["versi"] == 2 and st["kode_flight"] == "TST01"
    assert "D01" in st["geom_blok"]
    j = c.get("/api/status").get_json()
    assert "Batch" in j["log_tail"]                        # T-3: log run terbaca UI
    aplikasi.RUNNER["obj"] = None


def test_jalankan_lock_menolak_permintaan_bersamaan(tmp_path, monkeypatch):
    import app as aplikasi
    aplikasi, src, out = _konfig_jalankan(tmp_path, monkeypatch)
    c = aplikasi.app.test_client()
    assert aplikasi.JALANKAN_LOCK.acquire(blocking=False)  # simulasi request lain masih jalan
    try:
        r = c.post("/api/jalankan")
    finally:
        aplikasi.JALANKAN_LOCK.release()
    assert r.status_code == 400 and "sedang diproses" in r.get_json()["error"]


def test_port_bebas_habis_kembalikan_none(monkeypatch):
    import app as aplikasi
    class SS:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def connect_ex(self, addr): return 0               # semua port "terpakai"
    monkeypatch.setattr(aplikasi.socket, "socket", lambda *a, **k: SS())
    assert aplikasi._port_bebas() is None
