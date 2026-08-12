#!/usr/bin/env -S uv run --quiet --with markdown python3
# -*- coding: utf-8 -*-
"""福祉専門職のための完全導入マニュアル.md → .html
   mcp-setup.html と同系統の配色・組版。依存は uv の一時環境で解決し、環境を汚さない。"""
import re
import pathlib
import markdown

SRC = pathlib.Path("docs/manuals/福祉専門職のための完全導入マニュアル.md")
DST = pathlib.Path("docs/manuals/福祉専門職のための完全導入マニュアル.html")

text = SRC.read_text(encoding="utf-8")

# 先頭の H1 をタイトルとして抜き、本文からは外す（HTML 側でヘッダに組む）
m = re.match(r"#\s+(.+?)\n", text)
title = m.group(1).strip() if m else "福祉専門職のための完全導入マニュアル"
body_md = text[m.end():] if m else text

html_body = markdown.markdown(
    body_md,
    extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"],
    output_format="html5",
)

STYLE = """
  :root{
    --ink:#1c1917; --ink2:#44403c; --ink3:#79716b;
    --line:#e7e5e4; --bg:#fdfcfb; --card:#fff;
    --accent:#7c5a3a; --accent-soft:#f6f0e9; --accent-line:#e6d8c7;
    --ok:#3f6f52; --ok-soft:#eef4f0; --ok-line:#d6e5db;
    --alert:#9a3d2c; --alert-soft:#fbf0ed; --alert-line:#eed4cc;
    --warn:#8a6d1f; --warn-soft:#faf5e6; --warn-line:#e8dcb5;
    --mute:#f6f5f3;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:"Yu Gothic UI","Yu Gothic","Meiryo","Hiragino Sans","Hiragino Kaku Gothic ProN",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    line-height:1.95;font-size:16px;letter-spacing:.01em}
  .wrap{max-width:860px;margin:0 auto;padding:40px 24px 96px}
  header.doc{border-bottom:2px solid var(--ink);padding-bottom:18px;margin-bottom:34px}
  h1{font-size:30px;line-height:1.4;margin:0 0 8px;letter-spacing:-.01em}
  .sub{color:var(--ink3);font-size:14px;margin:0}
  h1.part{font-size:24px;margin:64px 0 18px;padding:14px 18px;
    background:var(--accent-soft);border:1px solid var(--accent-line);
    border-radius:10px;color:var(--accent);letter-spacing:.02em}
  h2{font-size:22px;margin:52px 0 14px;padding-bottom:8px;border-bottom:1px solid var(--ink);line-height:1.5}
  h3{font-size:18px;margin:34px 0 10px;color:var(--ink2);line-height:1.55}
  h4{font-size:16px;margin:24px 0 8px;color:var(--ink2)}
  p{margin:0 0 15px}
  ul,ol{margin:0 0 16px;padding-left:1.5em}
  li{margin-bottom:7px}
  a{color:var(--accent);text-underline-offset:3px}
  code{background:var(--mute);border:1px solid var(--line);border-radius:5px;
    padding:1px 5px;font-size:13.5px;
    font-family:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace}
  pre{background:#faf9f7;border:1px solid var(--line);border-radius:10px;
    padding:14px 16px;overflow-x:auto;margin:0 0 18px;line-height:1.7}
  pre code{background:none;border:none;padding:0;font-size:13px}
  blockquote{margin:0 0 18px;padding:14px 18px;background:var(--accent-soft);
    border:1px solid var(--accent-line);border-left:4px solid var(--accent);
    border-radius:0 10px 10px 0;color:var(--ink2)}
  blockquote p:last-child{margin-bottom:0}
  table{border-collapse:collapse;width:100%;margin:0 0 20px;font-size:14.5px;
    background:var(--card);display:block;overflow-x:auto}
  th,td{border:1px solid var(--line);padding:9px 12px;text-align:left;vertical-align:top}
  th{background:var(--mute);font-weight:600;white-space:nowrap}
  hr{border:none;border-top:1px solid var(--line);margin:44px 0}
  strong{font-weight:700}
  footer.doc{margin-top:64px;padding-top:20px;border-top:1px solid var(--line);
    color:var(--ink3);font-size:13.5px}
  @media print{
    body{background:#fff;font-size:11pt;line-height:1.7}
    .wrap{max-width:none;padding:0}
    h1.part,h2,h3{break-after:avoid}
    pre,table,blockquote{break-inside:avoid}
  }
  @media (max-width:640px){
    .wrap{padding:24px 16px 64px}
    h1{font-size:24px} h1.part{font-size:20px} h2{font-size:19px}
  }
"""

# 「# 第 N 部」由来の h1 は部扉として別スタイルに
html_body = re.sub(r"<h1(\s+id=\"[^\"]*\")?>", lambda mo: f'<h1 class="part"{mo.group(1) or ""}>', html_body)

out = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">
<header class="doc">
  <h1>{title}</h1>
  <p class="sub">親亡き後支援データベース（oya-inai-db）／ このページは同フォルダの Markdown 版から生成しています</p>
</header>
{html_body}
<footer class="doc">
  親亡き後支援データベース（oya-inai-db）— MIT License.
  最新版は <a href="https://github.com/kazumasakawahara/oya-inai-db">GitHub リポジトリ</a> をご確認ください。
</footer>
</div>
</body>
</html>
"""

DST.write_text(out, encoding="utf-8")
print(f"wrote {DST} ({len(out):,} bytes)")
