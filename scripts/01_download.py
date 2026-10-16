"""Download the L01 land price (地価公示) zips of 2019 to 2026 from the national land numerical
information download site: per year the national file and the 47 prefecture files.

The file list is read from the DownLd(...) calls of the 2026 page (saved under docs/). Each zip is
checked as a zip, hashed, and recorded in data/raw/<version>/MANIFEST.json with the
Last-Modified the server states (upstream corrects files in place, so the date matters). A file
whose manifest entry still matches on disk is not fetched again. The version is the UTC date of
the first run; --version resumes another. Requests are sequential, one second apart; a 403 or
429 stops the run.
"""

import argparse
import datetime as dt
import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import ksj_l01 as k

ROOT = Path(__file__).parents[1]
UA = "ksj-l01-land-price/0.1 (+https://github.com/yuiseki/ksj-l01-land-price)"
PAUSE = 1.0


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


class Pushback(RuntimeError):
    """The server refused (403 or 429): stop rather than retry."""


def get(url: str, tries: int = 3) -> tuple[bytes, dict[str, str]]:
    for attempt in range(1, tries + 1):
        time.sleep(PAUSE)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
                heads = {h.lower(): v for h, v in r.headers.items()}
            want = heads.get("content-length")
            if want and int(want) != len(data):
                raise TimeoutError(f"short read {len(data)} of {want}")
            return data, heads
        except urllib.error.HTTPError as err:
            if err.code in (403, 429):
                raise Pushback(f"HTTP {err.code} for {url}") from err
            log(f"HTTP {err.code} for {url} (try {attempt}/{tries})")
        except (urllib.error.URLError, TimeoutError) as err:
            log(f"{err} for {url} (try {attempt}/{tries})")
        time.sleep(5 * attempt)
    raise RuntimeError(f"gave up on {url}")


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_bytes(data)
    part.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=dt.datetime.now(dt.UTC).strftime("%Y-%m-%d"))
    ap.add_argument("--limit", type=int, help="fetch at most this many files (a trial)")
    args = ap.parse_args()
    raw = ROOT / "data" / "raw" / args.version
    manifest_path = raw / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": {}}

    def save() -> None:
        write_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=1).encode())

    page, heads = get(k.PAGE_URL)
    manifest["page"] = {"url": k.PAGE_URL, "last_modified": heads.get("last-modified")}
    plan = k.select(k.parse_downloads(page.decode("utf-8")))
    if len(plan) != 8 * 48:
        log(f"the page lists {len(plan)} files for 2019 to 2026, expected 384")
        return 2
    manifest["failed"] = {}
    done = 0
    for f in plan:
        path = raw / str(f.year) / f.name
        have = manifest["files"].get(f.name)
        if (
            have
            and path.exists()
            and hashlib.sha256(path.read_bytes()).hexdigest() == have["sha256"]
        ):
            continue
        if args.limit is not None and done >= args.limit:
            break
        try:
            data, h = get(f.url)
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                bad = z.testzip()
                members = z.namelist()
            if bad:
                raise RuntimeError(f"bad zip member {bad}")
        except (RuntimeError, zipfile.BadZipFile) as err:
            log(f"FAILED {f.name}: {err}")
            manifest["failed"][f.name] = str(err)
            save()
            continue
        write_atomic(path, data)
        manifest["files"][f.name] = {
            "url": f.url,
            "year": f.year,
            "prefecture": f.prefecture,
            "page_size": f.page_size,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "last_modified": h.get("last-modified"),
            "fetched_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "members": members,
        }
        done += 1
        save()
        log(f"{f.name}  {len(data):,} bytes")
    # The pages and the attribute correspondence table are what name the columns of each year.
    for url in k.extra_urls():
        name = url.rsplit("/", 1)[1]
        path = raw / "docs" / name
        have = manifest.setdefault("docs", {}).get(name)
        if (
            have
            and path.exists()
            and hashlib.sha256(path.read_bytes()).hexdigest() == have["sha256"]
        ):
            continue
        data, h = get(url)
        write_atomic(path, data)
        manifest["docs"][name] = {
            "url": url,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "last_modified": h.get("last-modified"),
            "fetched_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        }
        save()
        log(f"{name}  {len(data):,} bytes")
    save()
    failed = len(manifest["failed"])
    log(f"{len(manifest['files'])} files, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Pushback as err:
        log(f"STOPPED: {err}")
        sys.exit(3)
