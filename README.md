# Ekspor Blok Otomatis — Pix4DField

Tool lokal untuk memotong (crop) layer hasil ekspor Pix4DField per blok kebun
memakai peta blok PDF, lalu menulisnya ke folder output BARU.

## Cara Pakai

1. Di Pix4DField: ekspor semua layer untuk 1 project sebagai **full extent** (satu kali per project, bukan per blok) ke satu folder.
2. Double-click `jalankan.bat` — server lokal mulai, browser terbuka otomatis (`http://127.0.0.1:<port>`).
3. **Tahap 1 (Setup):** isi folder sumber, folder output BARU (mis. `F:\dataset\Pix4DField-export-FLG03_auto`), peta blok PDF, kode flight → Simpan.
4. **Tahap 2 (Pindai):** periksa jumlah blok × layer, estimasi disk, koreksi divisi bila perlu → Pindai.
5. **Tahap 3 (Jalankan):** mulai batch; pantau progress/log; tombol Batalkan / Coba ulang / Buka folder / Unduh CSV / Unduh log tersedia.

## Verifikasi (gate)

- **Gate 0:** konfirmasi app mendukung export full-extent (sekali per project).
- **Gate 1:** overlay peta `laporan/gate1/qa_overlay_peta.png` di-ACC (posisi batas blok vs peta).
- **Gate 2:** 1 project kecil — bandingkan hasil vs ekspor manual (posisi, cakupan, ukuran file, palet); ukur rasio kompresi.
- **Gate 3:** batch penuh 1 flight ke folder `..._auto`; verifikasi visual beberapa blok.

## Catatan

- Output SELALU ke folder baru `..._auto`; arsip lama tidak pernah disentuh.
- Geometri blok dari PDF "Peta Informasi Tanam Tahun Inti" — kalibrasi affine residual ≈ 0,67 m; CRS EPSG:32749.
- Palet NIR/RedEdge/DSM belum ada referensinya → gradien aproksimasi (`data/palet/bawaan.json`) sampai disampel dari ekspor `.rgb` app di Gate 2.
- Tes: `.venv/Scripts/python.exe -m pytest tests/ -q`
- Rencana & spec: `docs/superpowers/`
