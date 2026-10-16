#!/usr/bin/env python3
"""Write data/README.md (the Hub card), data/LICENSE and data/provenance.yaml.

Counts come from the manifest of the newest run under data/raw/ and from data/parquet/.

    uv run python scripts/05_card.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPO = "ksj-l01-land-price"
CC = "https://creativecommons.org/licenses/by/4.0/legalcode.ja"
TERMS = "https://nlftp.mlit.go.jp/ksj/other/agreement.html"
PAGE = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L01-2026.html"
CREDIT = f"「国土数値情報（地価公示データ）」（国土交通省）（{PAGE}）を加工して作成"


def facts() -> dict:
    d = sorted((DATA / "raw").glob("*/MANIFEST.json"))[-1].parent
    m = json.loads((d / "MANIFEST.json").read_text())
    cols = json.loads((DATA / "parquet" / "columns.json").read_text())
    by_year: dict[int, list] = {}
    for e in m["files"].values():
        by_year.setdefault(e["year"], []).append(e)
    return {
        "run": d.name,
        "files": len(m["files"]),
        "bytes": sum(e["bytes"] for e in m["files"].values()),
        "rows": sum(v["rows"] for v in cols.values()),
        "fetched": min(e["fetched_at"] for e in m["files"].values())[:10],
        "by_year": by_year,
        "cols": cols,
    }


def card(f: dict) -> str:
    def modified(es: list) -> str:
        days = sorted({e["last_modified"][5:16] for e in es if e["last_modified"]})
        return f"{len(days)} dates, latest {days[-1]}" if len(days) > 1 else days[0]

    table = "\n".join(
        f"| {y} | {v['rows']:,} | {len(v['columns'])} | {v['datum']} | "
        f"{sum(e['bytes'] for e in f['by_year'][int(y)]) / 1e6:.0f} MB | {modified(f['by_year'][int(y)])} |"
        for y, v in f["cols"].items()
    )
    return f"""---
license: cc-by-4.0
license_name: cc-by-4.0
license_link: {CC}
language:
- ja
tags:
- japan
- land-price
- real-estate
- geospatial
- ksj
pretty_name: Japan official land prices (地価公示), 2019 to 2026
---

# {REPO}

The official land prices of Japan (地価公示, the 標準地 price announced every year for 1 January by
the Land Appraisal Committee of the Ministry of Land, Infrastructure, Transport and Tourism),
as the Ministry's 国土数値情報 L01 gives them: one point per standard lot, with the price, the
address, the area, the use of the land, the zoning and about a hundred more attributes.
Years 2019 to 2026, {f["rows"]:,} lot-years, the national file and the 47 prefecture files of
each year ({f["files"]} zips, {f["bytes"] / 1e6:.0f} MB), fetched on {f["fetched"]}.

Source: 国土数値情報ダウンロードサイト 地価公示データ, <{PAGE}> (国土交通省).

Credit (出典): 国土交通省 国土数値情報ダウンロードサイト ({PAGE}). The Parquet files are
processed from the source files; credit them as {CREDIT}.

## Which years, and why only these

Only 2019 to 2026 are here. The site marks these years as open data under CC BY 4.0
(公共データ利用規約 PDL1.0, which is compatible with CC BY 4.0). Years 1983 to 2018 are marked
商用可 under an older set of terms that also asks the redistributor to pass those terms on;
they are not included. The regional-block files of 2023 to 2026 are not included either: they
only split the national file.

## Layout

```
raw/{f["run"]}/MANIFEST.json                 url, size, sha256, Last-Modified and members of every zip
raw/{f["run"]}/<year>/L01-<yy>_GML.zip       the national file of the year, as served
raw/{f["run"]}/<year>/L01-<yy>_<pp>_GML.zip  the 47 prefecture files of the year (pp = 01 to 47)
raw/{f["run"]}/docs/                         the year pages and the 1983-2019 attribute table that name the columns
parquet/<year>.parquet                       one file per year, 47 row groups (one per prefecture, in code order)
parquet/columns.json                         per year: datum, .prj, the label of each column, the mapping below
```

