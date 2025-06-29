#!/usr/bin/env python
"""
Step 6-3 : add_literature_links.py
summary テキストに関連文献 (refs.yml) のリンクを自動付加する。

必須修正 🔴
  • 日本語キーワード対応: 文字境界ではなく単純包含判定 (kw in text)
"""

import argparse
import csv
import pathlib
import yaml

def load_refs(yaml_path: str) -> dict:
    """refs.yml → {"keyword": {"cite": "...", "url": "..."}, …}"""
    with open(yaml_path, encoding="utf8") as f:
        return yaml.safe_load(f)

def augment(text: str, refs: dict) -> str:
    """該当キーワードがあれば末尾に (Author Year: URL) を追加"""
    for kw, meta in refs.items():
        if kw in text:  # 🔴 日本語対応: 単純包含で十分
            return f'{text} ({meta["cite"]}: {meta["url"]})'
    return text

def process_csv(in_csv: str, out_csv: str, refs_yaml: str) -> None:
    refs = load_refs(refs_yaml)
    with open(in_csv, newline="", encoding="utf8") as f_in, \
         open(out_csv, "w", newline="", encoding="utf8") as f_out:
        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(f_out, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            row["summary"] = augment(row["summary"], refs)
            writer.writerow(row)
    print(f"✅  augmented CSV → {out_csv}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_csv", required=True)
    ap.add_argument("--out_csv", required=True)
    ap.add_argument("--refs", default="configs/refs.yml")
    args = ap.parse_args()
    process_csv(args.in_csv, args.out_csv, args.refs)
