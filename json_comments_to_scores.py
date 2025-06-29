import os
import json
import argparse
import re
import time
import openai
import pandas as pd
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

# APIキーは.envから読み込む（事前に os.environ にセットされている前提）
client = OpenAI()

def extract_score(text):
    try:
        match = re.search(r"([0]?\.\d{1,2}|1\.00?)", text)
        return float(match.group(1)) if match else None
    except:
        return None

def gpt_with_retry(prompt, retries=3, delay=5):
    for i in range(retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content.strip()
        except openai.error.RateLimitError:
            print(f"[Retry {i+1}] Rate limit hit. Waiting {delay}s...")
            time.sleep(delay)
        except Exception as e:
            print(f"[Other Error] {e}")
            break
    return None

def score_from_comment(comment, character_name):
    prompt = f"""
あなたはAI考古学者です。
以下のコメントは {character_name} の評価です。この地点に人工構造や人類活動の可能性がどれほどあるかを、0.00〜1.00で数値化してください。

【コメント】
{comment}

スコア（数値のみ、例：0.75）を出力してください：
"""
    output = gpt_with_retry(prompt)
    return extract_score(output)

def process_json_file(file_path):
    site_id = os.path.splitext(os.path.basename(file_path))[0].replace("site_", "")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = {"site_id": site_id}
    characters = data.get("characters", {})

    for char, content in characters.items():
        comment = content if isinstance(content, str) else content.get("comment", "")
        if not isinstance(comment, str) or comment.strip() == "":
            print(f"[site_{site_id} / {char}] 空コメントのためスキップ")
            result[f"{char}_score"] = None
            continue

        try:
            score = score_from_comment(comment, char)
            result[f"{char}_score"] = score
        except Exception as e:
            print(f"[Error] site_{site_id} / {char} → {e}")
            result[f"{char}_score"] = None

    result["summary"] = data.get("summary", "")
    return result

def main(input_dir, output_csv):
    files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if f.endswith(".json")]
    print(f"\U0001F50D {len(files)} 件のJSONを処理します（{input_dir}）")

    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_json_file, fp) for fp in files]
        for future in tqdm(as_completed(futures), total=len(futures)):
            results.append(future.result())

    df = pd.DataFrame(results)
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"✅ 出力完了：{output_csv}（{len(df)}件）")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True, help="入力ディレクトリ（JSON群）")
    parser.add_argument("--output_csv", required=True, help="出力CSVファイルパス")
    args = parser.parse_args()

    main(args.input_dir, args.output_csv)