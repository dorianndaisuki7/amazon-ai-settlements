#!/usr/bin/env python
"""
generate_random_points_in_amazon.py  – 5 km グリッド候補点
"""
import numpy as np, geopandas as gpd
from shapely.geometry import Point, box

BBOX_FILE = "data/amazon_bbox.geojson"     # Amazon 全域ポリゴン
OUT_FILE  = "data/candidates/random_candidates.geojson"
GRID_DEG  = 0.05       # ≒5 km（1°=111 km を目安）

bbox = gpd.read_file(BBOX_FILE).geometry.unary_union.envelope
lon_min, lat_min, lon_max, lat_max = bbox.bounds
lons = np.arange(lon_min, lon_max, GRID_DEG)
lats = np.arange(lat_min, lat_max, GRID_DEG)

pts = [Point(x, y) for x in lons for y in lats]
gdf = gpd.GeoDataFrame(geometry=pts, crs="EPSG:4326")
# Amazon ポリゴン内に clip
amazon = gpd.read_file(BBOX_FILE).to_crs(epsg=4326).unary_union
gdf = gdf[gdf.within(amazon)]

gdf.to_file(OUT_FILE, driver="GeoJSON")
print("saved", OUT_FILE, "->", len(gdf), "pts")
