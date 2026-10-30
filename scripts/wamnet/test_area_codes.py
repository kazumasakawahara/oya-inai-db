"""KITAKYUSHU_AREAS（wamnet_downloader.py）を総務省の市区町村コード表と照合し、所在地での絞り込みを確かめる試験。

使い方:
    uv run --with pytest --with pandas --with requests pytest scripts/wamnet/test_area_codes.py
総務省の Excel（000925835.xlsx など）が手元にあれば、それとも照合する:
    SOUMU_XLSX=/path/to/000925835.xlsx uv run --with pytest --with openpyxl pytest scripts/wamnet/test_area_codes.py

表の照合は ast で表だけ取り出すので pandas なしで動く。絞り込みの試験は pandas と requests が無ければ飛ばす。
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


def _downloader():
    pytest.importorskip("pandas")
    pytest.importorskip("requests")
    import importlib.util

    spec = importlib.util.spec_from_file_location("wamnet_downloader", DOWNLOADER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize(
    "value, expected",
    [
        ("福岡県北九州市小倉南区", True),
        ("福岡県行橋市", True),
        ("福岡県中間市", True),
        ("福岡県遠賀郡芦屋町", True),
        ("福岡県芦屋町", True),
        ("福岡県京都郡みやこ町", True),
        ("福岡県久留米市", False),  # 旧版が指定権者コード 40203 で拾っていた
        ("福岡県八女市", False),
        ("福岡県飯塚市", False),
        ("兵庫県芦屋市", False),
        ("北九州市小倉南区", False),  # 都道府県名が無い値は拾わない
        (None, False),
    ],
)
def test_is_kitakyushu_area(value, expected):
    assert _downloader().is_kitakyushu_area(value) is expected


def test_filter_uses_address_not_designator_code():
    """先頭のコード列（指定権者）ではなく、事業所住所（市区町村）で絞り込む。"""
    mod = _downloader()
    import pandas as pd

    df = pd.DataFrame(
        {
            "都道府県コード又は市区町村コード": ["401005", "402036", "400009", "400009"],
            "事業所住所（市区町村）": ["福岡県北九州市八幡西区", "福岡県久留米市", "福岡県行橋市", "福岡県飯塚市"],
        }
    )
    out = mod.filter_kitakyushu_area(df)
    assert list(out["事業所住所（市区町村）"]) == ["福岡県北九州市八幡西区", "福岡県行橋市"]
    assert list(out.columns) == list(df.columns)


def test_filter_fukuoka_pref_does_not_mutate():
    mod = _downloader()
    import pandas as pd

    df = pd.DataFrame({"都道府県コード又は市区町村コード": ["401005", "131016"], "事業所住所（市区町村）": ["a", "b"]})
    cols = list(df.columns)
    assert len(mod.filter_fukuoka_pref(df)) == 1
    assert list(df.columns) == cols


# ---- 公開時点（半年ごとの更新）----


@pytest.mark.parametrize(
    "today, expected",
    [
        ("2026-10-30", ["202609", "202603", "202509"]),
        ("2026-09-01", ["202609", "202603", "202509"]),
        ("2026-08-31", ["202603", "202509", "202503"]),
        ("2026-03-01", ["202603", "202509", "202503"]),
        ("2026-02-28", ["202509", "202503", "202409"]),
    ],
)
def test_candidate_periods(today, expected):
    from datetime import date

    assert _downloader().candidate_periods(date.fromisoformat(today), count=3) == expected


def test_find_latest_period_skips_unpublished():
    from datetime import date

    mod = _downloader()
    published = {"202509", "202503"}
    assert mod.find_latest_period(date(2026, 10, 30), is_published=published.__contains__) == "202509"
    assert mod.find_latest_period(date(2026, 10, 30), is_published=lambda p: False) is None


def test_check_exit_codes(tmp_path, monkeypatch):
    mod = _downloader()
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(mod, "find_latest_period", lambda: "202603")
    assert mod.check("auto") == 10  # 新しい公開時点があり、まだ取っていない
    (tmp_path / "kitakyushu_services_202603.csv").write_text("x")
    assert mod.check("auto") == 0
    monkeypatch.setattr(mod, "find_latest_period", lambda: None)
    assert mod.check("auto") == 1


@pytest.mark.parametrize("status, body, expected", [(200, b"PK\x03\x04", True), (200, b"<html", False), (404, b"", False)])
def test_period_is_published(monkeypatch, status, body, expected):
    mod = _downloader()

    class FakeResponse:
        status_code = status

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_content(self, chunk_size):
            yield body

    monkeypatch.setattr(mod.requests, "get", lambda *a, **k: FakeResponse())
    assert mod.period_is_published("202603") is expected
