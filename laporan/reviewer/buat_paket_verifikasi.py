"""Rakit paket verifikasi perbaikan (untuk agent AI reviewer independen).

Menghasilkan di laporan/reviewer/:
  - PAKET_VERIFIKASI_PERBAIKAN.md  (kode+tes+dokumen+bukti dalam SATU berkas, untuk AI chat)
  - paket_verifikasi_perbaikan_<tanggal>.zip  (versi ZIP: dokumen, kode, tes, bukti teks, diff)

Jalankan dari dalam repo:
  cd /d/pix4dfield_exporting_tools && .venv/Scripts/python.exe laporan/reviewer/buat_paket_verifikasi.py

Paket TIDAK memuat raster maupun koordinat poligon blok; ada scan sanitasi
otomatis yang menolak berkas bila menemukan pasangan koordinat UTM atau WKT
poligon berkoordinat besar (di luar fixture sintetis pada tests/).
"""
import os
import re
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "laporan" / "reviewer"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = Path(sys.executable)
TGL = date.today().strftime("%Y-%m-%d")
COMMIT_BASELINE = "65b4b44"

DOK_RESPONS = [
    "laporan/reviewer/LAPORAN_PERBAIKAN_2026-10-14.md",
]
DOK_REVIEW = [
    "laporan/reviewer/Review-Independen-2-Ekspor-Blok-Otomatis-2026-10-14.md",
    "laporan/reviewer/Verifikasi-Perbaikan-Ekspor-Blok-2026-10-14.md",
    "laporan/reviewer/LAPORAN_REVIEW_2026-10-14.md",
]
DOK_KONTEKS = [
    "laporan/reviewer/RINGKASAN_PROYEK_UNTUK_REVIEW.md",
    "laporan/reviewer/BRIEF.md",
    "laporan/reviewer/PANDUAN_REVIEW_AGENT_LAIN.md",
]
DOKS = [
    "README.md",
    "docs/superpowers/specs/2026-10-13-ekspor-blok-otomatis-design.md",
    "docs/superpowers/plans/2026-10-13-ekspor-blok-otomatis-implementasi.md",
]
KODE = [
    ".gitignore",
    "app.py",
    "jalankan.bat",
    "requirements.txt",
    "core/__init__.py",
    "core/config.py",
    "core/crop_engine.py",
    "core/kartu.py",
    "core/layer_scan.py",
    "core/palet.py",
    "core/pdf_blok.py",
    "core/qa_overlay.py",
    "core/runner.py",
    "templates/index.html",
    "static/app.js",
    "static/style.css",
]
TESTS = sorted(
    str(p.relative_to(ROOT)).replace("\\", "/")
    for p in (ROOT / "tests").glob("*.py")
)
EVID = [
    # basis (sudah ada di paket review pertama)
    "laporan/_uji_d17/RINGKASAN.md",
    "laporan/_uji_d17/gate2_verifikasi.json",
    "laporan/_uji_d17/verify_gate2.py",
    "laporan/_uji_d17/run_gate2.py",
    # baru untuk verifikasi perbaikan
    "laporan/_uji_d17/BUKTI_diff_vs_commit.txt",
    "laporan/_uji_d17/bukti_gate1_md5.txt",
    "laporan/_uji_d17/bukti_state_v2_sanitized.json",
    "laporan/_uji_d17/bukti_daftar_tes.txt",
    "laporan/_uji_d17/bukti_nir_rededge.py",
    "laporan/_uji_d17/bukti_nir_rededge.txt",
    "laporan/_uji_d17/verify_gate2_run_20261014.txt",
]
SKRIP_PAKET = [
    "laporan/reviewer/buat_paket_verifikasi.py",
    "laporan/reviewer/buat_paket_review.py",
]

BAHASA = {".py": "python", ".js": "javascript", ".css": "css", ".html": "html",
          ".bat": "bat", ".json": "json"}

# Pola sanitasi: pasangan koordinat UTM (x 6 digit, y 7 digit berawalan 9 -> EPSG:32749)
# dan WKT poligon berkoordinat besar; WKT yang identik dengan fixture sintetis
# di tests/ (= kebijakan: fixture sintetis boleh) diizinkan lewat daftar fixture.
POLA_PASANGAN = re.compile(r"\b\d{6}\.\d+\s+9\d{6}\.\d+\b|\b\d{6}\.\d+,\s*9\d{6}\.\d+\b")
POLA_WKT_UTM = re.compile(r"POLYGON\s*\(\(\s*\(?-?\d{5,}[^)]*\)\)")


def normal_wkt(s):
    return re.sub(r"\s+", " ", s).strip()


