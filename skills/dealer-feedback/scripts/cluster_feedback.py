#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
"""
Rule-based feedback classifier and theme clusterer.
Processes extracted Gong CSVs, classifies feedback vs noise using heuristics,
and clusters feedback transcripts into theme groups using keyword co-occurrence.

No LLM required — runs instantly on thousands of transcripts.

Usage:
  uv run cluster_feedback.py <input_csv> <product_name> <output_json> [--max-rows=0]
  uv run cluster_feedback.py --all <output_dir> [--max-rows=0]

The --all flag reads products.json and processes all CSVs in <output_dir>/*.csv
"""

import csv
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CATEGORIES = {
    "feature_request": {
        "label": "Feature Request",
        "patterns": [
            r'\b(?:I|we) wish\b', r'\b(?:I|we) need\b', r'\b(?:I|we) want\b',
            r'\bwould be (?:nice|great|helpful)\b', r'\bwould love\b',
            r'\bfeature request\b', r'\bwish list\b', r'\bmissing\b',
            r'\bshould (?:be able|have|let|allow)\b', r'\bcan you add\b',
            r'\bwhy can.t\b', r'\bno way to\b', r'\bwould help if\b',
        ],
    },
    "bug_issue": {
        "label": "Bug/Issue",
        "patterns": [
            r'\bdoesn.t work\b', r'\bnot working\b', r'\bbroken\b', r'\bbug\b',
            r'\berror\b', r'\bglitch\b', r'\bnot showing\b', r'\bnot syncing\b',
            r'\bwrong (?:price|number|data|info)\b', r'\bincorrect\b',
            r'\bnot (?:receiving|getting|seeing)\b', r'\bduplicate\b',
            r'\bspam\b', r'\bfake\b', r'\bnot loading\b', r'\btimeout\b',
        ],
    },
    "ux_friction": {
        "label": "UX Friction",
        "patterns": [
            r'\bconfusing\b', r'\bconfused\b', r'\bhard to\b', r'\bnot intuitive\b',
            r'\bcan.t figure\b', r'\bdon.t understand\b', r'\bdon.t know how\b',
            r'\bcomplicated\b', r'\boverwhelming\b', r'\bclunky\b',
            r'\bfrustrat', r'\bannoying\b', r'\bdifficult\b',
            r'\bdon.t (?:use|like)\b', r'\bnever use\b', r'\bnever log\b',
            r'\bdon.t log in\b',
        ],
    },
    "positive_signal": {
        "label": "Positive Signal",
        "patterns": [
            r'\blove (?:that|it|the|cargurus|this)\b', r'\bgreat (?:feature|tool|product)\b',
            r'\breally like\b', r'\bhelpful\b', r'\bawesome\b', r'\bimpressed\b',
            r'\bexcellent\b', r'\bfantastic\b', r'\bgreat job\b',
            r'\bworking (?:great|well|really)\b', r'\bhappy with\b',
            r'\bsee results\b', r'\bgetting results\b', r'\bsold .* cars?\b',
        ],
    },
    "competitive": {
        "label": "Competitive Comparison",
        "patterns": [
            r'\bautotrader\b', r'\bcars\.com\b', r'\bcarvana\b', r'\bcarfax\b',
            r'\bvauto\b', r'\bkbb\b', r'\bedmunds\b', r'\btruecar\b',
            r'\bfacebook (?:marketplace)?\b', r'\bmotors\.co\b',
            r'\bcompetitor\b', r'\bother (?:platform|site|vendor)\b',
            r'\bswitching to\b', r'\balternative\b',
        ],
    },
    "pricing_concern": {
        "label": "Pricing Concern",
        "patterns": [
            r'\btoo expensive\b', r'\bnot worth\b', r'\bcost(?:s|ing)?\b',
            r'\bprice increase\b', r'\brenewal\b', r'\bbudget\b',
            r'\bcan.t (?:afford|justify)\b', r'\bROI\b', r'\breturn on\b',
            r'\bworth it\b', r'\bvalue for\b', r'\boverpay\b', r'\boverpriced\b',
            r'\bcost per (?:lead|sale)\b', r'\bspend\b',
        ],
    },
    "adoption_barrier": {
        "label": "Adoption Barrier",
        "patterns": [
            r'\badopt', r'\bonboard', r'\btraining\b', r'\blearning curve\b',
            r'\bnever (?:used|tried|set up)\b', r'\bnot using\b',
            r'\bdon.t (?:use|log)\b', r'\brarely\b', r'\bnot (?:familiar|aware)\b',
            r'\bdidn.t know\b', r'\bno one (?:uses|told)\b',
            r'\bchurn\b', r'\bcancel', r'\bdowngrad',
        ],
    },
}

