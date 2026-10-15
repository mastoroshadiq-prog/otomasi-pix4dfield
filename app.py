import json, shutil, socket, threading, webbrowser
from dataclasses import asdict, fields
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from core import config as cfg_mod
from core import layer_scan, pdf_blok
from core.runner import Runner

app = Flask(__name__)
KONFIG = cfg_mod.load_config()
RUNNER = {"obj": None}
KARTU = {"status": None}
JALANKAN_LOCK = threading.Lock()
PILIH_LOCK = threading.Lock()

_JENIS_PILIH = {
    "folder": ("Pilih folder", None),
    "pdf": ("Pilih peta blok PDF", [("Peta PDF", "*.pdf"), ("Semua berkas", "*.*")]),
    "shp": ("Pilih shapefile kebun", [("Shapefile", "*.shp"), ("Semua berkas", "*.*")]),
}


def _port_bebas(mulai=5000, akhir=5050):
    for p in range(mulai, akhir):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return None


def _free_bytes(path):
    p = Path(path or ".").resolve()
    while not p.exists() and p.parent != p:
        p = p.parent
    return shutil.disk_usage(str(p)).free


def _folder_awal(nilai):
    """Folder awal dialog: path yang ada terdekat dari nilai lama ('' bila tak ada)."""
    p = Path(nilai) if nilai else None
    while p and not p.exists() and p.parent != p:
        p = p.parent
    return str(p) if p and p.exists() else ""


def _dialog_pilih(jenis, nilai):
    """Dialog native Windows (tkinter). Return path terpilih, '' bila dibatalkan."""
    import tkinter as tk
    from tkinter import filedialog
    judul, tipe = _JENIS_PILIH[jenis]
    awal = _folder_awal(nilai)
    akar = tk.Tk()
    akar.withdraw()
    akar.attributes("-topmost", True)
    try:
        if jenis == "folder":
            return filedialog.askdirectory(parent=akar, title=judul, initialdir=awal or None) or ""
        return filedialog.askopenfilename(parent=akar, title=judul, initialdir=awal or None,
                                          filetypes=tipe) or ""
    finally:
        akar.destroy()


def _muat_geojson():
    """Muat blok.geojson; bila belum ada: kalibrasi + ekstraksi dari PDF (sekali)."""
    gj_path = Path(KONFIG.path_blok)
    if not gj_path.exists():
        pdf = Path(KONFIG.pdf_peta)
        if not pdf.exists():
            raise ValueError(f"PDF peta tidak ditemukan: {pdf}")
        kal_path = Path(KONFIG.path_kalibrasi)
        if kal_path.exists():
            kal = pdf_blok.muat_kalibrasi(kal_path)
        else:
            kal = pdf_blok.kalibrasi_pdf(pdf)
            pdf_blok.simpan_kalibrasi(kal, kal_path)
        if not kal["ok"]:
            raise ValueError(f"Kalibrasi PDF gagal (residual maks {kal['residual_max_m']:.2f} m)")
        shp = KONFIG.shp_kebun if KONFIG.shp_kebun and Path(KONFIG.shp_kebun).exists() else None
        pdf_blok.ekstrak_blok(pdf, kal, gj_path, gj_path.with_name("qa_pdf_blok.json"),
                              gj_path.with_name("qa_overlay_peta.png"), shp_path=shp)
    return json.loads(gj_path.read_text(encoding="utf-8"))


def _bangun_rows():
    gj = _muat_geojson()
    if not KONFIG.folder_sumber:
        raise ValueError("Folder sumber belum diisi")
    if not KONFIG.folder_output:
        raise ValueError("Folder output belum diisi")
    if not KONFIG.kode_flight:
        raise ValueError("Kode flight belum diisi (mis. FLG03)")
    hasil = layer_scan.scan_folder(KONFIG.folder_sumber)
    if "ortho" not in hasil["layers"]:
        raise ValueError("Layer Orthomosaic (5-band) tidak ditemukan di folder sumber")
    blok = layer_scan.blok_dalam_cakupan(gj, hasil["layers"]["ortho"]["bounds"])
    if not blok:
        raise ValueError("Tidak ada blok peta yang beririsan dengan cakupan ortho")
    rows = layer_scan.rencana_output(blok, hasil["layers"], KONFIG.folder_output, KONFIG.kode_flight)
    from shapely.geometry import shape
    wkt_map = {f["properties"]["kode"]: shape(f["geometry"]).wkt for f in blok}
    for r in rows:
        r["geom"] = wkt_map[r["kode"]]
    luas_blok = sum(f["properties"]["luas_ha"] for f in blok)
    ukuran_src = sum(Path(v["data"]).stat().st_size for v in hasil["layers"].values())
    luas_fp = layer_scan.luas_footprint_ha(hasil["layers"]["ortho"]["data"])
    estimasi = layer_scan.estimasi_byte_output(ukuran_src, luas_blok, luas_fp)
    kal = None
    kal_path = Path(KONFIG.path_kalibrasi)
    if kal_path.exists():
        k = pdf_blok.muat_kalibrasi(kal_path)
        kal = {"residual_max_m": k["residual_max_m"], "titik_kontrol": k["titik_kontrol"]}
    return {"rows": rows, "layers": {k: str(v["data"]) for k, v in hasil["layers"].items()},
            "ditolak": hasil["ditolak"], "n_blok": len(blok), "estimasi_byte": estimasi,
            "blok": [{"kode": f["properties"]["kode"],
                      "divisi": f["properties"].get("divisi", ""),
                      "luas_ha": f["properties"].get("luas_ha")} for f in blok],
            "kalibrasi": kal}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/config")
