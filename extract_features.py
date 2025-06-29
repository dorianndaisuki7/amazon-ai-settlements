import geopandas as gpd
import rasterio
from rasterio.enums import Resampling
import numpy as np
import os
from shapely.geometry import Point
from tqdm import tqdm

# 入出力ファイル
in_path = "data/candidates/top_sites.geojson"
out_path = "data/candidates/candidates_with_features_debug.gpkg"

# ラスタパス（適宜調整）
raster_layers = {
    "ndvi": "data/layers/ndvi_merged.vrt",
    "carbon": "data/layers/soil_carbon_0_5cm_amazon.tif",
    "elevation": "data/layers/elevation_srtm_90m.tif",
    "slope": "data/layers/soil_carbon_0_5cm_amazon.tif",
    "river_dist": "data/layers/river_distance.tif"
}

slope_std_path = "data/layers/slope_std.tif"

# NaNロガー
def sample_raster_with_log(gdf, tif_path, name):
    vals = []
    print(f"📥 Sampling {name} from {tif_path}")
    with rasterio.open(tif_path) as src:
        bounds = src.bounds
        for i, pt in enumerate(tqdm(gdf.geometry, desc=f"{name}")):
            try:
                x, y = pt.centroid.x, pt.centroid.y
                if not (bounds.left <= x <= bounds.right and bounds.bottom <= y <= bounds.top):
                    print(f"[NaN:out_of_bounds] {name} at index={i}, point={pt}")
                    vals.append(np.nan)
                    continue
                row, col = src.index(x, y)
                val = src.read(1, window=((row, row+1), (col, col+1)))
                if val.size == 0:
                    print(f"[NaN:empty] {name} at index={i}, point={pt}")
                    vals.append(np.nan)
                else:
                    vals.append(float(val[0, 0]))
            except Exception as e:
                print(f"[NaN:exception] {name} at index={i}, point={pt} → {e}")
                vals.append(np.nan)
    return vals

# main 処理
def main():
    print(f"🟢 Feature extraction – debug start")
    gdf = gpd.read_file(in_path)
    print(f"  • Candidates loaded: {len(gdf)}")

    # 各ラスタから抽出
    for name, tif_path in raster_layers.items():
        gdf[name] = sample_raster_with_log(gdf, tif_path, name)

    # 傾斜（標準偏差）だけ別で処理
    gdf["slope"] = sample_raster_with_log(gdf, slope_std_path, "slope")

    # NaN要約
    print("📊 NaN Summary:")
    for col in ["ndvi", "carbon", "elevation", "landcover", "slope"]:
        total = len(gdf)
        nan = gdf[col].isna().sum()
        print(f"  • {col}: NaN = {nan} / {total} ({nan/total:.2%})")

    # 出力
    gdf.to_file(out_path, driver="GPKG")
    print(f"✅ Saved to {out_path}")

if __name__ == "__main__":
    main()