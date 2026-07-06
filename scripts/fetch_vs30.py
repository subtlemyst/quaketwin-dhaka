"""Fetch the USGS Global Vs30 Mosaic clip for the Dhaka study area.

Performs a windowed HTTP range-read of the Cloud-Optimized GeoTIFF (no full
download; the global file is ~1 GB, the clip is a few KB) and caches it under
data/raw/vs30/. Source: Heath et al. (2020), USGS data release
doi:10.5066/P1NV6UNM (CC0).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import rasterio
from rasterio.windows import from_bounds

from quaketwin.config import get_bbox

VS30_COG_URL = (
    "https://prod-is-usgs-sb-prod-publish.s3.amazonaws.com/"
    "67be4ac3d34e8876fcbfbd89/vs30_mosaic_median_30c.tif"
)
MARGIN_DEG = 0.03


def main() -> None:
    bbox = get_bbox()
    out_path = ROOT / "data/raw/vs30/usgs_vs30_dhaka.tif"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading Vs30 window from USGS COG for bbox {bbox.model_dump()}", flush=True)
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_TIMEOUT="60",
        GDAL_HTTP_MAX_RETRY="3",
        GDAL_HTTP_RETRY_DELAY="2",
    ):
        with rasterio.open(VS30_COG_URL) as ds:
            win = from_bounds(
                bbox.west - MARGIN_DEG,
                bbox.south - MARGIN_DEG,
                bbox.east + MARGIN_DEG,
                bbox.north + MARGIN_DEG,
                ds.transform,
            )
            arr = ds.read(1, window=win)
            transform = ds.window_transform(win)
            profile = ds.profile.copy()
            profile.update(
                height=arr.shape[0], width=arr.shape[1], transform=transform, driver="GTiff"
            )

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(arr, 1)

    print(
        f"Saved {out_path} ({arr.shape[0]}x{arr.shape[1]} px, "
        f"Vs30 {arr.min():.0f}-{arr.max():.0f} m/s, mean {arr.mean():.0f})",
        flush=True,
    )


if __name__ == "__main__":
    main()
