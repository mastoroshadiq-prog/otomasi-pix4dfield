from pathlib import Path
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.windows import Window, from_bounds
from shapely import wkt

CHUNK_ROWS = 2048


def crop_layer(src_path, geom_wkt, dst_path):
    geom = wkt.loads(geom_wkt)
    with rasterio.open(src_path) as ds:
        minx, miny, maxx, maxy = geom.bounds
        win = from_bounds(minx, miny, maxx, maxy, transform=ds.transform)
        win = win.round_offsets().round_lengths()
        win = Window(win.col_off - 1, win.row_off - 1, win.width + 2, win.height + 2)
        win = win.intersection(Window(0, 0, ds.width, ds.height))
        win = Window(int(win.col_off), int(win.row_off), int(win.width), int(win.height))
        profile = ds.profile.copy()
        profile.update(driver="GTiff", width=int(win.width), height=int(win.height),
                       transform=ds.window_transform(win), tiled=True,
                       blockxsize=256, blockysize=256, BIGTIFF="YES", num_threads="ALL_CPUS")
        float32 = np.issubdtype(np.dtype(ds.dtypes[0]), np.floating)
        profile.update(compress="DEFLATE", **(dict(predictor=3) if float32 else {}))
        nodata = ds.nodata if ds.nodata is not None else (0.0 if float32 else 0)
        profile["nodata"] = nodata
        Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
        total = int(win.width) * int(win.height)
        with rasterio.open(dst_path, "w", **profile) as out:
            for row in range(0, int(win.height), CHUNK_ROWS):
                h = min(CHUNK_ROWS, int(win.height) - row)
                winr = Window(int(win.col_off), int(win.row_off) + row, int(win.width), h)
                arr = ds.read(window=winr)
                mask = geometry_mask([geom], out_shape=(h, int(win.width)),
                                     transform=ds.window_transform(winr), invert=True)
                arr = np.where(mask[None, ...], arr, nodata)
                out.write(arr, window=Window(0, row, int(win.width), h))
    return {"piksel": total, "ukuran": Path(dst_path).stat().st_size}


def proses_baris(row, folder_palet):
    """Satu baris rencana output: crop data → render rgb → legend."""
    from core import palet
    stat = crop_layer(row["src_data"], row["geom"], row["dst_data"])
    if row.get("dst_rgb"):
        if row["layer"] == "ortho":
            render_ortho_rgb(row["dst_data"], row["dst_rgb"])
        else:
            pal = palet.palet_untuk_data(palet.muat_palet(row["layer"], folder_palet), row["dst_data"])
            render_rgb(row["dst_data"], row["dst_rgb"], pal)
            if row.get("dst_legend"):
                palet.make_legend(pal, row["dst_legend"], satuan=row["layer"].upper())
    return stat


def render_ortho_rgb(src_data_tif, dst_rgb, peta_band=None, chunk=CHUNK_ROWS):
    """Ortho 5-band (band1=Green, 2=Red, 3=RedEdge, 4=NIR, 5=Alpha) → rgb uint8 JPEG.
    peta_band default R←2, G←1, B←3 (diverifikasi vs referensi di Gate 2)."""
    peta_band = peta_band or {1: 2, 2: 1, 3: 3}
    _render_uint8(src_data_tif, dst_rgb, None, peta_band, chunk=chunk)


def render_rgb(src_data_tif, dst_rgb, pal, chunk=CHUNK_ROWS):
    _render_uint8(src_data_tif, dst_rgb, pal, None, chunk=chunk)


def _render_uint8(src, dst, pal, peta_band, chunk):
    from core import palet
    with rasterio.open(src) as ds:
        profile = dict(driver="GTiff", width=ds.width, height=ds.height, count=3,
                       dtype="uint8", crs=ds.crs, transform=ds.transform,
                       compress="JPEG", JPEG_QUALITY=85, tiled=True,
                       blockxsize=256, blockysize=256, BIGTIFF="YES",
                       nodata=0, photometric="YCBCR")
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        lo = hi = None
        if pal is None:
            samp = ds.read(out_shape=(ds.count, min(256, ds.height), min(256, ds.width)))
            vals = np.stack([samp[peta_band[k] - 1] for k in (1, 2, 3)]).astype("float64")
            lo, hi = np.percentile(vals, (2, 98))
        with rasterio.open(dst, "w", **profile) as out:
            for row in range(0, ds.height, chunk):
                h = min(chunk, ds.height - row)
                win = Window(0, row, ds.width, h)
                if pal is not None:
                    rgb = palet.apply_palette(ds.read(1, window=win), pal)
                else:
                    bands = [ds.read(b, window=win).astype("float64")
                             for b in (peta_band[1], peta_band[2], peta_band[3])]
                    rgb = np.stack(bands)
                    rgb = np.clip((rgb - lo) / max(hi - lo, 1e-9) * 255, 0, 255).astype("uint8")
                out.write(rgb, window=win)
        with rasterio.open(dst, "r+") as ds2:
            ds2.build_overviews([2, 4, 8, 16], Resampling.average)
