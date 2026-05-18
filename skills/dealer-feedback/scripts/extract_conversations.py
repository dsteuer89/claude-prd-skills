#!/usr/bin/env python3
# /// script
# dependencies = [
#   "snowflake-connector-python",
# ]
# ///
"""
Extract Gong conversations matching product trackers from Snowflake.
Flattens transcripts to plain text and exports to CSV.

Usage:
  uv run extract_conversations.py <tracker_patterns> <since_timestamp> <limit> <output_csv> [--sort=mentions] [--offset=N]

Args:
  tracker_patterns: Comma-separated LIKE patterns, e.g. "Shopper Signals%,Digital Deal%"
  since_timestamp: ISO timestamp watermark, e.g. "2025-07-01T00:00:00Z"
  limit: Max conversations to return
  output_csv: Output file path
  --sort=mentions: Sort by mention count descending (default: date ascending)
  --offset=N: Skip first N conversations (for pagination)
"""

import sys
import os
import json
import csv
from datetime import datetime, date

import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

CONFIG_FILE = os.path.expanduser("~/.ai_skills/config.json")
DB = "DATA_SHARE_GONG"
SCHEMA = "GONG_DATA_CLOUD"
WAREHOUSE = "ANALYST_WH"


def load_config():
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    return config["skills"]["da-snowflake"]


def get_connection(config):
    key_path = config["snowflake_auth_key_path"]
    password = config.get("snowflake_private_key_password") or None
    password_bytes = password.encode('utf-8') if password else None

    with open(key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(
            f.read(), password=password_bytes, backend=default_backend()
        )

    pk_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    return snowflake.connector.connect(
        user=config["snowflake_user"],
        account="cargurus.us-east-1.privatelink",
        private_key=pk_bytes,
        warehouse=WAREHOUSE,
        database=DB,
        schema=SCHEMA,
    )


def build_query(tracker_patterns, since_timestamp, limit, sort="date", offset=0):
    like_clauses = ", ".join(f"'{p}'" for p in tracker_patterns)

    if sort == "mentions":
        inner_order = "mc.MENTION_COUNT DESC"
        outer_order = "tc.MENTION_COUNT DESC"
    else:
        inner_order = "c.CONVERSATION_DATETIME ASC"
        outer_order = "tc.CONVERSATION_DATETIME ASC"

    return f"""
WITH matched_convos AS (
  SELECT DISTINCT
    ct.CONVERSATION_KEY,
    t.NAME AS TRACKER_NAME,
    ct.COUNT AS MENTION_COUNT
  FROM {DB}.{SCHEMA}.CONVERSATION_TRACKERS ct
  JOIN {DB}.{SCHEMA}.TRACKERS t ON ct.TRACKER_ID = t.TRACKER_ID
  WHERE t.IS_DELETED = FALSE
    AND ct.IS_DELETED = FALSE
    AND t.NAME LIKE ANY ({like_clauses})
),
top_convos AS (
  SELECT
    mc.CONVERSATION_KEY,
    mc.TRACKER_NAME,
    mc.MENTION_COUNT,
    c.CONVERSATION_ID,
    c.CONVERSATION_DATETIME,
    c.CONVERSATION_TYPE
  FROM matched_convos mc
  JOIN {DB}.{SCHEMA}.CONVERSATIONS c
    ON mc.CONVERSATION_KEY = c.CONVERSATION_KEY
  WHERE c.IS_DELETED = FALSE
    AND c.CONVERSATION_TYPE = 'call'
    AND c.CONVERSATION_DATETIME > '{since_timestamp}'
  ORDER BY {inner_order}
  LIMIT {limit} OFFSET {offset}
),
flat_text AS (
  SELECT
    tr.CONVERSATION_KEY,
    seg.value:speakerId::STRING AS SPEAKER_ID,
    seg.index AS SEG_IDX,
    f.index AS SENT_IDX,
    f.value:text::STRING AS SENTENCE
  FROM {DB}.{SCHEMA}.CALL_TRANSCRIPTS tr,
    LATERAL FLATTEN(input => tr.TRANSCRIPT) seg,
    LATERAL FLATTEN(input => seg.value:sentences) f
  WHERE tr.IS_DELETED = FALSE
    AND tr.CONVERSATION_KEY IN (SELECT CONVERSATION_KEY FROM top_convos)
),
agg_text AS (
  SELECT
    CONVERSATION_KEY,
    LISTAGG(SENTENCE, ' ') WITHIN GROUP (ORDER BY SEG_IDX, SENT_IDX) AS FULL_TEXT
  FROM flat_text
  GROUP BY CONVERSATION_KEY
)
SELECT
  tc.CONVERSATION_KEY,
  tc.CONVERSATION_ID,
  tc.CONVERSATION_DATETIME,
  tc.CONVERSATION_TYPE,
  tc.TRACKER_NAME,
  tc.MENTION_COUNT,
  'https://cargurus.app.gong.io/call?id=' || tc.CONVERSATION_ID AS GONG_URL,
  LEFT(at.FULL_TEXT, 12000) AS TRANSCRIPT_EXCERPT
FROM top_convos tc
LEFT JOIN agg_text at
  ON tc.CONVERSATION_KEY = at.CONVERSATION_KEY
ORDER BY {outer_order}
"""


def fmt(val):
    if val is None:
        return ""
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, (list, dict)):
        return json.dumps(val)
    return str(val)


def main():
    if len(sys.argv) < 5:
        print(
            "Usage: extract_conversations.py <tracker_patterns> <since> <limit> <output_csv>",
            file=sys.stderr,
        )
        sys.exit(1)

    tracker_patterns = [p.strip() for p in sys.argv[1].split(",")]
    since = sys.argv[2]
    limit = int(sys.argv[3])
    output_csv = sys.argv[4]

    sort = "date"
    offset = 0
    for arg in sys.argv[5:]:
        if arg.startswith("--sort="):
            sort = arg.split("=", 1)[1]
        elif arg.startswith("--offset="):
            offset = int(arg.split("=", 1)[1])

    config = load_config()
    conn = get_connection(config)
    cursor = conn.cursor()

    sql = build_query(tracker_patterns, since, limit, sort=sort, offset=offset)
    print(f"Extracting conversations matching: {tracker_patterns}", file=sys.stderr)
    print(f"Since: {since} | Limit: {limit}", file=sys.stderr)

    cursor.execute(sql)
    columns = [d[0] for d in cursor.description]
    rows = cursor.fetchall()

    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([fmt(v) for v in row])

    print(f"Exported {len(rows)} conversations to {output_csv}", file=sys.stderr)

    if rows:
        dates = [r[2] for r in rows if r[2]]
        latest = max(dates) if dates else "unknown"
        print(f"Latest conversation: {latest}", file=sys.stderr)

    cursor.close()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    main()
