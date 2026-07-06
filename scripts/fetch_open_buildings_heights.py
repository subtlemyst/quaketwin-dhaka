"""Fetch Google Open Buildings heights for the Dhaka study bbox."""

from __future__ import annotations

import gzip
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import httpx
import pandas as pd
import s2sphere as s2

from quaketwin.config import get_bbox, load_config

INDEX_URL = "https://storage.googleapis.com/open-buildings-data/v3/score_thresholds_s2_level_4.csv"
TILE_BASE = "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_4_gzip/"
CHUNK_ROWS = 250_000


def _level4_tokens_for_bbox(bbox, level: int = 4) -> list[str]:
    """Return S2 level-4 tile tokens (3-char hex) covering bbox corners + center."""
    points = [
        (bbox.south, bbox.west),
        (bbox.south, bbox.east),
        (bbox.north, bbox.west),
        (bbox.north, bbox.east),
        ((bbox.south + bbox.north) / 2, (bbox.west + bbox.east) / 2),
    ]
    tokens: set[str] = set()
    for lat, lon in points:
        cell = s2.CellId.from_lat_lng(s2.LatLng.from_degrees(lat, lon)).parent(level)
        tokens.add(format(cell.id(), "x")[:3])
    index = pd.read_csv(INDEX_URL)
    known = set(index["s2_token"].astype(str))
    return sorted(tokens & known)


def _filter_tile_chunks(gz_path: Path, bbox, tile: str) -> list[pd.DataFrame]:
    """Stream-read a tile CSV.gz and keep only bbox rows with height."""
    kept: list[pd.DataFrame] = []
    lat_col = lon_col = height_col = None
    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as fh:
        for chunk in pd.read_csv(fh, chunksize=CHUNK_ROWS):
            if lat_col is None:
                lat_col = "latitude" if "latitude" in chunk.columns else "lat"
                lon_col = "longitude" if "longitude" in chunk.columns else "lon"
                height_col = "height" if "height" in chunk.columns else "height_m"
                if height_col not in chunk.columns:
                    print(f"    no height column in {tile}, skip", flush=True)
                    return []
            sub = chunk[
                (chunk[lat_col] >= bbox.south)
                & (chunk[lat_col] <= bbox.north)
                & (chunk[lon_col] >= bbox.west)
                & (chunk[lon_col] <= bbox.east)
                & (chunk[height_col].notna())
            ]
            if len(sub) == 0:
                continue
            kept.append(
                sub[[lon_col, lat_col, height_col]].rename(
                    columns={lon_col: "lon", lat_col: "lat", height_col: "height_m"}
                )
            )
    return kept


def main() -> None:
    bbox = get_bbox(load_config())
    out_dir = ROOT / "data/raw/open_buildings"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "dhaka_heights.parquet"

    print("Resolving Open Buildings S2 tiles for study bbox...", flush=True)
    tiles = _level4_tokens_for_bbox(bbox)
    if not tiles:
        raise SystemExit(
            "No Open Buildings tiles matched the study bbox; "
            "check network access or S2 token resolution."
        )
    print(f"  {len(tiles)} tiles: {', '.join(tiles)}", flush=True)

    rows: list[pd.DataFrame] = []
    with httpx.Client(timeout=600.0, follow_redirects=True) as client:
        for i, tile in enumerate(tiles, 1):
            url = f"{TILE_BASE}{tile}_buildings.csv.gz"
            print(f"  [{i}/{len(tiles)}] {tile} (streaming download)...", flush=True)
            try:
                with client.stream("GET", url) as resp:
                    if resp.status_code != 200:
                        print(f"    HTTP {resp.status_code}, skip", flush=True)
                        continue
                    with tempfile.NamedTemporaryFile(suffix=".csv.gz", delete=False) as tmp:
                        tmp_path = Path(tmp.name)
                        for block in resp.iter_bytes(chunk_size=8 * 1024 * 1024):
                            tmp.write(block)
                tile_rows = _filter_tile_chunks(tmp_path, bbox, tile)
                tmp_path.unlink(missing_ok=True)
                if tile_rows:
                    rows.extend(tile_rows)
                    print(f"    kept {sum(len(r) for r in tile_rows):,} bbox rows", flush=True)
            except Exception as exc:
                print(f"    skip: {exc}", flush=True)
                continue

    if not rows:
        raise SystemExit("No Open Buildings heights fetched; tiles may be empty for this bbox.")

    out = pd.concat(rows, ignore_index=True)
    out = out.drop_duplicates(subset=["lon", "lat"])
    out.to_parquet(out_path, index=False)
    csv_path = out_dir / "dhaka_heights.csv"
    out.to_csv(csv_path, index=False)
    print(f"Wrote {len(out):,} points -> {out_path} and {csv_path}", flush=True)


if __name__ == "__main__":
    main()
