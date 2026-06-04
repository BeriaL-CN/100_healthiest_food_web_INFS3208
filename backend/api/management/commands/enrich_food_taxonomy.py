import csv
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError

from api.food_formatters import origin_position_for_label, primary_origin_label


DEFAULT_INPUT = Path(__file__).resolve().parents[5] / "data" / "openfoodfacts_cleaned_foods_local_language.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[5] / "data" / "openfoodfacts_taxonomy_enriched_foods.csv"
OFF_CATEGORIES_URL = "https://world.openfoodfacts.org/categories.json"
WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "INFS3208-healthiest-food-map/1.0 (local manual data sync)"
EXTRA_COLUMNS = [
    "taxonomy_id",
    "taxonomy_name",
    "wikidata_qid",
    "wikidata_label",
    "wikidata_origin_label",
    "wikidata_origin_lat",
    "wikidata_origin_lng",
    "mapped_origin_label",
    "mapped_origin_lat",
    "mapped_origin_lng",
    "mapped_origin_source",
    "enrichment_source",
]


class Command(BaseCommand):
    help = "Enrich a cleaned Open Food Facts CSV with OFF taxonomy and Wikidata fields."

    def add_arguments(self, parser):
        parser.add_argument("--input", default=str(DEFAULT_INPUT))
        parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
        parser.add_argument("--timeout", type=int, default=30)

    def handle(self, *args, **options):
        input_path = Path(options["input"])
        output_path = Path(options["output"])
        timeout = options["timeout"]

        if not input_path.exists():
            raise CommandError(f"Cleaned CSV was not found: {input_path}")

        rows = read_csv_rows(input_path)
        if not rows:
            raise CommandError("Cleaned CSV has no rows to enrich.")

        self.stdout.write("Fetching Open Food Facts category taxonomy...")
        taxonomy = fetch_off_category_taxonomy(timeout)

        enriched_rows, qids = attach_taxonomy(rows, taxonomy)
        missing_qid_names = {
            row["taxonomy_name"]
            for row in enriched_rows
            if row.get("taxonomy_name") and not row.get("wikidata_qid")
        }
        if missing_qid_names:
            self.stdout.write(f"Searching Wikidata QIDs for {len(missing_qid_names)} fallback names...")
            searched_qids = fetch_wikidata_search_qids(missing_qid_names, timeout)
            for row in enriched_rows:
                if not row.get("wikidata_qid") and row.get("taxonomy_name") in searched_qids:
                    row["wikidata_qid"] = searched_qids[row["taxonomy_name"]]
                    row["enrichment_source"] = "display-name+wikidata-search"
                    qids.add(row["wikidata_qid"])

        if qids:
            self.stdout.write(f"Fetching Wikidata origin data for {len(qids)} taxonomy entities...")
            wikidata_rows = fetch_wikidata_origins(qids, timeout)
            attach_wikidata(enriched_rows, wikidata_rows)

        attach_mapped_origins(enriched_rows)
        write_csv(output_path, enriched_rows, rows[0].keys())
        self.stdout.write(self.style.SUCCESS(f"Saved {len(enriched_rows)} enriched foods to {output_path}"))


def read_csv_rows(path):
    # 读取本地清洗结果；外部 API 只用于补充 taxonomy/Wikidata，不重新下载产品数据。
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def fetch_json(url, timeout):
    # OFF/Wikidata 都要求合理 User-Agent，避免匿名脚本式访问影响公共服务。
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_off_category_taxonomy(timeout):
    try:
        data = fetch_json(OFF_CATEGORIES_URL, timeout)
    except (HTTPError, URLError, TimeoutError) as error:
        # OFF taxonomy 服务临时 503 时不中断流程，后面改用 CSV 显示名/Wikidata 搜索兜底。
        print(f"Open Food Facts taxonomy fetch failed; falling back to local names: {error}")
        return {}

    tags = data.get("tags") or []
    return {tag.get("id"): tag for tag in tags if tag.get("id")}


def attach_taxonomy(rows, taxonomy):
    # 从最具体的 category tag 往前找 taxonomy，优先选有 Wikidata 链接的实体。
    qids = set()
    enriched_rows = []
    for row in rows:
        category_tags = [tag.strip() for tag in (row.get("category_tags") or "").split(",") if tag.strip()]
        taxonomy_entry = best_taxonomy_entry(category_tags, taxonomy)
        fallback_name = row.get("display_name") or row.get("product_name") or row.get("category")
        linkeddata = (taxonomy_entry or {}).get("linkeddata") or {}
        qid = linkeddata.get("wikidata:en") or linkeddata.get("wikidata")

        enriched = {
            **row,
            "taxonomy_id": (taxonomy_entry or {}).get("id"),
            "taxonomy_name": (taxonomy_entry or {}).get("name") or fallback_name,
            "wikidata_qid": qid,
            "wikidata_label": "",
            "wikidata_origin_label": "",
            "wikidata_origin_lat": "",
            "wikidata_origin_lng": "",
            "enrichment_source": "off-taxonomy" if taxonomy_entry else "",
        }
        if qid:
            qids.add(qid)

        enriched_rows.append(enriched)

    return enriched_rows, qids


