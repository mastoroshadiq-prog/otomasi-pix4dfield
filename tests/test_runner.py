from pathlib import Path
from core.runner import Runner

def _baris(tmp_path, n=3):
    rows = []
    for i in range(n):
        d = tmp_path / "out" / "DIV" / f"FLG01_DIV-B{i:02d}"
        rows.append({"divisi": "DIV", "kode": f"B{i:02d}", "layer": "ndre",
                     "src_data": "x.tif", "dst_dir": str(d), "nama_base": "NDRE",
                     "dst_data": str(d / "NDRE.data.tif"), "dst_rgb": None, "dst_legend": None})
    return rows

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
