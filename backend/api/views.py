from pathlib import Path
import re

import pandas as pd
from django.http import JsonResponse

from .food_formatters import format_local_food, origin_position_for_label, primary_origin_label
from .food_store import load_cleaned_foods, load_wikidata_origins, merge_wikidata_origins


DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "top_100_fruits.csv"
ENRICHED_DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "top_100_fruits_off_enriched.csv"


def load_local_foods():
    # 旧课程 CSV 作为本地部署兜底，也提供一份可定位的原产地参考。
    data_file = ENRICHED_DATA_FILE if ENRICHED_DATA_FILE.exists() else DATA_FILE
    if not data_file.exists():
        return None

    df = pd.read_csv(data_file)
    return [format_local_food(row, index) for index, row in df.iterrows()]


def normalise_food_key(value):
    # 用较宽松的 key 匹配 OFF 食物名和旧 CSV 食物名，提升原产地补齐率。
    if not value:
        return ""

    value = re.sub(r"[^a-z0-9 ]+", " ", value.lower())
    value = re.sub(r"\b(whole|wheat|green|red|black|brown|dry|fresh|organic|extra|rolled)\b", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:-1] if value.endswith("s") else value


def build_local_origin_index(local_foods):
    # 将本地 CSV 建成索引，后面给 OFF 清洗结果补 origin 坐标。
    index = {}
    for food in local_foods:
        keys = {
            normalise_food_key(food.get("name")),
            normalise_food_key(food.get("displayName")),
        }
        for key in keys:
            if key:
                index.setdefault(key, food)

    return index


def bottom_grid_position(index):
    # Worldwide/unknown 不能定位到国家时，放到地图底部网格，保证 100 个 marker 都可见。
    columns = 12
    row = index // columns
    column = index % columns

    longitude = -165 + (330 * column / (columns - 1))
    latitude = -78 + (row * 4)
    return [round(latitude, 3), round(longitude, 3)]


def spread_overlapping_positions(foods):
    # 同一国家/地区的 marker 会重叠，这里按小网格偏移，保留 basePosition 供弹窗说明。
    grouped = {}
    for food in foods:
        position = food.get("origin", {}).get("position")
        if not position:
            continue

        key = (round(position[0], 4), round(position[1], 4))
        grouped.setdefault(key, []).append(food)

    for group in grouped.values():
        if len(group) == 1:
            continue

        for index, food in enumerate(group):
            row = index // 5
            column = index % 5
            offset_lat = (row - 1) * 0.9
            offset_lng = (column - 2) * 1.4
            original_position = food["origin"]["position"]
            food["origin"] = {
                **food["origin"],
                "position": [
                    round(original_position[0] + offset_lat, 4),
                    round(original_position[1] + offset_lng, 4),
                ],
                "basePosition": original_position,
                "displayOffset": True,
            }

    return foods


def build_map_foods(cleaned_foods, local_foods, limit):
    # 地图数据优先使用 OFF/Wikidata/local origin；仍无坐标时用底部占位点补齐。
    local_index = build_local_origin_index(local_foods)
    map_foods = []
    used_local_names = set()
    placeholder_index = 0

    for index, food in enumerate(cleaned_foods[:limit]):
        keys = [
            normalise_food_key(food.get("displayName")),
            normalise_food_key(food.get("name")),
            normalise_food_key(food.get("category")),
        ]
        local_match = next((local_index.get(key) for key in keys if local_index.get(key)), None)

        mapped_food = {**food}

        if local_match and local_match.get("origin", {}).get("position"):
            used_local_names.add(local_match.get("name"))
            mapped_food["origin"] = {
                **local_match["origin"],
                "source": "local-origin-dataset",
            }
            mapped_food.setdefault("metadata", {})["matchedLocalFood"] = local_match.get("name")
        else:
            off_origin_label = food.get("origin", {}).get("label")
            off_origin_position = origin_position_for_label(off_origin_label, None)
            mapped_food["origin"] = {
                "label": primary_origin_label(off_origin_label) or "Worldwide/unknown",
                "position": off_origin_position or bottom_grid_position(placeholder_index),
                "method": "openfoodfacts-origin-label" if off_origin_position else "map-bottom-grid-placeholder",
                "source": "openfoodfacts-origin" if off_origin_position else "map-placeholder",
            }
            if off_origin_position is None:
                placeholder_index += 1
                mapped_food.setdefault("metadata", {})["originNote"] = (
                    "No local or Open Food Facts mappable origin; shown near the bottom of the map"
                )

        map_foods.append(mapped_food)

    # If the current Open Food Facts cache has fewer than 100 usable rows, fill
    # the remaining map slots from the local origin dataset so the visual map is complete.
    for local_food in local_foods:
        if len(map_foods) >= limit:
            break

        if local_food.get("name") in used_local_names or not local_food.get("origin", {}).get("position"):
            continue

        filler_food = {
            **local_food,
            "source": "local-marker-fill",
            "metadata": {
                **(local_food.get("metadata") or {}),
                "originNote": "Local marker used because the Open Food Facts cache has fewer than 100 usable foods",
            },
        }
        map_foods.append(filler_food)

    return spread_overlapping_positions(map_foods)


def fruit_data(request):
    # 前端统一访问这个 API；source=local 看旧数据，source=map 返回带地图坐标的版本。
    limit = int(request.GET.get("limit", 100))
    source = request.GET.get("source")

    if source == "local":
        data = load_local_foods()
        if data is None:
            return JsonResponse({"error": "Local data file was not found"}, status=404)

        return JsonResponse(data[:limit], safe=False)

    # Prefer the cleaned SQLite snapshot generated from Open Food Facts. If it
    # has not been synced yet, keep local deployment working with the CSV data.
    cleaned_foods = load_cleaned_foods(limit=limit)
    if cleaned_foods:
        origins = load_wikidata_origins()
        cleaned_foods = merge_wikidata_origins(cleaned_foods, origins)

        if source == "map":
            local_foods = load_local_foods()
            if local_foods is None:
                return JsonResponse({"error": "Local data file was not found"}, status=404)

            return JsonResponse(build_map_foods(cleaned_foods, local_foods, limit), safe=False)

        return JsonResponse(cleaned_foods, safe=False)

    data = load_local_foods()
    if data is None:
        return JsonResponse({"error": "Local data file was not found"}, status=404)

    return JsonResponse(data[:limit], safe=False)
