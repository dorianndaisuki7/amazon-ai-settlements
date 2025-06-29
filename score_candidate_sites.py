#!/usr/bin/env python
"""
score_candidate_sites.py
候補点 GeoDataFrame に特徴量スコアを付けて保存するスクリプト
"""

import argparse, yaml, logging
import numpy as np
import geopandas as gpd
import pandas as pd              # ★ 追加：文字列→数値変換に使用
import os, sys
from pathlib import Path

# ----------------------------- ヘルパ -----------------------------
def load_config(yaml_path):
    with open(yaml_path, "r", encoding="utf8") as f:
        return yaml.safe_load(f)

# ----------------------------- スコア計算 -----------------------------
def compute_score_vec(df, cfg):
    """ベクトル化スコア計算（高速・拡張しやすい）"""
    score   = np.zeros(len(df))
    weights = np.zeros(len(df))

    # NDVI
    ndvi   = df["ndvi"].values
    valid  = ~np.isnan(ndvi)
    ndvi_score = 1 - np.abs(ndvi - cfg["ndvi"]["ideal"]) / cfg["ndvi"]["range"]
    score[valid]   += ndvi_score[valid] * cfg["ndvi"]["weight"]
    weights[valid] += cfg["ndvi"]["weight"]

    # Slope
    slope  = df["slope"].values
    valid  = ~np.isnan(slope)
    slope_score = np.clip(1 - slope / cfg["slope"]["max_deg"], 0, 1)
    score[valid]   += slope_score[valid] * cfg["slope"]["weight"]
    weights[valid] += cfg["slope"]["weight"]

    # Elevation
    elev   = df["elevation"].values
    valid  = ~np.isnan(elev)
    elev_score = 1 - np.abs(elev - cfg["elevation"]["ideal"]) / cfg["elevation"]["range"]
    score[valid]   += elev_score[valid] * cfg["elevation"]["weight"]
    weights[valid] += cfg["elevation"]["weight"]

    # Carbon
    carbon = df["carbon"].values
    valid  = ~np.isnan(carbon)
    carbon_score = np.clip(carbon / cfg["carbon"]["norm_div"], 0, 1)
    score[valid]   += carbon_score[valid] * cfg["carbon"]["weight"]
    weights[valid] += cfg["carbon"]["weight"]

    # Landcover
    lc = df["landcover"].values.astype(float)
    valid = ~np.isnan(lc)
    lc_score = np.isin(lc, cfg["landcover"]["pref_classes"]).astype(float)
    score[valid]   += lc_score[valid] * cfg["landcover"]["weight"]
    weights[valid] += cfg["landcover"]["weight"]

    # 最終スコア
    return np.divide(score, weights, out=np.zeros_like(score), where=weights > 0)

# ----------------------------- メイン -----------------------------
def main(args):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    cfg = load_config(args.config)

    logging.info("Load: %s", args.input)
    gdf = gpd.read_file(args.input)

    # ★ 数値化パッチ：文字列 → float / 失敗は NaN
    for col in ["ndvi", "slope", "elevation", "carbon", "landcover"]:
        if col in gdf.columns:
            gdf[col] = pd.to_numeric(gdf[col], errors="coerce")

    # 必須列チェック
    required = {"ndvi","slope","elevation","carbon","landcover"}
    missing  = required - set(gdf.columns)
    if missing:
        logging.error("Missing columns: %s", ", ".join(missing))
        sys.exit(1)

    # スコア計算
    logging.info("Compute scores …")
    gdf["site_score"] = compute_score_vec(gdf, cfg)

    # NaN→0 に置換（保存安定化）
    gdf.fillna(0, inplace=True)

    logging.info("Score mean=%.3f  std=%.3f", gdf["site_score"].mean(), gdf["site_score"].std())

    # 出力
    ext    = os.path.splitext(args.output)[1].lower()
    driver = "GPKG" if ext == ".gpkg" else "GeoJSON"
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    logging.info("Save: %s (%s)", args.output, driver)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  required=True, dest="input")
    ap.add_argument("--out", required=True, dest="output")
    ap.add_argument("--config", default="configs/weights.yml")

    args = ap.parse_args()
    main(args)
