# FAQ & トラブルシューティング

---

## よくある質問

### Q: データはどこに保存されますか？

データはすべて**お使いのパソコン内**に保存されます。具体的には `oya-inai-db/neo4j_data/` フォルダ内の Docker ボリュームに格納されます。クラウドには送信されません。

ただし、**AI機能（ナラティブAI抽出・AIチャット・意味検索）で Gemini API や Claude API を選んだ場合**は、入力内容が各社のサーバーに送信されます。個人情報を含むデータを扱う場合は、Ollama（完全ローカル）を選ぶか、組織の個人情報保護規程と照らし合わせて運用してください。（音声の文字起こしは 2026-08-12 に廃止しました）

### Q: 利用料金はいくらですか？

**ソフトウェア本体は無償です。** 中核機能（利用者台帳・緊急照会・更新期限アラート・訪問前ブリーフィング）は、AI（LLM）をまったく設定しなくても動きます。この状態なら費用は一切かかりません。

「ソフト無償・知能は持ち込み」という考え方で、AIを使うかどうか・どのAIを使うかは利用する組織が選びます。

### Q: AI機能を使うには、どれを選べばよいですか？

3つから選べます。

| 選択肢 | 費用 | 個人情報の扱い |
|--------|------|----------------|
| **① Ollama** | ¥0（完全ローカル） | データがパソコンの外に出ない。**個人情報を扱う運用に最も安全** |
| **② Gemini API** | Flash系とEmbeddingは無料枠あり | ⚠️ 下記の注意を参照 |
| **③ Claude API** | 有料 | 外部サービスに送信される |

> ⚠️ **Gemini 無料枠についての注意（2026年8月時点で確認）**
> 無料枠では、**入力したデータが Google のプロダクト改善に利用されます**。
> クライアントの個人情報を扱う運用では、**Ollama か Gemini の有料枠を推奨します。**
> なお Pro モデルは 2026年4月以降、無料枠の対象外です。

設定は `.env` ファイルと、画面の**「LLM設定」ページ**（サイドバー）で行います。

### Q: AIを設定しないと、何ができなくなりますか？

AI機能だけが使えなくなります。**エラーにはなりません。**

| AIなしで動く（中核機能） | AI設定時のみ使える |
|--------------------------|--------------------|
| 利用者台帳（クライアント一覧・詳細） | ナラティブAI抽出 |
| 緊急照会（禁忌事項・連絡先） | AIチャット |
| 更新期限アラート | 記録を探す（意味検索） |
| 訪問前ブリーフィング | — |

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

セットアップ後は、**AI機能を使わなければオフラインで動作します。** Gemini API / Claude API を使う場合のみ、その機能を使うときにインターネット接続が必要です。Ollama を選んだ場合はオフラインのままでもAI機能が使えます。

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

### AI機能が使えない・ボタンが反応しない

**症状**: ナラティブAI抽出、AIチャット、「記録を探す」が使えない

**対処法**:

これは故障ではなく、**LLMが未設定**の可能性が高いです。

1. サイドバーの**「LLM設定」**ページを開いて、設定状況を確認する
2. `.env` の `GEMINI_API_KEY` が設定されているか確認する
3. どのAIを使うか決めていない場合は、[よくある質問](#q-ai機能を使うにはどれを選べばよいですか)を参照

中核機能（利用者台帳・緊急照会・更新期限アラート・訪問前ブリーフィング）は、AIが未設定でも使えます。

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
