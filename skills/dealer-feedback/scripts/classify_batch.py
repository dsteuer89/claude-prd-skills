#!/usr/bin/env python3
# /// script
# dependencies = [
#   "anthropic",
# ]
# ///
"""
Batch-classify Gong transcripts for dealer product feedback using Claude API.

Reads a CSV of extracted conversations, sends transcript snippets to Claude
in batches for classification, and aggregates into themed output.

Usage:
  uv run classify_batch.py <input_csv> <product_name> <output_json> [--batch-size=20] [--max-rows=0]

Args:
  input_csv: CSV from extract_conversations.py
  product_name: Product name for context (e.g. "Shopper Signals")
  output_json: Output path for analysis JSON
  --batch-size=N: Transcripts per API call (default 20)
  --max-rows=N: Max rows to process, 0=all (default 0)
"""

import csv
import json
import os
import re
import sys
import time

import anthropic

CATEGORIES = [
    "Feature Request",
    "Bug/Issue",
    "UX Friction",
    "Positive Signal",
    "Competitive Comparison",
    "Pricing Concern",
    "Adoption Barrier",
]

FEEDBACK_INDICATORS = [
    r'\b(?:I|we) wish\b', r'\b(?:I|we) need\b', r'\b(?:I|we) want\b',
    r'\bwould be (?:nice|great|helpful)\b', r'\bwould love\b',
    r'\bfrustrat', r'\bannoying\b', r'\bconfusing\b', r'\bdifficult\b',
    r'\bproblem (?:is|with)\b', r'\bissue (?:is|with)\b', r'\bbug\b',
    r'\bdoesn.t work\b', r'\bnot working\b', r'\bbroken\b',
    r'\blove (?:that|it|the)\b', r'\bgreat (?:feature|tool|product)\b',
    r'\breally like\b', r'\bhelpful\b', r'\bawesome\b',
    r'\bcompetitor', r'\bcars\.com\b', r'\bautotrader\b', r'\bcarvana\b',
    r'\bvauto\b', r'\btoo expensive\b', r'\bnot worth\b', r'\bpric(?:e|ing)\b',
    r'\bcancel', r'\bchurn\b', r'\bdowngrad',
    r'\bdon.t (?:use|like|understand)\b', r'\bnever use\b',
    r'\bhard to\b', r'\bcan.t figure\b', r'\bnot intuitive\b',
    r'\bfeature request\b', r'\bwish list\b', r'\bmissing\b',
    r'\bROI\b', r'\breturn on\b', r'\bvalue\b', r'\bworth it\b',
    r'\bswitching\b', r'\balternative\b', r'\breplac',
    r'\badopt', r'\bonboard', r'\btraining\b', r'\blearning curve\b',
    r'\blead(?:s)? (?:quality|score|volume)\b',
    r'\bshopper (?:signal|profile|intent)\b',
    r'\bdigital deal\b', r'\bcredit app',
    r'\bfeedback\b', r'\bsuggestion\b', r'\brecommend',
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in FEEDBACK_INDICATORS]


