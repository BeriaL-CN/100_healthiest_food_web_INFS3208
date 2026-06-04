from ast import literal_eval
import csv
import re
from pathlib import Path

import pandas as pd


DEFAULT_REGION_COORDINATES = {
    "Africa": [1.6508, 17.6791],
    "Asia": [34.0479, 100.6197],
    "Asia Minor": [38.9519, 35.5013],
    "Australia": [-25.2744, 133.7751],
    "Austria": [47.5162, 14.5501],
    "Belgium": [50.5039, 4.4699],
    "Caribbean": [18.2, -66.5],
    "Central America": [15.7835, -90.2308],
    "Central Asia": [39.4009, 72.8677],
    "Central/South America": [4.5709, -74.2973],
    "Canada": [56.1304, -106.3468],
    "East Asia": [35.8617, 104.1954],
    "Europe": [54.526, 15.2551],
    "France": [46.2276, 2.2137],
    "Germany": [51.1657, 10.4515],
    "Greece": [39.0742, 21.8243],
    "Ireland": [53.4129, -8.2439],
    "Italy": [42.6384, 12.6743],
    "Eastern Mediterranean": [34.0, 35.5],
    "Mediterranean Region": [37.0, 18.0],
    "Mediterranean Sea": [35.0, 18.0],
    "Middle East": [29.2985, 42.551],
    "North America": [54.526, -105.2551],
    "North Atlantic Ocean": [35.0, -40.0],
    "North Pacific Ocean": [30.0, -160.0],
    "Northern Europe": [60.0, 15.0],
    "Oregon": [44.0, -120.5],
    "Netherlands": [52.1326, 5.2913],
    "Persia": [32.4279, 53.688],
    "Rome": [41.9028, 12.4964],
    "South America": [-15.600, -56.100],
    "South Asia": [20.5937, 78.9629],
    "Southeast Asia": [1.3521, 103.8198],
    "Spain": [40.4637, -3.7492],
    "UK": [55.3781, -3.436],
    "United Kingdom": [55.3781, -3.436],
    "United States": [39.8283, -98.5795],
    "Vietnam": [14.0583, 108.2772],
    "West Asia": [32.4279, 53.688],
    "Western Asia": [32.4279, 53.688],
}

# 国家/地区坐标优先从 CSV 读取；CSV 不存在时用这份最小内置表兜底。
REGION_COORDINATES_FILE = Path(__file__).resolve().parents[2] / "data" / "region_coordinates.csv"


def load_region_coordinates():
    if not REGION_COORDINATES_FILE.exists():
        return DEFAULT_REGION_COORDINATES

    coordinates = {}
    with REGION_COORDINATES_FILE.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            coordinates[row["label"]] = [float(row["latitude"]), float(row["longitude"])]

    return coordinates


REGION_COORDINATES = load_region_coordinates()

ORIGIN_LABEL_ALIASES = {
    "de:nordostatlantik": "North Atlantic Ocean",
    "France,Provence": "France",
    "Italia": "Italy",
    "Oregon,USA": "Oregon",
    "Pays Bas": "Netherlands",
    "People's Republic of China": "China",
    "Union Européenne": "Europe",
}

NON_ENGLISH_NAME_HINTS = {
    "avena",
    "copos",
    "graine",
    "graines",
    "gourmand",
    "haricots",
    "lentilles",
    "lijnzaad",
    "nudeln",
}

NON_POSITIONAL_ORIGINS = {
    "more than one country",
    "European Union and Non European Union",
    "fr:import",
    "Worldwide",
}


def number_or_none(value):
    # 将 CSV/API 里的空值、NaN、字符串数字统一转换成前端可用的 number/null。
    if value is None or pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def text_or_none(value):
    # pandas 会把空 CSV 单元格读成 NaN；这里避免 JsonResponse 输出非法的 NaN。
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()
    return text or None


def position_or_none(value):
    # 旧课程 CSV 的坐标是字符串形式的数组，这里安全地转回 [lat, lng]。
    if value is None or pd.isna(value):
        return None

    try:
        latitude, longitude = literal_eval(value)
        return [float(latitude), float(longitude)]
    except (TypeError, ValueError, SyntaxError):
        return None


def is_likely_english_name(name):
    # 这是旧版“英文展示名”过滤的辅助函数；新版清洗可选择跳过它。
    if not name:
        return False

    lowered = name.lower()
    if any(hint in lowered for hint in NON_ENGLISH_NAME_HINTS):
        return False

    return bool(re.fullmatch(r"[A-Za-z0-9 '&.,()#°-]+", name))


