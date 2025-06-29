# scripts/filter_valid_comment_jsons.py
import os
import json
import shutil
import argparse

def has_nonempty_comment(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for char, comment in data.get("characters", {}).items():
        if isinstance(comment, str) and comment.strip():
            return True
    return False

def main(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    count = 0
    for fname in os.listdir(input_dir):
        if fname.endswith(".json"):
            fpath = os.path.join(input_dir, fname)
            if has_nonempty_comment(fpath):
                shutil.copy(fpath, os.path.join(output_dir, fname))
                count += 1
    print(f"✅ コメントありJSONを {count} 件抽出しました → {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True, help="元のJSONフォルダ")
    parser.add_argument("--output_dir", required=True, help="コメントありJSONを保存する先")
    args = parser.parse_args()
    main(args.input_dir, args.output_dir)