---
license: cc-by-4.0
license_name: cc-by-4.0
license_link: https://creativecommons.org/licenses/by/4.0/legalcode.ja
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

# ksj-l01-land-price

The official land prices of Japan (地価公示, the 標準地 price announced every year for 1 January by
the Land Appraisal Committee of the Ministry of Land, Infrastructure, Transport and Tourism),
as the Ministry's 国土数値情報 L01 gives them: one point per standard lot, with the price, the
address, the area, the use of the land, the zoning and about a hundred more attributes.
Years 2019 to 2026, 207,087 lot-years, the national file and the 47 prefecture files of
each year (384 zips, 320 MB), fetched on 2026-10-16.

Source: 国土数値情報ダウンロードサイト 地価公示データ, <https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L01-2026.html> (国土交通省).

Credit (出典): 国土交通省 国土数値情報ダウンロードサイト (https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L01-2026.html). The Parquet files are
processed from the source files; credit them as 「国土数値情報（地価公示データ）」（国土交通省）（https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L01-2026.html）を加工して作成.

## Which years, and why only these

Only 2019 to 2026 are here. The site marks these years as open data under CC BY 4.0
(公共データ利用規約 PDL1.0, which is compatible with CC BY 4.0). Years 1983 to 2018 are marked
商用可 under an older set of terms that also asks the redistributor to pass those terms on;
they are not included. The regional-block files of 2023 to 2026 are not included either: they
only split the national file.

## Layout

```
raw/2026-10-16/MANIFEST.json                 url, size, sha256, Last-Modified and members of every zip
raw/2026-10-16/<year>/L01-<yy>_GML.zip       the national file of the year, as served
raw/2026-10-16/<year>/L01-<yy>_<pp>_GML.zip  the 47 prefecture files of the year (pp = 01 to 47)
raw/2026-10-16/docs/                         the year pages and the 1983-2019 attribute table that name the columns
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
| 2019 | 25,993 | 128 | JGD2000 | 38 MB | 2 dates, latest 27 Jun 2022 |
| 2020 | 25,993 | 130 | JGD2000 | 38 MB | 2 dates, latest 27 Jun 2022 |
| 2021 | 25,993 | 132 | JGD2000 | 38 MB | 3 dates, latest 27 Jun 2022 |
| 2022 | 25,993 | 139 | JGD2000 | 39 MB | 17 Mar 2022 |
| 2023 | 25,993 | 141 | JGD2000 | 40 MB | 16 Mar 2023 |
| 2024 | 25,994 | 144 | JGD2011 | 42 MB | 2 dates, latest 30 Oct 2024 |
| 2025 | 25,563 | 146 | JGD2011 | 42 MB | 2 dates, latest 23 Apr 2026 |
| 2026 | 25,565 | 148 | JGD2011 | 42 MB | 2 dates, latest 23 Apr 2026 |

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

The 国土数値情報 terms (https://nlftp.mlit.go.jp/ksj/other/agreement.html) apply the 公共データ利用規約 (PDL1.0) to this data, which
allows copying, redistribution and adaptation, including for commercial use, on condition of
the credit above and a note when the data has been processed, and which is compatible with CC
BY 4.0. This dataset is therefore marked CC BY 4.0.

Collection code: <https://github.com/yuiseki/ksj-l01-land-price> (MIT).
