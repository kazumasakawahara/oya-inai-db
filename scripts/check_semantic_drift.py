"""
四者一致チェッカー（意味・ルール層のドリフト検知）

SEMANTIC_MODEL.md §6 の機械検証ブロック（あるべき仕様）を基準に、
  ① 正本ドキュメント（docs/SEMANTIC_MODEL.md、無ければ shared-schema のマスター）
  ② lib/schema_validator.py（Guardian の実装）
  ③ GET /api/narrative/schema（実行時 allowlist。API 停止時は本リポジトリの
    lib/db_new_operations.py をソース AST 解析）
  ④ api/app/lib/db_operations.py（API 書き込み経路の門番。ALLOWED_REL_TYPES /
    MERGE_KEYS / ALLOWED_CREATE_LABELS を AST 解析。DRIFT-13 が機械検出され
    なかった死角の解消——2026-08-10）
を突合する。

carve-out 注記（DRIFT-13・2026-08-10）: 本スクリプトは nest-support 版を原型に
持つが、oya-inai-db では検査対象をすべて**本リポジトリ内のファイル**に向ける。
外部リポジトリ（~/Dev-Work/neo4j-agno-agent 等）を参照しない。

既知の不一致は正本の acceptedDrifts に登録されており KNOWN として報告する。
未登録の不一致のみ FAIL（終了コード 1）。--strict で KNOWN も FAIL 扱い。

使い方:
  uv run python scripts/check_semantic_drift.py
  uv run python scripts/check_semantic_drift.py --strict

出力はラベル名・件数のみ（スキーマレベル）。実データは扱わない。
"""

import argparse
import ast
import importlib.util
import inspect
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DOC_CANDIDATES = [
    REPO_ROOT / "docs" / "SEMANTIC_MODEL.md",
    Path.home() / "Dev-Work" / "shared-schema" / "SEMANTIC_MODEL.md",
]
AGNO_SCHEMA_URL = os.environ.get(
    "AGNO_SCHEMA_URL", "http://localhost:8001/api/narrative/schema"
)
AGNO_SOURCE = Path(
    os.environ.get(
        "AGNO_DB_OPERATIONS",
        REPO_ROOT / "lib" / "db_new_operations.py",
    )
)

_FENCE_RE = re.compile(r"```json machine-check\n(.*?)```", re.DOTALL)


def load_lib_module(filename: str):
    """lib/ 配下のモジュールをファイルパス直指定で読み込む。

    `import lib.xxx` は lib/__init__.py が dotenv / streamlit を巻き込むため、
    依存が欠けた環境ではチェッカー全体が起動できなかった（DRIFT-13 の死角）。
    検査対象（schema_validator / insight_engine）自体は標準ライブラリのみに
    依存するので、パッケージを経由せず単体で読み込む。
    """
    path = REPO_ROOT / "lib" / filename
    spec = importlib.util.spec_from_file_location(f"_drift_check_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

results = {"OK": 0, "KNOWN": 0, "FAIL": 0, "WARN": 0}


def report(level: str, message: str):
    results[level] = results.get(level, 0) + 1
    print(f"[{level}] {message}")


# ---------------------------------------------------------------------------
# ① 正本ドキュメントの機械検証ブロック
# ---------------------------------------------------------------------------

def load_doc_spec() -> dict:
    for path in DOC_CANDIDATES:
        if path.is_file():
            m = _FENCE_RE.search(path.read_text(encoding="utf-8"))
            if not m:
                print(f"ERROR: {path} に ```json machine-check ブロックがありません")
                sys.exit(2)
            print(f"正本: {path}")
            return json.loads(m.group(1))
    print("ERROR: SEMANTIC_MODEL.md が見つかりません")
    sys.exit(2)


# ---------------------------------------------------------------------------
# ③ agno 実行時 allowlist（API → ソース AST の順で取得）
# ---------------------------------------------------------------------------

def fetch_agno_allowlist() -> tuple[set, set, str] | None:
    try:
        with urllib.request.urlopen(AGNO_SCHEMA_URL, timeout=3) as resp:
            data = json.loads(resp.read())
            return (
                set(data["allowed_labels"]),
                set(data["allowed_rels"]),
                f"API {AGNO_SCHEMA_URL}",
            )
    except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError):
        pass

    if not AGNO_SOURCE.is_file():
        return None
    tree = ast.parse(AGNO_SOURCE.read_text(encoding="utf-8"))
    consts: dict[str, object] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in (
                "MERGE_KEYS", "ALLOWED_CREATE_LABELS", "ALLOWED_REL_TYPES",
            ):
                try:
                    consts[target.id] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    if "MERGE_KEYS" not in consts or "ALLOWED_REL_TYPES" not in consts:
        return None
    labels = set(consts["MERGE_KEYS"].keys()) | set(
        consts.get("ALLOWED_CREATE_LABELS", set())
    )
    return labels, set(consts["ALLOWED_REL_TYPES"]), f"AST {AGNO_SOURCE}"


