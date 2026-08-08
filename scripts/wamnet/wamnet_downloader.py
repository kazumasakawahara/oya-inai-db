#!/usr/bin/env python3
"""
WAM NET 障害福祉サービス事業所データ 一括ダウンロード＆抽出スクリプト

機能:
1. 全27種類のサービスデータを一括ダウンロード
2. 福岡県（北九州市近郊）のデータを抽出
3. 全サービスを1つのCSVに統合
4. Neo4jインポート用のデータを生成
"""

import os
import zipfile
import requests
import pandas as pd
from pathlib import Path
from io import BytesIO
import time

# ============================================================
# 設定
# ============================================================

# データ公開時点（最新: 202509）
DATA_PERIOD = "202509"

# 出力先ディレクトリ
OUTPUT_DIR = Path("./wamnet_data")

# サービス種類とコードの対応表
SERVICE_CODES = {
    # 訪問系サービス
    "11": "居宅介護",
    "12": "重度訪問介護",
    "13": "行動援護",
    "14": "重度障害者等包括支援",
    "15": "同行援護",
    # 日中活動系サービス
    "21": "療養介護",
    "22": "生活介護",
    "24": "短期入所",
    # 施設系サービス
    "32": "施設入所支援",
    # 居住系サービス
    "33": "共同生活援助",
    "34": "宿泊型自立訓練",
    "61": "自立生活援助",
    # 訓練系・就労系サービス
    "41": "自立訓練_機能訓練",
    "42": "自立訓練_生活訓練",
    "45": "就労継続支援A型",
    "46": "就労継続支援B型",
    "60": "就労移行支援",
    "62": "就労定着支援",
    # 障害児通所系サービス
    "63": "児童発達支援",
    "64": "医療型児童発達支援",
    "65": "放課後等デイサービス",
    "66": "居宅訪問型児童発達支援",
    "67": "保育所等訪問支援",
    # 障害児入所系サービス
    "68": "福祉型障害児入所施設",
    "69": "医療型障害児入所施設",
    # 相談系サービス
    "52": "計画相談支援",
    "53": "地域相談支援_地域移行",
    "54": "地域相談支援_地域定着",
    "70": "障害児相談支援",
}

# 北九州市近郊の市区町村コード（福岡県）
# 参考: https://www.soumu.go.jp/denshijiti/code.html
KITAKYUSHU_AREA_CODES = [
    "40100",  # 北九州市
    "40101",  # 北九州市門司区
    "40103",  # 北九州市若松区
    "40105",  # 北九州市戸畑区
    "40106",  # 北九州市小倉北区
    "40107",  # 北九州市小倉南区
    "40108",  # 北九州市八幡東区
    "40109",  # 北九州市八幡西区
    "40202",  # 直方市
    "40203",  # 飯塚市
    "40204",  # 田川市
    "40205",  # 柳川市
    "40206",  # 八女市
    "40207",  # 筑後市
    "40210",  # 行橋市
    "40211",  # 豊前市
    "40212",  # 中間市
    "40213",  # 小郡市
    "40220",  # 宮若市
    "40221",  # 嘉麻市
    "40231",  # 朝倉市
    "40341",  # 遠賀郡芦屋町
    "40342",  # 遠賀郡水巻町
    "40343",  # 遠賀郡岡垣町
    "40344",  # 遠賀郡遠賀町
    "40381",  # 鞍手郡小竹町
    "40382",  # 鞍手郡鞍手町
    "40401",  # 嘉穂郡桂川町
    "40421",  # 田川郡香春町
    "40422",  # 田川郡添田町
    "40423",  # 田川郡糸田町
    "40424",  # 田川郡川崎町
    "40425",  # 田川郡大任町
    "40426",  # 田川郡赤村
    "40427",  # 田川郡福智町
    "40601",  # 京都郡苅田町
    "40602",  # 京都郡みやこ町
    "40604",  # 築上郡吉富町
    "40605",  # 築上郡上毛町
    "40606",  # 築上郡築上町
]

# 福岡県全体（必要に応じて使用）
FUKUOKA_PREF_CODE = "40"


# ============================================================
# メイン処理
# ============================================================

def generate_url(period: str, service_code: str) -> str:
    """ダウンロードURLを生成"""
    base_url = "https://www.wam.go.jp/content/files/pcpub/top/sfkopendata"
    return f"{base_url}/{period}/sfkopendata_{period}_{service_code}.zip"


