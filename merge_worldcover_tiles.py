import os, glob, rasterio
from rasterio.merge import merge

# ── プロジェクトルートと入出力パスを決定 ──────────────────
script_dir   = os.path.dirname(os.path.abspath(__file__))          # .../scripts
project_root = os.path.abspath(os.path.join(script_dir, os.pardir))# 1つ上
input_folder = os.path.join(project_root, 'data', 'raw_exports')
output_file  = os.path.join(project_root, 'data', 'layers',
                            'worldcover_2021_amazon_merged.tif')

# ── tif 検出 ───────────────────────────────────────────────
tif_files = glob.glob(os.path.join(input_folder, '*.tif'))
print(f"📂 マージ対象ファイル数: {len(tif_files)}")
if len(tif_files) == 0:
    raise RuntimeError(f'⚠️ tif が見つかりません: {input_folder}')

# ── マージ処理 ─────────────────────────────────────────────
srcs = [rasterio.open(fp) for fp in tif_files]
mosaic, transform = merge(srcs)

meta = srcs[0].meta.copy()
meta.update(driver='GTiff',
            height=mosaic.shape[1],
            width=mosaic.shape[2],
            transform=transform,
            count=1)

os.makedirs(os.path.dirname(output_file), exist_ok=True)
with rasterio.open(output_file, 'w', **meta) as dst:
    dst.write(mosaic)

print(f"✅ 統合完了 → {output_file}")