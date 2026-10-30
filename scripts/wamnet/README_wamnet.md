# WAM NET 障害福祉サービス事業所データ ダウンローダー

## 概要

このスクリプトは、WAM NETから障害福祉サービス事業所のオープンデータを
一括ダウンロードし、北九州市近郊のデータを抽出します。

## 機能

1. **27種類のサービスデータを自動ダウンロード**
2. **北九州市近郊のデータを、事業所の所在地（事業所住所（市区町村））で抽出**
3. **全サービスを1つのCSVに統合**
4. **Neo4jインポート用データを生成**

## 対象地域

- 北九州市（7区）
- 行橋市、中間市
- 遠賀郡（芦屋町・水巻町・岡垣町・遠賀町）
- 京都郡（苅田町・みやこ町）

（2026-10-30 決定。先頭列の「都道府県コード又は市区町村コード」は事業所を指定した自治体のコードで
所在地ではないため、絞り込みには使わない。）

## 実行方法

### 1. 必要なライブラリをインストール

```bash
cd ~/AI-Workspace
uv init wamnet-project  # 新規プロジェクト作成（オプション）
cd wamnet-project
uv add requests pandas
```

または既存の環境で：

```bash
uv pip install requests pandas
```

### 2. スクリプトを配置

ダウンロードした `wamnet_downloader.py` を作業フォルダに配置します。

```bash
mv ~/Downloads/wamnet_downloader.py ~/AI-Workspace/
cd ~/AI-Workspace
```

### 3. 実行

```bash
uv run python wamnet_downloader.py
```

### 4. 出力結果

実行後、`wamnet_data/` フォルダに以下が生成されます：

```
wamnet_data/
├── kitakyushu_services_202509.csv  # 北九州市近郊の全サービス統合データ
├── neo4j_import_202509.csv          # Neo4jインポート用
└── raw/                              # サービス種類別の個別CSV
    ├── 11_居宅介護.csv
    ├── 22_生活介護.csv
    ├── 46_就労継続支援B型.csv
    └── ...
```

## 出力データの内容

統合CSVには以下の情報が含まれます：

- 事業所番号
- 事業所名
- 法人名
- 住所
- 電話番号
- サービス種類
- 定員
- 営業時間
- など（WAM NETの公開項目に準拠）

## Neo4jへのインポート

生成された `neo4j_import_202509.csv` を使って、Neo4jにインポートできます。
詳細なインポートスクリプトは、データの列構造を確認後に作成します。

## カスタマイズ

### 対象地域の変更

`wamnet_downloader.py` 内の `KITAKYUSHU_AREAS`（コード→市区町村名）を編集して、
対象の市区町村を追加・削除できます。コードは総務省「都道府県コード及び市区町村コード」の上5桁です。
追加した市区町村の行を `soumu_area_codes_reference.json` にも足し、`test_area_codes.py` を通してください
（`uv run --with pytest pytest test_area_codes.py`）。

### データ公開時点の変更

WAM NET は3月末・9月末時点のデータを半年ごとに公開します。既定（`--period auto`）では、
公開済みの最新の公開時点を探して取得します。過去のデータは `--period` で指定します：

```bash
uv run --with pandas --with requests python wamnet_downloader.py                 # 最新を自動で
uv run --with pandas --with requests python wamnet_downloader.py --period 202503 # 2025年3月末
uv run --with pandas --with requests python wamnet_downloader.py --check         # 新しい公開があるかだけ確かめる
```

`--check` の終了コード: 0 = 最新を取得済み、10 = 新しい公開時点がある、1 = WAM NET に接続できない。
出力は実行したフォルダの `wamnet_data/` に、公開時点つきのファイル名で書き出します。

## 注意事項

- サーバー負荷軽減のため、各ダウンロード間に0.5秒の待機時間を設けています
- 全データのダウンロードには数分かかります
- データは定期的に更新されるため、最新データが必要な場合は再実行してください

## トラブルシューティング

### エラー: `requests` が見つからない

```bash
uv add requests
```

### エラー: `pandas` が見つからない

```bash
uv add pandas
```

### 文字化けする場合

CSVファイルはUTF-8（BOM付き）で保存されています。
Excelで開く場合は正しく表示されるはずです。
