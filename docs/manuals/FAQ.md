# FAQ & トラブルシューティング

---

## よくある質問

### Q: データはどこに保存されますか？

データはすべて**お使いのパソコン内**に保存されます。具体的には `oya-inai-db/neo4j_data/` フォルダ内の Docker ボリュームに格納されます。クラウドのデータベースは使いません。

ただし、**Claude に登録・まとめ入力・照会を頼んだ内容**（そこに含まれる支援記録・禁忌事項などのテキスト）は、Anthropic 社のサーバーに送信されます。組織で導入する場合は、契約するプランのデータ取り扱い方針を確認し、個人情報保護規程と照らし合わせて運用してください（→ `PRIVACY_GUIDELINES.md`）。

### Q: 利用料金はいくらですか？

**ソフトウェア本体は無償です。** そのうえで、新しい方の登録や、語り・文書からのまとめ入力は **Claude**（Anthropic 社の AI アシスタント）に頼む設計のため、**Claude の有料プランの契約が実質的な導入要件**です。

閲覧と日々の記録（緊急照会・更新期限アラート・出来事の記録・面談記録）だけなら、Claude なしでも動きます。

### Q: AI はどれを選べばよいですか？

選択の必要はありません。**このシステムの AI は Claude 一本**です（2026-08 方針決定）。

以前あった「Ollama / Gemini / Claude API の 3 択」と、アプリ内の AI 機能（ナラティブ AI 抽出・AI チャット・意味検索・音声の文字起こし）は廃止しました。かわりに **Claude Desktop からデータベースに直接つないで**、登録・まとめ入力・照会を行います。設定は `docs/mcp-setup.md` と `ç¦ç¥å°éè·ã®ããã®å®å¨å°å¥ããã¥ã¢ã«.md` 第 6 章を参照してください。

### Q: Claude を設定しないと、何ができなくなりますか？

画面の機能はすべてそのまま使えます。**エラーにはなりません。**

| Claude なしで動く（Web 画面） | Claude が担当（要設定） |
|------------------------------|------------------------|
| 利用者台帳（クライアント一覧・詳細） | 新しい方の登録 |
| 緊急照会（禁忌事項・連絡先） | 語り・文書からのまとめ入力 |
| 更新期限アラート | 自由な言葉での照会・記録の検索 |
| 出来事の記録・面談記録 | 書類の下書き作成 |
| エコマップ・知識グラフ | — |

ただし、**新しい方の登録画面はアプリにはありません。** データベースを育てていくには Claude が必要です。

### Q: 複数の担当者で使えますか？

はい。Neo4j データベースは同じネットワーク内の複数のパソコンからアクセスできます。ただし現在のバージョンでは、厳密なユーザー管理機能（誰がどの操作をしたかの追跡）は備えていません。

### Q: バックアップはどうすればよいですか？

```bash
# Neo4j データのバックアップ
docker compose stop
cp -r neo4j_data neo4j_data_backup_$(date +%Y%m%d)
docker compose start
```

定期的なバックアップを推奨します。

### Q: データを別のパソコンに移行できますか？

はい。`neo4j_data/` フォルダをコピーすることで移行できます。

### Q: インターネット接続は必要ですか？

初回セットアップ時には必要です（Docker イメージのダウンロード、パッケージの取得）。

セットアップ後は、**Web 画面での閲覧・記録はオフラインで動作します。** Claude に登録・照会を頼むときだけ、インターネット接続が必要です。

### Q: 練習用のデータはありますか？

あります。架空の人物による**合成データ**なので、安心して操作の練習ができます。

```powershell
# Windows
.\installer\load-demo-data.ps1
```

```bash
# Mac
./installer/load-demo-data.sh
```

---

## トラブルシューティング

### 画面が開かない／ localhost:3001 につながらない

**症状**: ブラウザで <http://localhost:3001> を開いても、画面が表示されない

**対処法（Windows）**:
1. Docker Desktop が起動しているか確認（タスクバーのクジラのアイコン）
2. `stop.bat` をダブルクリックして停止
3. `start.bat` をダブルクリックして起動し直す
4. 起動には時間がかかります。1〜2分待ってからブラウザを再読み込み（F5）

**対処法（Mac）**:
1. Docker Desktop が起動しているか確認（メニューバーのクジラのアイコン）
2. `start.command` をダブルクリックして起動し直す
3. 自動診断を実行:
```bash
./scripts/doctor.sh
```

### Docker が起動しない

**症状**: `docker: command not found` または Docker Desktop が反応しない

**対処法（macOS）**:
1. Docker Desktop アプリが起動しているか確認（メニューバーにクジラのアイコン）
2. 起動していない場合: アプリケーションフォルダから Docker を開く
3. アイコンが表示されるまで1〜2分待つ
4. それでも動かない場合: Docker Desktop を再インストール

**対処法（Windows）**:
1. タスクバー右下の通知領域にクジラのアイコンがあるか確認
2. 起動していない場合: スタートメニューから「Docker Desktop」を検索して起動
3. 「Docker Desktop is starting...」が消えるまで待つ（初回は数分かかることがあります）
4. WSL2 バックエンドが有効か確認（Docker Desktop → Settings → General → Use the WSL 2 based engine）

```bash
# Docker の状態確認
docker info
```

### Neo4j に接続できない

**症状**: `curl: (7) Failed to connect to localhost port 7474`、または画面にデータが出てこない

