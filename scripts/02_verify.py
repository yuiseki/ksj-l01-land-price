"""Check what 01_download.py fetched: every manifest entry against the file on disk, and, for
each year, that the national file holds exactly the rows of the 47 prefecture files (all
columns and the point).

    uv run python scripts/02_verify.py [--version 2026-10-16]
"""

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

import ksj_l01 as k

ROOT = Path(__file__).parents[1]


def read_zip(path: Path) -> tuple[list[str], list[tuple], str]:
    """Field names, rows as (attribute tuple + (lon, lat)), and the .prj text of one L01 zip."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()

        def one(ext: str) -> str:
            hits = [n for n in names if n.endswith(ext)]
            if len(hits) != 1:
                raise SystemExit(f"{path.name}: {len(hits)} files ending {ext}")
            return hits[0]

        fields, rows = k.read_dbf(z.read(one(".dbf")))
        pts = k.read_shp_points(z.read(one(".shp")))
        prj = z.read(one(".prj")).decode("ascii")
    if len(rows) != len(pts):
        raise SystemExit(f"{path.name}: {len(rows)} rows but {len(pts)} points")
    return (
        fields,
        [tuple(r) + (round(x, 7), round(y, 7)) for r, (x, y) in zip(rows, pts, strict=True)],
        prj,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="2026-10-16")
    args = ap.parse_args()
    raw = ROOT / "data" / "raw" / args.version
    manifest = json.loads((raw / "MANIFEST.json").read_text())
    problems = []
    if manifest.get("failed"):
        problems.append(f"manifest lists failed files: {sorted(manifest['failed'])}")
    for name, e in manifest["files"].items():
        path = raw / str(e["year"]) / name
        if not path.exists():
            problems.append(f"missing {path}")
        elif (
            hashlib.sha256(path.read_bytes()).hexdigest() != e["sha256"]
            or path.stat().st_size != e["bytes"]
        ):
            problems.append(f"sha256 or size differs: {name}")
    stray = {p.name for p in raw.glob("20*/*") if p.is_file()} - set(manifest["files"])
    if stray:
        problems.append(f"files not in the manifest: {sorted(stray)}")
    if len(manifest["files"]) != 8 * 48:
        problems.append(f"{len(manifest['files'])} files in the manifest, expected 384")
    total = 0
    for year in range(k.FIRST_YEAR, k.LAST_YEAR + 1):
        yy = str(year)[2:]
        f_nat, rows_nat, prj_nat = read_zip(raw / str(year) / f"L01-{yy}_GML.zip")
        merged: Counter = Counter()
        n_pref = 0
        for p in range(1, 48):
            f_p, rows_p, prj_p = read_zip(raw / str(year) / f"L01-{yy}_{p:02d}_GML.zip")
            if f_p != f_nat:
                problems.append(f"{year} {p:02d}: field names differ from the national file")
            if prj_p != prj_nat:
                problems.append(f"{year} {p:02d}: .prj differs from the national file")
            merged.update(rows_p)
            n_pref += len(rows_p)
        nat = Counter(rows_nat)
        same = nat == merged
        print(f"{year}: national {len(rows_nat):,} rows, prefectures {n_pref:,} rows, "
              f"{len(f_nat)} columns, {'identical' if same else 'DIFFERENT'}, "
              f"{prj_nat[:20]}")  # fmt: skip
        if not same:
            problems.append(f"{year}: national rows differ from the prefecture rows")
        total += len(rows_nat)
    print(f"{total:,} rows in the 8 national files")
    for p in problems:
        print("PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
