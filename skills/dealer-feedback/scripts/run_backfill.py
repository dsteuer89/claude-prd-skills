#!/usr/bin/env python3
# /// script
# dependencies = [
#   "snowflake-connector-python",
#   "anthropic",
# ]
# ///
"""
Full backfill pipeline: extract Gong conversations from Snowflake, classify
with Claude API, and output per-product analysis JSON files.

Usage:
  uv run run_backfill.py [--extract-limit=1000] [--classify-limit=0] [--batch-size=20] [--output-dir=/tmp/dealer-feedback/backfill] [--products=all] [--skip-extract] [--skip-classify]

Args:
  --extract-limit=N: Max conversations to extract per product from Snowflake (default 1000)
  --classify-limit=N: Max transcripts to classify per product, 0=all (default 0)
  --batch-size=N: Transcripts per Claude API call (default 20)
  --output-dir=PATH: Base output directory (default /tmp/dealer-feedback/backfill)
  --products=LIST: Comma-separated product names to process, or "all" (default all)
  --skip-extract: Skip extraction, use existing CSVs
  --skip-classify: Skip classification (extract only)
  --since=TIMESTAMP: Only extract conversations after this date (default 2020-01-01)
"""

import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_FILE = os.path.join(SCRIPT_DIR, "products.json")
EXTRACT_SCRIPT = os.path.join(SCRIPT_DIR, "extract_conversations.py")
CLASSIFY_SCRIPT = os.path.join(SCRIPT_DIR, "classify_batch.py")


def load_products():
    with open(PRODUCTS_FILE) as f:
        data = json.load(f)

    products = {}
    for pillar_name, pillar_products in data.get("pillars", {}).items():
        for product_name, product_config in pillar_products.items():
            if product_config.get("tracker_patterns"):
                products[product_name] = {
                    "pillar": pillar_name,
                    "tracker_patterns": product_config["tracker_patterns"],
                    "page_id": product_config.get("page_id"),
                }

    for product_name, product_config in data.get("cross_cutting", {}).items():
        if product_config.get("tracker_patterns"):
            products[product_name] = {
                "pillar": "Cross-Cutting",
                "tracker_patterns": product_config["tracker_patterns"],
                "page_id": product_config.get("page_id"),
            }

    return products


def slugify(name):
    return name.lower().replace(" ", "-").replace("/", "-").replace(".", "")


def extract_product(product_name, config, output_dir, limit, since):
    slug = slugify(product_name)
    csv_path = os.path.join(output_dir, f"{slug}.csv")
    patterns = ",".join(config["tracker_patterns"])

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"EXTRACT: {product_name} ({patterns})", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    cmd = [
        "uv", "run", EXTRACT_SCRIPT,
        patterns, since, str(limit), csv_path,
        "--sort=mentions",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"  EXTRACT FAILED for {product_name}", file=sys.stderr)
        return None

    if not os.path.exists(csv_path):
        return None

    with open(csv_path) as f:
        row_count = sum(1 for _ in f) - 1

    if row_count <= 0:
        print(f"  No conversations found for {product_name}", file=sys.stderr)
        return None

    print(f"  Extracted {row_count} conversations", file=sys.stderr)
    return csv_path


def classify_product(product_name, csv_path, output_dir, batch_size, max_rows):
    slug = slugify(product_name)
    json_path = os.path.join(output_dir, "analysis", f"{slug}.json")

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"CLASSIFY: {product_name}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    cmd = [
        "uv", "run", CLASSIFY_SCRIPT,
        csv_path, product_name, json_path,
        f"--batch-size={batch_size}",
    ]
    if max_rows > 0:
        cmd.append(f"--max-rows={max_rows}")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"  CLASSIFY FAILED for {product_name}", file=sys.stderr)
        return None

    return json_path


def main():
    extract_limit = 1000
    classify_limit = 0
    batch_size = 20
    output_dir = "/tmp/dealer-feedback/backfill"
    product_filter = "all"
    skip_extract = False
    skip_classify = False
    since = "2020-01-01T00:00:00Z"

    for arg in sys.argv[1:]:
        if arg.startswith("--extract-limit="):
            extract_limit = int(arg.split("=", 1)[1])
        elif arg.startswith("--classify-limit="):
            classify_limit = int(arg.split("=", 1)[1])
        elif arg.startswith("--batch-size="):
            batch_size = int(arg.split("=", 1)[1])
        elif arg.startswith("--output-dir="):
            output_dir = arg.split("=", 1)[1]
        elif arg.startswith("--products="):
            product_filter = arg.split("=", 1)[1]
        elif arg == "--skip-extract":
            skip_extract = True
        elif arg == "--skip-classify":
            skip_classify = True
        elif arg.startswith("--since="):
            since = arg.split("=", 1)[1]

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "analysis"), exist_ok=True)

    products = load_products()

    if product_filter != "all":
        requested = [p.strip() for p in product_filter.split(",")]
        products = {k: v for k, v in products.items() if k in requested}

    print(f"Products to process: {list(products.keys())}", file=sys.stderr)
    print(f"Extract limit: {extract_limit} | Classify limit: {classify_limit or 'all'} | Batch size: {batch_size}", file=sys.stderr)

    results = {}

    for product_name, config in products.items():
        slug = slugify(product_name)
        csv_path = os.path.join(output_dir, f"{slug}.csv")

        if not skip_extract:
            csv_path = extract_product(product_name, config, output_dir, extract_limit, since)
            if not csv_path:
                results[product_name] = {"status": "no_data"}
                continue

        if skip_classify:
            results[product_name] = {"status": "extracted", "csv": csv_path}
            continue

        if not os.path.exists(csv_path):
            print(f"  No CSV found for {product_name} at {csv_path}", file=sys.stderr)
            results[product_name] = {"status": "no_csv"}
            continue

        json_path = classify_product(product_name, csv_path, output_dir, batch_size, classify_limit)
        if json_path and os.path.exists(json_path):
            with open(json_path) as f:
                analysis = json.load(f)
            results[product_name] = {
                "status": "complete",
                "csv": csv_path,
                "json": json_path,
                "transcripts_analyzed": analysis["transcripts_analyzed"],
                "feedback_count": analysis["feedback_count"],
                "themes": len(analysis["themes"]),
            }
        else:
            results[product_name] = {"status": "classify_failed"}

    print(f"\n{'='*60}", file=sys.stderr)
    print("BACKFILL SUMMARY", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    total_analyzed = 0
    total_feedback = 0
    total_themes = 0

    for name, r in results.items():
        status = r["status"]
        if status == "complete":
            total_analyzed += r["transcripts_analyzed"]
            total_feedback += r["feedback_count"]
            total_themes += r["themes"]
            print(f"  {name}: {r['transcripts_analyzed']} analyzed, "
                  f"{r['feedback_count']} feedback, {r['themes']} themes", file=sys.stderr)
        else:
            print(f"  {name}: {status}", file=sys.stderr)

    print(f"\nTOTAL: {total_analyzed} analyzed, {total_feedback} feedback, {total_themes} themes", file=sys.stderr)

    summary_path = os.path.join(output_dir, "backfill_summary.json")
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSummary written to {summary_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
