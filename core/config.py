import json
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

@dataclass
class AppConfig:
    folder_sumber: str = ""
    folder_output: str = ""
    pdf_peta: str = str(ROOT / "data" / "sumber" / "peta_blok.pdf")
    kode_flight: str = ""
    shp_kebun: str = r"E:\2. Tanam Inti\2_Tanam_Inti.shp"
    workers: int = 1
    port: int = 0
    path_kalibrasi: str = str(ROOT / "data" / "kalibrasi.json")
    path_blok: str = str(ROOT / "data" / "blok.geojson")
    folder_palet: str = str(ROOT / "data" / "palet")
    folder_log: str = str(ROOT / "logs")

def _path(path) -> Path:
    return Path(path) if path else ROOT / "data" / "config.json"

def load_config(path=None) -> AppConfig:
    p = _path(path)
    if not p.exists():
        return AppConfig()
    data = json.loads(p.read_text(encoding="utf-8"))
    return AppConfig(**{k: v for k, v in data.items() if k in AppConfig.__dataclass_fields__})

def save_config(cfg: AppConfig, path=None) -> None:
    p = _path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(cfg), indent=2, ensure_ascii=False), encoding="utf-8")