def get_config():
    return jsonify(asdict(KONFIG))


@app.post("/api/config")
def post_config():
    data = request.get_json(force=True)
    for f in fields(KONFIG):
        if f.name in data:
            setattr(KONFIG, f.name, data[f.name])
    cfg_mod.save_config(KONFIG)
    return jsonify({"ok": True})


@app.post("/api/pilih")
def api_pilih():
    data = request.get_json(force=True, silent=True) or {}
    jenis = data.get("jenis", "")
    if jenis not in _JENIS_PILIH:
        return jsonify({"ok": False, "error": "Jenis pilihan tidak dikenal"}), 400
    try:
        with PILIH_LOCK:
            hasil = _dialog_pilih(jenis, str(data.get("nilai") or ""))
    except Exception as e:
        return jsonify({"ok": False, "error": f"Dialog gagal dibuka: {e}"}), 500
    return jsonify({"ok": True, "path": str(Path(hasil)) if hasil else None})


@app.get("/api/blok")
def get_blok():
    try:
        gj = _muat_geojson()
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True,
                    "blok": [{"kode": f["properties"]["kode"],
                              "divisi": f["properties"].get("divisi", ""),
                              "luas_ha": f["properties"].get("luas_ha")} for f in gj["features"]]})


@app.post("/api/blok/divisi")
def post_blok_divisi():
    data = request.get_json(force=True)
    kode, divisi = data["kode"], data["divisi"]
    gj_path = Path(KONFIG.path_blok)
    gj = json.loads(gj_path.read_text(encoding="utf-8"))
    n = 0
    for f in gj["features"]:
        if f["properties"]["kode"] == kode:
            f["properties"]["divisi"] = divisi
            n += 1
    gj_path.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    return jsonify({"ok": n > 0, "diubah": n})


@app.post("/api/pindai")
def pindai():
    try:
        info = _bangun_rows()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    bebas = _free_bytes(KONFIG.folder_output)
    return jsonify({"ok": True, "n_blok": info["n_blok"], "layers": info["layers"],
                    "ditolak": info["ditolak"], "n_baris": len(info["rows"]),
                    "estimasi_byte": info["estimasi_byte"], "disk_bebas_byte": bebas,
                    "cukup_disk": bebas > info["estimasi_byte"] * 1.2,
                    "blok": info["blok"], "kalibrasi": info["kalibrasi"]})


@app.post("/api/jalankan")
def jalankan():
    if not JALANKAN_LOCK.acquire(blocking=False):
        return jsonify({"ok": False, "error": "Permintaan lain sedang diproses"}), 400
    try:
        if RUNNER["obj"] and RUNNER["obj"].snapshot()["aktif"]:
            return jsonify({"ok": False, "error": "Batch sedang berjalan"}), 400
        out = Path(KONFIG.folder_output)
        if out.exists() and any(out.iterdir()) and not out.name.endswith("_auto"):
            return jsonify({"ok": False, "error":
                            "Folder output sudah berisi dan bukan folder baru '_auto' — "
                            "pilih folder output baru agar arsip lama tidak tertimpa"}), 400
        st_path = out / "state.json"
        if st_path.exists():
            st = json.loads(st_path.read_text(encoding="utf-8"))
            if st.get("versi", 1) >= 2 and st.get("kode_flight") and st["kode_flight"] != KONFIG.kode_flight:
                return jsonify({"ok": False, "error":
                                f"Folder output berisi hasil flight '{st['kode_flight']}' — "
                                f"kode flight sekarang '{KONFIG.kode_flight}'. "
                                "Ganti folder output atau kode flight"}), 400
        try:
            info = _bangun_rows()
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        bebas = _free_bytes(KONFIG.folder_output)
        if bebas < info["estimasi_byte"] * 1.2:
            return jsonify({"ok": False, "error": "Ruang disk tidak cukup: estimasi %.1f GB, bebas %.1f GB"
                            % (info["estimasi_byte"] / 1e9, bebas / 1e9)}), 400
        r = Runner(info["rows"], KONFIG.folder_output, KONFIG.folder_log,
                   folder_palet=KONFIG.folder_palet, kode_flight=KONFIG.kode_flight)
        RUNNER["obj"] = r
        r.start()
        return jsonify({"ok": True})
    finally:
        JALANKAN_LOCK.release()