def fixture_sintetis():
    """Kumpulan WKT fixture yang dipakai tests/ (sintetis, boleh muncul di mana pun)."""
    wkts = set()
    for rel in TESTS:
        for m in POLA_WKT_UTM.finditer(baca(rel)):
            wkts.add(normal_wkt(m.group(0)))
    return wkts


def baca(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def blok_berkas(rel):
    isi = baca(rel)
    if rel.endswith((".md", ".txt")):
        return f"### FILE: {rel}\n\n{isi}\n"
    lang = BAHASA.get(Path(rel).suffix.lower(), "")
    return f"### FILE: {rel}\n\n```{lang}\n{isi}\n```\n"


def jalankan(cmd):
    return subprocess.run(
        cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def git_teks():
    head = jalankan(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
    log = jalankan(["git", "log", "--oneline", "--stat"]).stdout
    status = jalankan(["git", "status", "--short"]).stdout
    return head, log, status


def tes_teks():
    r = jalankan([str(PY), "-m", "pytest", "tests", "-q"])
    return ("$ .venv/Scripts/python.exe -m pytest tests/ -q\n\n"
            + (r.stdout or "") + (r.stderr or "")
            + f"\n(exit code: {r.returncode})").strip()


def _tanpa_hunk_tes(isi):
    """Buang bagian diff milik tests/ (fixture sintetis diizinkan kebijakan paket)."""
    keluaran, lewati = [], False
    for b in isi.splitlines():
        if b.startswith("diff --git "):
            target = b.rsplit(" b/", 1)[-1] if " b/" in b else ""
            lewati = target.startswith("tests/")
        if not lewati:
            keluaran.append(b)
    return "\n".join(keluaran)


def scan_sanitasi(rel, isi, fixtures):
    """Kembalikan daftar masalah koordinat.

    Fixture sintetis diizinkan: berkas di bawah tests/ dilewati, dan di berkas
    lain WKT yang persis sama dengan fixture tests/ tidak dianggap temuan.
    """
    if rel.startswith("tests/"):
        return []
    if rel.endswith("BUKTI_diff_vs_commit.txt"):
        isi = _tanpa_hunk_tes(isi)
    masalah = []
    for m in POLA_PASANGAN.finditer(isi):
        masalah.append(f"{rel}: pasangan koordinat UTM di posisi {m.start()}")
    for m in POLA_WKT_UTM.finditer(isi):
        if normal_wkt(m.group(0)) not in fixtures:
            masalah.append(f"{rel}: WKT poligon berkoordinat besar di posisi {m.start()}")
    return masalah


def main():
    head, log, status = git_teks()

    semua_teks = []
    for rel in DOK_RESPONS + DOK_REVIEW + DOK_KONTEKS + DOKS + KODE + TESTS + EVID + SKRIP_PAKET:
        semua_teks.append((rel, baca(rel)))

    masalah = []
    fixtures = fixture_sintetis()
    for rel, isi in semua_teks:
        masalah += scan_sanitasi(rel, isi, fixtures)
    if masalah:
        print("SCAN SANITASI GAGAL — paket TIDAK dibuat:")
        for m in masalah[:40]:
            print("  -", m)
        sys.exit(1)
    print(f"Scan sanitasi lolos: {len(semua_teks)} berkas diperiksa, "
          f"{len(fixtures)} WKT fixture sintetis diizinkan, 0 temuan.")

    tes = tes_teks()

    potongan = [
        "# Paket Verifikasi Perbaikan — Ekspor Blok Otomatis (Pix4DField)\n",
        f"Dibuat: {TGL} | HEAD: {head} | Baseline review pertama: commit {COMMIT_BASELINE} "
        f"| Repo: D:\\pix4dfield_exporting_tools\n",
        "> Paket ini untuk memverifikasi PERBAIKAN atas review independen kedua.\n"
        "> Mulai dari dokumen bagian 0 (laporan perbaikan), lalu bagian 1 (review\n"
        "> yang direspons + laporan verifikasi independen paket sebelumnya).\n"
        "> Semua dokumen ditulis pihak pelaksana dan bisa keliru — verifikasi\n"
        "> setiap klaim ke kode/tes/bukti di paket ini. Perubahan BELUM di-commit;\n"
        "> bukti utama diff ada di bagian 7. Paket tidak memuat raster maupun koordinat\n"
        "> poligon blok (scan sanitasi otomatis, lihat bagian 9).\n",
        "\n---\n\n## 0. Respons implementer: Laporan Perbaikan (mulai dari sini)\n",
        blok_berkas(DOK_RESPONS[0]),
        "\n---\n\n## 1. Review & verifikasi independen (review kedua, laporan verifikasi perbaikan, review pertama)\n",
    ]
    potongan += [blok_berkas(r) for r in DOK_REVIEW]
    potongan.append("\n---\n\n## 2. Konteks proyek & aturan review\n")
    potongan += [blok_berkas(r) for r in DOK_KONTEKS]
    potongan.append("\n---\n\n## 3. Dokumen kontrak terkini (spec & rencana yang diperbarui)\n")
    potongan += [blok_berkas(r) for r in DOKS]
    potongan.append("\n---\n\n## 4. Kode aplikasi terkini (pasca perbaikan)\n")
    potongan += [blok_berkas(r) for r in KODE]
    potongan.append("\n---\n\n## 5. Tes otomatis terkini\n")
    potongan += [blok_berkas(r) for r in TESTS]
    potongan.append("\n---\n\n## 6. Bukti & artefak verifikasi\n")
    for rel in EVID:
        if rel.endswith("BUKTI_diff_vs_commit.txt"):
            continue  # tampil penuh di bagian 7, hindari duplikasi
        potongan.append(blok_berkas(rel))
    potongan.append("\n---\n\n## 7. Diff lengkap vs commit baseline " + COMMIT_BASELINE + "\n")
    potongan.append(blok_berkas("laporan/_uji_d17/BUKTI_diff_vs_commit.txt"))
    potongan.append("\n---\n\n## 8. Hasil tes saat paket dibuat\n")
    potongan.append("```\n" + tes + "\n```\n")
    potongan.append("\n---\n\n## 9. Riwayat git (log --oneline --stat), status, dan skrip pembuat paket\n")
    potongan.append("Sanitasi otomatis: pasangan koordinat UTM (EPSG:32749) dan WKT poligon\n"
                    "berkoordinat besar dipindai di semua berkas yang disertakan; hasil: 0 temuan.\n")
    potongan.append("```\n" + log + "\n```\n")
    potongan.append("status --short:\n\n```\n" + (status or "(bersih)") + "\n```\n")
    potongan.append("Skrip pembuat paket ini:\n")
    potongan += [blok_berkas(r) for r in SKRIP_PAKET]

    md_path = OUT_DIR / "PAKET_VERIFIKASI_PERBAIKAN.md"
    md_path.write_text("\n".join(potongan), encoding="utf-8")

    zip_path = OUT_DIR / f"paket_verifikasi_perbaikan_{TGL}.zip"
    berkas_zip = DOK_RESPONS + DOK_REVIEW + DOK_KONTEKS + DOKS + KODE + TESTS + EVID + SKRIP_PAKET
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "BACA_DULU.txt",
            "Paket verifikasi perbaikan - Ekspor Blok Otomatis (Pix4DField)\r\n"
            "1. baca laporan/reviewer/LAPORAN_PERBAIKAN_2026-10-14.md (respons implementer)\r\n"
            "2. baca laporan/reviewer/Review-Independen-2-...md (review yang direspons)\r\n"
            "3. hasil verifikasi independen paket sebelumnya: laporan/reviewer/Verifikasi-Perbaikan-Ekspor-Blok-2026-10-14.md\r\n"
            "4. bukti utama diff: laporan/_uji_d17/BUKTI_diff_vs_commit.txt (vs commit 65b4b44)\r\n"
            "5. bukti data nyata: laporan/_uji_d17/verify_gate2_run_20261014.txt + gate2_verifikasi.json\r\n"
            "6. versi satu-berkas (untuk AI chat): pilih berkas PAKET_VERIFIKASI_PERBAIKAN.md\r\n"
            "Paket memuat kode, tes, dokumen, dan bukti teks. TIDAK memuat raster maupun\r\n"
            "koordinat poligon blok; bukti memuat path lokal mesin pembuat. Perubahan belum\r\n"
            "di-commit (semua ada di working tree).\r\n"
            "Checklist verifikasi ada di LAPORAN_PERBAIKAN_2026-10-14.md bagian 6.\r\n")
        for rel in berkas_zip:
            z.write(ROOT / rel, rel)
        z.writestr("PAKET_VERIFIKASI_PERBAIKAN.md", md_path.read_bytes())
        z.writestr("BUKTI_tes_pytest.txt", tes + "\n")
        z.writestr("BUKTI_git_log.txt",
                   log + "\n\nstatus --short:\n" + (status or "(bersih)") + "\n")

    print(f"OK: {md_path} ({md_path.stat().st_size / 1024:.0f} KB)")
    print(f"OK: {zip_path} ({zip_path.stat().st_size / 1024:.0f} KB, {len(berkas_zip)} berkas)")


if __name__ == "__main__":
    main()
