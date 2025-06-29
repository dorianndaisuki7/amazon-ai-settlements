#!/usr/bin/env python
"""
Step 3: generate_hypotheses.py
Amazon Archaeology Challenge － クラスタリング + GPT 多視点評価

ワークフロー
1. 上位 quantile の候補点を抽出
2. EPSG:5880 へ投影し、eps を自動または指定で決定
3. DBSCAN → noise 除外
4. convex_hull + buffer でクラスタ面ポリゴン化、統計算出
5. GeoJSON 保存
6. GPT を非同期で呼び出し（Explorer / Skeptic / Engineer）
7. ナレーター要約を追加し Markdown レポート生成
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import numpy as np
import openai
import tiktoken
import yaml
from sklearn.cluster import DBSCAN
from tenacity import retry, stop_after_attempt, wait_random_exponential
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils import cluster as clu  # project_gdf(), suggest_eps()

# --------------------------------------------------------------------------- #
# 設定読み込み
# --------------------------------------------------------------------------- #


def load_cluster_cfg(path: str = "configs/cluster.yml") -> Dict:
    """YAML を読み込んで dict で返す"""
    with open(path, "r", encoding="utf8") as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------------------- #
# GPT 呼び出し
# --------------------------------------------------------------------------- #


@retry(
    wait=wait_random_exponential(min=1, max=20),
    stop=stop_after_attempt(5),
    reraise=True,
)
async def call_gpt_async(
    client: "openai.AsyncClient",
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    """Rate-limit／サーバエラー時に自動リトライする GPT 呼び出し"""
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message.content


# --------------------------------------------------------------------------- #
# メイン処理
# --------------------------------------------------------------------------- #


async def main(
    in_file: str,
    cfg_path: str,
    out_geojson: str,
    out_md: str,
) -> None:
    # 0. 設定 & 入力読み込み -------------------------------------------------- #
    cfg = load_cluster_cfg(cfg_path)
    gdf = gpd.read_file(in_file)

    # 1. 上位 quantile 抽出 ---------------------------------------------------- #
    top = gdf[gdf["site_score"] >= gdf["site_score"].quantile(cfg["top_quantile"])].copy()
    if top.empty:
        raise RuntimeError("Top-quantile 抽出の結果が 0 行でした。site_score を確認してください。")

    # 2. 投影 & eps 判定 ------------------------------------------------------ #
    gdf_proj = clu.project_gdf(top, epsg=cfg["proj_epsg"])
    eps_km: float = (
        clu.suggest_eps(gdf_proj) if cfg["eps_km"] == "auto" else float(cfg["eps_km"])
    )
    eps_m = eps_km * 1000.0

    # 3. DBSCAN --------------------------------------------------------------- #
    coords = np.column_stack([gdf_proj.geometry.x, gdf_proj.geometry.y])
    db = DBSCAN(eps=eps_m, min_samples=cfg["min_samples"])
    gdf_proj["cluster"] = db.fit_predict(coords)
    gdf_proj = gdf_proj[gdf_proj["cluster"] != -1]  # noise 除外
    if gdf_proj.empty:
        raise RuntimeError("DBSCAN 後にクラスタが 1 つも残りませんでした。eps か min_samples を調整してください。")

    # 4. クラスタ面ポリゴン + 統計 ------------------------------------------ #
    records: List[Dict] = []
    for cid, sub in gdf_proj.groupby("cluster"):
        hull = sub.unary_union.convex_hull.buffer(cfg["buffer_m"])
        q25, q75 = sub["site_score"].quantile([0.25, 0.75])
        records.append(
            {
                "cluster": int(cid),
                "geometry": hull,
                "mean": sub["site_score"].mean(),
                "q25": q25,
                "q75": q75,
                "iqr": q75 - q25,
                "min": sub["site_score"].min(),
                "max": sub["site_score"].max(),
                "n_pts": len(sub),
            }
        )

    clusters = gpd.GeoDataFrame(records, geometry="geometry", crs=f"EPSG:{cfg['proj_epsg']}")
    clusters_latlon = clusters.to_crs(epsg=4326)
    Path(out_geojson).parent.mkdir(parents=True, exist_ok=True)
    clusters_latlon.to_file(out_geojson, driver="GeoJSON")

    # 5. GPT 非同期呼び出し --------------------------------------------------- #
    tmpl = json.load(open("configs/prompt_templates_generation.json", encoding="utf8"))
    char_prompts = tmpl["characters"]
    narrator_tmpl = tmpl["narrator"]["prompt"]
    lang_setting = tmpl.get("lang", "en")

    if not (api_key := os.getenv("OPENAI_API_KEY")):
        raise EnvironmentError("環境変数 OPENAI_API_KEY が設定されていません。")

    openai.api_key = api_key

    async with openai.AsyncClient() as client:
        # --- 5-A. キャラ応答 -------------------------------------------------- #
        tasks = []
        for _, row in clusters.iterrows():
            cid = row["cluster"]
            context = (
                f"Amazônia cluster {cid}, {row['n_pts']} pts, "
                f"area ≈ {row.geometry.area/1e6:.1f} km²"
            )
            stats_s = (
                f"mean {row['mean']:.3f}, "
                f"Q25 {row['q25']:.3f}, Q75 {row['q75']:.3f}, "
                f"IQR {row['iqr']:.3f}"
            )
            for char, prop in char_prompts.items():
                system_prompt = prop["prompt"]
                user_prompt = f"{context}\nStats: {stats_s}"
                t = asyncio.create_task(
                    call_gpt_async(client, system_prompt, user_prompt, temperature=0.7)
                )
                t.meta = (cid, char)  # メタデータ添付
                tasks.append(t)

        responses = await asyncio.gather(*tasks)

        cluster_results: Dict[int, Dict[str, str]] = {}
        for t, res in zip(tasks, responses):
            cid, char = t.meta
            cluster_results.setdefault(cid, {})[char] = res

        # --- 5-B. ナレーター要約 -------------------------------------------- #
        narrator_results: Dict[int, str] = {}
        for cid, char_dict in cluster_results.items():
            joined = "\n\n---\n\n".join(char_dict.values())
            narrator_results[cid] = await call_gpt_async(
                client,
                narrator_tmpl.format(lang=lang_setting),
                joined,
                temperature=0.5,
            )

    # 6. Markdown 書き出し ---------------------------------------------------- #
    Path(out_md).parent.mkdir(parents=True, exist_ok=True)
    with open(out_md, "w", encoding="utf8") as f:
        f.write("# Hypotheses – Amazon Archaeology Challenge\n\n")
        for cid in sorted(cluster_results.keys()):
            f.write(f"## Cluster {cid}\n\n")
            for char, text in cluster_results[cid].items():
                f.write(f"### {char}\n\n{text}\n\n")
            f.write("### Narrator Summary\n\n")
            f.write(f"{narrator_results[cid]}\n\n")

    # 完了ログ
    print("✅ Step 3 完了")
    print(f"  • GeoJSON:  {out_geojson}")
    print(f"  • Markdown: {out_md}")


# --------------------------------------------------------------------------- #
#  エントリポイント
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Step 3 – generate hypotheses")
    parser.add_argument(
        "--input",
        default="data/candidates/candidates_scored.geojson",
        help="入力 GeoJSON ファイル（site_score 列必須）",
    )
    parser.add_argument(
        "--cfg",
        default="configs/cluster.yml",
        help="クラスタリング & GPT 設定 YAML",
    )
    parser.add_argument(
        "--out_geojson",
        default="data/candidates/top_sites.geojson",
        help="出力 GeoJSON（クラスタ面ポリゴン）",
    )
    parser.add_argument(
        "--out_md",
        default="report/hypotheses.md",
        help="出力 Markdown（仮説レポート）",
    )
    args = parser.parse_args()

    asyncio.run(
        main(
            args.input,
            args.cfg,
            args.out_geojson,
            args.out_md,
        )
    )