Each zip holds the GML, a Shapefile, a GeoJSON and the metadata. For every year the national
file holds exactly the rows (all columns and the point) of the 47 prefecture files; this was
checked. Prefectures are in the raw files for people who want only one.

## Parquet

One row per standard lot and year. The first columns are the same in every year:

| column | meaning |
|---|---|
| `year` | the year of the announcement |
| `prefecture` | prefecture code (01 to 47), from the file the row came from |
| `municipality_code` | the 5-digit municipality code of the lot |
| `price_yen` | the announced price, yen per square metre |
| `change_pct` | change from the previous year in percent; empty for 2019 to 2021, which do not have the column |
| `address` | the address; for 2019 to 2021 the 住居表示 column, from 2022 the 所在並びに地番 column |
| `area_m2` | the lot area in square metres |
| `lon`, `lat` | the point, as in the file (the datum below) |

These are copied from one original column each; `columns.json` gives the column and the
label of each year, and the label is checked against that year's own documentation when the
file is built. After them come all original columns `L01_001`, `L01_002` and so on, unchanged,
as text. **The numbering of the original columns differs between years** (128 columns in 2019,
148 in 2026), so `L01_008` is the price in 2026 and something else in 2019; use the labels
in `columns.json`, or the first columns above. Where the source writes a missing value as `_`,
the original column keeps `_`.

| year | rows | original columns | datum | zips | Last-Modified of the zips |
|---|---:|---:|---|---:|---|
{table}

Coordinates are JGD2000 up to 2023 and JGD2011 from 2024 (the `.prj` of each zip says so).
The two datums give slightly different coordinates for the same place, by an amount that depends
on the region; nothing was converted here, so take the datum into account when joining years or
joining to precise data.

The point of a lot is not surveyed: the Ministry took it from residential maps and similar
sources, and states a standard deviation of 1.75 m against the location map for 2026.
Lots are not constant: 2019 to 2023 each hold 25,993 lots, 2024 holds 25,994, 2025 holds
25,563 and 2026 holds 25,565 (the Ministry's summary for 2026 gives 25,565 surveyed points, the
same number; this was read from its press material, not from the data). A lot that was dropped
or replaced is only in the years in which it existed.

## Corrections

The source overwrites its files in place when it corrects them, and this copy is one run (see
`MANIFEST.json` for the date and the Last-Modified of each zip); a later run replaces it. The
site records corrections, for example the addresses of Tokyo in 2025 and 2026 (April 2026).

## Licence

The 国土数値情報 terms ({TERMS}) apply the 公共データ利用規約 (PDL1.0) to this data, which
allows copying, redistribution and adaptation, including for commercial use, on condition of
the credit above and a note when the data has been processed, and which is compatible with CC
BY 4.0. This dataset is therefore marked CC BY 4.0.

Collection code: <https://github.com/yuiseki/{REPO}> (MIT).
"""


def provenance(f: dict) -> str:
    return f"""source: 国土数値情報 地価公示データ (L01), 国土交通省, 2019 to 2026
url: {PAGE}
retrieved: {f["fetched"]}
run: {f["run"]}
terms: {TERMS}
files: {f["files"]}
rows: {f["rows"]}
"""


def main() -> int:
    f = facts()
    (DATA / "README.md").write_text(card(f), encoding="utf-8")
    (DATA / "provenance.yaml").write_text(provenance(f), encoding="utf-8")
    (DATA / "LICENSE").write_text(
        "Creative Commons Attribution 4.0 International (CC BY 4.0)\n"
        f"{CC}\n\n"
        "The data is the L01 land price (地価公示) data of the national land numerical\n"
        "information of the Ministry of Land, Infrastructure, Transport and Tourism, Japan.\n"
        f"Credit: {CREDIT}.\n"
        f"Terms: {TERMS}\n",
        encoding="utf-8",
    )
    print(f"wrote data/README.md, LICENSE, provenance.yaml for run {f['run']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
