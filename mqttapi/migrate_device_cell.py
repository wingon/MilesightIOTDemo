#!/usr/bin/env python3
"""Apply the device_cell migration: link Environment_Device to grid cells.

Idempotent: CREATE TABLE IF NOT EXISTS, safe to re-run.
"""

from pathlib import Path

import pymysql

from app.config import load_settings


def main() -> None:
    settings = load_settings()
    sql_path = Path(__file__).resolve().parent / "sql" / "migrate_device_cell.sql"
    sql = sql_path.read_text(encoding="utf-8")

    conn = pymysql.connect(
        host=settings.wingon_db_host,
        port=settings.wingon_db_port,
        user=settings.wingon_db_user,
        password=settings.wingon_db_password,
        database=settings.wingon_db_name,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            for statement in sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    cur.execute(stmt)
        print(f"Applied device_cell migration to database '{settings.wingon_db_name}'.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
