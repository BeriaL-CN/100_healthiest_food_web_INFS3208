#!/usr/bin/env python3
"""
Prepare local data caches for deployment.

This script wraps the Django management commands so deployment only needs one
Python entry point. External data access is still explicit: Open Food Facts is
used to build the main food cache, while Wikidata origin enrichment is opt-in.
"""

import argparse
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
FOOD_DB_PATH = BACKEND_DIR / "data" / "foods.sqlite3"


def run_manage_command(args):
    command = [sys.executable, "manage.py", *args]
    print(f"Running: {' '.join(command)}")
    subprocess.run(command, cwd=BACKEND_DIR, check=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare local SQLite data caches.")
    parser.add_argument("--target-size", type=int, default=100)
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--skip-if-exists", action="store_true")
    parser.add_argument("--with-wikidata", action="store_true")
    parser.add_argument("--wikidata-limit", type=int, default=100)
    parser.add_argument("--wikidata-sleep", type=float, default=1.0)
    return parser.parse_args()


def main():
    args = parse_args()

    if args.skip_if_exists and FOOD_DB_PATH.exists():
        print(f"Skipping Open Food Facts sync because {FOOD_DB_PATH} already exists.")
    else:
        run_manage_command(
            [
                "sync_openfoodfacts",
                "--target-size",
                str(args.target_size),
                "--page-size",
                str(args.page_size),
                "--max-pages",
                str(args.max_pages),
            ]
        )

    if args.with_wikidata:
        # Wikidata is kept opt-in because it uses the public SPARQL endpoint and
        # should be refreshed intentionally, not on every deployment by default.
        run_manage_command(
            [
                "sync_wikidata_origins",
                "--limit",
                str(args.wikidata_limit),
                "--sleep",
                str(args.wikidata_sleep),
            ]
        )
    else:
        print("Skipping Wikidata origin sync. Use --with-wikidata to enable it.")


if __name__ == "__main__":
    main()
