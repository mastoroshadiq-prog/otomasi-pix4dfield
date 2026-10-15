"""Bukti R-8: band NIR vs RedEdge di folder sumber uji — hash berkas vs hash piksel.

Berkas sumber berukuran sama besar dan dugaan awal 'identik bitwise' perlu diklarifikasi:
hash berkas (md5) bisa berbeda karena struktur biner TIFF, sementara isi piksel sama.

Jalankan: .venv/Scripts/python.exe laporan/_uji_d17/bukti_nir_rededge.py
"""
import hashlib
import json
from pathlib import Path

import rasterio

SUMBER = Path(r"F:\dataset\Pix4DField-export-Fligh01\AME III - Test OtoExport")
FILES = ["AME III NIR.data.tif", "AME III RedEdge.data.tif"]
CHUNK = 4096


def md5_berkas(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 22), b""):
            h.update(blk)
    return h.hexdigest()


def sha256_piksel(p):
    """SHA-256 atas byte mentah seluruh band (urutan band → baris) — bukti identik piksel."""
    h = hashlib.sha256()
    with rasterio.open(p) as ds:
        for b in range(1, ds.count + 1):
            for row in range(0, ds.height, CHUNK):
                win = ((row, min(row + CHUNK, ds.height)), (0, ds.width))
                h.update(ds.read(b, window=win).tobytes())
        return h.hexdigest(), ds.count, ds.dtypes[0], ds.nodata, ds.checksum(1)


def main():
    hasil = {}
    for nama in FILES:
        p = SUMBER / nama
        sha, count, dtype, nodata, cek_gdal = sha256_piksel(p)
        hasil[nama] = {"ukuran_byte": p.stat().st_size, "md5_berkas": md5_berkas(p),
                       "sha256_piksel_semua_band": sha, "band": count, "dtype": dtype,
                       "nodata": nodata, "checksum_gdal_band1": cek_gdal}
        print(nama, json.dumps(hasil[nama]), flush=True)
    a, b = (hasil[f] for f in FILES)
    print("\nRINGKASAN R-8:", json.dumps({
        "ukuran_sama": a["ukuran_byte"] == b["ukuran_byte"],
        "md5_berkas_sama": a["md5_berkas"] == b["md5_berkas"],
        "sha256_piksel_sama": a["sha256_piksel_semua_band"] == b["sha256_piksel_semua_band"],
        "checksum_gdal_sama": a["checksum_gdal_band1"] == b["checksum_gdal_band1"]}, indent=1))


if __name__ == "__main__":
    main()
