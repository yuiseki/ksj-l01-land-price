"""Write one Parquet file per year, built from the 47 prefecture zips (one row group per
prefecture, in code order), plus columns.json.

Each row has: year, prefecture (the 2-digit code from the file name), the columns every year
has in some form under fixed names (municipality_code, price_yen, change_pct, address,
area_m2; the mapping is checked against the year's own documentation), lon and lat as the file
states them (JGD2000 up to 2023, JGD2011 from 2024 by the .prj), and then every original
L01_nnn column unchanged as text. Column layouts differ by year; columns.json says what each
year's columns are.

    uv run python scripts/03_export_parquet.py [--version 2026-10-16]
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path

import ksj_l01 as k
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).parents[1]


def year_labels(raw: Path, year: int) -> dict[int, str]:
    if year == 2019:
        return k.xlsx_labels(raw / "docs" / "L01-2006-2019_shape_property_table.xlsx", "2019")
    html = (raw / "docs" / f"KsjTmplt-L01-{year}.html").read_text(encoding="utf-8")
    return k.page_labels(html)


def load_zip(path: Path) -> tuple[list[str], list[list[str]], list[tuple[float, float]], str]:
    with zipfile.ZipFile(path) as z:
        pick = {e: next(n for n in z.namelist() if n.endswith(e)) for e in (".dbf", ".shp", ".prj")}
        fields, rows = k.read_dbf(z.read(pick[".dbf"]))
        pts = k.read_shp_points(z.read(pick[".shp"]))
        prj = z.read(pick[".prj"]).decode("ascii")
    return fields, rows, pts, prj


def table(year: int, pref: str, fields: list[str], rows: list[list[str]], pts, mapping) -> pa.Table:
    col = {f: [r[i] for r in rows] for i, f in enumerate(fields)}
    n = len(rows)
    out = {
        "year": pa.array([year] * n, pa.int16()),
        "prefecture": pa.array([pref] * n, pa.string()),
        "municipality_code": pa.array(col[mapping["municipality_code"][0]], pa.string()),
        "price_yen": pa.array([k.to_int(v) for v in col[mapping["price"][0]]], pa.int64()),
        "change_pct": pa.array(
            [k.to_float(v) for v in col[mapping["change_pct"][0]]]
            if "change_pct" in mapping
            else [None] * n,
            pa.float64(),
        ),
        "address": pa.array(col[mapping["address"][0]], pa.string()),
        "area_m2": pa.array([k.to_float(v) for v in col[mapping["area_m2"][0]]], pa.float64()),
        "lon": pa.array([p[0] for p in pts], pa.float64()),
        "lat": pa.array([p[1] for p in pts], pa.float64()),
    }
    for f in fields:
        out[f] = pa.array(col[f], pa.string())
    return pa.table(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="2026-10-16")
    args = ap.parse_args()
    raw = ROOT / "data" / "raw" / args.version
    out_dir = ROOT / "data" / "parquet"
    out_dir.mkdir(parents=True, exist_ok=True)
    columns: dict[str, dict] = {}
    for year in range(k.FIRST_YEAR, k.LAST_YEAR + 1):
        labels = year_labels(raw, year)
        bad = k.check_core(year, labels)
        if bad:
            print(f"{year}: the mapped columns do not match the documentation: {bad}")
            return 2
        mapping = k.CORE[year]
        path = out_dir / f"{year}.parquet"
        tmp = path.with_suffix(".parquet.part")
        writer, rows_total, fields0, prj0 = None, 0, None, None
        for p in range(1, 48):
            fields, rows, pts, prj = load_zip(
                raw / str(year) / f"L01-{str(year)[2:]}_{p:02d}_GML.zip"
            )
            if fields0 is None:
                fields0, prj0 = fields, prj
            elif fields != fields0 or prj != prj0:
                print(f"{year} {p:02d}: layout differs from prefecture 01")
                return 2
            t = table(year, f"{p:02d}", fields, rows, pts, mapping)
            if writer is None:
                writer = pq.ParquetWriter(tmp, t.schema, compression="zstd")
            writer.write_table(t)
            rows_total += len(rows)
        writer.close()
        tmp.replace(path)
        datum = "JGD2011" if "JGD_2011" in prj0 else "JGD2000" if "JGD_2000" in prj0 else prj0[:30]
        columns[str(year)] = {
            "rows": rows_total,
            "datum": datum,
            "prj": prj0,
            "core": {n: {"column": c, "label": lab} for n, (c, lab) in mapping.items()},
            "labels": {f"L01_{i:03d}": lab for i, lab in sorted(labels.items())},
            "columns": fields0,
        }
        print(f"{year}: {rows_total:,} rows, {len(fields0)} original columns, {datum}, "
              f"{path.stat().st_size / 1e6:.1f} MB")  # fmt: skip
    (out_dir / "columns.json").write_text(json.dumps(columns, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
