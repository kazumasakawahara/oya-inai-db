#!/usr/bin/env python3
"""
sync_skill_refs.py — スキル層の参照文書を正典から機械配布する

**保守者専用。**正典 Vault（oya-inai-wiki）を持つ環境でのみ意味を持つ。
導入者は実行不要——`reference/` の写しは生成済みの状態で配布される。
正典が見つからず FAIL するのは導入環境では正常（実行しないこと）。

正典（oya-inai-wiki）→ 本リポジトリ claude-skills/ 内の写しを read-only 同期する。
sync-schema.sh（shared-schema）と同じ規約:
  - 編集は正典でのみ行う。写しは本スクリプトが上書きする「生成物」であり編集禁止
  - 既存の写しは上書き前に退避する。退避先はスキル木の外
    （`<repo>/.sync-backups/`。スキル木内に置くと ~/.claude/skills/ への
    コピーやスキル同期に .bak が紛れ込むため）
正典 Vault の場所は環境変数 `OYA_INAI_VAULT` で上書きできる
（既定: ~/Obsidian/oya-inai-wiki）。
台帳: shared-schema/SEMANTIC_MODEL.md §7-2「登録済み同期点」に本スクリプトの
同期点2件（SP-2: routing 文書・SP-3: 8棚表）が登録されている。

同期点:
  1. docs/dual-intake-routing.md（仕分けの判断規則・正本表22行）
       → claude-skills/oya-inai-intake/reference/dual-intake-routing.md
  2. 8棚表（Vault CLAUDE.md §1 の raw/ 棚構成 ⇔ oya-inai-intake SKILL.md Step 2 の表）
       → コピーではなく「一致の検査」。棚名の集合が完全一致しなければ FAIL

使い方:
    python3 scripts/sync_skill_refs.py           # 同期（棚表は検査のみ）
    python3 scripts/sync_skill_refs.py --check   # 差分・乖離の表示のみ（書き込まない）

終了コード: 0 = 一致 / 1 = 差分あり（--check）または同期を実施 / 2 = FAIL
  ※ DRIFT-13 の恒久策に従う: 検査対象は REPO_ROOT 相対で解決し、
    「対象ファイルが見つからない」「棚が0件」は WARN でなく FAIL とする
    （未検査を合格と区別できないため）
"""

import datetime
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = os.environ.get("OYA_INAI_VAULT",
                       os.path.expanduser("~/Obsidian/oya-inai-wiki"))
BACKUP_DIR = os.path.join(REPO_ROOT, ".sync-backups")   # スキル木の外・git 管理外

ROUTING_MASTER = os.path.join(VAULT, "docs", "dual-intake-routing.md")
ROUTING_COPY = os.path.join(
    REPO_ROOT, "claude-skills", "oya-inai-intake", "reference",
    "dual-intake-routing.md")

SHELF_CANON = os.path.join(VAULT, "CLAUDE.md")          # §1 の raw/ 棚構成
SKILL_MD = os.path.join(
    REPO_ROOT, "claude-skills", "oya-inai-intake", "SKILL.md")
EXPECTED_SHELVES = 8

SHELF_RE = re.compile(r"(\d\d_[^/\s`|]+)/")

BANNER_TMPL = (
    "<!-- AUTO-GENERATED COPY — DO NOT EDIT.\n"
    "  Synced from oya-inai-wiki docs/dual-intake-routing.md (正典).\n"
    "  Edit the master there and run scripts/sync_skill_refs.py."
    " (synced: {stamp}) -->\n\n"
)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def strip_banner(text):
    if text.startswith("<!-- AUTO-GENERATED"):
        end = text.find("-->")
        if end != -1:
            return text[end + 3:].lstrip("\n")
    return text


def shelf_set(path, scope_re=None):
    """path から棚名（NN_名前）の集合を取る。scope_re で対象範囲を絞れる。"""
    text = read(path)
    if scope_re:
        m = scope_re.search(text)
        if not m:
            return set()
        text = m.group(0)
    return set(SHELF_RE.findall(text))


def main():
    check_only = "--check" in sys.argv[1:]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    fails, diffs = [], []

    # --- 同期点1: routing 文書 ------------------------------------------
    if not os.path.isfile(ROUTING_MASTER):
        fails.append(f"正典が見つからない: {ROUTING_MASTER}")
    else:
        master = read(ROUTING_MASTER)
        if os.path.isfile(ROUTING_COPY) and strip_banner(read(ROUTING_COPY)) == master:
            print(f"OK (in sync): {os.path.relpath(ROUTING_COPY, REPO_ROOT)}")
        elif check_only:
            diffs.append(f"DIFF (would update): {os.path.relpath(ROUTING_COPY, REPO_ROOT)}")
        else:
            os.makedirs(os.path.dirname(ROUTING_COPY), exist_ok=True)
            if os.path.isfile(ROUTING_COPY):
                os.makedirs(BACKUP_DIR, exist_ok=True)
                bak = os.path.join(
                    BACKUP_DIR,
                    f"{os.path.basename(ROUTING_COPY)}.bak-{stamp}")
                os.replace(ROUTING_COPY, bak)
                print(f"backup: {os.path.relpath(bak, REPO_ROOT)}")
            with open(ROUTING_COPY, "w", encoding="utf-8") as f:
                f.write(BANNER_TMPL.format(stamp=stamp) + master)
            diffs.append(f"synced: {os.path.relpath(ROUTING_COPY, REPO_ROOT)}")

    # --- 同期点2: 8棚表（検査のみ・コピーしない）------------------------
    for label, path in (("正典(CLAUDE.md §1)", SHELF_CANON), ("SKILL.md", SKILL_MD)):
        if not os.path.isfile(path):
            fails.append(f"棚表の検査対象が見つからない: {label}: {path}")
    if not fails:
        canon = shelf_set(SHELF_CANON,
                          scope_re=re.compile(r"raw/.*?(?=\n├── wiki/)", re.S))
        skill = shelf_set(SKILL_MD)
        if len(canon) != EXPECTED_SHELVES:
            fails.append(
                f"正典の棚が {EXPECTED_SHELVES} 件でない（{len(canon)} 件検出）。"
                f"0件・過不足は未検査と区別できないため FAIL")
        elif canon != skill:
            only_canon = sorted(canon - skill)
            only_skill = sorted(skill - canon)
            fails.append(
                f"8棚表が乖離: 正典のみ {only_canon} / SKILL.md のみ {only_skill}")
        else:
            print(f"OK (8棚表一致): {EXPECTED_SHELVES} 棚")

    for d in diffs:
        print(d)
    for f_ in fails:
        print(f"FAIL: {f_}")
    if fails:
        return 2
    if diffs:
        return 1
    print("違反なし。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