**対処法**:
```bash
# コンテナの状態確認（oya-inai-db-neo4j があるか）
docker ps

# コンテナが停止している場合、再起動
docker compose up -d

# ログの確認
docker logs oya-inai-db-neo4j
```

**よくある原因**:
- Docker Desktop が起動していない
- ポートが他のアプリケーションに使われている（`lsof -i :7474` で確認）
- メモリ不足（Docker Desktop の Settings → Resources でメモリを4GB以上に設定）

ブラウザで <http://localhost:7474> を開き、画面が出ればデータベースは応答しています（ユーザー名 `neo4j` / パスワード `password`）。

### API（port 8001）に繋がらないと表示される

**症状**: 画面は開くが、データの読み書きでエラーになる

**対処法**:
1. `docker ps` で `oya-inai-db-neo4j` が動いているか確認
2. `.env` ファイルがあるか確認（無ければ `.env.example` をコピーして作る）
3. `.env` の `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` が既定値のままか確認
4. `stop.bat`（Mac は起動スクリプトの再実行）で止めてから、`start.bat` / `start.command` で起動し直す

### Claude がデータベースにつながらない

**症状**: Claude Desktop に「データベースを見て」と頼んでも、「接続できません」などと言われる

**対処法**:

1. Docker Desktop と Neo4j コンテナが動いているか確認する（`docker ps` で `oya-inai-db-neo4j` があるか）
2. MCP の設定を変えた直後なら、Claude Desktop を**完全終了**してから開き直す（ウィンドウを閉じるだけでは設定が読み込まれません。手順は `docs/mcp-setup.md` の冒頭）
3. それでも直らなければ、`docs/mcp-setup.md` のトラブルシューティング（§8）を見る
4. エラーの文面をそのまま Claude に貼って「どうすればいい？」と聞くのも有効です

Web 画面（利用者台帳・緊急照会・更新期限アラート・出来事の記録・面談記録）は、Claude が未設定でも使えます。

### 入力画面のボタンが押せない

**症状**: 入力したのに、次に進むボタンが押せない

**対処法**:

入力画面は番号のついたステップ（① → ② → …）式です。まだ埋まっていない項目があると、
**「あと「◯◯」を済ませると押せます」**というヒントが表示されます。そこに書かれた項目を埋めてください。

### デモデータの投入でエラーが出る

**症状**: `load-demo-data.ps1` / `load-demo-data.sh` 実行時にエラー

**対処法**:
```bash
# Neo4j が起動しているか確認
curl -s http://localhost:7474

# 認証情報の確認（デフォルト: neo4j / password）
curl -u neo4j:password http://localhost:7474/db/neo4j/tx/commit \
  -H "Content-Type: application/json" \
  -d '{"statements": [{"statement": "RETURN 1"}]}'
```

初回起動時は Neo4j のパスワード設定に時間がかかることがあります。1〜2分待ってから再実行してください。

### Mac で「開発元を確認できない」と言われる

**症状**: スクリプト実行時にセキュリティ警告

**対処法**:
```bash
# ファイルの実行権限を確認・付与
chmod +x installer/install-mac.sh
chmod +x installer/load-demo-data.sh
chmod +x start.command
chmod +x scripts/doctor.sh
```

### Windows で「スクリプトの実行が無効」と言われる

**症状**: `.ps1` ファイルを実行すると「このシステムではスクリプトの実行が無効になっています」と表示される

**対処法**:
```powershell
# 現在のセッションのみ実行を許可（推奨）
Set-ExecutionPolicy Bypass -Scope Process -Force

# その後スクリプトを実行
.\installer\install-windows.ps1
```

> **注意**: `Set-ExecutionPolicy Bypass -Scope Process` は現在のPowerShellウィンドウのみに適用され、ウィンドウを閉じれば元に戻ります。システム全体の設定は変更しません。

### Windows で Docker のメモリが不足する

**症状**: Neo4j コンテナが起動後すぐに停止する、または「out of memory」エラー

**対処法**:
1. Docker Desktop → Settings → Resources → WSL Integration
2. メモリを 4GB 以上に設定
3. または `.wslconfig` で設定:

```
# %USERPROFILE%\.wslconfig に以下を記述
[wsl2]
memory=4GB
```

4. WSL を再起動: `wsl --shutdown` → Docker Desktop を再起動

### Windows でポートが使用中と表示される

**症状**: 起動時に「port is already allocated」エラー

**対処法**:
```powershell
# 使用中のポートを確認
netstat -ano | findstr :7474
netstat -ano | findstr :7687
netstat -ano | findstr :8001
netstat -ano | findstr :3001

# 該当プロセスを確認（PID は上記コマンドの最後の列）
tasklist | findstr <PID>
```

ポートを使用しているプロセスを終了するか、`docker-compose.yml` のポート番号を変更してください。

### メモリ使用量が多い

**症状**: パソコンの動作が遅くなった

**対処法**:
- Docker Desktop の Settings → Resources で Neo4j に割り当てるメモリを調整
- `docker-compose.yml` の `NEO4J_server_memory_heap_max__size` を `256M` に下げる
- 使わないときは `stop.bat`（または `docker compose stop`）でコンテナを停止

---

## サポート・問い合わせ

困ったことがあれば、以下の方法でサポートを受けられます:

1. **自動診断を実行**: `./scripts/doctor.sh`（Mac）で環境をまとめてチェック
2. **GitHub Issues**: バグ報告や機能要望は GitHub の Issues に投稿
3. **職場の管理担当者に相談**: 画面に出ているエラー文をそのまま伝える（スクリーンショットが便利）