def extract_snippets(text, window=200, max_snippets=6):
    snippets = []
    seen = set()
    for pattern in COMPILED:
        for match in pattern.finditer(text):
            start = max(0, match.start() - window)
            end = min(len(text), match.end() + window)
            rounded = (start // 100) * 100
            if rounded in seen:
                continue
            seen.add(rounded)
            snippet = re.sub(r'\s+', ' ', text[start:end].strip())
            snippets.append(snippet)
            if len(snippets) >= max_snippets:
                return snippets
    return snippets


def build_batch_prompt(product_name, transcripts):
    """Build a prompt for classifying a batch of transcripts."""
    categories_str = ", ".join(CATEGORIES)

    transcript_blocks = []
    for i, t in enumerate(transcripts):
        snippets_text = "\n".join(f"  - {s}" for s in t["snippets"]) if t["snippets"] else "  (no feedback indicators found)"
        transcript_blocks.append(
            f"### Transcript {i+1} (ID: {t['id']})\n"
            f"Gong URL: {t['gong_url']}\n"
            f"Date: {t['date']}\n"
            f"Tracker: {t['tracker']}\n"
            f"Mentions: {t['mentions']}\n"
            f"Feedback-relevant snippets:\n{snippets_text}"
        )

    return f"""You are analyzing dealer conversation transcripts from Gong for the CarGurus product "{product_name}".

For each transcript below, determine:
1. Is this FEEDBACK (contains actionable product feedback from a dealer) or NOISE (routine support, training, or no product feedback)?
2. If FEEDBACK, what is the theme? Use a short descriptive phrase (e.g. "IMV accuracy frustration", "Lead routing failures").
3. If FEEDBACK, what category? One of: {categories_str}
4. If FEEDBACK, a one-sentence summary of the feedback.

Respond with a JSON array. Each element must have:
- "id": the transcript ID
- "classification": "feedback" or "noise"
- "theme": string or null if noise
- "category": string or null if noise
- "summary": string or null if noise

{chr(10).join(transcript_blocks)}

Respond ONLY with the JSON array, no other text."""


def classify_batch(client, product_name, transcripts, model="claude-sonnet-4-6"):
    prompt = build_batch_prompt(product_name, transcripts)

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = re.sub(r'^```(?:json)?\n?', '', text)
                text = re.sub(r'\n?```$', '', text)
            return json.loads(text)
        except (json.JSONDecodeError, anthropic.APIError) as e:
            print(f"  Attempt {attempt+1} failed: {e}", file=sys.stderr)
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None


def aggregate_themes(all_classifications):
    """Aggregate per-transcript classifications into theme rollups."""
    theme_map = {}
    feedback_count = 0
    noise_count = 0

    for c in all_classifications:
        if c["classification"] == "feedback":
            feedback_count += 1
            theme_key = c["theme"].strip().lower() if c["theme"] else "uncategorized"
            if theme_key not in theme_map:
                theme_map[theme_key] = {
                    "theme": c["theme"],
                    "category": c["category"],
                    "count": 0,
                    "summaries": [],
                    "gong_urls": [],
                }
            entry = theme_map[theme_key]
            entry["count"] += 1
            if c.get("summary") and len(entry["summaries"]) < 5:
                entry["summaries"].append(c["summary"])
            if c.get("gong_url") and len(entry["gong_urls"]) < 3:
                entry["gong_urls"].append(c["gong_url"])
        else:
            noise_count += 1

    return feedback_count, noise_count, theme_map


def merge_similar_themes(theme_map, similarity_threshold=0.6):
    """Merge themes that are very similar using simple word overlap."""
    keys = list(theme_map.keys())
    merged = {}
    used = set()

    for i, k1 in enumerate(keys):
        if k1 in used:
            continue
        merged_entry = dict(theme_map[k1])
        for j in range(i + 1, len(keys)):
            k2 = keys[j]
            if k2 in used:
                continue
            words1 = set(k1.split())
            words2 = set(k2.split())
            if not words1 or not words2:
                continue
            overlap = len(words1 & words2) / min(len(words1), len(words2))
            if overlap >= similarity_threshold:
                other = theme_map[k2]
                merged_entry["count"] += other["count"]
                merged_entry["summaries"].extend(other["summaries"])
                for url in other["gong_urls"]:
                    if url not in merged_entry["gong_urls"] and len(merged_entry["gong_urls"]) < 3:
                        merged_entry["gong_urls"].append(url)
                used.add(k2)
        merged[k1] = merged_entry
        used.add(k1)

    return merged


def main():
    if len(sys.argv) < 4:
        print(
            "Usage: classify_batch.py <input_csv> <product_name> <output_json> "
            "[--batch-size=20] [--max-rows=0]",
            file=sys.stderr,
        )
        sys.exit(1)

    input_csv = sys.argv[1]
    product_name = sys.argv[2]
    output_json = sys.argv[3]

    batch_size = 20
    max_rows = 0
    for arg in sys.argv[4:]:
        if arg.startswith("--batch-size="):
            batch_size = int(arg.split("=", 1)[1])
        elif arg.startswith("--max-rows="):
            max_rows = int(arg.split("=", 1)[1])

    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = []
        for i, row in enumerate(reader):
            if max_rows and i >= max_rows:
                break
            rows.append(row)

    if not rows:
        print(f"No rows in {input_csv}", file=sys.stderr)
        sys.exit(0)

    print(f"Processing {len(rows)} transcripts for {product_name}", file=sys.stderr)

    transcripts = []
    for row in rows:
        text = row.get("TRANSCRIPT_EXCERPT", "")
        snippets = extract_snippets(text)
        transcripts.append({
            "id": row.get("CONVERSATION_KEY", ""),
            "gong_url": row.get("GONG_URL", ""),
            "date": row.get("CONVERSATION_DATETIME", ""),
            "tracker": row.get("TRACKER_NAME", ""),
            "mentions": row.get("MENTION_COUNT", ""),
            "snippets": snippets,
        })

    client = anthropic.Anthropic()
    all_classifications = []

    batches = [transcripts[i:i + batch_size] for i in range(0, len(transcripts), batch_size)]
    print(f"Sending {len(batches)} batches (batch_size={batch_size})", file=sys.stderr)

    for batch_num, batch in enumerate(batches, 1):
        print(f"  Batch {batch_num}/{len(batches)} ({len(batch)} transcripts)...", file=sys.stderr)
        results = classify_batch(client, product_name, batch)
        if results:
            url_map = {t["id"]: t["gong_url"] for t in batch}
            for r in results:
                r["gong_url"] = url_map.get(r["id"], "")
            all_classifications.extend(results)
            print(f"    -> {sum(1 for r in results if r['classification'] == 'feedback')} feedback, "
                  f"{sum(1 for r in results if r['classification'] == 'noise')} noise", file=sys.stderr)
        else:
            print(f"    -> FAILED, skipping batch", file=sys.stderr)

        if batch_num < len(batches):
            time.sleep(1)

    feedback_count, noise_count, theme_map = aggregate_themes(all_classifications)
    theme_map = merge_similar_themes(theme_map)

    themes_sorted = sorted(theme_map.values(), key=lambda t: t["count"], reverse=True)
    themes_output = []
    for t in themes_sorted:
        combined_summary = " ".join(t["summaries"][:3])
        if len(combined_summary) > 300:
            combined_summary = combined_summary[:297] + "..."
        themes_output.append({
            "theme": t["theme"],
            "category": t["category"],
            "count": t["count"],
            "summary": combined_summary,
            "example_gong_urls": t["gong_urls"][:3],
        })

    output = {
        "product": product_name,
        "transcripts_analyzed": len(rows),
        "feedback_count": feedback_count,
        "noise_count": noise_count,
        "themes": themes_output,
    }

    os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)
    with open(output_json, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDone: {feedback_count} feedback / {noise_count} noise / {len(themes_output)} themes", file=sys.stderr)
    print(f"Output: {output_json}", file=sys.stderr)


if __name__ == "__main__":
    main()
