#!/usr/bin/env python3
"""Add gateway_model to ug65 table (UG56 support)."""

from pathlib import Path

import pymysql

from app.config import load_settings


def main():
    settings = load_settings()
    sql_path = Path(__file__).resolve().parent / "sql" / "migrate_ug56.sql"
    sql = sql_path.read_text(encoding="utf-8")

    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            for statement in sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    cur.execute(stmt)
        print("Applied migrate_ug56.sql (ug65.gateway_model).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
