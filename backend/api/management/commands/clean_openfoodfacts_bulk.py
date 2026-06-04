import csv
import gzip
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from api.food_formatters import format_openfoodfacts_product, is_likely_english_name
from api.food_store import replace_cleaned_foods


DEFAULT_INPUT = Path(__file__).resolve().parents[5] / "data" / "en.openfoodfacts.org.products.csv.gz"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[5] / "data" / "openfoodfacts_cleaned_foods.csv"
# 自然食物关键词：OFF bulk 是商品级数据，先用这些分类词找到更像食材/作物的候选。
SIMPLE_CATEGORY_TERMS = {
    "fruit",
    "vegetable",
    "legume",
    "lentil",
    "bean",
    "nut",
    "seed",
    "cereal",
    "grain",
    "rice",
    "oat",
    "fish",
    "seafood",
    "herb",
    "spice",
}
# 复杂食品分类：这些更像菜品、零食或加工组合，不适合用来做“食物原产地”地图。
COMPLEX_CATEGORY_TERMS = {
    "breakfast",
    "bread",
    "butter",
    "cake",
    "chocolate",
    "crispbread",
    "dessert",
    "meal",
    "muesli",
    "noodle",
    "pasta",
    "pita",
    "pizza",
    "prepared",
    "products",
    "ready",
    "sauce",
    "snack",
    "spaghetti",
    "sweet",
}
# 复杂食品名称：按词过滤商品名，保留原始语言，但排除明显不是自然食材的形态。
COMPLEX_NAME_TERMS = {
    "blend",
    "bread",
    "butter",
    "canned",
    "chicken",
    "crispbread",
    "filets",
    "fillet",
    "lasagne",
    "macaroni",
    "mince",
    "mix",
    "mixed",
    "noodle",
    "pasta",
    "penne",
    "pita",
    "powder",
    "powdered",
    "products",
    "puff",
    "rigatoni",
    "spaghetti",
    "trio",
}
# 旧版英文显示名过滤词：默认保留这个模式；新 CSV 可通过 --allow-non-english-names 跳过。
LANGUAGE_REJECT_TERMS = {
    "alimentaire",
    "aneth",
    "anneaux",
    "basilic",
    "bazylia",
    "bio",
    "blaumohn",
    "bleu",
    "bouquet",
    "carrefour",
    "carpentras",
    "chiasaat",
    "chica",
    "cury",
    "dinkel",
    "ducros",
    "fagioli",
    "farine",
    "farro",
    "feuille",
    "fraises",
    "funghi",
    "grillo",
    "groceries",
    "haricot",
    "herbe",
    "jaune",
    "keimsaat",
    "kleie",
    "kresse",
    "leinsaat",
    "legumi",
    "levure",
    "lineseeds",
    "linsen",
    "maanzaad",
    "malt",
    "mistura",
    "mixtures",
    "mosh",
    "omega",
    "orge",
    "ortie",
    "panch",
    "papavero",
    "pavot",
    "pilzmischung",
    "poudre",
    "poulet",
    "purasana",
    "puren",
    "ravintohiivahiutale",
    "ravintohiivahiutaleet",
    "rote",
    "saatenmischung",
    "sachet",
    "salade",
    "samen",
    "schnittlauch",
    "sementes",
    "soja",
    "spit",
    "superseeds",
    "vert",
    "with",
    "yeast",
    "zuppa",
}
DISPLAY_REJECT_TERMS = COMPLEX_NAME_TERMS.union(
    {
        "groceries",
        "mixtures",
        "superseeds",
        "yeast",
    }
)
# 去重状态词：只在比较相似名称时忽略，不强制改掉最终展示名。
DEDUP_MODIFIER_TERMS = {
    "bio",
    "biologisch",
    "cold",
    "cream",
    "creamy",
    "cleaned",
    "conventional",
    "dry",
    "dried",
    "entieres",
    "gebroken",
    "ground",
    "high",
    "hulled",
    "meal",
    "milled",
    "moulues",
    "organic",
    "raw",
    "roasted",
    "salted",
    "seed",
    "seeds",
    "shelled",
    "split",
    "supervalu",
    "triple",
    "unroasted",
    "unsalted",
    "value",
    "whole",
    "better",
    "eat",
}
# 同一食物家族的数量上限：避免高蛋白豆类/种子把 Top 100 完全占满。
FAMILY_LIMITS = {
    "beans": 10,
    "lentils": 6,
    "peas": 5,
    "flax": 4,
    "chia": 4,
    "sunflower": 3,
    "oats": 4,
    "rice": 4,
    "mushrooms": 4,
}
# 小型 CSV 输出字段：作为前端 API/SQLite 的稳定本地快照。
CSV_COLUMNS = [
    "rank",
    "code",
    "display_name",
    "product_name",
    "category",
    "category_tags",
    "brand",
    "countries",
    "origins",
    "manufacturing_places",
    "nutri_score_grade",
    "nutri_score",
    "nova_group",
    "health_score",
    "calories_100g",
    "protein_100g",
    "fat_100g",
    "carbohydrates_100g",
    "sugar_100g",
    "fiber_100g",
    "salt_100g",
    "saturated_fat_100g",
    "image_url",
]

