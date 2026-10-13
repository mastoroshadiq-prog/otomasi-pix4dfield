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
