"""Rakit paket review portabel untuk agent AI lain.

Menghasilkan di laporan/reviewer/:
  - PAKET_KODE_UNTUK_REVIEW.md  (kode+tes+dokumen+bukti dalam SATU berkas, untuk AI chat)
  - paket_review_ekspor_blok_<tanggal>.zip  (versi ZIP: dokumen, kode, tes, bukti teks)

Jalankan dari dalam repo:
  cd /d/pix4dfield_exporting_tools && .venv/Scripts/python.exe laporan/reviewer/buat_paket_review.py
"""
import os
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

DOK_REVIEW = [
    "laporan/reviewer/RINGKASAN_PROYEK_UNTUK_REVIEW.md",
    "laporan/reviewer/BRIEF.md",
]
DOKS = [
    "README.md",
    "docs/superpowers/specs/2026-10-13-ekspor-blok-otomatis-design.md",
    "docs/superpowers/plans/2026-10-13-ekspor-blok-otomatis-implementasi.md",
]
KODE = [
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
    "laporan/_uji_d17/RINGKASAN.md",
    "laporan/_uji_d17/gate2_verifikasi.json",
    "laporan/_uji_d17/verify_gate2.py",
    "laporan/_uji_d17/run_gate2.py",
]

BAHASA = {".py": "python", ".js": "javascript", ".css": "css", ".html": "html",
          ".bat": "bat", ".json": "json"}


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


def main():
    head, log, status = git_teks()
    tes = tes_teks()

    potongan = [
        "# Paket Kode untuk Review — Ekspor Blok Otomatis (Pix4DField)\n",
        f"Dibuat: {TGL} | HEAD: {head} | Repo: D:\\pix4dfield_exporting_tools\n",
        "> Semua dokumen di paket ini ditulis pihak pelaksana dan bisa keliru — "
        "verifikasi setiap klaim ke kode. Aturan review lengkap di bagian 1 (BRIEF). "
        "Paket tidak memuat raster maupun koordinat poligon blok.\n",
        "\n---\n\n## 0. Ringkasan proyek untuk reviewer\n",
        baca(DOK_REVIEW[0]),
        "\n---\n\n## 1. Brief review (aturan main + checklist A–H)\n",
        baca(DOK_REVIEW[1]),
        "\n---\n\n## 2. Dokumen kontrak (spec, rencana, README)\n",
    ]
    potongan += [blok_berkas(r) for r in DOKS]
    potongan.append("\n---\n\n## 3. Kode aplikasi\n")
    potongan += [blok_berkas(r) for r in KODE]
    potongan.append("\n---\n\n## 4. Tes otomatis\n")
    potongan += [blok_berkas(r) for r in TESTS]
    potongan.append("\n---\n\n## 5. Bukti & artefak verifikasi\n")
    potongan += [blok_berkas(r) for r in EVID]
    potongan.append("\n---\n\n## 6. Riwayat git (log --oneline --stat) & status saat paket dibuat\n")
    potongan.append("```\n" + log + "\n```\n")
    potongan.append("status --short:\n\n```\n" + (status or "(bersih)") + "\n```\n")
    potongan.append("\n---\n\n## 7. Hasil tes saat paket dibuat\n")
    potongan.append("```\n" + tes + "\n```\n")

    md_path = OUT_DIR / "PAKET_KODE_UNTUK_REVIEW.md"
    md_path.write_text("\n".join(potongan), encoding="utf-8")

    zip_path = OUT_DIR / f"paket_review_ekspor_blok_{TGL}.zip"
    berkas_zip = DOK_REVIEW + DOKS + KODE + TESTS + EVID
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "BACA_DULU.txt",
            "Paket review - Ekspor Blok Otomatis (Pix4DField)\r\n"
            "Mulai dari: laporan/reviewer/RINGKASAN_PROYEK_UNTUK_REVIEW.md\r\n"
            "lalu laporan/reviewer/BRIEF.md (aturan main + checklist A-H).\r\n"
            "Paket memuat kode, tes, dokumen, dan bukti teks. TIDAK memuat raster\r\n"
            "maupun koordinat poligon blok; bukti memuat path lokal mesin pembuat.\r\n")
        for rel in berkas_zip:
            z.write(ROOT / rel, rel)
        z.writestr("BUKTI_git_log.txt", log + "\n\nstatus --short:\n" + (status or "(bersih)") + "\n")
        z.writestr("BUKTI_tes_pytest.txt", tes + "\n")

    print(f"OK: {md_path} ({md_path.stat().st_size / 1024:.0f} KB)")
    print(f"OK: {zip_path} ({zip_path.stat().st_size / 1024:.0f} KB, {len(berkas_zip)} berkas)")


if __name__ == "__main__":
    main()
