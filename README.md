# ksj-l01-land-price

A reproducible copy of the official land prices of Japan (地価公示, L01 of the 国土数値情報
published by the Ministry of Land, Infrastructure, Transport and Tourism), years 2019 to 2026,
the national file and the 47 prefecture files of each year. The Hugging Face dataset is
<https://huggingface.co/datasets/yuiseki/ksj-l01-land-price>.

Only the years under the open-data terms (PDL1.0, compatible with CC BY 4.0) are collected;
see `data/README.md` (the dataset card) for what is in it, the Parquet layout, and why the
column numbering must not be assumed to be the same from year to year.

## Run

```
uv run python scripts/01_download.py        # 384 zips and the pages that name the columns, resumable
uv run python scripts/02_verify.py          # manifest vs disk; national file = sum of the prefectures
uv run python scripts/03_export_parquet.py  # data/parquet/<year>.parquet + columns.json
uv run python scripts/04_verify_parquet.py  # Parquet vs the zips
uv run python scripts/05_card.py            # data/README.md, LICENSE, provenance.yaml
uv run python src/publish.py                # dry run; --push uploads
uv run pytest
```

The data is not in git (`data/raw/`, `data/parquet/` are ignored). The source corrects its
files in place and adds a year every March, so run the steps again and publish again to follow it.

Code: MIT. Data: CC BY 4.0, see `data/LICENSE`.