def primary_origin_label(label):
    # 清洗复合/古代地理标签，让地图尽量落到一个可定位区域。
    if not label:
        return None

    cleaned_label = re.sub(r"^Ancient\s+", "", label.strip(), flags=re.I).strip()
    cleaned_label = ORIGIN_LABEL_ALIASES.get(cleaned_label, cleaned_label)
    if cleaned_label in REGION_COORDINATES or cleaned_label in NON_POSITIONAL_ORIGINS:
        return cleaned_label

    primary_label = cleaned_label.split("/", 1)[0].strip()
    return primary_label


def origin_position_for_label(label, position):
    # 先查国家/地区坐标表，再回退到原始坐标；Worldwide 这类不强行定位。
    primary_label = primary_origin_label(label)
    if primary_label in NON_POSITIONAL_ORIGINS:
        return None

    if primary_label in REGION_COORDINATES:
        return REGION_COORDINATES[primary_label]

    return position


def title_from_category(value):
    # OFF category 常带连字符，展示时转成人类可读标题。
    if not value:
        return None

    cleaned = value.replace("-", " ").strip()
    return cleaned[:1].upper() + cleaned[1:]


def build_display_name(name, category, source):
    # 本地 CSV 保留原名；OFF 数据在旧模式下可用英文 category 替代非英文商品名。
    if source != "openfoodfacts":
        return name

    # Use category only when the product name is not suitable for English UI.
    # Specific English names are kept because they preserve useful food detail.
    if category and not is_likely_english_name(name):
        return title_from_category(category)

    return name


def ensure_display_fields(food):
    # 统一补齐 React 组件依赖的 displayName 和 metadata.productName 字段。
    display_name = build_display_name(food.get("name"), food.get("category"), food.get("source"))
    food["displayName"] = display_name or food.get("name")

    metadata = food.setdefault("metadata", {})
    if food.get("source") == "openfoodfacts":
        metadata.setdefault("productName", food.get("name"))

    return food


def format_local_food(row, index):
    # Keep the original coursework CSV usable by mapping it to the same shape
    # as the Open Food Facts cache. Fields that the CSV cannot provide stay null.
    origin_label = row.get("Originated From")
    primary_label = primary_origin_label(origin_label)
    raw_position = position_or_none(row.get("location"))
    origin_position = origin_position_for_label(origin_label, raw_position)
    origin_was_cleaned = bool(origin_label and primary_label != origin_label)

    return ensure_display_fields({
        "id": f"local-{index + 1}",
        "name": row.get("Food"),
        "category": "Local dataset",
        "source": "local",
        "healthScore": number_or_none(row.get("Antioxidant Score")),
        "nutrients": {
            "calories": number_or_none(row.get("Calories")),
            "protein": number_or_none(row.get("Protein (g)")),
            "fat": number_or_none(row.get("OFF Fat (g)")),
            "carbohydrates": number_or_none(row.get("OFF Carbohydrates (g)")),
            "sugar": number_or_none(row.get("OFF Sugar (g)")),
            "fiber": number_or_none(row.get("Fiber (g)")),
            "vitaminC": number_or_none(row.get("Vitamin C (mg)")),
            "salt": number_or_none(row.get("OFF Salt (g)")),
            "saturatedFat": number_or_none(row.get("OFF Saturated Fat (g)")),
        },
        "origin": {
            "label": primary_label,
            "position": origin_position,
            "method": (
                "non-positional-origin"
                if primary_label in NON_POSITIONAL_ORIGINS
                else "local-origin-cleaned-label" if origin_was_cleaned else "local-origin-estimate"
            ),
        },
        "metadata": {
            "nutritionValue": row.get("Nutrition Value (per 100g)"),
            "quantity": row.get("Quantity"),
            "antioxidantScore": number_or_none(row.get("Antioxidant Score")),
            "openFoodFactsCode": text_or_none(row.get("OFF Code")),
            "brand": text_or_none(row.get("OFF Brand")),
            "imageUrl": text_or_none(row.get("OFF Image URL")),
            "nutriScore": number_or_none(row.get("OFF Nutri-Score")),
            "nutriScoreGrade": text_or_none(row.get("OFF Nutri-Score Grade")),
            "novaGroup": number_or_none(row.get("OFF NOVA Group")),
            "dataQuality": "local-kaggle-off-enriched" if text_or_none(row.get("OFF Code")) else "local-fallback",
            "offProductName": text_or_none(row.get("OFF Product Name")),
            "offGenericName": text_or_none(row.get("OFF Generic Name")),
            "offCategory": text_or_none(row.get("OFF Category")),
            "offMatchScore": number_or_none(row.get("OFF Match Score")),
            "originalOriginLabel": origin_label if origin_was_cleaned else None,
            "originNote": (
                "Worldwide origin; no single marker is shown"
                if primary_label in NON_POSITIONAL_ORIGINS
                else f"Original region label: {origin_label}" if origin_was_cleaned else None
            ),
        },
    })


