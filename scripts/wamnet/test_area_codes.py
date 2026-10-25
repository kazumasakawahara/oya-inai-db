"""KITAKYUSHU_AREAS（wamnet_downloader.py）を総務省の市区町村コード表と照合する試験。

使い方:
    uv run --with pytest pytest scripts/wamnet/test_area_codes.py
総務省の Excel（000925835.xlsx など）が手元にあれば、それとも照合する:
    SOUMU_XLSX=/path/to/000925835.xlsx uv run --with pytest --with openpyxl pytest scripts/wamnet/test_area_codes.py

wamnet_downloader.py は pandas と requests を読み込むので、import せずに ast で表だけ取り出す。
"""
import ast
import json
import os
import re
from pathlib import Path

import pytest

HERE = Path(__file__).parent
DOWNLOADER = HERE / "wamnet_downloader.py"
REFERENCE = HERE / "soumu_area_codes_reference.json"


def load_areas():
    tree = ast.parse(DOWNLOADER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "KITAKYUSHU_AREAS" for t in node.targets
        ):
            keys = [k.value for k in node.value.keys]
            assert len(keys) == len(set(keys)), "KITAKYUSHU_AREAS にコードの重複がある"
            return ast.literal_eval(node.value)
    raise AssertionError("KITAKYUSHU_AREAS が見つからない")


def load_reference():
    rows = json.loads(REFERENCE.read_text(encoding="utf-8"))["rows"]
    return {r["code5"]: r for r in rows}


def check_digit(code5):
    """全国地方公共団体コードの検査数字（上5桁に 6,5,4,3,2 を掛けた和を 11 で割った余りを 11 から引き、その1の位）。"""
    s = sum(int(d) * w for d, w in zip(code5, (6, 5, 4, 3, 2)))
    return (11 - s % 11) % 10


def test_codes_are_fukuoka_5digit():
    for code in load_areas():
        assert re.fullmatch(r"40\d{3}", code), code


def test_reference_check_digits():
    """参照ファイルの写し間違いを、6桁目の検査数字で見つける。"""
    for code5, r in load_reference().items():
        assert r["code6"][:5] == code5
        assert int(r["code6"][5]) == check_digit(code5), r


def test_areas_match_reference():
    ref = load_reference()
    errors = []
    for code, name in load_areas().items():
        r = ref.get(code)
        if r is None:
            errors.append(f"{code} {name}: 参照表に無いコード")
        elif name != r["gun"] + r["name"]:
            errors.append(f"{code} {name}: 総務省表では {r['gun']}{r['name']}")
    assert not errors, "\n".join(errors)


@pytest.mark.skipif(not os.environ.get("SOUMU_XLSX"), reason="SOUMU_XLSX が未設定")
def test_areas_match_soumu_xlsx():
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(os.environ["SOUMU_XLSX"], read_only=True, data_only=True)
    official = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            if row and row[0] is not None and re.fullmatch(r"\d{6}", str(row[0]).strip()):
                official.setdefault(str(row[0]).strip()[:5], str(row[2] or "").strip())
    errors = []
    for code, name in load_areas().items():
        o = official.get(code)
        # 総務省表は町村名に郡を付けない（「芦屋町」）ので、末尾一致で比べる
        if not o or not name.endswith(o):
            errors.append(f"{code} {name}: 総務省表では {o or '（無し）'}")
    for code5, r in load_reference().items():
        if official.get(code5) != r["name"]:
            errors.append(f"参照表 {code5} {r['name']}: 総務省表では {official.get(code5)}")
    assert not errors, "\n".join(errors)
