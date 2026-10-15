from core.config import AppConfig, load_config, save_config

def test_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = AppConfig(folder_sumber="F:/sumber", folder_output="F:/keluar", kode_flight="FLG03")
    save_config(cfg, p)
    assert load_config(p) == cfg

def test_missing_file_kembali_default(tmp_path):
    cfg = load_config(tmp_path / "belum_ada.json")
    assert cfg.kode_flight == ""
    assert cfg.pdf_peta.endswith("peta_blok.pdf")
    assert not hasattr(cfg, "workers")                    # N-5: field mati dihapus

def test_config_lama_dengan_workers_tetap_dimuat(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"kode_flight": "FLG09", "workers": 4}', encoding="utf-8")
    cfg = load_config(p)
    assert cfg.kode_flight == "FLG09"                     # field asing diabaikan
    assert not hasattr(cfg, "workers")

def test_abaikan_field_asing(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"kode_flight": "FLG09", "field_asing": 1}', encoding="utf-8")
    assert load_config(p).kode_flight == "FLG09"