COMPILED_CATEGORIES = {}
for cat_key, cat_def in CATEGORIES.items():
    COMPILED_CATEGORIES[cat_key] = {
        "label": cat_def["label"],
        "patterns": [re.compile(p, re.IGNORECASE) for p in cat_def["patterns"]],
    }

THEME_KEYWORDS = {
    "deal_rating_imv": ["deal rating", "IMV", "instant market value", "great deal", "fair deal",
                         "overpriced", "high price", "price badge", "deal badge"],
    "lead_quality": ["lead quality", "fake lead", "spam lead", "tire kicker", "don't respond",
                     "don't answer", "unresponsive", "wrong number", "bad lead"],
    "lead_routing_crm": ["CRM", "lead routing", "wrong email", "not receiving", "duplicate lead",
                          "dealertrack", "routeone", "elead", "vin solutions", "lead not"],
    "pricing_cost": ["price increase", "too expensive", "cost per", "renewal", "budget cut",
                     "can't afford", "ROI", "return on investment", "cost too high", "overpriced package"],
    "dashboard_login": ["dashboard", "log in", "login", "don't log", "never log", "password",
                         "can't access", "okta", "credentials"],
    "feed_sync": ["feed", "sync", "syncing", "DMS", "vAuto", "inventory feed", "price sync",
                   "not showing", "not updating", "mileage"],
    "cancel_churn": ["cancel", "cancellation", "churn", "leaving", "30 day", "notice period",
                     "term", "contract"],
    "competitive_autotrader": ["autotrader", "auto trader", "AT ", "deal builder"],
    "competitive_carscom": ["cars.com", "cars dot com"],
    "competitive_facebook": ["facebook", "marketplace", "FB "],
    "competitive_carfax": ["carfax", "car fax"],
    "competitive_motors": ["motors.co", "motors group"],
    "ftc_fees": ["FTC", "fee", "doc fee", "dealer fee", "junk fee", "all-in pricing",
                 "fee transparency", "fee setup", "double counting"],
    "training_onboard": ["training", "onboarding", "how to use", "never trained", "walkthrough",
                         "show me how", "tutorial"],
    "package_naming": ["enhanced", "featured", "featured plus", "priority plus", "package",
                       "tier", "upgrade", "downgrade"],
    "shopper_profile": ["shopper profile", "shopper signal", "engagement", "vehicle saves",
                        "browsing history", "shopper journey", "intent"],
    "digital_deal_config": ["digital deal", "credit app", "trade-in", "delivery", "area boost",
                            "geo expansion"],
    "smc_conversion": ["sell my car", "SMC", "acquisition", "buy car from", "exclusive lead",
                       "offer price", "KBB"],
    "vinmax_attribution": ["vinmax", "vin max", "aged", "turn time", "pack", "boost"],
    "nce_coop": ["new car exposure", "NCE", "co-op", "OEM", "new car"],
    "account_management": ["account manager", "AM ", "never called", "no contact",
                           "unresponsive rep", "proactive"],
    "billing": ["billing", "invoice", "charged", "payment", "lockbox", "overpayment"],
    "inventory_low": ["low inventory", "thin inventory", "not enough cars", "auction",
                      "inventory decline"],
    "geo_leads": ["delivery lead", "out of state", "remote lead", "distance", "miles away",
                  "1000 miles"],
}


