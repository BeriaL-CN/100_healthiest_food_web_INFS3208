import csv
import gzip
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


DEFAULT_LOCAL = Path(__file__).resolve().parents[5] / "data" / "top_100_fruits.csv"
DEFAULT_OFF = Path(__file__).resolve().parents[5] / "data" / "en.openfoodfacts.org.products.csv.gz"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[5] / "data" / "top_100_fruits_off_enriched.csv"
csv.field_size_limit(64 * 1024 * 1024)

COMPLEX_TERMS = {
    "blend",
    "bread",
    "butter",
    "cake",
    "cereal",
    "chocolate",
    "creamer",
    "crispbread",
    "dessert",
    "fillet",
    "fillets",
    "flour",
    "meal",
    "muesli",
    "noodle",
    "pasta",
    "penne",
    "pita",
    "pizza",
    "prepared",
    "ready",
    "risotto",
    "sauce",
    "snack",
    "soup",
    "sweet",
}
EXTRA_COLUMNS = [
    "OFF Code",
    "OFF Product Name",
    "OFF Generic Name",
    "OFF Category",
    "OFF Brand",
    "OFF Nutri-Score Grade",
    "OFF Nutri-Score",
    "OFF NOVA Group",
    "OFF Fat (g)",
    "OFF Carbohydrates (g)",
    "OFF Sugar (g)",
    "OFF Salt (g)",
    "OFF Saturated Fat (g)",
    "OFF Image URL",
    "OFF Match Score",
    "OFF Match Method",
]


class Command(BaseCommand):
    help = "Enrich the Kaggle local food CSV with matching Open Food Facts nutrition rows."

    def add_arguments(self, parser):
        parser.add_argument("--local", default=str(DEFAULT_LOCAL))
        parser.add_argument("--off", default=str(DEFAULT_OFF))
        parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
        parser.add_argument("--scan-limit", type=int, default=0)

    def handle(self, *args, **options):
        local_path = Path(options["local"])
        off_path = Path(options["off"])
        output_path = Path(options["output"])
        scan_limit = options["scan_limit"]

        if not local_path.exists():
            raise CommandError(f"Local Kaggle CSV was not found: {local_path}")
        if not off_path.exists():
            raise CommandError(f"Open Food Facts bulk file was not found: {off_path}")

        local_rows = read_local_rows(local_path)
        matchers = build_matchers(local_rows)
        best_matches = scan_openfoodfacts(off_path, matchers, scan_limit, self.stdout)
        enriched_rows = attach_matches(local_rows, matchers, best_matches)
        write_output(output_path, enriched_rows, local_rows[0].keys())

        matched_count = sum(1 for row in enriched_rows if row.get("OFF Code"))
        self.stdout.write(self.style.SUCCESS(f"Saved {len(enriched_rows)} foods to {output_path}"))
        self.stdout.write(self.style.SUCCESS(f"Matched {matched_count} foods with Open Food Facts rows"))


def read_local_rows(path):
    # Kaggle CSV 是主数据源，OFF 只补缺失营养字段，不替换食品名/原产地。
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def normalise_text(value):
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def singularise(word):
    if word.endswith("ies") and len(word) > 4:
        return f"{word[:-3]}y"
    if word.endswith("s") and len(word) > 3:
        return word[:-1]
    return word


def build_matchers(local_rows):
    matchers = []
    for index, row in enumerate(local_rows):
        name = row.get("Food") or ""
        words = [singularise(word) for word in normalise_text(name).split()]
        significant_words = [word for word in words if len(word) > 2]
        matchers.append(
            {
                "index": index,
                "name": name,
                "key": " ".join(significant_words),
                "words": set(significant_words),
            }
        )

    return matchers


def build_word_index(matchers):
    index = {}
    for matcher in matchers:
        for word in matcher["words"]:
            index.setdefault(word, set()).add(matcher["index"])

    return index


def scan_openfoodfacts(path, matchers, scan_limit, stdout):
    best_matches = {}
    matcher_by_index = {matcher["index"]: matcher for matcher in matchers}
    word_index = build_word_index(matchers)
    scanned = 0
    with gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")
        for row in reader:
            scanned += 1
            if scan_limit and scanned > scan_limit:
                break

            if is_complex_row(row):
                continue

            searchable = normalise_text(
                " ".join(
                    [
                        row.get("product_name") or "",
                        row.get("generic_name") or "",
                    ]
                )
            )
            category_text = normalise_text(row.get("categories_en") or "")
            searchable_words = {singularise(word) for word in searchable.split()}
            category_words = {singularise(word) for word in category_text.split()}
            if not searchable_words:
                continue

            candidate_indexes = set()
            for word in searchable_words.union(category_words):
                candidate_indexes.update(word_index.get(word, set()))

            for matcher_index in candidate_indexes:
                matcher = matcher_by_index[matcher_index]
                score = score_match(matcher, row, searchable, searchable_words, category_text, category_words)
                if score <= 0:
                    continue

                current = best_matches.get(matcher["index"])
                if not current or score > current["score"]:
                    best_matches[matcher["index"]] = {"score": score, "row": row}

            if scanned % 500000 == 0:
                stdout.write(f"Scanned {scanned:,} Open Food Facts rows; matched {len(best_matches)} local foods")

    stdout.write(f"Scanned {scanned:,} Open Food Facts rows; matched {len(best_matches)} local foods")
    return best_matches


