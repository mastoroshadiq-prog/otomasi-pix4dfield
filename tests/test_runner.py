from pathlib import Path
import json
from core.runner import Runner

def _baris(tmp_path, n=3):
    rows = []
    for i in range(n):
        d = tmp_path / "out" / "DIV" / f"FLG01_DIV-B{i:02d}"
        rows.append({"divisi": "DIV", "kode": f"B{i:02d}", "layer": "ndre",
                     "src_data": "x.tif", "dst_dir": str(d), "nama_base": "NDRE",
                     "dst_data": str(d / "NDRE.data.tif"), "dst_rgb": None, "dst_legend": None})
    return rows

def _crop_ok(row, calls=None, ukuran=10):
    if calls is not None:
        calls.append(row["kode"])
    Path(row["dst_data"]).parent.mkdir(parents=True, exist_ok=True)
    Path(row["dst_data"]).write_bytes(b"x" * ukuran)
    return {"piksel": 1, "ukuran": ukuran}

def test_sukses_dan_csv(tmp_path):
    rows = _baris(tmp_path)
    def crop(row):
        Path(row["dst_data"]).parent.mkdir(parents=True, exist_ok=True)
        Path(row["dst_data"]).write_bytes(b"x" * 10)
        return {"piksel": 100, "ukuran": 10}
    r = Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop)
    r.run()
    snap = r.snapshot()
    assert all(it["status"] == "selesai" for it in snap["items"])
    csv = (tmp_path / "out" / "hasil_per_blok.csv").read_text(encoding="utf-8")
    assert "B00" in csv and "selesai" in csv

def test_resume_melewati_selesai(tmp_path):
    rows = _baris(tmp_path)
    calls = []
    def crop(row):
        calls.append(row["kode"])
        Path(row["dst_data"]).parent.mkdir(parents=True, exist_ok=True)
        Path(row["dst_data"]).write_bytes(b"x")
        return {"piksel": 1, "ukuran": 1}
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop).run()
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop).run()
    assert calls == ["B00", "B01", "B02"]      # run kedua tak mengulang

def test_gagal_retry_sekali_lalu_lanjut(tmp_path):
    rows = _baris(tmp_path, 2)
    state = {"n": 0}
    def crop(row):
        if row["kode"] == "B00":
            state["n"] += 1
            if state["n"] <= 2:                 # gagal di percobaan + retry
                raise RuntimeError("disk penuh")
        Path(row["dst_data"]).parent.mkdir(parents=True, exist_ok=True)
        Path(row["dst_data"]).write_bytes(b"x")
        return {"piksel": 1, "ukuran": 1}
    r = Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop)
    r.run()
    snap = {it["kode"]: it["status"] for it in r.snapshot()["items"]}
    assert snap["B00"] == "gagal" and snap["B01"] == "selesai"   # batch lanjut

def test_cancel_stop_aman(tmp_path):
    rows = _baris(tmp_path, 3)
    r = None
    def crop(row):
        Path(row["dst_data"]).parent.mkdir(parents=True, exist_ok=True)
        Path(row["dst_data"]).write_bytes(b"x")
        if row["kode"] == "B00":
            r.cancel()           # pengguna menekan Batalkan saat blok pertama selesai
        return {"piksel": 1, "ukuran": 1}
    r = Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop)
    r.run()
    snap = {it["kode"]: it["status"] for it in r.snapshot()["items"]}
    assert snap["B00"] == "selesai"
    assert snap["B01"] == "pending" and snap["B02"] == "pending"

def test_disk_penuh_hentikan_batch(tmp_path):
    rows = _baris(tmp_path, 3)
    def crop(row):
        if row["kode"] == "B01":
            raise OSError(28, "No space left on device")
        Path(row["dst_data"]).parent.mkdir(parents=True, exist_ok=True)
        Path(row["dst_data"]).write_bytes(b"x")
        return {"piksel": 1, "ukuran": 1}
    r = Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop)
    r.run()
    snap = {it["kode"]: it["status"] for it in r.snapshot()["items"]}
    assert snap["B00"] == "selesai" and snap["B01"] == "gagal" and snap["B02"] == "pending"


# --- T-2: resume aman (verifikasi file + kode flight) ---

def test_resume_verifikasi_file_hilang_diulang(tmp_path):
    rows = _baris(tmp_path)
    calls = []
    crop = lambda row: _crop_ok(row, calls, ukuran=10)
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop).run()
    Path(rows[1]["dst_data"]).unlink()                    # file B01 hilang
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop).run()
    assert calls == ["B00", "B01", "B02", "B01"]

def test_resume_ukuran_beda_diulang(tmp_path):
    rows = _baris(tmp_path, 1)
    calls = []
    crop = lambda row: _crop_ok(row, calls, ukuran=10)
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop).run()
    Path(rows[0]["dst_data"]).write_bytes(b"xx")          # ukuran file berubah
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop).run()
    assert calls == ["B00", "B00"]