def get_nutrient(nutriments, key):
    # OFF nutriments 字段有时带 _100g 后缀，有时直接使用基础 key。
    return number_or_none(nutriments.get(f"{key}_100g", nutriments.get(key)))


def calculate_health_score(product):
    # Open Food Facts provides Nutri-Score grades, not a top-100 ranking. This
    # project score gives us a repeatable local sort while staying transparent.
    nutriments = product.get("nutriments") or {}
    nutriscore_score = number_or_none(product.get("nutriscore_score"))
    nova_group = number_or_none(product.get("nova_group"))

    score = 100.0
    if nutriscore_score is not None:
        score -= nutriscore_score

    protein = get_nutrient(nutriments, "proteins") or 0
    fiber = get_nutrient(nutriments, "fiber") or 0
    sugar = get_nutrient(nutriments, "sugars") or 0
    saturated_fat = get_nutrient(nutriments, "saturated-fat") or 0
    salt = get_nutrient(nutriments, "salt") or 0

    score += min(protein, 20) * 0.8
    score += min(fiber, 20) * 1.2
    score -= min(sugar, 60) * 0.4
    score -= min(saturated_fat, 30) * 0.9
    score -= min(salt, 10) * 2.0

    if nova_group is not None:
        score -= max(nova_group - 1, 0) * 4

    required_keys = [
        "energy-kcal",
        "proteins",
        "fat",
        "carbohydrates",
        "sugars",
        "fiber",
        "salt",
        "saturated-fat",
    ]
    completeness = sum(get_nutrient(nutriments, key) is not None for key in required_keys)
    score += completeness * 0.75

    return round(score, 2)


def format_openfoodfacts_product(product, rank=None):
    # This canonical response model is what Django returns to React regardless
    # of whether the row came from Open Food Facts, SQLite, or the CSV fallback.
    nutriments = product.get("nutriments") or {}
    name = product.get("product_name") or product.get("generic_name") or "Unknown food"
    categories = product.get("categories_tags_en") or product.get("categories_tags") or []
    category_tags = product.get("categories_tags") or []
    countries = product.get("countries_tags_en") or product.get("countries_tags") or []
    origin_label = product.get("origins_en") or product.get("origins") or product.get("manufacturing_places")

    return ensure_display_fields({
        "id": f"off-{product.get('code')}",
        "rank": rank,
        "name": name,
        "category": categories[-1] if categories else None,
        "source": "openfoodfacts",
        "healthScore": calculate_health_score(product),
        "nutrients": {
            "calories": get_nutrient(nutriments, "energy-kcal"),
            "protein": get_nutrient(nutriments, "proteins"),
            "fat": get_nutrient(nutriments, "fat"),
            "carbohydrates": get_nutrient(nutriments, "carbohydrates"),
            "sugar": get_nutrient(nutriments, "sugars"),
            "fiber": get_nutrient(nutriments, "fiber"),
            "vitaminC": get_nutrient(nutriments, "vitamin-c"),
            "salt": get_nutrient(nutriments, "salt"),
            "saturatedFat": get_nutrient(nutriments, "saturated-fat"),
        },
        "origin": {
            "label": origin_label or (countries[0] if countries else None),
            "position": None,
            "method": "openfoodfacts-origin-text" if origin_label else "openfoodfacts-country-tag",
        },
        "metadata": {
            "nutritionValue": "Open Food Facts Nutri-Score A product",
            "quantity": product.get("quantity"),
            "antioxidantScore": None,
            "openFoodFactsCode": product.get("code"),
            "brand": product.get("brands"),
            "categoryTags": category_tags,
            "imageUrl": product.get("image_front_url") or product.get("image_url"),
            "nutriScore": product.get("nutriscore_score"),
            "nutriScoreGrade": product.get("nutrition_grades"),
            "novaGroup": product.get("nova_group"),
            "dataQuality": "cleaned-openfoodfacts",
            "productName": name,
            "openFoodFactsOrigin": origin_label,
        },
    })
