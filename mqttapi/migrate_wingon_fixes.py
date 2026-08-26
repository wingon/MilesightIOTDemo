#!/usr/bin/env python3
"""Apply the WingOnIOT risk-fix migrations (table rename, partition, soft-delete,
one-device-one-cell, one-room-per-cell trigger).

NOT idempotent — run once against a backed-up database.
Usage:  python migrate_wingon_fixes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymysql

from app.config import load_settings


def run_statements(conn, sql: str, label: str) -> None:
    """Split on ';' at line boundaries and run each statement (safe for plain DDL).

    RENAME TABLE is skipped when the target table already exists, so a partially
    applied migration can be re-run safely (the remaining ALTERs still apply).
    """
    with conn.cursor() as cur:
        # Strip full-line comments first so a leading comment block does not get
        # merged into the following statement.
        body = "\n".join(
            ln for ln in sql.splitlines() if not ln.strip().startswith("--")
        )
        for statement in body.split(";"):
            stmt = statement.strip()
            if not stmt:
                continue
            head = stmt.splitlines()[0].strip().upper()
            if head.startswith("RENAME TABLE"):
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = 'Environmental_Monitoring'"
                )
                row = cur.fetchone()
                exists = int(row[0]) if row else 0
                if exists > 0:
                    print(f"  skip: {label} :: RENAME TABLE (target already exists)")
                    continue
            cur.execute(stmt)
            print(f"  ok: {label} :: {stmt.splitlines()[0][:80]}")


def run_trigger(conn, sql: str) -> None:
    """Run the trigger file as a single statement (contains BEGIN...END ;)."""
    with conn.cursor() as cur:
        cur.execute(sql)
        print(f"  ok: trigger :: {sql.splitlines()[0][:80]}")


def main() -> None:
    settings = load_settings()
    base = Path(__file__).resolve().parent / "sql"

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
        fixes = (base / "migrate_wingon_fixes.sql").read_text(encoding="utf-8")
        run_statements(conn, fixes, "fixes")

        trigger_sql = (base / "migrate_wingon_trigger.sql").read_text(encoding="utf-8")
        run_trigger(conn, trigger_sql)

        print(f"Applied WingOnIOT risk-fix migrations to '{settings.wingon_db_name}'.")
    except Exception as exc:
        print(f"Migration failed (rollback to backup required): {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
