#!/usr/bin/env python
"""
top_sites.geojson に連番の site_id を付与して保存するスクリプト
"""

import geopandas as gpd
import os

in_path = "data/candidates/top_sites.geojson"
out_path = "data/candidates/top_sites_with_id.geojson"

# GeoJSON を読み込み
gdf = gpd.read_file(in_path)

# site_id を site_000 形式で付与（文字列で桁合わせ）
gdf = gdf.reset_index(drop=True)
gdf["site_id"] = gdf.index.map(lambda i: f"site_{i:03d}")

# 保存（GeoJSON形式）
os.makedirs(os.path.dirname(out_path), exist_ok=True)
gdf.to_file(out_path, driver="GeoJSON")

print(f"✅ site_id を付与しました → {out_path}")