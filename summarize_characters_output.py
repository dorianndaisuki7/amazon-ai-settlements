#!/usr/bin/env python
"""
Summarize Character Dialogues – v1.1
───────────────────────────────────
各バージョン(v01〜v05 …)の `site_XXX.json` を走査し、
1. Markdown まとめレポート (バージョン毎 or フラット)
2. CSV 一覧表
を同時に生成するユーティリティ。

JSON 構造は以下を想定：
{
  "site_metadata": {"site_id": "site_000", ...},
  "characters": {"explorer": "...", "engineer": "...", ...},
  "summary": "..."
}
"""
from __future__ import annotations
import argparse, json, csv
from pathlib import Path
from collections import defaultdict

# ───────────────────────────────────────────────────────
# ヘルパ
# ───────────────────────────────────────────────────────

def read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def detect_version(file_path: Path, input_dir: Path) -> str:
    rel_parts = file_path.relative_to(input_dir).parts
    version = rel_parts[0] if len(rel_parts) > 1 and rel_parts[0].startswith("v") else "v05"
    return version


def truncate(text: str, length: int = 120) -> str:
    return text if len(text) <= length else text[: length - 3] + "…"

# ───────────────────────────────────────────────────────
# メイン
# ───────────────────────────────────────────────────────

def main(args: argparse.Namespace) -> None:
    input_dir = Path(args.input_dir)
    md_lines: list[str] = ["# Character Dialogue Summary\n"]
    csv_rows: list[dict] = []

    # JSON探索
    files = list(input_dir.rglob("site_*.json"))
    if not files:
        raise FileNotFoundError(f"No site_*.json found under {input_dir}")

    # バージョンでグループ化
    version_groups: dict[str, list[Path]] = defaultdict(list)
    for fp in files:
        ver = detect_version(fp, input_dir) if args.group_by_version else "all"
        version_groups[ver].append(fp)

    for ver in sorted(version_groups):
        if args.group_by_version:
            md_lines.append(f"\n## {ver}\n")
        for fp in sorted(version_groups[ver]):
            data = read_json(fp)
            meta = data.get("site_metadata", {})
            chars = data.get("characters", {})
            summary = data.get("summary", "")
            site_id = meta.get("site_id", fp.stem)

            # Markdown
            md_lines.append(f"### {site_id}\n")
            md_lines.append(f"**Summary**: {summary.strip()}\n")
            for char in ["explorer", "engineer", "skeptic", "historian", "ecologist"]:
                if char in chars:
                    md_lines.append(f"- **{char.capitalize()}**: {truncate(chars[char].strip(), args.max_len)}")
            md_lines.append("")  # blank line

            # CSV row
            row = {
                "version": ver if args.group_by_version else "all",
                "site_id": site_id,
                "summary": summary.replace("\n", " ").strip(),
            }
            for char in ["explorer", "engineer", "skeptic", "historian", "ecologist"]:
                row[char] = truncate(chars.get(char, ""), args.max_len).replace("\n", " ")
            csv_rows.append(row)

    # 書き出し
    Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"✅ Markdown saved → {args.output_md}")

    Path(args.output_csv).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["version", "site_id", "summary", "explorer", "engineer", "skeptic", "historian", "ecologist"]
    with open(args.output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"✅ CSV saved → {args.output_csv}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Summarize character dialogue JSON outputs")
    p.add_argument("--input_dir", default="outputs/character_dialogues", help="site_*.json を含むルートディレクトリ")
    p.add_argument("--output_md", default="report/summary.md", help="Markdown 出力ファイル")
    p.add_argument("--output_csv", default="report/summary.csv", help="CSV 出力ファイル")
    p.add_argument("--group_by_version", action="store_true", help="バージョン別にグループ化して出力")
    p.add_argument("--max_len", type=int, default=120, help="キャラ要約の最大文字数")
    a = p.parse_args()

    main(a)