import ksj_l01 as k
import pytest

PAGE = """
<a onclick="javascript:DownLd('0.11MB','L01-26_31_GML.zip','/ksj/gml/data/L01/L01-26//L01-26_31_GML.zip' ,this);">
<a onclick="javascript:DownLd('19.9MB','L01-26_GML.zip','/ksj/gml/data/L01/L01-26//L01-26_GML.zip' ,this);">
<a onclick="javascript:DownLd('18.9MB','L01-19_GML.zip','/ksj/gml/data/L01/L01-19//L01-19_GML.zip' ,this);">
<a onclick="javascript:DownLd('2.20MB','L01-83_31_GML.zip','/ksj/gml/data/L01/L01-83//L01-83_31_GML.zip' ,this);">
"""


def test_parse_downloads_reads_every_call():
    files = k.parse_downloads(PAGE)
    assert [f.name for f in files] == [
        "L01-26_31_GML.zip",
        "L01-26_GML.zip",
        "L01-19_GML.zip",
        "L01-83_31_GML.zip",
    ]
    assert files[0].url == "https://nlftp.mlit.go.jp/ksj/gml/data/L01/L01-26/L01-26_31_GML.zip"
    assert files[0].page_size == "0.11MB"


def test_year_and_prefecture_from_name():
    f = k.parse_downloads(PAGE)
    assert (f[0].year, f[0].prefecture) == (2026, "31")
    assert (f[1].year, f[1].prefecture) == (2026, None)
    assert (f[2].year, f[2].prefecture) == (2019, None)
    assert (f[3].year, f[3].prefecture) == (1983, "31")


def test_select_keeps_only_the_licence_clear_years_without_regional_blocks():
    files = k.parse_downloads(PAGE) + k.parse_downloads(
        "DownLd('19MB','L01-23_52_GML.zip','/ksj/gml/data/L01/L01-23//L01-23_52_GML.zip' ,this)"
    )
    kept = k.select(files)
    assert [f.name for f in kept] == ["L01-26_31_GML.zip", "L01-26_GML.zip", "L01-19_GML.zip"]


def test_select_rejects_a_name_that_is_not_the_known_shape():
    bad = k.parse_downloads(
        "DownLd('1MB','L01-26_xx.zip','/ksj/gml/data/L01/L01-26//L01-26_xx.zip' ,this)"
    )
    with pytest.raises(ValueError):
        k.select(bad)


def test_expected_plan_is_8_years_of_48():
    names = []
    for y in range(19, 27):
        names.append(f"L01-{y}_GML.zip")
        names += [f"L01-{y}_{p:02d}_GML.zip" for p in range(1, 48)]
    html = "".join(f"DownLd('1MB','{n}','/ksj/gml/data/L01/{n[:6]}//{n}' ,this)" for n in names)
    assert len(k.select(k.parse_downloads(html))) == 384


def make_dbf(fields, rows):
    """fields: [(name, type, length, decimals)]; rows: list of lists of str (cp932)."""
    import struct

    rec_len = 1 + sum(f[2] for f in fields)
    head_len = 32 + 32 * len(fields) + 1
    out = bytearray(
        struct.pack("<BBBBIHH", 3, 26, 10, 16, len(rows), head_len, rec_len) + bytes(20)
    )
    for name, typ, ln, dec in fields:
        out += (
            name.encode().ljust(11, b"\0") + typ.encode() + bytes(4) + bytes([ln, dec]) + bytes(14)
        )
    out += b"\r"
    for r in rows:
        out += b" " + b"".join(
            v.encode("cp932").ljust(f[2], b" ") for v, f in zip(r, fields, strict=True)
        )
    return bytes(out + b"\x1a")