# ---------------------------------------------------------------------------
# 突合ロジック
# ---------------------------------------------------------------------------

def accepted(spec: dict, target: str, kind: str) -> dict | None:
    for d in spec.get("acceptedDrifts", []):
        if d["target"] == target and d["kind"] == kind:
            return d
    return None


def diff_sets(spec: dict, name: str, canonical: set, actual: set, target: str):
    """canonical（あるべき仕様）と actual（実装）を突合し、差分を報告する。"""
    missing = canonical - actual
    extra = actual - canonical

    for kind, values in (("missing-values", missing), ("extra-values", extra)):
        if not values:
            continue
        drift = accepted(spec, target, kind)
        word = "不足" if kind == "missing-values" else "過剰"
        if drift and values == set(drift["values"]):
            report("KNOWN", f"{name}: {word} {sorted(values)} （{drift['id']}: {drift['reason']}）")
        elif drift:
            known = values & set(drift["values"])
            unknown = values - set(drift["values"])
            if known:
                report("KNOWN", f"{name}: {word} {sorted(known)} （{drift['id']}）")
            if unknown:
                report("FAIL", f"{name}: 未登録の{word} {sorted(unknown)}")
        else:
            report("FAIL", f"{name}: 未登録の{word} {sorted(values)}")
    if not missing and not extra:
        report("OK", f"{name}: 一致（{len(canonical)}件）")


def check_validator(spec: dict):
    sv = load_lib_module("schema_validator.py")

    canon = spec["canonical"]
    diff_sets(spec, "Guardian ノードラベル", set(canon["nodeLabels"]),
              set(sv.VALID_NODE_LABELS), "validator.nodeLabels")
    diff_sets(spec, "Guardian リレーション", set(canon["relationshipTypes"]),
              set(sv.VALID_RELATIONSHIP_TYPES), "validator.relationshipTypes")
    for key, values in canon["enums"].items():
        if key not in sv.ENUM_VALUES:
            report("WARN", f"Guardian 列挙 {key}: validator に検証定義なし（検証対象外）")
            continue
        diff_sets(spec, f"Guardian 列挙 {key}", set(values),
                  set(sv.ENUM_VALUES[key]), f"validator.enums.{key}")


def check_insight_engine(spec: dict):
    ie = load_lib_module("insight_engine.py")

    if set(spec["canonical"]["negativeEmotions"]) == ie.NEGATIVE_EMOTIONS:
        report("OK", "負の感情の集合: 一致（5件）")
    else:
        report("FAIL", f"負の感情の集合: 正本={sorted(spec['canonical']['negativeEmotions'])} "
                       f"実装={sorted(ie.NEGATIVE_EMOTIONS)}")

    m = spec["metrics"]
    expected_defaults = [
        (ie.detect_emotion_drift, {"baseline_days": m["emotionDrift"]["baselineDays"],
                                   "recent_days": m["emotionDrift"]["recentDays"],
                                   "threshold": m["emotionDrift"]["warnThreshold"]}),
        (ie.detect_cascading_risk, {"days": m["cascadingRisk"]["days"],
                                    "min_cascade": m["cascadingRisk"]["minCascade"]}),
        (ie.detect_staff_overload, {"days": m["staffOverload"]["days"],
                                    "negative_ratio_threshold": m["staffOverload"]["negativeRatioThreshold"]}),
        (ie.discover_care_patterns, {"min_frequency": m["carePattern"]["discoverMinFrequency"]}),
        (ie.propose_care_promotions, {"min_frequency": m["carePattern"]["promoteMinFrequency"]}),
    ]
    for func, params in expected_defaults:
        sig = inspect.signature(func)
        for pname, expected in params.items():
            actual = sig.parameters[pname].default
            if actual == expected:
                report("OK", f"閾値 {func.__name__}.{pname} = {expected}")
            else:
                report("FAIL", f"閾値 {func.__name__}.{pname}: 正本={expected} 実装={actual}")

    # シグネチャに現れないハードコード値はソーステキストの簡易照合
    source = inspect.getsource(ie)
    for label, needle in [
        (f"重大判定 severeThreshold = {m['emotionDrift']['severeThreshold']}",
         f">= {m['emotionDrift']['severeThreshold']}"),
        (f"スタッフ負荷 minLogs = {m['staffOverload']['minLogs']}",
         f">= {m['staffOverload']['minLogs']}"),
    ]:
        if needle in source:
            report("OK", f"閾値 {label}（ソース照合）")
        else:
            report("WARN", f"閾値 {label}: ソース内に見つからず（手動確認要）")