def download_and_extract_csv(url: str) -> pd.DataFrame | None:
    """ZIPファイルをダウンロードしてCSVを抽出"""
    try:
        print(f"  ダウンロード中: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # ZIPを展開
        with zipfile.ZipFile(BytesIO(response.content)) as zf:
            # ZIP内のCSVファイルを探す
            csv_files = [f for f in zf.namelist() if f.endswith('.csv')]
            if not csv_files:
                print(f"  ⚠️ CSVファイルが見つかりません")
                return None
            
            # 最初のCSVを読み込む
            with zf.open(csv_files[0]) as csv_file:
                df = pd.read_csv(csv_file, encoding='utf-8', dtype=str)
                print(f"  ✓ {len(df)}件のデータを取得")
                return df
                
    except requests.exceptions.RequestException as e:
        print(f"  ⚠️ ダウンロードエラー: {e}")
        return None
    except Exception as e:
        print(f"  ⚠️ 処理エラー: {e}")
        return None


def filter_kitakyushu_area(df: pd.DataFrame) -> pd.DataFrame:
    """北九州市近郊のデータを抽出"""
    # 市区町村コードの列名を探す（データによって異なる可能性）
    code_columns = [col for col in df.columns if 'コード' in col or 'code' in col.lower()]
    
    if not code_columns:
        # 最初の列が市区町村コードの場合が多い
        code_col = df.columns[0]
    else:
        code_col = code_columns[0]
    
    # 北九州市近郊のデータを抽出
    # コードの先頭5桁で比較（市区町村コードは5桁）
    df['_temp_code'] = df[code_col].astype(str).str[:5]
    filtered = df[df['_temp_code'].isin(KITAKYUSHU_AREA_CODES)]
    filtered = filtered.drop(columns=['_temp_code'])
    
    return filtered


def filter_fukuoka_pref(df: pd.DataFrame) -> pd.DataFrame:
    """福岡県全体のデータを抽出"""
    code_columns = [col for col in df.columns if 'コード' in col or 'code' in col.lower()]
    
    if not code_columns:
        code_col = df.columns[0]
    else:
        code_col = code_columns[0]
    
    # 福岡県のデータを抽出（コードが40で始まる）
    df['_temp_code'] = df[code_col].astype(str).str[:2]
    filtered = df[df['_temp_code'] == FUKUOKA_PREF_CODE]
    filtered = filtered.drop(columns=['_temp_code'])
    
    return filtered


def main():
    """メイン処理"""
    print("=" * 60)
    print("WAM NET 障害福祉サービス事業所データ 一括ダウンロード")
    print("=" * 60)
    print(f"\nデータ公開時点: {DATA_PERIOD}")
    print(f"対象サービス数: {len(SERVICE_CODES)}種類")
    print(f"対象地域: 北九州市近郊（{len(KITAKYUSHU_AREA_CODES)}市区町村）")
    print()
    
    # 出力ディレクトリ作成
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = OUTPUT_DIR / "raw"
    raw_dir.mkdir(exist_ok=True)
    
    # 全サービスのデータを収集
    all_data = []
    
    for code, service_name in SERVICE_CODES.items():
        print(f"\n[{code}] {service_name}")
        
        url = generate_url(DATA_PERIOD, code)
        df = download_and_extract_csv(url)
        
        if df is not None and len(df) > 0:
            # サービス種類列を追加
            df['サービス種類コード'] = code
            df['サービス種類'] = service_name
            
            # 福岡県のデータを抽出
            df_fukuoka = filter_fukuoka_pref(df)
            print(f"  → 福岡県: {len(df_fukuoka)}件")
            
            # 北九州市近郊のデータを抽出
            df_kitakyushu = filter_kitakyushu_area(df)
            print(f"  → 北九州市近郊: {len(df_kitakyushu)}件")
            
            if len(df_kitakyushu) > 0:
                all_data.append(df_kitakyushu)
                
                # 個別CSVも保存
                output_file = raw_dir / f"{code}_{service_name}.csv"
                df_kitakyushu.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        # サーバー負荷軽減のため少し待機
        time.sleep(0.5)
    
    # 全データを統合
    if all_data:
        print("\n" + "=" * 60)
        print("統合処理")
        print("=" * 60)
        
        combined_df = pd.concat(all_data, ignore_index=True)
        print(f"\n統合データ: {len(combined_df)}件")
        
        # 統合CSVを保存
        combined_file = OUTPUT_DIR / f"kitakyushu_services_{DATA_PERIOD}.csv"
        combined_df.to_csv(combined_file, index=False, encoding='utf-8-sig')
        print(f"✓ 保存完了: {combined_file}")
        
        # サマリー表示
        print("\n【サービス種類別集計】")
        summary = combined_df.groupby('サービス種類').size().sort_values(ascending=False)
        for service, count in summary.items():
            print(f"  {service}: {count}件")
        
        # Neo4jインポート用データも生成
        neo4j_file = OUTPUT_DIR / f"neo4j_import_{DATA_PERIOD}.csv"
        # 必要な列だけ抽出（列名はデータによって異なる可能性があるため、後で調整）
        combined_df.to_csv(neo4j_file, index=False, encoding='utf-8-sig')
        print(f"✓ Neo4jインポート用: {neo4j_file}")
        
    else:
        print("\n⚠️ データが取得できませんでした")
    
    print("\n" + "=" * 60)
    print("完了")
    print("=" * 60)


if __name__ == "__main__":
    main()
