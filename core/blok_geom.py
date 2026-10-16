"""Geometri kartu mode blok penuh (opsi B).

Kartu per kode = union semua pecahan shp Tanam Inti (dipotong ke bentang
berdata ortho), lalu sisa celah (jalan/tepi) ditambal ke blok terdekat per
langkah buffer — pembagian jatuh alami di garis tengah celah.
Kode tanpa fragmen shp → None; pemanggil memakai geometri peta PDF apa adanya.
"""
from shapely.ops import unary_union

MAKS_TAMBAL_M = 80.0
LANGKAH_TAMBAL_M = 1.0
SISA_BERHENTI_M2 = 4.0


def frags_dari_shp(path_shp):
    """{kode: [geom, ...]} — semua fragmen/pecahan duplikat dipertahankan."""
    from core import kartu
    return {k: [d["geom"] for d in v] for k, v in kartu.muat_shp(path_shp).items()}


def geometri_kartu(bentang, frags_map, kode_list, maks_tambal=MAKS_TAMBAL_M,
                   langkah=LANGKAH_TAMBAL_M):
    if bentang is None or bentang.is_empty:
        return {k: None for k in kode_list}
    G, dipakai = {}, []
    for k in kode_list:
        frags = frags_map.get(k)
        g = unary_union(frags).intersection(bentang) if frags else None
        G[k] = g if g is not None and not g.is_empty else None
        if G[k] is not None:
            dipakai.append(k)
    if not dipakai:
        return G
    U = {k: G[k] for k in dipakai}
    sisa = bentang.difference(unary_union(list(U.values()))).buffer(0)
    r = 0.0
    while sisa.area > SISA_BERHENTI_M2 and r < maks_tambal:
        r = min(r + langkah, maks_tambal)
        for k in dipakai:
            grab = sisa.intersection(U[k].buffer(r)).buffer(0)
            if grab.area > 1.0:
                G[k] = G[k].union(grab).buffer(0)
                sisa = sisa.difference(grab).buffer(0)
    return G