def extract_snippets(text, window=200, max_snippets=10):
    all_patterns = []
    for cat_def in COMPILED_CATEGORIES.values():
        all_patterns.extend(cat_def["patterns"])

    snippets = []
    seen = set()
    for pattern in all_patterns:
        for match in pattern.finditer(text):
            start = max(0, match.start() - window)
            end = min(len(text), match.end() + window)
            rounded = (start // 150) * 150
            if rounded in seen:
                continue
            seen.add(rounded)
            snippet = re.sub(r'\s+', ' ', text[start:end].strip())
            snippets.append(snippet)
            if len(snippets) >= max_snippets:
                return snippets
    return snippets


def classify_category(text, snippets):
    scores = Counter()
    for cat_key, cat_def in COMPILED_CATEGORIES.items():
        for pattern in cat_def["patterns"]:
            matches = pattern.findall(text)
            scores[cat_key] += len(matches)

    if not scores:
        return None, 0

    top = scores.most_common(1)[0]
    if top[1] == 0:
        return None, 0

    return COMPILED_CATEGORIES[top[0]]["label"], top[1]


def detect_themes(text):
    text_lower = text.lower()
    matched = []
    for theme_key, keywords in THEME_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        if score >= 2:
            matched.append((theme_key, score))
        elif score == 1:
            for kw in keywords:
                if kw.lower() in text_lower and len(kw) > 5:
                    matched.append((theme_key, score))
                    break

    matched.sort(key=lambda x: x[1], reverse=True)
    return [m[0] for m in matched[:3]]


def is_feedback(text, snippets, category, category_score):
    if not snippets:
        return False

    noise_indicators = [
        r'\bhow do I\b', r'\bcan you show me\b', r'\bwalk me through\b',
        r'\blet me share my screen\b', r'\bI.ll send you\b',
        r'\bschedule a\b', r'\bfollow up\b', r'\bnext steps\b',
        r'\blet me pull up\b', r'\bI.m going to show\b',
        r'\bI.ll email\b', r'\bsend (?:me|you) (?:a|the)\b',
        r'\bhold on\b', r'\bone second\b', r'\blet me check\b',
    ]
    noise_score = sum(1 for p in noise_indicators if re.search(p, text, re.IGNORECASE))

    if category_score >= 5 and len(snippets) >= 3:
        return True
    if category_score >= 3 and len(snippets) >= 2 and noise_score < 4:
        return True

    if noise_score >= 4 and category_score <= 2:
        return False
    if len(snippets) <= 1 and category_score <= 1:
        return False

    return category_score >= 2 and len(snippets) >= 2


def process_csv(csv_path, product_name, max_rows=0):
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if max_rows > 0:
        rows = rows[:max_rows]

    if not rows:
        return None

    transcripts = []
    for row in rows:
        text = row.get("TRANSCRIPT_EXCERPT", "")
        snippets = extract_snippets(text)
        category, cat_score = classify_category(text, snippets)
        themes = detect_themes(text)
        is_fb = is_feedback(text, snippets, category, cat_score)

        transcripts.append({
            "conversation_key": row.get("CONVERSATION_KEY", ""),
            "gong_url": row.get("GONG_URL", ""),
            "date": row.get("CONVERSATION_DATETIME", ""),
            "tracker": row.get("TRACKER_NAME", ""),
            "mentions": row.get("MENTION_COUNT", ""),
            "is_feedback": is_fb,
            "category": category,
            "category_score": cat_score,
            "themes": themes,
            "snippets": snippets[:4],
        })

    feedback = [t for t in transcripts if t["is_feedback"]]
    noise = [t for t in transcripts if not t["is_feedback"]]

    theme_clusters = defaultdict(lambda: {
        "transcripts": [],
        "categories": Counter(),
        "all_snippets": [],
        "gong_urls": [],
    })

    for t in feedback:
        assigned_themes = t["themes"] if t["themes"] else ["uncategorized"]
        for theme_key in assigned_themes[:2]:
            cluster = theme_clusters[theme_key]
            cluster["transcripts"].append(t["conversation_key"])
            if t["category"]:
                cluster["categories"][t["category"]] += 1
            cluster["all_snippets"].extend(t["snippets"][:2])
            if t["gong_url"] and len(cluster["gong_urls"]) < 5:
                cluster["gong_urls"].append(t["gong_url"])

    clusters_sorted = sorted(
        theme_clusters.items(),
        key=lambda x: len(x[1]["transcripts"]),
        reverse=True,
    )

    cluster_output = []
    for theme_key, cluster in clusters_sorted:
        top_category = cluster["categories"].most_common(1)
        category = top_category[0][0] if top_category else "Bug/Issue"

        representative_snippets = cluster["all_snippets"][:8]

        cluster_output.append({
            "theme_key": theme_key,
            "count": len(cluster["transcripts"]),
            "category": category,
            "example_gong_urls": cluster["gong_urls"][:3],
            "representative_snippets": representative_snippets,
        })

    return {
        "product": product_name,
        "transcripts_analyzed": len(transcripts),
        "feedback_count": len(feedback),
        "noise_count": len(noise),
        "clusters": cluster_output,
    }


SLUG_OVERRIDES = {
    "Listings": "core-listings",
    "Cancel / Churn": "cancel-churn",
}


def slugify(name):
    if name in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[name]
    return re.sub(r'-+', '-', name.lower().replace(" ", "-").replace("/", "-").replace(".", ""))


def process_all(output_dir, max_rows=0):
    products_file = os.path.join(SCRIPT_DIR, "products.json")
    with open(products_file) as f:
        data = json.load(f)

    products = {}
    for pillar_products in data.get("pillars", {}).values():
        for name, config in pillar_products.items():
            if config.get("tracker_patterns"):
                products[name] = config
    for name, config in data.get("cross_cutting", {}).items():
        if config.get("tracker_patterns"):
            products[name] = config

    results = {}
    for product_name in products:
        slug = slugify(product_name)
        csv_path = os.path.join(output_dir, f"{slug}.csv")
        if not os.path.exists(csv_path):
            print(f"SKIP {product_name}: no CSV at {csv_path}", file=sys.stderr)
            continue

        with open(csv_path) as f:
            row_count = sum(1 for _ in f) - 1
        if row_count <= 0:
            print(f"SKIP {product_name}: empty CSV", file=sys.stderr)
            continue

        result = process_csv(csv_path, product_name, max_rows)
        if result:
            json_path = os.path.join(output_dir, "clusters", f"{slug}.json")
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            with open(json_path, "w") as f:
                json.dump(result, f, indent=2)
            print(f"{product_name}: {result['feedback_count']} feedback / "
                  f"{result['noise_count']} noise / {len(result['clusters'])} clusters "
                  f"(from {result['transcripts_analyzed']} transcripts)", file=sys.stderr)
            results[product_name] = json_path

    return results


def main():
    max_rows = 0
    for arg in sys.argv[1:]:
        if arg.startswith("--max-rows="):
            max_rows = int(arg.split("=", 1)[1])

    if "--all" in sys.argv:
        idx = sys.argv.index("--all")
        output_dir = sys.argv[idx + 1] if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--") else "/tmp/dealer-feedback/backfill"
        results = process_all(output_dir, max_rows)
        print(f"\nProcessed {len(results)} products", file=sys.stderr)
        return

    if len(sys.argv) < 4:
        print("Usage: cluster_feedback.py <input_csv> <product_name> <output_json> [--max-rows=0]", file=sys.stderr)
        print("       cluster_feedback.py --all <output_dir> [--max-rows=0]", file=sys.stderr)
        sys.exit(1)

    input_csv = sys.argv[1]
    product_name = sys.argv[2]
    output_json = sys.argv[3]

    result = process_csv(input_csv, product_name, max_rows)
    if result:
        os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)
        with open(output_json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"{product_name}: {result['feedback_count']} feedback / "
              f"{result['noise_count']} noise / {len(result['clusters'])} clusters", file=sys.stderr)


if __name__ == "__main__":
    main()
