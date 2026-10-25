#!/usr/bin/env python3
"""旧 KITAKYUSHU_AREA_CODES（2026-10-25 以前）で作った取り込みに、近郊外の事業所が何件混ざったかを数える。

出すのは件数だけ。事業所名・住所・電話番号などの行の中身は表示しない。

使い方:
    # CSV（wamnet_downloader.py の出力）
    uv run --with pandas python scripts/wamnet/count_area_mismatch.py csv wamnet_data/kitakyushu_services_202509.csv
    # Neo4j の ServiceProvider（読み取り専用で接続する。接続先は必ず明示する）
    NEO4J_PASSWORD=... uv run --with neo4j python scripts/wamnet/count_area_mismatch.py neo4j --uri bolt://localhost:7687

nest-support の本番 DB には向けないこと。
"""
import argparse
import ast
import os
import sys
from collections import Counter
from pathlib import Path

# 旧表のコード（直す前の値）。総務省表と照合した結果は soumu_area_codes_reference.json と同じ出典。
OLD_CODES = [
    "40100", "40101", "40103", "40105", "40106", "40107", "40108", "40109",
    "40202", "40203", "40204", "40205", "40206", "40207", "40210", "40211",
    "40212", "40213", "40220", "40221", "40231", "40341", "40342", "40343",
    "40344", "40381", "40382", "40401", "40421", "40422", "40423", "40424",
    "40425", "40426", "40427", "40601", "40602", "40604", "40605", "40606",
]


def load_areas():
    src = (Path(__file__).parent / "wamnet_downloader.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "KITAKYUSHU_AREAS" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise SystemExit("KITAKYUSHU_AREAS が見つからない")


def classify(code5, areas):
    if code5 in areas:
        return "新表にある（近郊）"
    if code5 in OLD_CODES:
        return "旧表だけにある（近郊外の可能性）"
    return "どちらの表にも無い"


def count_csv(paths, areas):
    import pandas as pd

    for path in paths:
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig")
        # wamnet_downloader.filter_kitakyushu_area と同じ列の選び方
        code_columns = [c for c in df.columns if "コード" in c or "code" in c.lower()]
        code_col = code_columns[0] if code_columns else df.columns[0]
        codes = df[code_col].astype(str).str[:5]
        print(f"\n== {path}（{len(df)} 行、照合列: {code_col}）")
        by_class = Counter(classify(c, areas) for c in codes)
        for k, v in by_class.most_common():
            print(f"  {k}: {v}")
        print("  コード別:")
        for code, v in sorted(Counter(codes).items()):
            print(f"    {code} {areas.get(code, '')} [{classify(code, areas)}]: {v}")
        # コード列が「指定機関」のコードなら、事業所の所在地とずれる。所在地の市区町村列も件数だけ出す
        for col in [c for c in df.columns if "市区町村" in c and "コード" not in c]:
            print(f"  列「{col}」の値別件数:")
            for val, v in df[col].fillna("（空）").value_counts().items():
                print(f"    {val}: {v}")


def count_neo4j(uri, areas):
    from neo4j import GraphDatabase, READ_ACCESS

    names = {n for n in areas.values()}
    short = {n.split("郡", 1)[1] if "郡" in n else n for n in names}
    driver = GraphDatabase.driver(
        uri, auth=(os.getenv("NEO4J_USERNAME", "neo4j"), os.environ["NEO4J_PASSWORD"])
    )
    query = (
        "MATCH (sp:ServiceProvider) "
        "RETURN coalesce(sp.prefecture, '') AS pref, coalesce(sp.city, '') AS city, count(*) AS n"
    )
    with driver.session(default_access_mode=READ_ACCESS) as session:
        rows = [r.data() for r in session.run(query)]
    driver.close()
    total = sum(r["n"] for r in rows)
    inside = Counter()
    outside = Counter()
    for r in rows:
        city = r["city"]
        hit = city in names or city in short or any(city.startswith(n) for n in names | short)
        (inside if hit else outside)[(r["pref"], city or "（空）")] += r["n"]
    print(f"ServiceProvider: {total} 件")
    print(f"  新表の市区町村: {sum(inside.values())} 件")
    print(f"  新表に無い市区町村: {sum(outside.values())} 件")
    for (pref, city), v in outside.most_common():
        print(f"    {pref} {city}: {v}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="mode", required=True)
    c = sub.add_parser("csv")
    c.add_argument("paths", nargs="+")
    n = sub.add_parser("neo4j")
    n.add_argument("--uri", required=True, help="接続先を必ず明示する（既定値は持たない）")
    args = p.parse_args()
    areas = load_areas()
    if args.mode == "csv":
        count_csv(args.paths, areas)
    else:
        count_neo4j(args.uri, areas)


if __name__ == "__main__":
    sys.exit(main())