def is_complex_row(row):
    text = normalise_text(
        " ".join(
            [
                row.get("product_name") or "",
                row.get("generic_name") or "",
                row.get("categories_en") or "",
                row.get("food_groups_en") or "",
            ]
        )
    )
    return any(term in text.split() for term in COMPLEX_TERMS)


def score_match(matcher, row, searchable, searchable_words, category_text, category_words):
    if not matcher["words"]:
        return 0

    if matcher["key"] and re.search(rf"\b{re.escape(matcher['key'])}\b", searchable):
        score = 100
    elif matcher["words"].issubset(searchable_words):
        score = 85
    elif matcher["key"] and re.search(rf"\b{re.escape(matcher['key'])}\b", category_text):
        score = 65
    elif matcher["words"].issubset(category_words):
        score = 55
    elif len(matcher["words"]) == 1 and matcher["words"].intersection(searchable_words):
        score = 45
    else:
        return 0

    score += nutrition_completeness(row) * 3
    score += nutriscore_bonus(row.get("nutriscore_grade"))
    score += nova_bonus(row.get("nova_group"))
    score -= brand_penalty(row)
    score -= extra_word_penalty(matcher, row)
    return score


def nutrition_completeness(row):
    keys = [
        "fat_100g",
        "carbohydrates_100g",
        "sugars_100g",
        "salt_100g",
        "saturated-fat_100g",
        "fiber_100g",
        "proteins_100g",
        "energy-kcal_100g",
    ]
    return sum(bool(row.get(key)) for key in keys)


def nutriscore_bonus(grade):
    grade = (grade or "").lower()
    return {"a": 12, "b": 8, "c": 3, "d": -5, "e": -10}.get(grade, 0)


def nova_bonus(value):
    try:
        nova = int(float(value))
    except (TypeError, ValueError):
        return 0

    return {1: 10, 2: 5, 3: 0, 4: -12}.get(nova, 0)


def brand_penalty(row):
    name = normalise_text(row.get("product_name"))
    generic = normalise_text(row.get("generic_name"))
    if generic and generic in name:
        return 0
    return 4 if row.get("brands") else 0


def extra_word_penalty(matcher, row):
    name_words = {
        singularise(word)
        for word in normalise_text(row.get("product_name") or row.get("generic_name")).split()
        if len(word) > 2
    }
    extras = name_words.difference(matcher["words"])
    return min(len(extras) * 15, 60)


def attach_matches(local_rows, matchers, best_matches):
    enriched_rows = []
    for matcher, row in zip(matchers, local_rows):
        match = best_matches.get(matcher["index"])
        enriched = {**row}
        if match:
            off = match["row"]
            enriched.update(
                {
                    "OFF Code": off.get("code"),
                    "OFF Product Name": off.get("product_name"),
                    "OFF Generic Name": off.get("generic_name"),
                    "OFF Category": off.get("categories_en"),
                    "OFF Brand": off.get("brands"),
                    "OFF Nutri-Score Grade": off.get("nutriscore_grade"),
                    "OFF Nutri-Score": off.get("nutriscore_score"),
                    "OFF NOVA Group": off.get("nova_group"),
                    "OFF Fat (g)": off.get("fat_100g"),
                    "OFF Carbohydrates (g)": off.get("carbohydrates_100g"),
                    "OFF Sugar (g)": off.get("sugars_100g"),
                    "OFF Salt (g)": off.get("salt_100g"),
                    "OFF Saturated Fat (g)": off.get("saturated-fat_100g"),
                    "OFF Image URL": off.get("image_url"),
                    "OFF Match Score": round(match["score"], 2),
                    "OFF Match Method": "local-name-to-openfoodfacts-bulk",
                }
            )
        else:
            enriched.update({column: "" for column in EXTRA_COLUMNS})

        enriched_rows.append(enriched)

    return enriched_rows


def write_output(path, rows, base_columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(base_columns) + [column for column in EXTRA_COLUMNS if column not in base_columns]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
