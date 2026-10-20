import csv, json, logging, threading, time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

@dataclass
class Item:
    divisi: str
    kode: str
    layer: str
    src_data: str
    dst_dir: str
    dst_data: str
    dst_rgb: str | None
    dst_legend: str | None
    src_rgb: str | None = None
    src_legend: str | None = None
    nama_base: str = ""
    geom: str = ""
    luas_ha: float = 0.0
    status: str = "pending"
    error: str = ""
    dur_s: float = 0.0
    size: int = 0

class Runner:
    def __init__(self, rows, output_root, folder_log, crop_fn=None,
                 qa_sample=2, folder_palet=None, kode_flight=""):
        from core import config as cfg_mod
        self.items = [Item(**r) for r in rows]
        self.output_root = Path(output_root)
        self.folder_log = Path(folder_log)
        self.kode_flight = kode_flight
        if crop_fn is None:
            from core import crop_engine
            fp = folder_palet or str(cfg_mod.ROOT / "data" / "palet")
            crop_fn = lambda row: crop_engine.proses_baris(row, fp)
        self.crop_fn = crop_fn
        self.qa_sample = qa_sample
        self._batal = threading.Event()
        self._lock = threading.Lock()
        self._thread = None
        self._logger = None
        self._qa_dibuat = 0
        self.state_path = self.output_root / "state.json"
        self.csv_path = self.output_root / "hasil_per_blok.csv"
        self.log_path = None

    def _log(self, msg):
        if self._logger:
            self._logger.info(msg)

    def snapshot(self):
        with self._lock:
            items = []
            for it in self.items:
                d = asdict(it)
                d.pop("geom", None)          # WKT tidak dipakai UI; hemat payload poll
                items.append(d)
        return {"aktif": bool(self._thread and self._thread.is_alive()),
                "total": len(items),
                "selesai": sum(1 for it in items if it["status"] == "selesai"),
                "gagal": sum(1 for it in items if it["status"] == "gagal"),
                "dilewati": sum(1 for it in items if it["status"] == "dilewati"),
                "items": items,
                "log_file": str(self.log_path) if self.log_path else ""}

    def _tulis_state(self):
        with self._lock:
            geom_blok, items = {}, []
            for it in self.items:
                d = asdict(it)
                g = d.pop("geom", "")
                if g and it.kode not in geom_blok:
                    geom_blok[it.kode] = g
                items.append(d)
            data = {"versi": 2, "kode_flight": self.kode_flight,
                    "output_root": str(self.output_root), "geom_blok": geom_blok,
                    "items": items,
                    "diperbarui": datetime.now().isoformat(timespec="seconds")}
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.state_path)

    @staticmethod
    def _berkas_lengkap(prev):
        """Verifikasi murah jalur resume: file output ada & ukuran data cocok."""
        for k in ("dst_data", "dst_rgb", "dst_legend"):
            p = prev.get(k)
            if p and not Path(p).exists():
                return False
        d, ukuran = prev.get("dst_data"), prev.get("size") or 0
        return not (d and ukuran and Path(d).stat().st_size != ukuran)

    def _muat_state(self):
        """Resume: item selesai/dilewati dilewati — setelah verifikasi file & flight."""
        if not self.state_path.exists():
            return
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        flight_lama = data.get("kode_flight", "")
        if data.get("versi", 1) >= 2 and flight_lama != self.kode_flight:
            self._log(f"state.json milik flight '{flight_lama}' ≠ '{self.kode_flight}' — resume diabaikan")
            return
        geom_blok = data.get("geom_blok", {})
        lama = {(it["kode"], it["layer"]): it for it in data.get("items", [])}
        with self._lock:
            for it in self.items:
                prev = lama.get((it.kode, it.layer))
                if prev and prev["status"] in ("selesai", "dilewati"):
                    if prev["status"] == "selesai" and not self._berkas_lengkap(prev):
                        self._log(f"{it.kode}/{it.layer}: file output hilang/berubah — diulang")
                        continue
                    it.status = prev["status"]
                    it.size = prev.get("size", 0)
                    it.dur_s = prev.get("dur_s", 0.0)
                    it.error = prev.get("error", "")
                if not it.geom and geom_blok.get(it.kode):
                    it.geom = geom_blok[it.kode]

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._batal.clear()
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._batal.set()

    def retry(self, kode):
        with self._lock:
            ada = False
            for it in self.items:
                if it.kode == kode and it.status == "gagal":
                    it.status = "pending"
                    it.error = ""
                    ada = True
        if ada:
            self.start()

    def run(self):
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.folder_log.mkdir(parents=True, exist_ok=True)
        base = self.folder_log / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"
        self.log_path = base
        n = 1
        while self.log_path.exists():          # run kedua dalam detik yang sama
            self.log_path = base.with_name(f"{base.stem}_{n}.log")
            n += 1
        if self._logger is None:
            self._logger = logging.getLogger(f"runner_{id(self)}")
            self._logger.setLevel(logging.INFO)
        for h in list(self._logger.handlers):  # tutup handler lama (retry) agar file log baru terpasang
            self._logger.removeHandler(h)
            h.close()
        fh = logging.FileHandler(self.log_path, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self._logger.addHandler(fh)
        self._muat_state()
        with self._lock:
            todo = [it for it in self.items if it.status == "pending"]
            n_dilewati = sum(1 for it in self.items if it.status == "dilewati")
        self._log(f"Batch mulai: {len(todo)} item"
                  + (f" ({n_dilewati} dilewati tanpa data)" if n_dilewati else ""))
        for it in todo:
            if self._batal.is_set():
                self._log("Dibatalkan — item tersisa tetap pending")
                break
            self._proses(it)
            self._tulis_state()
            self._tulis_csv()
        self._tulis_state()
        self._tulis_csv()
        self._log("Batch selesai")

    def _proses(self, it):
        row = {"divisi": it.divisi, "kode": it.kode, "layer": it.layer, "src_data": it.src_data,
               "dst_dir": it.dst_dir, "dst_data": it.dst_data, "dst_rgb": it.dst_rgb,
               "dst_legend": it.dst_legend, "src_rgb": it.src_rgb, "src_legend": it.src_legend,
               "nama_base": it.nama_base, "geom": it.geom}
        for percobaan in (1, 2):      # retry otomatis 1×
            t0 = time.time()
            it.status = "berjalan"
            it.error = ""
            self._log(f"{it.kode}/{it.layer}: mulai (percobaan {percobaan})")
            try:
                stat = self.crop_fn(row)
                it.size = stat.get("ukuran", 0)
                it.dur_s = time.time() - t0
                it.status = "selesai"
                self._log(f"{it.kode}/{it.layer}: selesai {it.size} B dalam {it.dur_s:.1f}s")
                if (it.layer == "ortho" and self._qa_dibuat < self.qa_sample
                        and it.dst_rgb and it.geom):
                    try:
                        from core import qa_overlay
                        qa_overlay.render_blok_overlay(
                            it.dst_rgb, it.geom, str(Path(it.dst_dir) / "qa_overlay.png"))
                        self._log(f"{it.kode}: overlay QA → qa_overlay.png")
                    except Exception as e:
                        self._log(f"{it.kode}: overlay QA gagal ({e})")
                    self._qa_dibuat += 1
                return
            except KeyboardInterrupt:
                it.status = "pending"
                self.cancel()
                return
            except Exception as e:
                it.error = str(e)
                it.dur_s = time.time() - t0
                self._log(f"{it.kode}/{it.layer}: gagal ({e})")
                if getattr(e, "errno", None) == 28:
                    self._log("Disk penuh — batch dihentikan; item tersisa tetap pending")
                    it.status = "gagal"
                    self.cancel()
                    return
        it.status = "gagal"

    def _tulis_csv(self):
        with self._lock:
            items = [asdict(it) for it in self.items]
        cols = ["divisi", "kode", "luas_ha", "layer", "status", "size", "dur_s", "dst_data", "error"]
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=cols)
            wr.writeheader()
            for it in items:
                wr.writerow({k: it[k] for k in cols})
