#!/usr/bin/env python3
"""Combine batch 1 (v3) and batch 2 analysis into single markdown files."""
import json, os, sys

V3_DIR = "/tmp/dealer-feedback/backfill-v3/analysis-v3"
B2_DIR = "/tmp/dealer-feedback/backfill-b2/analysis-b2"
OUT_DIR = "/tmp/dealer-feedback/combined/markdown"

SLUG_MAP = {
    "stockvantage": "StockVantage",
    "sell-my-car": "Sell My Car",
    "pricevantage": "PriceVantage",
    "core-listings": "Listings",
    "shopper-signals": "Shopper Signals",
    "digital-deal": "Digital Deal",
    "competitors": "Competitors",
    "ftc": "FTC",
    "cancel-churn": "Cancel / Churn",
    "vinmax": "VINMax",
    "new-car-exposure": "New Car Exposure",
}

def theme_table(themes):
    lines = []
    lines.append("| # | Theme | Category | Count | Summary | Example Calls |")
    lines.append("|---|-------|----------|-------|---------|---------------|")
    for i, t in enumerate(themes, 1):
        urls = t.get("example_gong_urls", [])[:3]
        links = ", ".join(f"[{j+1}]({u})" for j, u in enumerate(urls)) if urls else ""
        lines.append(f"| {i} | {t['theme']} | {t['category']} | {t['count']} | {t['summary']} | {links} |")
    return "\n".join(lines)

def example_links(themes):
    lines = []
    for t in themes:
        urls = t.get("example_gong_urls", [])[:3]
        if not urls:
            continue
        links = ", ".join(f"[Call {i+1}]({u})" for i, u in enumerate(urls))
        name = t["theme"][:50] + "..." if len(t["theme"]) > 50 else t["theme"]
        lines.append(f"- **{name}**: {links}")
    return "\n".join(lines)

def generate_combined(slug):
    v3_path = os.path.join(V3_DIR, f"{slug}.json")
    b2_path = os.path.join(B2_DIR, f"{slug}.json")

    has_v3 = os.path.exists(v3_path)
    has_b2 = os.path.exists(b2_path)

    if not has_v3 and not has_b2:
        return None

    product = SLUG_MAP.get(slug, slug)

    v3 = json.load(open(v3_path)) if has_v3 else None
    b2 = json.load(open(b2_path)) if has_b2 else None

    total_transcripts = (v3["transcripts_analyzed"] if v3 else 0) + (b2["transcripts_analyzed"] if b2 else 0)
    total_feedback = (v3["feedback_count"] if v3 else 0) + (b2["feedback_count"] if b2 else 0)
    total_noise = (v3["noise_count"] if v3 else 0) + (b2["noise_count"] if b2 else 0)
    total_themes_b1 = len(v3["themes"]) if v3 else 0
    total_themes_b2 = len(b2["themes"]) if b2 else 0

    md = []
    md.append(f"# {product} — Dealer Feedback")
    md.append("")
    md.append(f"**Source:** Gong conversation backfill (top conversations by mention count, all-time)")
    md.append(f"**Total transcripts analyzed:** {total_transcripts} | **Feedback:** {total_feedback} | **Noise:** {total_noise}")
    md.append("")
    md.append("---")
    md.append("")

    # Batch 1 section
    if v3:
        md.append(f"## Top {v3['transcripts_analyzed']} Conversations (by mention count)")
        md.append("")
        md.append(f"**Transcripts:** {v3['transcripts_analyzed']} | **Feedback:** {v3['feedback_count']} | **Noise:** {v3['noise_count']} | **Themes:** {total_themes_b1}")
        md.append("")
        md.append(theme_table(v3["themes"]))
        md.append("")

    # Batch 2 section
    if b2:
        offset = v3["transcripts_analyzed"] if v3 else 0
        md.append("---")
        md.append("")
        md.append(f"## Conversations {offset + 1}–{offset + b2['transcripts_analyzed']} (by mention count)")
        md.append("")
        md.append(f"**Transcripts:** {b2['transcripts_analyzed']} | **Feedback:** {b2['feedback_count']} | **Noise:** {b2['noise_count']} | **Themes:** {total_themes_b2}")
        md.append("")
        md.append(theme_table(b2["themes"]))
        md.append("")

    return "\n".join(md)

os.makedirs(OUT_DIR, exist_ok=True)

for slug in SLUG_MAP:
    content = generate_combined(slug)
    if content:
        out_path = os.path.join(OUT_DIR, f"{slug}.md")
        with open(out_path, "w") as f:
            f.write(content)
        print(f"{slug}.md written")
    else:
        print(f"{slug}: no data, skipped")
