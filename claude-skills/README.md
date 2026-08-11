# claude-skills/ — 単一インテーク・スキル層（任意・後付け）

「人が語りを渡し、AI が Obsidian と Neo4j へ仕分け、人がチャットで答えを引き出す」を実現する Claude Skills 3本です。

**入れなくても oya-inai-db は従来どおり動きます**（中核機能は AI なしで完結・検証済み）。語りの仕分けと二系統への投入を AI に任せたい人だけが導入してください。

## スキル3本の役割

| スキル | 役割 | 性格 |
|---|---|---|
| `oya-inai-intake`（親） | 語り・添付を受け、**仕分け宣言**を出して落とし先を決める | 判断だけを持つ |
| `oya-inai-vault`（子） | Obsidian Vault へ保存（raw/ 原本・ページ生成・lint・log） | 手続き。黙認方式 |
| `oya-inai-neo4j`（子） | Neo4j 支援DBへ構造化登録 | 手続き。**登録前に必ず人の確認** |

判断規則の正典は `oya-inai-intake/reference/dual-intake-routing.md` として**同梱済み**です（機械配布された写し・編集禁止。維持者が `scripts/sync_skill_refs.py` で更新します）。

## 前提（正直に書きます・軽くありません）

- **Claude の有料枠**（無料枠は不可。プライバシー保護の要件でもあります）
- **filesystem MCP**（Obsidian Vault を読み書きするため）
- **neo4j MCP** ＋ Neo4j の稼働（構造化登録のため。API サーバー稼働を推奨）
- Obsidian Vault（[oya-inai-keikaku-soudan](https://github.com/kazumasakawahara/oya-inai-keikaku-soudan) テンプレートから導入したもの）

MCP の設定手順は `docs/mcp-setup.md` を参照してください。

## 導入手順

Claude Code / Claude Desktop のスキルフォルダへ3本をコピーします。

```bash
# コピーする場合
cp -R claude-skills/oya-inai-intake ~/.claude/skills/
cp -R claude-skills/oya-inai-vault  ~/.claude/skills/
cp -R claude-skills/oya-inai-neo4j  ~/.claude/skills/

# リポジトリを clone 済みなら symlink でもよい（更新が自動で反映される）
ln -s "$(pwd)/claude-skills/oya-inai-intake" ~/.claude/skills/
ln -s "$(pwd)/claude-skills/oya-inai-vault"  ~/.claude/skills/
ln -s "$(pwd)/claude-skills/oya-inai-neo4j"  ~/.claude/skills/
```

導入の確認: Claude に「この面談メモを取り込んで」と語りを渡し、仕分け宣言（`〈出所〉からの〈種類〉として受け取りました…`）が返れば動いています。

## やめ方（撤退線）

`~/.claude/skills/` から3ディレクトリを削除するだけです。oya-inai-db 本体・Vault・データベースには何の影響もありません。