csv.field_size_limit(64 * 1024 * 1024)


class Command(BaseCommand):
    help = "Clean the local Open Food Facts bulk TSV into a small CSV and SQLite cache."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(DEFAULT_INPUT))
        parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
        parser.add_argument("--target-size", type=int, default=100)
        parser.add_argument("--candidate-limit", type=int, default=5000)
        parser.add_argument("--write-sqlite", action="store_true", default=True)
        parser.add_argument(
            "--allow-non-english-names",
            action="store_true",
            help="Keep non-English product names; still applies complex-food and duplicate filters.",
        )

    def handle(self, *args, **options):
        input_path = Path(options["file"])
        output_path = Path(options["output"])
        target_size = options["target_size"]
        candidate_limit = options["candidate_limit"]
        allow_non_english_names = options["allow_non_english_names"]

        if not input_path.exists():
            raise CommandError(f"Bulk file not found: {input_path}")

        candidates = self.collect_candidates(input_path, candidate_limit, allow_non_english_names)
        if not candidates:
            raise CommandError("No suitable Open Food Facts candidates were found.")

        cleaned = self.select_top_foods(candidates, target_size, allow_non_english_names)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.write_cleaned_csv(output_path, cleaned)

        if options["write_sqlite"]:
            replace_cleaned_foods(cleaned)

        self.stdout.write(self.style.SUCCESS(f"Saved {len(cleaned)} foods to {output_path}"))

    def collect_candidates(self, input_path, candidate_limit, allow_non_english_names):
        # 流式读取 1GB+ 的 OFF 压缩 TSV，避免解压出巨大临时文件。
        candidates = []
        scanned = 0
        with gzip.open(input_path, "rt", encoding="utf-8", errors="replace", newline="") as file:
            reader = csv.DictReader(file, delimiter="\t")
            for row in reader:
                scanned += 1
                if not self.is_candidate(row):
                    continue

                food = format_openfoodfacts_product(self.row_to_product(row))
                if not is_clean_display_name(food.get("displayName"), allow_non_english_names):
                    continue

                candidates.append(food)
                if len(candidates) >= candidate_limit:
                    break

                if scanned % 250000 == 0:
                    self.stdout.write(f"Scanned {scanned:,} rows; kept {len(candidates):,} candidates")

        self.stdout.write(f"Scanned {scanned:,} rows; kept {len(candidates):,} candidates")
        return candidates

    def is_candidate(self, row):
        if (row.get("nutriscore_grade") or "").lower() != "a":
            return False

        nova_group = row.get("nova_group")
        if nova_group and nova_group not in {"1", "2", "3"}:
            return False

        categories = " ".join(
            [
                row.get("categories_en") or "",
                row.get("categories_tags") or "",
                row.get("main_category_en") or "",
                row.get("food_groups_en") or "",
            ]
        ).lower()
        if not any(term in categories for term in SIMPLE_CATEGORY_TERMS):
            return False

        if any(term in categories for term in COMPLEX_CATEGORY_TERMS):
            return False

        name = row.get("product_name") or row.get("generic_name")
        if not name:
            return False

        searchable_name = " ".join([name, row.get("generic_name") or ""]).lower()
        if any(term in searchable_name for term in COMPLEX_NAME_TERMS):
            return False

        return True

    def row_to_product(self, row):
        return {
            "code": row.get("code"),
            "product_name": row.get("product_name"),
            "generic_name": row.get("generic_name"),
            "brands": row.get("brands"),
            "quantity": row.get("quantity"),
            "categories_tags": split_tags(row.get("categories_tags")),
            "categories_tags_en": split_tags(row.get("categories_en")),
            "countries_tags_en": split_tags(row.get("countries_en")),
            "origins": row.get("origins"),
            "origins_en": row.get("origins_en"),
            "manufacturing_places": row.get("manufacturing_places"),
            "nutrition_grades": row.get("nutriscore_grade"),
            "nutriscore_score": row.get("nutriscore_score"),
            "nova_group": row.get("nova_group"),
            "image_url": row.get("image_url"),
            "nutriments": {
                "energy-kcal_100g": row.get("energy-kcal_100g"),
                "proteins_100g": row.get("proteins_100g"),
                "fat_100g": row.get("fat_100g"),
                "carbohydrates_100g": row.get("carbohydrates_100g"),
                "sugars_100g": row.get("sugars_100g"),
                "fiber_100g": row.get("fiber_100g"),
                "salt_100g": row.get("salt_100g"),
                "saturated-fat_100g": row.get("saturated-fat_100g"),
                "vitamin-c_100g": row.get("vitamin-c_100g"),
            },
        }

    def select_top_foods(self, foods, target_size, allow_non_english_names):
        # 先按健康分排序，再做去重和家族上限，保证 Top 100 不被同类食品刷屏。
        seen = set()
        family_counts = {}
        ranked = []
        for food in sorted(foods, key=food_rank_key, reverse=True):
            name_key = dedup_key(food.get("displayName"))
            if not name_key or name_key in seen:
                continue

            if not allow_non_english_names and not is_likely_english_name(food.get("displayName")):
                continue

            family = family_key(food.get("displayName"))
            if family:
                current_count = family_counts.get(family, 0)
                if current_count >= FAMILY_LIMITS[family]:
                    continue

            seen.add(name_key)
            if family:
                family_counts[family] = family_counts.get(family, 0) + 1

            food["rank"] = len(ranked) + 1
            ranked.append(food)

            if len(ranked) == target_size:
                break

        return ranked

    def write_cleaned_csv(self, output_path, foods):
        with output_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for food in foods:
                nutrients = food.get("nutrients") or {}
                metadata = food.get("metadata") or {}
                writer.writerow(
                    {
                        "rank": food.get("rank"),
                        "code": metadata.get("openFoodFactsCode"),
                        "display_name": food.get("displayName"),
                        "product_name": metadata.get("productName") or food.get("name"),
                        "category": food.get("category"),
                        "category_tags": ",".join(metadata.get("categoryTags") or []),
                        "brand": metadata.get("brand"),
                        "countries": food.get("origin", {}).get("label"),
                        "origins": metadata.get("openFoodFactsOrigin"),
                        "manufacturing_places": "",
                        "nutri_score_grade": metadata.get("nutriScoreGrade"),
                        "nutri_score": metadata.get("nutriScore"),
                        "nova_group": metadata.get("novaGroup"),
                        "health_score": food.get("healthScore"),
                        "calories_100g": nutrients.get("calories"),
                        "protein_100g": nutrients.get("protein"),
                        "fat_100g": nutrients.get("fat"),
                        "carbohydrates_100g": nutrients.get("carbohydrates"),
                        "sugar_100g": nutrients.get("sugar"),
                        "fiber_100g": nutrients.get("fiber"),
                        "salt_100g": nutrients.get("salt"),
                        "saturated_fat_100g": nutrients.get("saturatedFat"),
                        "image_url": metadata.get("imageUrl"),
                    }
                )


