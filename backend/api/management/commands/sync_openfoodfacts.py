import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError

from api.food_formatters import format_openfoodfacts_product, is_likely_english_name
from api.food_store import FOOD_DB_PATH, replace_cleaned_foods


OFF_SEARCH_URL = "https://world.openfoodfacts.org/api/v2/search"
SIMPLE_FOOD_CATEGORIES = [
    "Fruits",
    "Fresh fruits",
    "Vegetables",
    "Fresh vegetables",
    "Legumes",
    "Lentils",
    "Beans",
    "Nuts",
    "Seeds",
    "Cereals and grains",
    "Rice",
    "Oats",
    "Fish",
    "Seafood",
    "Herbs",
    "Spices",
]
FIELDS = [
    "code",
    "product_name",
    "generic_name",
    "brands",
    "quantity",
    "categories_tags",
    "categories_tags_en",
    "countries_tags",
    "countries_tags_en",
    "nutrition_grades",
    "nutriscore_score",
    "nova_group",
    "nutriments",
    "image_front_url",
    "image_url",
]


class Command(BaseCommand):
    help = "Fetch Nutri-Score A products from Open Food Facts, clean them, and store a local SQLite index."

    def add_arguments(self, parser):
        parser.add_argument("--target-size", type=int, default=100)
        parser.add_argument("--page-size", type=int, default=30)
        parser.add_argument("--max-pages", type=int, default=2)
        parser.add_argument("--sleep", type=float, default=7.0)
        parser.add_argument(
            "--categories",
            default=",".join(SIMPLE_FOOD_CATEGORIES),
            help="Comma-separated Open Food Facts categories to search.",
        )

    def handle(self, *args, **options):
        target_size = options["target_size"]
        page_size = options["page_size"]
        max_pages = options["max_pages"]
        sleep_seconds = options["sleep"]
        categories = [category.strip() for category in options["categories"].split(",") if category.strip()]

        if target_size <= 0:
            raise CommandError("--target-size must be greater than 0")

        self.stdout.write(
            f"Fetching simple Nutri-Score A foods from Open Food Facts "
            f"(target={target_size}, categories={len(categories)}, page_size={page_size}, max_pages={max_pages})"
        )

        candidates = []
        for category in categories:
            page = 1
            while max_pages == 0 or page <= max_pages:
                # Search API results are used only during sync. Runtime requests
                # read SQLite so the frontend never depends on Open Food Facts.
                payload = self.fetch_page(category, page, page_size)
                products = payload.get("products") or []
                if not products:
                    break

                candidates.extend(format_openfoodfacts_product(product) for product in products)
                self.stdout.write(f"Fetched {category}, page {page}: {len(products)} products")

                if len(candidates) >= target_size * 4:
                    break

                # Keep requests deliberately spaced out for the public API.
                page += 1
                time.sleep(sleep_seconds)

            if len(candidates) >= target_size * 4:
                break

        if not candidates:
            raise CommandError("Open Food Facts returned no products to clean.")

        cleaned = self.select_top_foods(candidates, target_size)
        replace_cleaned_foods(cleaned)

        self.stdout.write(
            self.style.SUCCESS(
                f"Saved {len(cleaned)} cleaned foods to {FOOD_DB_PATH}"
            )
        )

    def fetch_page(self, category, page, page_size):
        # Limit fields to the data needed for cleaning and display; this keeps
        # each cached sync smaller and easier to inspect.
        query = urlencode(
            {
                "categories_tags_en": category,
                "nutrition_grades_tags": "a",
                "nova_groups_tags": "1,2,3",
                "fields": ",".join(FIELDS),
                "page": page,
                "page_size": page_size,
                "json": 1,
            }
        )
        request = Request(
            f"{OFF_SEARCH_URL}?{query}",
            headers={
                "User-Agent": (
                    "INFS3208HealthiestFoodProject/1.0 "
                    "(student project; local cache sync)"
                )
            },
        )

        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def select_top_foods(self, foods, target_size):
        # De-duplicate by display name so one branded product cannot dominate
        # the list with repeated package variants.
        seen = set()
        ranked = []
        for food in sorted(foods, key=lambda item: item.get("healthScore") or 0, reverse=True):
            name_key = food["displayName"].strip().lower()
            if not name_key or name_key in seen or not is_likely_english_name(food.get("displayName")):
                continue

            seen.add(name_key)
            food["rank"] = len(ranked) + 1
            ranked.append(food)

            if len(ranked) == target_size:
                break

        return ranked