def check_api_gatekeeper(spec: dict):
    """④ api/app/lib/db_operations.py（API 書き込み経路の門番）を AST 照合。

    /api/narrative/intake の allowlist 二重検証はこのファイルの
    ALLOWED_REL_TYPES / MERGE_KEYS / ALLOWED_CREATE_LABELS を参照する。
    DRIFT-13 ではここが検査対象に入っておらず、正典収載済みの
    CONFIRMS / CONTRADICTS が実行時に reject される状態が検出されなかった。
    実行時 import は Neo4j ドライバ等を巻き込むため AST（literal_eval）で読む。
    このファイルは `NAME: set[str] = {...}` の注釈付き代入なので AnnAssign も拾う。
    """
    src = REPO_ROOT / "api" / "app" / "lib" / "db_operations.py"
    if not src.is_file():
        report("FAIL", "API 門番: api/app/lib/db_operations.py が見つかりません")
        return
    tree = ast.parse(src.read_text(encoding="utf-8"))
    wanted = ("MERGE_KEYS", "ALLOWED_CREATE_LABELS", "ALLOWED_REL_TYPES")
    consts: dict[str, object] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if isinstance(target, ast.Name) and target.id in wanted:
            try:
                consts[target.id] = ast.literal_eval(value)
            except ValueError:
                pass
    if "MERGE_KEYS" not in consts or "ALLOWED_REL_TYPES" not in consts:
        report("FAIL", "API 門番: MERGE_KEYS / ALLOWED_REL_TYPES を AST で取得できません")
        return
    merge_keys: dict = consts["MERGE_KEYS"]
    create_labels = set(consts.get("ALLOWED_CREATE_LABELS", set()))
    canon = spec["canonical"]

    diff_sets(spec, "API 門番 ノードラベル", set(canon["nodeLabels"]),
              set(merge_keys) | create_labels, "apiGatekeeper.nodeLabels")
    diff_sets(spec, "API 門番 リレーション", set(canon["relationshipTypes"]),
              set(consts["ALLOWED_REL_TYPES"]), "apiGatekeeper.relationshipTypes")

    nest_spec = spec.get("nestLib", {})
    for label, expected in nest_spec.get("mergeKeys", {}).items():
        actual = merge_keys.get(label)
        if actual == expected:
            report("OK", f"API 門番 MERGE キー {label} = {expected}")
        else:
            report("FAIL", f"API 門番 MERGE キー {label}: 正本={expected} 実装={actual}")
    for label in nest_spec.get("neverMergeLabels", []):
        if label in merge_keys:
            report("FAIL", f"API 門番: {label} が MERGE_KEYS に存在"
                           "（追記専用・常時 CREATE が正。ENT-16 / ENT-24 参照）")
        else:
            report("OK", f"API 門番: {label} は MERGE_KEYS に無い（追記専用・正）")


def check_agno(spec: dict):
    fetched = fetch_agno_allowlist()
    if fetched is None:
        report("WARN", "agno allowlist を取得できません（API 停止かつソース不在）。三者目は未検証")
        return
    labels, rels, origin = fetched
    print(f"agno allowlist: {origin}")
    canon = spec["canonical"]
    diff_sets(spec, "agno ノードラベル", set(canon["nodeLabels"]), labels,
              "agno.nodeLabels")
    diff_sets(spec, "agno リレーション", set(canon["relationshipTypes"]), rels,
              "agno.relationshipTypes")


def main():
    parser = argparse.ArgumentParser(description="意味・ルール層の三者一致チェック")
    parser.add_argument("--strict", action="store_true",
                        help="既知ドリフト（KNOWN）も失敗として扱う")
    args = parser.parse_args()

    spec = load_doc_spec()
    print("--- ② Guardian (lib/schema_validator.py) ---")
    check_validator(spec)
    print("--- ② Oracle (lib/insight_engine.py) ---")
    check_insight_engine(spec)
    print("--- ③ agno 実行時 allowlist (lib/db_new_operations.py) ---")
    check_agno(spec)
    print("--- ④ API 門番 (api/app/lib/db_operations.py) ---")
    check_api_gatekeeper(spec)

    print(f"\n結果: OK={results['OK']} KNOWN={results['KNOWN']} "
          f"FAIL={results['FAIL']} WARN={results['WARN']}")
    if results["FAIL"] or (args.strict and results["KNOWN"]):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