def split_tags(value):
    if not value:
        return []

    return [item.strip() for item in value.split(",") if item.strip()]


def dedup_key(display_name):
    # Ignore processing/state words when comparing names, while preserving
    # variety words such as red, black, navy, pinto, great northern, or golden.
    text = (display_name or "").lower()
    text = text.replace("-", " ")
    text = "".join(character if character.isalnum() or character.isspace() else " " for character in text)
    words = [word for word in text.split() if word not in DEDUP_MODIFIER_TERMS]

    singular_words = []
    for word in words:
        if word in {"garbanzo", "chana"}:
            word = "chickpea"
        elif word in {"flaxseed", "flaxseeds", "linseed", "linseeds"}:
            word = "flax"
        elif word.endswith("ies") and len(word) > 4:
            word = f"{word[:-3]}y"
        elif word.endswith("s") and len(word) > 3:
            word = word[:-1]
        singular_words.append(word)

    if "lentil" in singular_words:
        singular_words = [word for word in singular_words if word != "bean"]

    return " ".join(singular_words)


def is_clean_display_name(display_name, allow_non_english_names=False):
    # 新版 CSV 允许非英文商品名；旧版 CSV 仍可启用英文/语言提示词过滤。
    if not allow_non_english_names and not is_likely_english_name(display_name):
        return False

    text = (display_name or "").lower()
    text = text.replace("-", " ")
    words = {word.strip(".,()#'\"") for word in text.split()}
    reject_terms = set(DISPLAY_REJECT_TERMS)
    if not allow_non_english_names:
        reject_terms.update(LANGUAGE_REJECT_TERMS)

    return not words.intersection(reject_terms)


