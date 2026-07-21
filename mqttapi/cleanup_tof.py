#!/usr/bin/env python3
"""Backfill incomplete rows and remove known bad/test records."""

from __future__ import annotations

import argparse
import json

import pymysql

from app.config import load_settings
from app.db import Database
from app.decoder import parse_message


def find_incomplete_rows(db: Database) -> list[dict]:
    sql = """
        SELECT id, topic, raw_message, payload_json
        FROM tof
        WHERE (
            JSON_EXTRACT(payload_json, '$.device_info.device_sn') IS NOT NULL
            AND device_name IS NULL
        ) OR (
            JSON_EXTRACT(payload_json, '$.device_info.device_sn') IS NOT NULL
            AND device_sn = SUBSTRING_INDEX(SUBSTRING_INDEX(topic, '/', 2), '/', -1)
            AND device_sn REGEXP '^[0-9]+$'
        )
        ORDER BY id
    """
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchall())


def backfill_row(db: Database, row: dict) -> None:
    topic = row["topic"]
    raw_message = row["raw_message"] or ""
    payload_json = row["payload_json"]
    if isinstance(payload_json, str):
        payload_json = json.loads(payload_json)

    record = parse_message(topic, raw_message.encode("utf-8"))
    if isinstance(payload_json, dict):
        record["payload_json"] = payload_json
    db.update_tof_from_record(row["id"], record)


def delete_test_rows(db: Database, dry_run: bool = False) -> int:
    """Remove publisher_test fake EM400 records."""
    sql = """
        DELETE FROM tof
        WHERE topic = 'em/6748d11290120003/status'
          AND JSON_EXTRACT(payload_json, '$.sn') = '6748d11290120003'
          AND JSON_EXTRACT(payload_json, '$.distance') IS NOT NULL
          AND JSON_EXTRACT(payload_json, '$.device_info') IS NULL
    """
    if dry_run:
        count_sql = sql.replace("DELETE FROM tof", "SELECT COUNT(*) AS cnt FROM tof")
        with db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(count_sql)
                return int(cur.fetchone()["cnt"])

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return int(cur.rowcount)


def main():
    parser = argparse.ArgumentParser(description="Cleanup and backfill tof table")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without writing")
    args = parser.parse_args()

    settings = load_settings()
    db = Database(settings)

    incomplete = find_incomplete_rows(db)
    print(f"Incomplete rows: {len(incomplete)}")

    if not args.dry_run:
        for row in incomplete:
            backfill_row(db, row)
            print(f"Backfilled id={row['id']}")

    test_count = delete_test_rows(db, dry_run=args.dry_run)
    action = "Would delete" if args.dry_run else "Deleted"
    print(f"{action} {test_count} test record(s)")

    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM tof")
            total = int(cur.fetchone()["cnt"])
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM tof
                WHERE JSON_EXTRACT(payload_json, '$.device_info.device_sn') IS NOT NULL
                  AND device_name IS NULL
                """
            )
            remaining = int(cur.fetchone()["cnt"])
    print(f"Total rows: {total}, remaining incomplete: {remaining}")


if __name__ == "__main__":
    main()
