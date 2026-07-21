#!/usr/bin/env python3
"""Initialize milesight database tables (tof + ug65)."""

from pathlib import Path

import pymysql

from app.config import load_settings


def run_sql_file(cur, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    for statement in sql.split(";"):
        stmt = statement.strip()
        if stmt:
            cur.execute(stmt)


def main():
    settings = load_settings()
    base = Path(__file__).resolve().parent / "sql"

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
            run_sql_file(cur, base / "init.sql")
            run_sql_file(cur, base / "init_ug65.sql")
        print(f"Initialized database '{settings.db_name}' (tables: tof, ug65).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