def food_rank_key(food):
    display_name = food.get("displayName") or ""
    # Keep nutrition as the primary sort, then prefer cleaner generic names
    # over brand/process-heavy variants inside otherwise similar candidates.
    return (
        food.get("healthScore") or 0,
        -name_modifier_count(display_name),
        -len(display_name),
    )


def name_modifier_count(display_name):
    text = (display_name or "").lower().replace("-", " ")
    words = [word.strip(".,()#'\"") for word in text.split()]
    return sum(1 for word in words if word in DEDUP_MODIFIER_TERMS)


def family_key(display_name):
    text = (display_name or "").lower()
    text = text.replace("-", " ")
    words = {word.strip(".,()#'\"") for word in text.split()}

    # Family caps keep the top 100 visually and nutritionally varied without
    # deleting legitimate varieties inside a family.
    if words.intersection({"lentil", "lentils"}):
        return "lentils"
    if words.intersection({"bean", "beans", "haricot", "haricots", "chickpea", "chickpeas", "garbanzo", "chana"}):
        return "beans"
    if words.intersection({"pea", "peas"}):
        return "peas"
    if words.intersection({"flax", "flaxseed", "flaxseeds", "linseed", "linseeds", "lino"}):
        return "flax"
    if words.intersection({"chia"}):
        return "chia"
    if words.intersection({"sunflower", "tournesol"}):
        return "sunflower"
    if words.intersection({"oat", "oats", "avena"}):
        return "oats"
    if words.intersection({"rice"}):
        return "rice"
    if words.intersection({"mushroom", "mushrooms"}):
        return "mushrooms"

    return None
