#!/usr/bin/env python
"""
Step 5: generate_character_dialogue.py  (v3 ‑ final)
──────────────────────────────────────────
• top_sites.geojson の各地点を 5 キャラ＋summary で評価
• prompt_templates_dialogue.json でプロンプトを外部管理
• 非同期 + リトライで高速＆堅牢に GPT を呼び出し
• 出力: outputs/character_dialogues/<site_id>.json
    └ site_metadata / characters / summary の 3 層構造
• CLI: --max_tokens / --temperature 調整可
• .env 自動読み込み（GPT用.env）
• Polygonでも centroid で安全に座標取得
• エラーは retry_failed.json に自動集約
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import geopandas as gpd
import openai
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_random_exponential

# ---------------------------------------------------------------------------
# .env 読み込み
# ---------------------------------------------------------------------------
# スクリプト → scripts/、.env → プロジェクトルート想定
ENV_PATH = Path(__file__).resolve().parent.parent / "GPT用.env"
load_dotenv(dotenv_path=ENV_PATH)

# ---------------------------------------------------------------------------
# GPT 呼び出しユーティリティ
# ---------------------------------------------------------------------------

@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(5), reraise=True)
async def call_chat_async(
    client: "openai.AsyncClient",
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """OpenAI Chat API をリトライ付きで非同期呼び出し"""
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

# ---------------------------------------------------------------------------
# 1 キャラ評価タスク
# ---------------------------------------------------------------------------

async def evaluate_character(
    client: "openai.AsyncClient",
    char_name: str,
    char_cfg: Dict[str, Any],
    info: Dict[str, Any],
    max_tokens: int,
    base_temperature: float,
) -> Tuple[str, str]:
    """1 キャラの評価を取得して (char, text) を返す"""

    temp_map = {
        "explorer": base_temperature + 0.2,
        "engineer": base_temperature,
        "skeptic": max(0.1, base_temperature - 0.3),
        "historian": base_temperature,
        "ecologist": base_temperature,
    }
    temperature = temp_map.get(char_name.lower(), base_temperature)

    system_prompt = f"{char_cfg['role']}\n{char_cfg.get('style', '')}"
    user_prompt = (
        f"{char_cfg['instruction']}\n\n"
        f"{char_cfg['input_template'].format(**info)}"
    )

    try:
        text = await call_chat_async(
            client, system_prompt, user_prompt, max_tokens, temperature
        )
    except Exception as e:
        text = f"[Error] {type(e).__name__}: {e}"
    return char_name, text

# ---------------------------------------------------------------------------
# 1 地点評価タスク
# ---------------------------------------------------------------------------

async def evaluate_site(
    client: "openai.AsyncClient",
    site_id: str,
    row: "gpd.GeoSeries",
    prompt_cfg: Dict[str, Any],
    max_tokens: int,
    temperature: float,
) -> Dict[str, Any]:
    """複数キャラ + summary で地点を評価し JSON レコードを返す"""

    # Polygon / MultiPolygon でも安全に座標取得
    point = row.geometry.centroid

    info: Dict[str, Any] = {
        "coordinates": f"{point.x:.5f}, {point.y:.5f}",
        "landform": row.get("landform", "未分類"),
        "ndvi": row.get("ndvi", "NaN"),
        "slope_deg": row.get("slope", "NaN"),
        "elevation_m": row.get("elevation", "NaN"),
        "river_distance_km": row.get("river_dist", "NaN"),
        "landcover_class": row.get("landcover", "NaN"),
        "hypothesis_summary": row.get("hypothesis", "仮説未入力"),
        "region_name": row.get("region", "Amazonia"),
    }

    # キャラ並列呼び出し
    char_tasks = [
        evaluate_character(client, char, cfg, info, max_tokens, temperature)
        for char, cfg in prompt_cfg.items() if char != "summary"
    ]
    char_results = await asyncio.gather(*char_tasks)
    characters: Dict[str, str] = {k: v for k, v in char_results}

    # summary 生成
    if "summary" in prompt_cfg:
        sum_cfg = prompt_cfg["summary"]
        system_prompt = f"{sum_cfg['role']}\n{sum_cfg.get('style', '')}"
        summary_input = sum_cfg["input_template"].format(
            explorer_opinion=characters.get("explorer", ""),
            engineer_opinion=characters.get("engineer", ""),
            skeptic_opinion=characters.get("skeptic", ""),
            historian_opinion=characters.get("historian", ""),
            ecologist_opinion=characters.get("ecologist", ""),
        )
        summary_text = await call_chat_async(
            client, system_prompt, summary_input, max_tokens, temperature
        )
    else:
        summary_text = ""

    return {
        "site_metadata": {"site_id": site_id, **info},
        "characters": characters,
        "summary": summary_text,
    }

# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

async def main(
    top_sites_path: str,
    prompt_file: str,
    output_dir: str,
    max_tokens: int,
    temperature: float,
):
    gdf = gpd.read_file(top_sites_path)
    prompt_cfg = json.load(open(prompt_file, encoding="utf-8"))

    if not (api_key := os.getenv("OPENAI_API_KEY")):
        raise EnvironmentError("OPENAI_API_KEY が設定されていません")
    openai.api_key = api_key

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    failed: List[Tuple[str, str]] = []

    async with openai.AsyncClient() as client:
        tasks = [
            evaluate_site(
                client, f"site_{idx:03d}", row, prompt_cfg, max_tokens, temperature
            )
            for idx, row in gdf.iterrows()
        ]

        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
            except Exception as e:
                failed.append(("unknown", str(e)))
                continue
            site_id = result["site_metadata"]["site_id"]
            out_path = Path(output_dir) / f"{site_id}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"✅ {site_id} saved → {out_path}")

    if failed:
        with open(Path(output_dir) / "retry_failed.json", "w", encoding="utf-8") as f:
            json.dump(failed, f, ensure_ascii=False, indent=2)
        print(f"⚠ {len(failed)} task(s) failed. retry_failed.json を出力しました。")
    else:
        print("🎉 All tasks completed without errors.")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Step 5 – generate character dialogues")
    parser.add_argument("--top_sites", default="data/candidates/top_sites.geojson")
    parser.add_argument("--prompt_file", default="configs/prompt_templates_dialogue.json")
    parser.add_argument("--output_dir", default="outputs/character_dialogues/")
    parser.add_argument("--max_tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.7)
    args = parser.parse_args()

# 🟢 ここを追加
    asyncio.run(
        main(
            top_sites_path=args.top_sites,
            prompt_file=args.prompt_file,
            output_dir=args.output_dir,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
    )