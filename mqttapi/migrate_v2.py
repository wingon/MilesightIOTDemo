#!/usr/bin/env python3
"""Apply v2 schema migration and backfill parsed columns from payload_json."""

from __future__ import annotations

import json

import pymysql

from app.config import load_settings
from app.db import Database
from app.decoder import flatten_milesight_json, parse_message

MIGRATION_COLUMNS = {
    "device_name": "VARCHAR(128) NULL",
    "device_mac": "VARCHAR(32) NULL",
    "wlan_mac": "VARCHAR(32) NULL",
    "ip_address": "VARCHAR(45) NULL",
    "custom_device_id": "VARCHAR(64) NULL",
    "custom_site_id": "VARCHAR(64) NULL",
    "running_time_sec": "INT UNSIGNED NULL",
    "firmware_version": "VARCHAR(64) NULL",
    "hardware_version": "VARCHAR(64) NULL",
    "trigger_time": "DATETIME(3) NULL",
    "start_time": "DATETIME(3) NULL",
    "end_time": "DATETIME(3) NULL",
    "time_zone": "VARCHAR(255) NULL",
    "dst_enable": "TINYINT(1) NULL",
    "dst_status": "TINYINT(1) NULL",
    "line_trigger_data": "JSON NULL",
    "region_trigger_data": "JSON NULL",
    "region_count_data": "JSON NULL",
    "dwell_time_data": "JSON NULL",
    "dwell_start_time": "JSON NULL",
    "line_periodic_data": "JSON NULL",
    "line_total_data": "JSON NULL",
    "line_count_data": "JSON NULL",
    "region_periodic_data": "JSON NULL",
    "alarm_data": "JSON NULL",
}


def ensure_columns(settings):
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='tof'
                """,
                (settings.db_name,),
            )
            existing = {row[0] for row in cur.fetchall()}

            for column, definition in MIGRATION_COLUMNS.items():
                if column not in existing:
                    cur.execute(f"ALTER TABLE tof ADD COLUMN {column} {definition}")
                    print(f"Added column: {column}")

            cur.execute("SHOW INDEX FROM tof WHERE Key_name='idx_start_time'")
            if not cur.fetchone():
                cur.execute("CREATE INDEX idx_start_time ON tof (start_time)")
                print("Added index: idx_start_time")
    finally:
        conn.close()


def backfill_rows(db: Database):
    with db.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, topic, raw_message, payload_json FROM tof ORDER BY id"
            )
            rows = cur.fetchall()

    updated = 0
    for row in rows:
        row_id = row["id"]
        topic = row["topic"]
        raw_message = row["raw_message"] or ""
        payload_json = row["payload_json"]

        if isinstance(payload_json, str):
            try:
                payload_json = json.loads(payload_json)
            except json.JSONDecodeError:
                payload_json = None

        if payload_json and isinstance(payload_json, dict) and "device_info" in payload_json:
            record = parse_message(topic, raw_message.encode("utf-8"))
        elif payload_json and isinstance(payload_json, dict):
            record = parse_message(topic, raw_message.encode("utf-8"))
        else:
            record = parse_message(topic, raw_message.encode("utf-8"))

        if payload_json and isinstance(payload_json, dict):
            record["payload_json"] = payload_json
            structured = flatten_milesight_json(payload_json)
            for key, value in structured.items():
                if value is not None:
                    record[key] = value

        db.update_tof_from_record(row_id, record)
        updated += 1
        print(f"Backfilled id={row_id} device_sn={record.get('device_sn')}")

    print(f"Done. Updated {updated} row(s).")


def main():
    settings = load_settings()
    ensure_columns(settings)
    backfill_rows(Database(settings))


if __name__ == "__main__":
    main()
