import json
import sqlite3
from pathlib import Path

from django.conf import settings

from .food_formatters import ensure_display_fields


FOOD_DB_PATH = Path(settings.BASE_DIR) / "data" / "foods.sqlite3"


def connect_food_db(path=FOOD_DB_PATH):
    # SQLite 是前端运行时读取的轻量缓存，不在页面加载时请求外部 API。
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialise_food_db(connection):
    # Store the full cleaned JSON payload so the frontend contract can evolve
    # without needing a Django migration for every display-field change.
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS cleaned_foods (
            id TEXT PRIMARY KEY,
            rank INTEGER,
            name TEXT NOT NULL,
            category TEXT,
            source TEXT NOT NULL,
            health_score REAL,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cleaned_foods_rank
        ON cleaned_foods(rank, health_score DESC)
        """
    )
    # Wikidata enrichment is deliberately cached locally and refreshed only by a
    # manual command. Runtime API requests should never call the public endpoint.
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS wikidata_origins (
            food_id TEXT PRIMARY KEY,
            food_name TEXT NOT NULL,
            wikidata_qid TEXT,
            origin_label TEXT,
            latitude REAL,
            longitude REAL,
            source_url TEXT,
            raw_payload TEXT,
            synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()


def replace_cleaned_foods(foods, path=FOOD_DB_PATH):
    # A sync run is treated as a fresh snapshot of the cleaned top-food index.
    with connect_food_db(path) as connection:
        initialise_food_db(connection)
        connection.execute("DELETE FROM cleaned_foods")
        connection.executemany(
            """
            INSERT INTO cleaned_foods (
                id,
                rank,
                name,
                category,
                source,
                health_score,
                payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    food["id"],
                    food.get("rank"),
                    food["name"],
                    food.get("category"),
                    food["source"],
                    food.get("healthScore"),
                    json.dumps(food),
                )
                for food in foods
            ],
        )
        connection.commit()


def load_cleaned_foods(limit=100, path=FOOD_DB_PATH):
    # Missing database means the app can still run locally from the CSV fallback.
    if not path.exists():
        return []

    with connect_food_db(path) as connection:
        initialise_food_db(connection)
        rows = connection.execute(
            """
            SELECT payload
            FROM cleaned_foods
            ORDER BY COALESCE(rank, 999999), health_score DESC, name
            LIMIT ?
            """,
            (limit * 2,),
        ).fetchall()

    # 不在运行时按语言过滤；商品名可以保留原文，英文归一化交给 taxonomy enrichment CSV。
    foods = [ensure_display_fields(json.loads(row["payload"])) for row in rows]
    return foods[:limit]


def upsert_wikidata_origin(food_id, food_name, origin, path=FOOD_DB_PATH):
    # 手动同步 Wikidata 后写入缓存，地图请求只读本地结果。
    with connect_food_db(path) as connection:
        initialise_food_db(connection)
        connection.execute(
            """
            INSERT INTO wikidata_origins (
                food_id,
                food_name,
                wikidata_qid,
                origin_label,
                latitude,
                longitude,
                source_url,
                raw_payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(food_id) DO UPDATE SET
                food_name = excluded.food_name,
                wikidata_qid = excluded.wikidata_qid,
                origin_label = excluded.origin_label,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                source_url = excluded.source_url,
                raw_payload = excluded.raw_payload,
                synced_at = CURRENT_TIMESTAMP
            """,
            (
                food_id,
                food_name,
                origin.get("wikidataQid"),
                origin.get("label"),
                origin.get("position", [None, None])[0],
                origin.get("position", [None, None])[1],
                origin.get("sourceUrl"),
                json.dumps(origin),
            ),
        )
        connection.commit()


def load_wikidata_origins(path=FOOD_DB_PATH):
    if not path.exists():
        return {}

    with connect_food_db(path) as connection:
        initialise_food_db(connection)
        rows = connection.execute(
            """
            SELECT food_id, raw_payload
            FROM wikidata_origins
            WHERE raw_payload IS NOT NULL
            """
        ).fetchall()

    return {row["food_id"]: json.loads(row["raw_payload"]) for row in rows}


def merge_wikidata_origins(foods, origins_by_food_id):
    merged_foods = []
    for food in foods:
        origin = origins_by_food_id.get(food["id"])
        if not origin:
            merged_foods.append(food)
            continue

        merged = {
            **food,
            "origin": {
                **(food.get("origin") or {}),
                "wikidata": origin,
            },
        }

        # Prefer Wikidata coordinates for the map when the base data has no
        # exact position. Existing local CSV coordinates remain untouched.
        if origin.get("position") and not merged["origin"].get("position"):
            merged["origin"]["label"] = origin.get("label")
            merged["origin"]["position"] = origin.get("position")
            merged["origin"]["method"] = "wikidata-origin-cache"

        merged_foods.append(merged)

    return merged_foods
