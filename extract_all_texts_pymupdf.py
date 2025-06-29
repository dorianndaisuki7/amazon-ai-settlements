import fitz  # PyMuPDF
import os

# --- 設定 ---
INPUT_DIR = "../data/sources/core_sources"
OUTPUT_DIR = "../outputs/texts"

def extract_text_from_pdf(filepath):
    text = ""
    with fitz.open(filepath) as doc:
        for page in doc:
            text += page.get_text()
    return text

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print("⚠️ PDFファイルが見つかりませんでした。")
        return

    for filename in pdf_files:
        input_path = os.path.join(INPUT_DIR, filename)
        base_name = os.path.splitext(filename)[0]
        output_path = os.path.join(OUTPUT_DIR, f"{base_name}.txt")

        print(f"📄 処理中: {filename}")
        try:
            text = extract_text_from_pdf(input_path)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"✅ 抽出成功: {output_path}（{len(text)} 文字）")
        except Exception as e:
            print(f"❌ 抽出失敗: {filename} → {e}")

if __name__ == "__main__":
    main()