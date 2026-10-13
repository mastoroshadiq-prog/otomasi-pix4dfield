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
