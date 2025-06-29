import rasterio
import geopandas as gpd
from shapely.geometry import Point

# --- ファイルパス設定 ---
soil_tif_path = './data/layers/soil_carbon_0_5cm_amazon.tif'
geojson_path = './data/candidates/random_candidates.geojson'
output_path = './data/candidates/enriched_candidates.geojson'

# --- GeoJSON読み込み ---
gdf = gpd.read_file(geojson_path)

# --- ラスター読み込み ---
with rasterio.open(soil_tif_path) as src:
    band = src.read(1)
    transform = src.transform

    # 座標系変換（必要時）
    if gdf.crs != src.crs:
        print("⚠️ 座標系が一致していません。変換します。")
        gdf = gdf.to_crs(src.crs)

    # 値取得関数
    def get_soil_carbon(point):
        try:
            row, col = src.index(point.x, point.y)
            value = band[row, col]
            return float(value)
        except:
            return None

    # 値とフラグを追加
    gdf['soil_carbon'] = gdf.geometry.apply(get_soil_carbon)
    gdf['potential_terra_preta'] = gdf['soil_carbon'] >= 20

    # 信頼度ラベル（任意）
    def classify_conf(val):
        if val is None:
            return "low"
        elif val >= 30:
            return "high"
        elif val >= 20:
            return "medium"
        else:
            return "low"
    gdf["carbon_confidence"] = gdf["soil_carbon"].apply(classify_conf)

# --- 出力 ---
gdf.to_file(output_path, driver='GeoJSON')
print(f'✅ 出力完了: {output_path}')
print(f'⚠️ 土壌値なし: {gdf["soil_carbon"].isnull().sum()} 点')