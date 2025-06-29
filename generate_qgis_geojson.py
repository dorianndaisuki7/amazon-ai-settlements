#!/usr/bin/env python
"""
Step 6-1 : generate_qgis_geojson.py
Point GeoJSON と summary CSV を結合し、QGIS/Web 用に属性を追加する。

必須追加 🔴
  • geometry 欠損行を dropna(subset=["geometry"]) で除外
  • summary_short 列（全角/半角混在でも 80 文字でカット）を付与

使い方:
  python generate_qgis_geojson.py \
      --geo data/candidates/top_sites.geojson \
      --summary outputs/summary_all_versions.csv \
      --out outputs/summary_map.geojson
"""

import argparse
import geopandas as gpd
import pandas as pd

# --- 設定 ---
THRESH = 0.8  # 高評価とみなすスコア閾値

def main(geo_path: str, csv_path: str, out_path: str) -> None:
    # 🔴 geometry 欠損除去
    gdf = gpd.read_file(geo_path).dropna(subset=["geometry"])

    df = pd.read_csv(csv_path)

    merged = gdf.merge(df, on="site_id", how="left")

    # *_score → *_high フラグ
    score_cols = [c for c in df.columns if c.endswith("_score")]
    for col in score_cols:
        flag = col.replace("_score", "_high")
        merged[flag] = merged[col] >= THRESH

    # 🔴 summary_short (80 文字超は省略)
    merged["summary_short"] = merged["summary"].str.slice(0, 80) + "…"

    merged.to_file(out_path, driver="GeoJSON")
    print(f"✅  saved → {out_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--geo", required=True, help="Input GeoJSON with site_id")
    ap.add_argument("--summary", required=True, help="CSV with *_score, summary")
    ap.add_argument("--out", required=True, help="Output GeoJSON path")
    args = ap.parse_args()
    main(args.geo, args.summary, args.out)