def best_taxonomy_entry(category_tags, taxonomy):
    for tag in reversed(category_tags):
        entry = taxonomy.get(tag)
        if entry and ((entry.get("linkeddata") or {}).get("wikidata:en") or (entry.get("linkeddata") or {}).get("wikidata")):
            return entry

    for tag in reversed(category_tags):
        if tag in taxonomy:
            return taxonomy[tag]

    fallback_tag = best_local_category_tag(category_tags)
    if fallback_tag:
        return {
            "id": fallback_tag,
            "name": label_from_category_tag(fallback_tag),
            "linkeddata": {},
        }

    return None


def best_local_category_tag(category_tags):
    for tag in reversed(category_tags):
        if tag.startswith("en:"):
            return tag

    return category_tags[-1] if category_tags else None


def label_from_category_tag(tag):
    label = (tag or "").split(":", 1)[-1]
    label = label.replace("-", " ").strip()
    return label[:1].upper() + label[1:]


def fetch_wikidata_origins(qids, timeout):
    values = " ".join(f"wd:{qid}" for qid in sorted(qids) if re.fullmatch(r"Q[0-9]+", qid or ""))
    if not values:
        return {}

    query = f"""
    SELECT ?item ?itemLabel ?originLabel ?coord WHERE {{
      VALUES ?item {{ {values} }}
      OPTIONAL {{
        ?item (wdt:P495|wdt:P1071|wdt:P276) ?origin .
        OPTIONAL {{ ?origin wdt:P625 ?coord . }}
      }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    url = f"{WIKIDATA_SPARQL_URL}?{urlencode({'query': query, 'format': 'json'})}"
    data = fetch_json(url, timeout)
    results = {}
    for binding in data.get("results", {}).get("bindings", []):
        qid = binding.get("item", {}).get("value", "").rsplit("/", 1)[-1]
        if not qid:
            continue

        current = results.setdefault(qid, {})
        current.setdefault("wikidata_label", binding.get("itemLabel", {}).get("value", ""))
        if binding.get("originLabel"):
            current["wikidata_origin_label"] = binding["originLabel"]["value"]
        if binding.get("coord"):
            current["position"] = parse_wikidata_point(binding["coord"]["value"])

    return results


def fetch_wikidata_search_qids(names, timeout):
    # 旧 CSV 没有 taxonomy tag 时，用显示名搜索 Wikidata；这是手动离线同步，不在前端运行。
    results = {}
    for name in sorted(names):
        query = {
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "format": "json",
            "limit": 1,
        }
        try:
            data = fetch_json(f"{WIKIDATA_SEARCH_URL}?{urlencode(query)}", timeout)
        except (HTTPError, URLError, TimeoutError):
            continue

        matches = data.get("search") or []
        if matches and matches[0].get("id"):
            results[name] = matches[0]["id"]

    return results


def parse_wikidata_point(value):
    # Wikidata 坐标格式是 Point(longitude latitude)，前端地图需要 lat/lng。
    match = re.fullmatch(r"Point\\(([-0-9.]+) ([-0-9.]+)\\)", value or "")
    if not match:
        return None

    longitude, latitude = match.groups()
    return [latitude, longitude]


def attach_wikidata(rows, wikidata_rows):
    for row in rows:
        qid = row.get("wikidata_qid")
        wikidata = wikidata_rows.get(qid) or {}
        position = wikidata.get("position") or ["", ""]
        row["wikidata_label"] = wikidata.get("wikidata_label", "")
        row["wikidata_origin_label"] = wikidata.get("wikidata_origin_label", "")
        row["wikidata_origin_lat"] = position[0]
        row["wikidata_origin_lng"] = position[1]
        if wikidata:
            row["enrichment_source"] = "off-taxonomy+wikidata"


def attach_mapped_origins(rows):
    # 给最终 CSV 增加统一地图字段：Wikidata 优先，OFF origins/countries 兜底。
    for row in rows:
        origin_label = (
            row.get("wikidata_origin_label")
            or row.get("origins")
            or row.get("countries")
        )
        source = (
            "wikidata-origin"
            if row.get("wikidata_origin_label")
            else "openfoodfacts-origin"
            if row.get("origins")
            else "openfoodfacts-country"
            if row.get("countries")
            else ""
        )

        mapped_label = primary_origin_label(origin_label)
        position = None
        if row.get("wikidata_origin_lat") and row.get("wikidata_origin_lng"):
            position = [row["wikidata_origin_lat"], row["wikidata_origin_lng"]]
        else:
            position = origin_position_for_label(mapped_label, None)

        row["mapped_origin_label"] = mapped_label or ""
        row["mapped_origin_lat"] = position[0] if position else ""
        row["mapped_origin_lng"] = position[1] if position else ""
        row["mapped_origin_source"] = source


def write_csv(path, rows, base_columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(base_columns) + [column for column in EXTRA_COLUMNS if column not in base_columns]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