@app.get("/api/status")
def status():
    r = RUNNER["obj"]
    if r is None:
        return jsonify({"aktif": False, "items": [], "total": 0, "selesai": 0,
                        "gagal": 0, "log_tail": ""})
    snap = r.snapshot()
    log_tail = ""
    if r.log_path and Path(r.log_path).exists():
        log_tail = "\n".join(Path(r.log_path).read_text(encoding="utf-8", errors="replace").splitlines()[-80:])
    snap["log_tail"] = log_tail
    return jsonify(snap)


@app.post("/api/batalkan")
def batalkan():
    if RUNNER["obj"]:
        RUNNER["obj"].cancel()
    return jsonify({"ok": True})


@app.post("/api/ulangi")
def ulangi():
    kode = request.get_json(force=True)["kode"]
    if RUNNER["obj"]:
        RUNNER["obj"].retry(kode)
    return jsonify({"ok": True})


@app.post("/api/buka-folder")
def buka_folder():
    import os
    if KONFIG.folder_output and Path(KONFIG.folder_output).exists():
        os.startfile(KONFIG.folder_output)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Folder output belum ada"}), 400


@app.get("/api/unduh/hasil")
def unduh_hasil():
    p = Path(KONFIG.folder_output) / "hasil_per_blok.csv"
    if not p.exists():
        return jsonify({"ok": False, "error": "CSV belum ada"}), 404
    return send_file(p, as_attachment=True)


@app.get("/api/unduh/log")
def unduh_log():
    r = RUNNER["obj"]
    if r is None or not r.log_path or not Path(r.log_path).exists():
        return jsonify({"ok": False, "error": "Log belum ada"}), 404
    return send_file(r.log_path, as_attachment=True)


def _folder_kartu():
    return Path(KONFIG.folder_output) / "_validasi"


@app.get("/api/kartu")
def api_kartu():
    if not KONFIG.folder_output:
        return jsonify({"ok": True, "kartu": [], "dilewati": [], "dibuat": None})
    idx = _folder_kartu() / "index.json"
    if not idx.exists():
        return jsonify({"ok": True, "kartu": [], "dilewati": [], "dibuat": None})
    return jsonify({"ok": True, **json.loads(idx.read_text(encoding="utf-8"))})


@app.get("/api/kartu/file/<nama>")
def api_kartu_file(nama):
    if Path(nama).name != nama or not nama.lower().endswith(".png"):
        return jsonify({"ok": False, "error": "Nama file tidak valid"}), 400
    p = _folder_kartu() / nama
    if not p.exists():
        return jsonify({"ok": False, "error": "Kartu tidak ditemukan"}), 404
    return send_file(p)


@app.post("/api/kartu/buat")
def api_kartu_buat():
    if RUNNER["obj"] and RUNNER["obj"].snapshot()["aktif"]:
        return jsonify({"ok": False, "error": "Batch sedang berjalan — tunggu selesai"}), 400
    if KARTU["status"] and KARTU["status"].get("aktif"):
        return jsonify({"ok": False, "error": "Pembuatan kartu sedang berjalan"}), 400
    if not KONFIG.folder_output:
        return jsonify({"ok": False, "error": "Folder output belum diisi"}), 400
    if not KONFIG.kode_flight:
        return jsonify({"ok": False, "error": "Kode flight belum diisi"}), 400
    try:
        _muat_geojson()
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    KARTU["status"] = {"aktif": True, "i": 0, "n": 0, "pesan": "menyiapkan…",
                       "selesai": 0, "error": ""}

    def _jalan():
        from core import kartu as kartu_mod
        try:
            hasil = kartu_mod.buat_kartu(
                KONFIG.folder_output, KONFIG.path_blok, KONFIG.kode_flight,
                path_shp=KONFIG.shp_kebun or None,
                path_kalibrasi=KONFIG.path_kalibrasi or None,
                progress=lambda i, n, k: KARTU["status"].update({"i": i, "n": n, "pesan": k}))
            KARTU["status"].update({"aktif": False, "selesai": hasil["kartu"],
                                    "dilewati": hasil["dilewati"], "dest": hasil["dest"]})
        except Exception as e:
            KARTU["status"].update({"aktif": False, "error": str(e)})

    threading.Thread(target=_jalan, daemon=True).start()
    return jsonify({"ok": True})


@app.get("/api/kartu/status")
def api_kartu_status():
    return jsonify(KARTU["status"] or {"aktif": False})


if __name__ == "__main__":
    port = KONFIG.port or _port_bebas()
    if port is None:
        raise SystemExit("Tidak ada port bebas di 127.0.0.1:5000-5049 — tutup aplikasi lain lalu coba lagi")
    threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host="127.0.0.1", port=port, debug=False)
