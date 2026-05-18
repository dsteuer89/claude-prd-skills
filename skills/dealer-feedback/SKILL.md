---
name: dealer-feedback
description: Extract and track dealer product feedback from Gong conversations. Analyzes transcripts matched by product trackers, classifies feedback themes, and maintains Confluence pages with counts for prioritization. Run weekly or on-demand.
allowed-tools: mcp__atlassian__getConfluencePage, mcp__atlassian__createConfluencePage, mcp__atlassian__updateConfluencePage, mcp__atlassian__getPagesInConfluenceSpace, mcp__atlassian__searchConfluenceUsingCql
---

# Dealer Product Feedback — Weekly Refresh

Analyze Gong dealer conversations to extract product feedback, classify themes, and update the Confluence wiki at:
https://cargurus.atlassian.net/wiki/spaces/RTL/pages/6077612115/Dealer+Product+Feedback+Gong+Backfill

## Prerequisites

- VPN connected (Snowflake privatelink)
- Snowflake credentials configured in `~/.ai_skills/config.json` (same as da-snowflake)
- Confluence access via Atlassian MCP
- `uv` available for running Python scripts

## Constants

- **Confluence Cloud ID**: `bad1dfdc-baaa-45da-9dab-af313f387bf1`
- **RTL Space ID**: `4570841135`
- **Scripts directory**: Find the dealer-feedback scripts — check `skills/dealer-feedback/scripts/` relative to this skill, or `/Users/dsteuer/claude-skills/skills/dealer-feedback/scripts/`
- **Working directory**: `/tmp/dealer-feedback/weekly-{YYYY-MM-DD}`

## Confluence Page IDs

| Product | Page ID |
|---------|---------|
| **Parent Summary** | 6077612115 |
| StockVantage | 6076629145 |
| Sell My Car | 6076170451 |
| PriceVantage | 6076334143 |
| VINMax | 6077939746 |
| Listings | 6076661829 |
| New Car Exposure | 6076661849 |
| Shopper Signals | 6076923954 |
| Digital Deal | 6077087812 |
| FTC | 6076629185 |
| Competitors | 6076432509 |
| Cancel / Churn | 6076596347 |

## Invocation

- `/dealer-feedback refresh` — Run the full weekly pipeline (all products)
- `/dealer-feedback refresh --product "Shopper Signals"` — Single product only

## Pipeline Steps

### Step 1: Extract New Conversations from Snowflake

For each product in `scripts/products.json`:

```bash
uv run scripts/extract_conversations.py \
  "{tracker_patterns}" \
  "{7_days_ago_iso}" \
  500 \
  "/tmp/dealer-feedback/weekly-{date}/{slug}.csv" \
  --sort=mentions
```

- Use `--sort=mentions` to prioritize high-signal conversations
- Set `since_timestamp` to 7 days before today (ISO format)
- If Snowflake connection fails, print "VPN required — connect and retry" and stop
- If 0 rows for a product, skip it

### Step 2: Classify and Cluster

Run the clustering script on all extracted CSVs:

```bash
uv run scripts/cluster_feedback.py --all /tmp/dealer-feedback/weekly-{date}
```

This produces `{slug}_clustered.csv` files with rule-based feedback classification.

**Important:** CSVs must be at the base directory level (not in a subdirectory). If extraction puts them in a `conversations/` subfolder, move them up first.

### Step 3: Synthesize Themes

For each product with clustered data, launch a **background Sonnet agent** to synthesize themes. Run all products in parallel.

Each agent should:
1. Read the `{slug}_clustered.csv`
2. Group by cluster, filter noise aggressively (voicemails, demos, brief mentions without dealer opinion)
3. Name each surviving theme (5-15 words)
4. Assign category: `Feature Request`, `Bug/Issue`, `UX Friction`, `Positive Signal`, `Competitive Comparison`, `Pricing Concern`, `Adoption Barrier`
5. Write summary (2-4 sentences, specific and actionable)
6. Pick up to 3 example Gong call URLs per theme
7. Output JSON:

```json
{
  "product": "Product Name",
  "transcripts_analyzed": 123,
  "feedback_count": 100,
  "noise_count": 23,
  "themes": [
    {
      "theme": "Theme Name",
      "category": "Category",
      "count": 45,
      "summary": "...",
      "example_gong_urls": ["https://cargurus.app.gong.io/call?id=..."]
    }
  ]
}
```

Save to `/tmp/dealer-feedback/weekly-{date}/analysis/{slug}.json`

### Step 4: Merge with Existing Content

Read each product's current Confluence page to get the existing themes. Merge strategy:

- **Existing themes that match new themes** → update count, refresh summary if new data is richer
- **New themes not in existing data** → append to the table
- **Existing themes with no new signal** → keep as-is

Keep the two-section structure:
- **Top 500 Conversations (by mention count)** — the original backfill themes (don't modify these)
- **Conversations 501–1000 (by mention count)** — the second backfill batch (don't modify these)
- **Recent (weekly refresh)** — new section for incremental weekly findings

### Step 5: Generate Markdown and Push to Confluence

For each product, generate the full page markdown and push via `updateConfluencePage`:

- Tables must include the **Example Calls** column with clickable Gong links: `[1](url), [2](url), [3](url)`
- Use `contentFormat: "markdown"`
- Set `versionMessage` to `"Weekly refresh {YYYY-MM-DD}"`

### Step 6: Update Parent Summary Page

Read page 6077612115 and update:
- Total transcripts, feedback, noise, theme counts per product
- Product names in the table should link to their subpages
- Add or update a "Last refreshed: {date}" line

### Step 7: Report

Print summary:

```
Dealer Feedback weekly refresh complete ({date}).

Products processed: X
New conversations analyzed: Y  
New themes found: Z
Existing themes updated: W

Top new themes:
- [Product] "theme name" (count)
- ...
```

## Feedback Classification Guidelines

Be selective. Most Gong conversations are sales calls where the rep pitches the product. That is NOT feedback. Only classify when:

1. **The dealer speaks** — feedback comes from the external participant, not the CG rep
2. **There's an opinion or request** — "it would be nice if..." / "we don't use it because..." / "the problem is..."
3. **It's about the product** — not general relationship or contract logistics

Common noise to filter:
- Rep explaining features (demo/pitch)
- Voicemails and missed calls
- Brief mentions without dealer engagement
- Technical setup discussions (DealerTrack/RouteOne integration plumbing)
- General small talk

## Error Handling

- **Snowflake connection fails**: Print "VPN required" and stop immediately
- **No new conversations for a product**: Skip silently
- **Confluence update fails**: Retry once, then report the failure and continue with other products
- **Agent synthesis fails for a product**: Report and continue
