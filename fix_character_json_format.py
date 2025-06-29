#!/usr/bin/env python
# coding: utf-8

"""
各JSON内の "characters" セクションにおいて、値が文字列だった場合に
{"comment": <文字列>} の形式へ修正するスクリプト。
例：
  "explorer": "この地点は〜〜" →
  "explorer": {"comment": "この地点は〜〜"}
"""

import os
import json
import argparse
from tqdm import tqdm

def fix_character_comments(input_dir):
    fixed = 0
    files = [f for f in os.listdir(input_dir) if f.endswith(".json")]

    for filename in tqdm(files, desc="修正中"):
        path = os.path.join(input_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        changed = False
        if "characters" in data:
            for key, val in data["characters"].items():
                if isinstance(val, str):
                    data["characters"][key] = {"comment": val}
                    changed = True

        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            fixed += 1

    print(f"✅ 修正完了：{fixed} 件（{len(files)}件中）")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True, help="JSONフォルダへのパス")
    args = parser.parse_args()

    fix_character_comments(args.input_dir)
