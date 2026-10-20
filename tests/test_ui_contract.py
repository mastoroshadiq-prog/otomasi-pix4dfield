"""Kontrak UI ringan: id elemen, struktur tahap, dan endpoint yang dipakai app.js."""
import re
from pathlib import Path

AKAR = Path(__file__).resolve().parents[1]
JS = (AKAR / "static" / "app.js").read_text(encoding="utf-8")
HTML = (AKAR / "templates" / "index.html").read_text(encoding="utf-8")
APP = (AKAR / "app.py").read_text(encoding="utf-8")
CSS = (AKAR / "static" / "style.css").read_text(encoding="utf-8")


def test_id_yang_dipakai_js_ada_di_html():
    ids = set(re.findall(r'\$\("([A-Za-z0-9_-]+)"\)', JS))
    assert ids, 'tidak ada pemanggilan $("id") yang terbaca dari app.js'
    hilang = sorted(i for i in ids if f'id="{i}"' not in HTML)
    assert not hilang, f"id dipakai app.js tapi hilang dari index.html: {hilang}"


def test_endpoint_yang_dipanggil_js_ada_di_app():
    dipanggil = set(re.findall(r'fetch\("(/api/[^"]*)"', JS))
    assert dipanggil, 'tidak ada fetch("/api/...") yang terbaca dari app.js'
    rute = set(re.findall(r'@app\.(?:get|post)\("(/api/[^"]*)"', APP))
    hilang = sorted(
        u for u in dipanggil
        if not any(r == u or r.startswith(u.rstrip("/") + "/") for r in rute)
    )
    assert not hilang, f"endpoint dipanggil app.js tapi tidak ada di app.py: {hilang}"


def test_tahap_nav_punya_panel():
    tahap = set(re.findall(r'data-tahap="([a-z]+)"', HTML))
    assert tahap == {"setup", "pindai", "jalankan", "validasi"}
    for t in tahap:
        assert f'id="tahap-{t}"' in HTML, f"panel tahap-{t} tidak ada di index.html"


def test_kartu_gabungan_punya_tampilan_khusus_di_galeri():
    assert 'k.jenis === "gabungan"' in JS
    assert "thumb-gabungan" in JS
    assert ".thumb-gabungan" in CSS
