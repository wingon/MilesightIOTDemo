#!/usr/bin/env python3
"""WingOnIOT building_* / sys_* 表主键迁移为雪花 ID（一次性，幂等）。

背景：
  - Environment_Device / Environmental_Monitoring 两张表保持不动。
  - building_* 7 张 + sys_* 15 张主键由 AUTO_INCREMENT 改为应用生成雪花 ID。
  - 复用 app/snowflake.py（people_count_hourly 已在用）。

流程（分两阶段，最大化安全）：
  [阶段一] DML：为每行生成雪花 ID 映射，按外键依赖更新主键列 + 外键列，
           以事务方式提交（失败整体回滚，数据不变）。
  [阶段二] DDL：移除所有相关表的 AUTO_INCREMENT（显式提供 id 不再依赖自增）。

幂等：若 building 表已存在雪花规模 ID（> 1<<50），直接提示并退出。

还原：如需还原，用 db_backup/snowflake_before_*/WingOnIOT_tables.sql 恢复即可。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymysql

from app.config import load_settings
from app.snowflake import next_id

# 雪花 ID 最小规模判定阈值（当前纪元下的雪花 ID 都远大于 2^50）
SNOWFLAKE_THRESHOLD = 1 << 50

# (表名, 主键列, [(外键列, 被引用表), ...])
BUILDING_TABLES: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("building", "id", []),
    ("building_floor", "id", [("building_id", "building")]),
    ("building_cell", "id", [("floor_id", "building_floor"), ("building_id", "building")]),
    ("building_room", "id", [("building_id", "building"), ("floor_id", "building_floor")]),
    ("building_room_cell", "id", [("room_ref_id", "building_room"), ("cell_id", "building_cell"), ("floor_id", "building_floor")]),
    ("building_device_cell", "id", [("cell_id", "building_cell"), ("floor_id", "building_floor")]),
    ("building_facade_config", "id", []),
]

# sys 主表：(表名, 主键列, [(外键列, 被引用表), ...])
SYS_TABLES: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("sys_user", "id", [("dept_id", "sys_dept")]),
    ("sys_role", "id", []),
    ("sys_menu", "id", [("parent_id", "sys_menu")]),
    ("sys_dept", "dept_id", [("parent_id", "sys_dept")]),
    ("sys_post", "post_id", []),
    ("sys_config", "config_id", []),
    ("sys_dict_type", "dict_id", []),
    ("sys_dict_data", "dict_code", []),
    ("sys_oper_log", "id", []),
    ("sys_login_log", "info_id", []),
    ("sys_whitelist", "id", []),
]

# sys 关联表：(表名, [(外键列, 被引用表), ...])，整行外键全部映射
SYS_RELATIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("sys_user_role", [("user_id", "sys_user"), ("role_id", "sys_role")]),
    ("sys_user_post", [("user_id", "sys_user"), ("post_id", "sys_post")]),
    ("sys_role_menu", [("role_id", "sys_role"), ("menu_id", "sys_menu")]),
    ("sys_role_dept", [("role_id", "sys_role"), ("dept_id", "sys_dept")]),
]

ALL_TABLES = [t for t, _, _ in BUILDING_TABLES] + [t for t, _, _ in SYS_TABLES] + [t for t, _ in SYS_RELATIONS]


def get_mapping(cur, table: str, pk: str) -> dict[int, int]:
    """为该表所有行生成 旧 id -> 新雪花 id 映射。"""
    cur.execute(f"SELECT `{pk}` FROM `{table}` ORDER BY `{pk}`")
    rows = cur.fetchall()
    mapping: dict[int, int] = {}
    for r in rows:
        old = int(r[pk])
        mapping[old] = next_id()
    return mapping


def already_snowflake(cur, table: str, pk: str) -> bool:
    """检测主键是否已是雪花规模 ID。"""
    cur.execute(f"SELECT MAX(`{pk}`) AS m FROM `{table}`")
    row = cur.fetchone()
    return row is not None and row.get("m") is not None and int(row["m"]) > SNOWFLAKE_THRESHOLD


def migrate_primary_tables(cur, tables, mappings) -> None:
    """迁移主表：重写主键列，并用父表映射更新外键列。"""
    for table, pk, fks in tables:
        mapping = mappings[table]
        if not mapping:
            print(f"  - {table}: 空表，跳過")
            continue
        select_cols = [pk] + [fk for fk, _ in fks]
        cur.execute(
            "SELECT " + ", ".join(f"`{c}`" for c in select_cols) + f" FROM `{table}` ORDER BY `{pk}`"
        )
        rows = cur.fetchall()
        n = 0
        for r in rows:
            old_pk = int(r[pk])
            new_pk = mapping[old_pk]
            set_parts = [f"`{pk}` = %s"]
            params: list = [new_pk]
            for fk, ref_table in fks:
                val = r.get(fk)
                if val is None:
                    continue
                # parent_id = 0 表示顶级节点，保留 0（0 不参与映射）
                if fk == "parent_id" and int(val) == 0:
                    continue
                new_val = mappings[ref_table].get(int(val))
                if new_val is None:
                    print(f"    !! {table}.{fk}={val} 在 {ref_table} 映射中找不到，保留原值")
                    continue
                set_parts.append(f"`{fk}` = %s")
                params.append(new_val)
            params.append(old_pk)
            cur.execute(
                f"UPDATE `{table}` SET " + ", ".join(set_parts) + f" WHERE `{pk}` = %s",
                params,
            )
            n += 1
        print(f"  - {table}: {n} 行已遷移 (pk={pk})")


def migrate_relation_tables(cur, relations, mappings) -> None:
    """迁移关联表：整行外键列全部用主表映射更新（复合主键保持唯一）。"""
    for table, fks in relations:
        cur.execute("SELECT * FROM `%s`" % table)
        rows = cur.fetchall()
        if not rows:
            print(f"  - {table}: 空表，跳過")
            continue
        n = 0
        for r in rows:
            set_parts: list[str] = []
            params: list = []
            where_parts: list[str] = []
            where_params: list = []
            for fk, ref_table in fks:
                old = int(r[fk])
                new = mappings[ref_table][old]
                set_parts.append(f"`{fk}` = %s")
                params.append(new)
                where_parts.append(f"`{fk}` = %s")
                where_params.append(old)
            cur.execute(
                f"UPDATE `{table}` SET " + ", ".join(set_parts)
                + " WHERE " + " AND ".join(where_parts),
                params + where_params,
            )
            n += 1
        print(f"  - {table}: {n} 行已遷移")


def remove_auto_increment(cur, table: str, pk: str) -> None:
    """移除主键列的 AUTO_INCREMENT（保留类型/可空/默认/注释）。"""
    cur.execute(
        """SELECT COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT
           FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
        (table, pk),
    )
    col = cur.fetchone()
    if col is None:
        print(f"  !! {table}.{pk} 不存在，跳過")
        return
    col_type = col["COLUMN_TYPE"]
    nullable = "NULL" if col["IS_NULLABLE"] == "YES" else "NOT NULL"
    default = col["COLUMN_DEFAULT"]
    comment = col["COLUMN_COMMENT"] or ""
    ddl = f"ALTER TABLE `{table}` MODIFY `{pk}` {col_type} {nullable}"
    if default is not None:
        if isinstance(default, str):
            ddl += f" DEFAULT '{default}'"
        else:
            ddl += f" DEFAULT {default}"
    if comment:
        ddl += f" COMMENT '{comment}'"
    cur.execute(ddl)


