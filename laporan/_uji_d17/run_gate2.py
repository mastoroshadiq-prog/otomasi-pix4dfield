"""Gate 2 batch: 8 blok AME III dari ekspor uji, kode flight FLG01-AMEIII.

Jalankan: .venv/Scripts/python.exe laporan/_uji_d17/run_gate2.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from shapely.geometry import shape  # noqa: E402
from core import layer_scan  # noqa: E402
from core.runner import Runner  # noqa: E402

SUMBER = r"F:\dataset\Pix4DField-export-Fligh01\AME III - Test OtoExport"
OUTPUT = r"F:\dataset\Pix4DField-export-FLG01-AMEIII_auto"
KODE_FLIGHT = "FLG01-AMEIII"
BLOK = {"D13", "D14", "D15", "D16", "E13", "E14", "E15", "E16"}


def main():
    gj = json.loads((ROOT / "data" / "blok.geojson").read_text(encoding="utf-8"))
    hasil = layer_scan.scan_folder(SUMBER)
    sel = [f for f in layer_scan.blok_dalam_cakupan(gj, hasil["layers"]["ortho"]["bounds"])
           if f["properties"]["kode"] in BLOK]
    assert len(sel) == len(BLOK), f"blok target tidak lengkap: {len(sel)}/{len(BLOK)}"
    rows = layer_scan.rencana_output(sel, hasil["layers"], OUTPUT, KODE_FLIGHT)
    wkt = {f["properties"]["kode"]: shape(f["geometry"]).wkt for f in sel}
    for r in rows:
        r["geom"] = wkt[r["kode"]]
    print(f"Batch Gate 2: {len(sel)} blok x {len(hasil['layers'])} layer = {len(rows)} item")
    r = Runner(rows, OUTPUT, str(ROOT / "logs"),
               folder_palet=str(ROOT / "data" / "palet"), kode_flight=KODE_FLIGHT)
    t0 = time.time()
    r.run()
    snap = r.snapshot()
    print(f"\nSelesai dalam {time.time() - t0:.0f}s: "
          f"{snap['selesai']}/{snap['total']} selesai, {snap['gagal']} gagal")
    for it in snap["items"]:
        if it["status"] != "selesai":
            print(f"  {it['kode']}/{it['layer']}: {it['status']} {it['error']}")
    sys.exit(1 if snap["gagal"] else 0)


if __name__ == "__main__":
    main()
