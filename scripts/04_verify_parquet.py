"""Check the Parquet files against the zips they came from: per year and prefecture the rows of
the row group equal the rows of the prefecture zip (every original column, lon and lat), the
typed columns agree with the text columns, and the total equals the national file.

    uv run python scripts/04_verify_parquet.py [--version 2026-10-16]
"""

import argparse
import importlib
import sys
from pathlib import Path

import ksj_l01 as k
import pyarrow.parquet as pq

ROOT = Path(__file__).parents[1]
verify = importlib.import_module("02_verify")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="2026-10-16")
    args = ap.parse_args()
    raw = ROOT / "data" / "raw" / args.version
    problems = []
    for year in range(k.FIRST_YEAR, k.LAST_YEAR + 1):
        yy = str(year)[2:]
        pf = pq.ParquetFile(ROOT / "data" / "parquet" / f"{year}.parquet")
        if pf.num_row_groups != 47:
            problems.append(f"{year}: {pf.num_row_groups} row groups, expected 47")
            continue
        mapping = k.CORE[year]
        total = null_price = null_area = 0
        for p in range(1, 48):
            fields, rows, _ = verify.read_zip(raw / str(year) / f"L01-{yy}_{p:02d}_GML.zip")[:3]
            rg = pf.read_row_group(p - 1).to_pydict()
            if len(rg["year"]) != len(rows):
                problems.append(f"{year} {p:02d}: {len(rg['year'])} rows, zip has {len(rows)}")
                continue
            if set(rg["prefecture"]) != {f"{p:02d}"} or set(rg["year"]) != {year}:
                problems.append(f"{year} {p:02d}: wrong year or prefecture column")
            nf = len(fields)
            for i, row in enumerate(rows):
                text = [rg[f][i] for f in fields]
                if list(row[:nf]) != text:
                    problems.append(f"{year} {p:02d} row {i}: original columns differ")
                    break
                # the verify reader rounds to 7 places; the file keeps the full value
                if abs(rg["lon"][i] - row[nf]) > 1e-7 or abs(rg["lat"][i] - row[nf + 1]) > 1e-7:
                    problems.append(f"{year} {p:02d} row {i}: point differs")
                    break
                d = dict(zip(fields, row[:nf], strict=True))
                if rg["price_yen"][i] != k.to_int(d[mapping["price"][0]]):
                    problems.append(f"{year} {p:02d} row {i}: price_yen differs")
                    break
                want_chg = k.to_float(d[mapping["change_pct"][0]]) if "change_pct" in mapping else None
                if rg["change_pct"][i] != want_chg:
                    problems.append(f"{year} {p:02d} row {i}: change_pct differs")
                    break
                if rg["area_m2"][i] != k.to_float(d[mapping["area_m2"][0]]):
                    problems.append(f"{year} {p:02d} row {i}: area_m2 differs")
                    break
                if rg["municipality_code"][i] != d[mapping["municipality_code"][0]]:
                    problems.append(f"{year} {p:02d} row {i}: municipality_code differs")
                    break
            total += len(rows)
            null_price += sum(v is None for v in rg["price_yen"])
            null_area += sum(v is None for v in rg["area_m2"])
        nat = verify.read_zip(raw / str(year) / f"L01-{yy}_GML.zip")[1]
        if total != len(nat) or pf.metadata.num_rows != len(nat):
            problems.append(f"{year}: {total} rows against {len(nat)} in the national file")
        print(f"{year}: {total:,} rows, price_yen empty {null_price}, area_m2 empty {null_area}")
    for p in problems[:20]:
        print("PROBLEM:", p)
    print("OK" if not problems else f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