def verify_references(cur) -> None:
    """校验外键引用完整性：所有 FK 指向的主键都应存在。"""
    cur.execute(
        """SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME,
                  REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
           FROM information_schema.KEY_COLUMN_USAGE
           WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
             AND (TABLE_NAME LIKE 'building_%' OR REFERENCED_TABLE_NAME LIKE 'building_%'
                  OR TABLE_NAME LIKE 'sys_%' OR REFERENCED_TABLE_NAME LIKE 'sys_%')"""
    )
    fks = cur.fetchall()
    bad = 0
    for fk in fks:
        t, col, rt, rcol = fk["TABLE_NAME"], fk["COLUMN_NAME"], fk["REFERENCED_TABLE_NAME"], fk["REFERENCED_COLUMN_NAME"]
        # building 系列复合外键：(id, floor_id) / (cell_id, floor_id) 等，逐列校验即可
        sql = (
            f"SELECT COUNT(*) AS c FROM `{t}` child "
            f"LEFT JOIN `{rt}` parent ON parent.`{rcol}` = child.`{col}` "
            f"WHERE child.`{col}` IS NOT NULL AND parent.`{rcol}` IS NULL"
        )
        cur.execute(sql)
        cnt = int(cur.fetchone()["c"])
        if cnt:
            bad += 1
            print(f"  !! 引用不完整: {t}.{col} -> {rt}.{rcol} 有 {cnt} 行懸空")
    if bad == 0:
        print("  外鍵引用完整性 OK（無懸空引用）")
    else:
        print(f"  !! 共 {bad} 個外鍵存在懸空引用，請檢查！")


def main() -> None:
    settings = load_settings()
    conn = pymysql.connect(
        host=settings.wingon_db_host,
        port=settings.wingon_db_port,
        user=settings.wingon_db_user,
        password=settings.wingon_db_password,
        database=settings.wingon_db_name,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            if already_snowflake(cur, "building", "id"):
                print("building.id 已是雪花 ID，腳本已執行過，退出。")
                return

            print("== 階段一：DML 遷移（事務） ==")
            try:
                cur.execute("SET FOREIGN_KEY_CHECKS = 0")

                mappings: dict[str, dict[int, int]] = {}
                for table, pk, _ in BUILDING_TABLES + SYS_TABLES:
                    mappings[table] = get_mapping(cur, table, pk)
                    print(f"  建立映射 {table}: {len(mappings[table])} 行")

                migrate_primary_tables(cur, BUILDING_TABLES, mappings)
                migrate_primary_tables(cur, SYS_TABLES, mappings)
                migrate_relation_tables(cur, SYS_RELATIONS, mappings)

                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
                conn.commit()
                print("  階段一提交成功")
            except Exception:
                conn.rollback()
                cur.execute("SET FOREIGN_KEY_CHECKS = 1")
                print("階段一失敗，已整體回滾（數據未變）。", file=sys.stderr)
                raise

            print("== 階段二：移除 AUTO_INCREMENT（DDL） ==")
            with conn.cursor() as cur2:
                for table, pk, _ in BUILDING_TABLES + SYS_TABLES:
                    remove_auto_increment(cur2, table, pk)
                    print(f"  - {table}.{pk} 已移除 AUTO_INCREMENT")
                conn.commit()

            print("== 階段三：關聯完整性校驗 ==")
            with conn.cursor() as cur3:
                verify_references(cur3)

            print("\n遷移完成。")
            print("如需還原：mariadb-dump 導入 db_backup/snowflake_before_*/WingOnIOT_tables.sql")
    finally:
        conn.close()


if __name__ == "__main__":
    main()