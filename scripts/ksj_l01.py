"""Helpers for the national land numerical information L01 (地価公示) downloads.

The download page of the latest year lists every file as a DownLd('<size>','<name>','<path>'
,this) call; the file list is read from there, never guessed.
"""

import re
import struct
from dataclasses import dataclass

BASE = "https://nlftp.mlit.go.jp"
PAGE_URL = BASE + "/ksj/gml/datalist/KsjTmplt-L01-2026.html"
# Years whose terms are PDL1.0 (オープンデータ, CC BY 4.0 compatible); earlier years are under the
# older 商用可 terms and are not collected.
FIRST_YEAR, LAST_YEAR = 2019, 2026

ATTR_TABLE = BASE + "/ksj/gml/codelist/L01-2006-2019_shape_property_table.xlsx"


def extra_urls() -> list[str]:
    """The year pages (they name the columns of 2020 to 2026) and the 1983-2019 correspondence table."""
    pages = [
        f"{BASE}/ksj/gml/datalist/KsjTmplt-L01-{y}.html" for y in range(FIRST_YEAR, LAST_YEAR + 1)
    ]
    return pages + [ATTR_TABLE]


_CALL = re.compile(r"DownLd\('([^']*)','([^']*)','([^']*)'\s*,this\)")
_NAME = re.compile(r"^L01-(\d\d)(?:_(\d\d))?_GML\.zip$")


@dataclass(frozen=True)
class Listed:
    name: str
    url: str
    page_size: str

    @property
    def year(self) -> int:
        yy = int(_NAME.match(self.name).group(1))  # type: ignore[union-attr]
        return 1900 + yy if yy >= 83 else 2000 + yy

    @property
    def prefecture(self) -> str | None:
        return _NAME.match(self.name).group(2)  # type: ignore[union-attr]


def parse_downloads(html: str) -> list[Listed]:
    return [
        Listed(name, BASE + re.sub(r"/{2,}", "/", path), size)
        for size, name, path in _CALL.findall(html)
    ]


def select(files: list[Listed]) -> list[Listed]:
    """The national file and the 47 prefecture files of 2019 to 2026 (no regional blocks)."""
    kept = []
    for f in files:
        if not _NAME.match(f.name):
            raise ValueError(f"unexpected file name: {f.name}")
        if not FIRST_YEAR <= f.year <= LAST_YEAR:
            continue
        if f.prefecture is not None and not 1 <= int(f.prefecture) <= 47:
            continue
        kept.append(f)
    return kept


def read_dbf(data: bytes) -> tuple[list[str], list[list[str]]]:
    """Field names and rows of a dBase III file as text (cp932, padding stripped).

    Numbers stay text: upstream writes both a number and a flag in one column family, and the
    layout changes from year to year, so typing is left to the reader of a given column.
    """
    n, head_len, rec_len = struct.unpack("<IHH", data[4:12])
    fields, pos = [], 32
    while data[pos] != 0x0D:
        fields.append((data[pos : pos + 11].split(b"\0")[0].decode("ascii"), data[pos + 16]))
        pos += 32
    if 1 + sum(w for _, w in fields) != rec_len:
        raise ValueError("record length does not match the field widths")
    rows = []
    for i in range(n):
        rec = data[head_len + i * rec_len : head_len + (i + 1) * rec_len]
        if rec[:1] != b" ":
            raise ValueError(f"record {i} is deleted or malformed")
        row, off = [], 1
        for _, w in fields:
            row.append(rec[off : off + w].decode("cp932").strip(" \0"))
            off += w
        rows.append(row)
    return [f for f, _ in fields], rows


def read_shp_points(data: bytes) -> list[tuple[float, float]]:
    """(x, y) of every record of a point Shapefile, in file order."""
    if struct.unpack("<i", data[32:36])[0] != 1:
        raise ValueError("not a point Shapefile")
    pts, pos = [], 100
    while pos < len(data):
        _, words = struct.unpack(">ii", data[pos : pos + 8])
        shape, x, y = struct.unpack("<idd", data[pos + 8 : pos + 28])
        if shape != 1 or words != 10:
            raise ValueError("record is not a plain point")
        pts.append((x, y))
        pos += 8 + 2 * words
    return pts


def page_labels(html: str) -> dict[int, str]:
    """Column number to label, for pages that write the label and then (L01_nnn)."""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    return {int(c): n for n, c in re.findall(r"([^\s（）]+)\s*（L01_(\d+)）", text)}


# The columns every year has in some form, by year: (shapefile column, the label the year's
# own documentation gives it). The label is checked against the saved documentation, so a
# shifted layout fails loudly instead of mislabelling a column.
_OLD = {  # 2019 to 2021 (spec 2.5 and 3.0)
    "municipality_code": ("L01_021", "標準地行政区域コード"),
    "price": ("L01_006", "公示価格"),
    "address": ("L01_023", "住居表示"),
    "area_m2": ("L01_024", "地積"),
}
_MID = {  # 2022 and 2023 (spec 3.1.1)
    "municipality_code": ("L01_022", "標準地行政区域コード"),
    "price": ("L01_006", "公示価格"),
    "change_pct": ("L01_007", "対前年変動率"),
    "address": ("L01_024", "所在並びに地番"),
    "area_m2": ("L01_026", "地積"),
}
_NEW = {  # 2024 to 2026 (spec 3.2 to 4.0)
    "municipality_code": ("L01_001", "行政区域コード"),
    "price": ("L01_008", "地価公示価格"),
    "change_pct": ("L01_009", "対前年変動率"),
    "address": ("L01_025", "所在並びに地番"),
    "area_m2": ("L01_027", "地積"),
}
CORE: dict[int, dict[str, tuple[str, str]]] = (
    {y: _OLD for y in (2019, 2020, 2021)}
    | {y: _MID for y in (2022, 2023)}
    | {y: _NEW for y in (2024, 2025, 2026)}
)


def check_core(year: int, labels: dict[int, str]) -> list[str]:
    """Problems found when a year's mapped columns are compared with its documentation."""
    problems = []
    for name, (col, expected) in CORE[year].items():
        got = labels.get(int(col[4:]))
        if got != expected:
            problems.append(f"{name}: {col} is {got!r}, expected {expected!r}")
    return problems


def to_int(v: str) -> int | None:
    return int(v) if re.fullmatch(r"-?\d+", v) else None


def to_float(v: str) -> float | None:
    return float(v) if re.fullmatch(r"-?\d+(\.\d+)?", v) else None


def xlsx_labels(path, sheet: str) -> dict[int, str]:
    """Column number to label from a sheet of the attribute correspondence table (1983 to 2019).

    Rows that give a range of columns (``L01_057 ～ L01_090``) are skipped.
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True)
    out = {}
    for row in wb[sheet].iter_rows(values_only=True):
        m = re.fullmatch(r"L01_(\d+)", str(row[0] or ""))
        if m:
            out[int(m.group(1))] = str(row[1])
    return out
