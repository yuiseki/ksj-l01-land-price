#!/usr/bin/env python3
"""Push the card, the licence, the provenance, the Parquet and the current run to the Hub.

The source overwrites its files in place, so the Hub holds one run only: the newest complete
run under data/raw/. Each zip goes up unchanged after its sha256 is checked against
MANIFEST.json, and files of older runs are deleted on the Hub in the same commit. The card
must declare CC BY 4.0, name the run, and give the row total; the Parquet must hold as many
rows as the manifest.

    uv run python src/publish.py             # dry run: list the files and their total size
    uv run python src/publish.py --push
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPO = "yuiseki/ksj-l01-land-price"
DELETE_PATTERNS = ["raw/**", "parquet/**"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def current_run(data: Path) -> Path:
    runs = sorted((data / "raw").glob("*/MANIFEST.json"))
    if not runs:
        raise SystemExit("no run under data/raw/; run scripts/01_download.py")
    return runs[-1].parent


def collect(data: Path) -> list[str]:
    """Files to upload relative to data/; stops on anything the card or manifest refutes."""
    card = (data / "README.md").read_text(encoding="utf-8")
    if "license: cc-by-4.0" not in card:
        raise SystemExit("the card does not declare license: cc-by-4.0")
    d = current_run(data)
    if f"raw/{d.name}/" not in card:
        raise SystemExit(f"the card does not name the current run raw/{d.name}/")
    manifest = json.loads((d / "MANIFEST.json").read_text())
    if manifest["failed"]:
        raise SystemExit(f"the run has failed downloads: {list(manifest['failed'])[:5]}")
    if len(manifest["files"]) != 384:
        raise SystemExit(f"{len(manifest['files'])} files in the manifest, expected 384")
    cols = json.loads((data / "parquet" / "columns.json").read_text())
    rows = sum(v["rows"] for v in cols.values())
    if f"{rows:,}" not in card:
        raise SystemExit(f"the card does not give the row total {rows:,}")
    if sorted(cols) != [str(y) for y in range(2019, 2027)]:
        raise SystemExit("parquet/columns.json does not cover exactly 2019 to 2026")
    files = ["README.md", "LICENSE", "provenance.yaml", f"raw/{d.name}/MANIFEST.json"]
    for key, e in manifest["files"].items():
        path = d / str(e["year"]) / key
        if sha256(path) != e["sha256"]:
            raise SystemExit(f"{path} is not the file in its manifest")
        files.append(path.relative_to(data).as_posix())
    for key, e in manifest["docs"].items():
        path = d / "docs" / key
        if sha256(path) != e["sha256"]:
            raise SystemExit(f"{path} is not the file in its manifest")
        files.append(path.relative_to(data).as_posix())
    on_disk = {p.relative_to(data).as_posix() for p in d.rglob("*") if p.is_file()}
    stray = on_disk - set(files)
    if stray:
        raise SystemExit(f"files in the run that the manifest does not list: {sorted(stray)[:5]}")
    files += ["parquet/columns.json"] + [f"parquet/{y}.parquet" for y in cols]
    missing = [f for f in files if not (data / f).is_file()]
    if missing:
        raise SystemExit(f"missing: {missing[:5]}")
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    files = collect(DATA)
    total = sum((DATA / f).stat().st_size for f in files)
    print(f"{a.repo}\n  {len(files)} files, {total:,} bytes ({total / 1e6:.0f} MB)")
    print(f"  remote files matching {DELETE_PATTERNS} and not uploaded are deleted")
    if not a.push:
        print("\ndry run. pass --push to upload")
        return 0

    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(a.repo, repo_type="dataset", exist_ok=True, private=False)
    api.upload_folder(
        folder_path=str(DATA), repo_id=a.repo, repo_type="dataset", allow_patterns=files,
        delete_patterns=DELETE_PATTERNS,
    )  # fmt: skip
    print(f"\npushed to https://huggingface.co/datasets/{a.repo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