def test_resume_rgb_hilang_diulang(tmp_path):
    rows = _baris(tmp_path, 1)
    rows[0]["dst_rgb"] = str(Path(rows[0]["dst_dir"]) / "NDRE.rgb.tif")
    calls = []
    def crop(row):
        calls.append(row["kode"])
        Path(row["dst_data"]).parent.mkdir(parents=True, exist_ok=True)
        Path(row["dst_data"]).write_bytes(b"x")
        Path(row["dst_rgb"]).write_bytes(b"r")
        return {"piksel": 1, "ukuran": 1}
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop).run()
    Path(rows[0]["dst_rgb"]).unlink()
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop).run()
    assert calls == ["B00", "B00"]

def test_resume_kode_flight_berbeda_diabaikan(tmp_path):
    rows = _baris(tmp_path)
    calls = []
    crop = lambda row: _crop_ok(row, calls, ukuran=4)
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop, kode_flight="FLG01").run()
    calls.clear()
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop, kode_flight="FLG02").run()
    assert calls == ["B00", "B01", "B02"]                 # resume diabaikan → semua ulang


# --- N-1: state v2 (geom sekali per blok) & snapshot ramping ---

def test_state_v2_geom_sekali_per_blok(tmp_path):
    rows = _baris(tmp_path, 1)
    rows[0]["geom"] = "POLYGON ((0 0, 1 0, 1 1, 0 0))"
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=_crop_ok,
           kode_flight="FLG01").run()
    data = json.loads((tmp_path / "out" / "state.json").read_text(encoding="utf-8"))
    assert data["versi"] == 2
    assert data["kode_flight"] == "FLG01"
    assert data["geom_blok"]["B00"] == "POLYGON ((0 0, 1 0, 1 1, 0 0))"
    assert all("geom" not in it for it in data["items"])

def test_snapshot_tanpa_geom(tmp_path):
    rows = _baris(tmp_path, 1)
    rows[0]["geom"] = "POLYGON ((0 0, 1 0, 1 1, 0 0))"
    r = Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=_crop_ok)
    r.run()
    assert "geom" not in r.snapshot()["items"][0]

def test_resume_memulihkan_geom_dari_geom_blok(tmp_path):
    """Item yang belum jalan harus tetap mendapat geom saat resume dari state v2."""
    rows = _baris(tmp_path, 1)
    rows[0]["geom"] = "POLYGON ((0 0, 1 0, 1 1, 0 0))"
    def crop_gagal(row):
        raise RuntimeError("gagal sengaja")
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop_gagal,
           kode_flight="FLG01").run()
    rows2 = _baris(tmp_path, 1)                            # tanpa geom, seperti _bangun_rows lain
    r2 = Runner(rows2, tmp_path / "out", tmp_path / "log", crop_fn=_crop_ok,
                kode_flight="FLG01")
    r2._muat_state()
    assert r2.items[0].geom == "POLYGON ((0 0, 1 0, 1 1, 0 0))"


# --- S-1: baris "dilewati (tanpa data)" tidak diproses ---

def test_runner_melewati_baris_status_dilewati(tmp_path):
    rows = _baris(tmp_path, 2)
    rows[1]["status"] = "dilewati"
    rows[1]["error"] = "tanpa data (di luar cakupan layer)"
    calls = []
    crop = lambda row: _crop_ok(row, calls)
    r = Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop)
    r.run()
    assert calls == ["B00"]
    snap = r.snapshot()
    assert snap["dilewati"] == 1 and snap["selesai"] == 1 and snap["gagal"] == 0
    csv = (tmp_path / "out" / "hasil_per_blok.csv").read_text(encoding="utf-8")
    assert "dilewati" in csv and "B01" in csv

def test_resume_dilewati_tanpa_file_tetap_dilewati(tmp_path):
    rows = _baris(tmp_path, 2)
    rows[1]["status"] = "dilewati"
    rows[1]["error"] = "tanpa data (di luar cakupan layer)"
    calls = []
    crop = lambda row: _crop_ok(row, calls)
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop).run()
    calls.clear()
    Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop).run()
    assert calls == []                                    # B00 resume, B01 tetap dilewati
    r2 = Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop)
    r2._muat_state()
    st = {it.kode: it.status for it in r2.items}
    assert st == {"B00": "selesai", "B01": "dilewati"}


# --- T-3: retry() membuat file log baru ---

def test_retry_ulang_membuat_file_log_baru(tmp_path):
    rows = _baris(tmp_path, 1)
    n = {"n": 0}
    def crop(row):
        n["n"] += 1
        if n["n"] <= 2:                                   # gagal di percobaan + retry otomatis
            raise RuntimeError("gagal sengaja")
        return _crop_ok(row)
    r = Runner(rows, tmp_path / "out", tmp_path / "log", crop_fn=crop)
    r.run()
    log1 = Path(r.log_path)
    assert log1.exists() and {it.status for it in r.items} == {"gagal"}
    r.retry("B00")                                        # tombol "Coba ulang" di UI
    r._thread.join(timeout=20)
    assert {it.kode: it.status for it in r.items}["B00"] == "selesai"
    log2 = Path(r.log_path)
    assert log2 != log1 and log2.exists()
    assert "selesai" in log2.read_text(encoding="utf-8")
    assert log1.exists()                                  # log run pertama utuh
