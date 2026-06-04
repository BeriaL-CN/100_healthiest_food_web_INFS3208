import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand

from api.food_store import load_cleaned_foods, upsert_wikidata_origin


WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"


class Command(BaseCommand):
    help = "Manually enrich cached foods with Wikidata origin/location data."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--sleep", type=float, default=1.0)
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Reserved for future cache-expiry logic; current command always updates matched rows.",
        )

    def handle(self, *args, **options):
        foods = load_cleaned_foods(limit=options["limit"])
        sleep_seconds = options["sleep"]

        if not foods:
            self.stdout.write(self.style.WARNING("No cleaned foods found. Run sync_openfoodfacts first."))
            return

        matched = 0
        for food in foods:
            # This command is intentionally manual. It is the only place that
            # should contact Wikidata; Django views only read cached SQLite rows.
            origin = self.lookup_origin(food["name"])
            if origin:
                upsert_wikidata_origin(food["id"], food["name"], origin)
                matched += 1
                self.stdout.write(f"Matched {food['name']} -> {origin['label']}")
            else:
                self.stdout.write(f"No Wikidata origin found for {food['name']}")

            time.sleep(sleep_seconds)

        self.stdout.write(self.style.SUCCESS(f"Cached Wikidata origins for {matched} foods."))

    def lookup_origin(self, food_name):
        query = self.build_query(food_name)
        request = Request(
            f"{WIKIDATA_SPARQL_URL}?{urlencode({'query': query, 'format': 'json'})}",
            headers={
                "Accept": "application/sparql-results+json",
                "User-Agent": (
                    "INFS3208HealthiestFoodProject/1.0 "
                    "(student project; manual origin cache sync)"
                ),
            },
        )

        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))

        bindings = payload.get("results", {}).get("bindings", [])
        if not bindings:
            return None

        return self.format_binding(bindings[0])

    def build_query(self, food_name):
        escaped_name = food_name.replace("\\", "\\\\").replace('"', '\\"')
        # P495 is country of origin; P1071 is location of creation. The optional
        # P625 coordinate on the origin entity is what lets the map display it.
        return f"""
        SELECT ?food ?foodLabel ?origin ?originLabel ?coord WHERE {{
          ?food rdfs:label "{escaped_name}"@en.
          ?food (wdt:P495|wdt:P1071) ?origin.
          OPTIONAL {{ ?origin wdt:P625 ?coord. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 1
        """

    def format_binding(self, binding):
        origin_uri = binding.get("origin", {}).get("value")
        qid = origin_uri.rsplit("/", 1)[-1] if origin_uri else None
        position = self.parse_wikidata_point(binding.get("coord", {}).get("value"))

        return {
            "label": binding.get("originLabel", {}).get("value"),
            "position": position,
            "wikidataQid": qid,
            "sourceUrl": origin_uri,
            "method": "wikidata-p495-p1071",
        }

    def parse_wikidata_point(self, value):
        if not value or not value.startswith("Point("):
            return None

        longitude, latitude = value.removeprefix("Point(").removesuffix(")").split()
        return [float(latitude), float(longitude)]