def make_shp(points):
    import struct

    body = b"".join(
        struct.pack(">ii", i + 1, 10) + struct.pack("<idd", 1, x, y)
        for i, (x, y) in enumerate(points)
    )
    head = struct.pack(">i", 9994) + bytes(20) + struct.pack(">i", (100 + len(body)) // 2)
    head += struct.pack("<ii", 1000, 1) + bytes(64)
    return head + body


def test_read_dbf_decodes_cp932_and_strips_padding():
    data = make_dbf(
        [("L01_001", "C", 5, 0), ("L01_024", "C", 20, 0), ("L01_008", "N", 8, 0)],
        [["01101", "北海道　札幌市", "  459000"], ["13101", "東京都", "       0"]],
    )
    fields, rows = k.read_dbf(data)
    assert fields == ["L01_001", "L01_024", "L01_008"]
    assert rows == [["01101", "北海道　札幌市", "459000"], ["13101", "東京都", "0"]]


def test_read_dbf_rejects_deleted_records():
    data = bytearray(make_dbf([("A", "C", 2, 0)], [["x"]]))
    data[32 + 32 + 1] = ord("*")
    with pytest.raises(ValueError):
        k.read_dbf(bytes(data))


def test_read_shp_points_returns_lon_lat_in_order():
    pts = [(141.35, 43.06), (139.69, 35.68)]
    assert k.read_shp_points(make_shp(pts)) == pts


def test_read_shp_points_rejects_other_shape_types():
    data = bytearray(make_shp([(1.0, 2.0)]))
    data[32:36] = (5).to_bytes(4, "little")
    with pytest.raises(ValueError):
        k.read_shp_points(bytes(data))


def test_extra_urls_are_the_year_pages_and_the_attribute_table():
    urls = k.extra_urls()
    assert len(urls) == 9
    assert urls[0].endswith("KsjTmplt-L01-2019.html") and urls[7].endswith("KsjTmplt-L01-2026.html")
    assert urls[8].endswith("L01-2006-2019_shape_property_table.xlsx")


PAGE_ATTRS = """<td>地価公示価格 （L01_008）</td><td>標準地の当年の地価公示価格</td>
<td>対前年変動率 （L01_009）</td><td>x</td><td>用途区分 （L01_002）</td>"""


def test_page_labels_maps_column_number_to_the_label_before_it():
    assert k.page_labels(PAGE_ATTRS) == {8: "地価公示価格", 9: "対前年変動率", 2: "用途区分"}


def test_core_mapping_exists_for_every_year_and_names_the_expected_label():
    assert sorted(k.CORE) == list(range(2019, 2027))
    assert k.CORE[2026]["price"] == ("L01_008", "地価公示価格")
    assert k.CORE[2022]["change_pct"] == ("L01_007", "対前年変動率")
    assert "change_pct" not in k.CORE[2021]


def test_core_columns_checks_the_label_of_each_mapped_column():
    labels = {
        8: "地価公示価格",
        9: "対前年変動率",
        1: "行政区域コード",
        25: "所在並びに地番",
        27: "地積",
    }
    assert k.check_core(2026, labels) == []
    labels[8] = "何か別のもの"
    assert k.check_core(2026, labels) == [
        "price: L01_008 is '何か別のもの', expected '地価公示価格'"
    ]


def test_to_int_and_to_float_leave_unreadable_values_empty():
    assert k.to_int("459000") == 459000
    assert k.to_int("") is None and k.to_int("_") is None and k.to_int("3.1") is None
    assert k.to_float("3.1") == 3.1 and k.to_float("_") is None and k.to_float("") is None
    assert k.to_float("6.00000e-001") == 0.6
    assert k.to_float("-1.47000e+001") == -14.7
    assert k.to_float("5.30000e+000") == 5.3
    with pytest.raises(ValueError):
        k.to_float("abc")


def test_xlsx_labels_reads_single_columns_and_skips_ranges(tmp_path):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "2019"
    for row in [
        ["2019年", None],
        ["L01_001", "見出し"],
        ["L01_006", "公示価格"],
        ["L01_057 ～ L01_090", "調査価格"],
    ]:
        ws.append(row)
    path = tmp_path / "t.xlsx"
    wb.save(path)
    assert k.xlsx_labels(path, "2019") == {1: "見出し", 6: "公示価格"}
