#!/usr/bin/env python3
"""人流時數統計模組遷移：建立獨立菜單目錄（視圖 / 樓層 / 資料）。

執行方式：
    ../.venv/Scripts/python.exe migrate_people_count_module.py

動作：
  1. 刪除「樓宇監控」下舊的「人流統計」菜單（path=people-count）
  2. 新建頂級目錄「人流時數統計」，下掛 視圖/樓層/資料 3 個 C 菜單
  3. 清理「設備」子菜單與 people_count_device 表（設備功能已移除）
  4. 將新菜單授權給超級管理員角色
  5. 清理歷史大屏白名單
"""

from __future__ import annotations

import pymysql

from app.config import load_settings
from app.snowflake import next_id


def _menu_id(cur, **kw) -> int | None:
    """按條件查找菜單 id。"""
    where = " AND ".join(f"{k} = %s" for k in kw)
    cur.execute(f"SELECT id FROM sys_menu WHERE {where}", tuple(kw.values()))
    row = cur.fetchone()
    return int(row["id"]) if row else None


def main() -> None:
    settings = load_settings()
    conn = pymysql.connect(
        host=settings.wingon_db_host,
        port=settings.wingon_db_port,
        user=settings.wingon_db_user,
        password=settings.wingon_db_password,
        database=settings.wingon_db_name,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            # ---------- 1. 刪除舊「人流統計」菜單 ----------
            old = _menu_id(cur, path="people-count", menu_type="C")
            if old:
                cur.execute("DELETE FROM sys_role_menu WHERE menu_id = %s", (old,))
                cur.execute("DELETE FROM sys_menu WHERE id = %s", (old,))
                print(f"OK: 已刪除舊人流統計菜單 id={old}")

            # ---------- 2. 新建頂級目錄（找不到才建） ----------
            dir_id = _menu_id(cur, menu_name="人流時數統計", menu_type="M")
            if dir_id is None:
                dir_id = next_id()
                cur.execute(
                    """INSERT INTO sys_menu (id, parent_id, menu_name, i18n_key, path, component,
                                             menu_type, permission, icon, sort, visible, status)
                       VALUES (%s, 0, '人流時數統計', 'menu.peopleCountMonitor', '', '', 'M', '',
                               'AreaChartOutlined', 5, 1, 1)""",
                    (dir_id,),
                )
                print(f"OK: 新建目錄 id={dir_id}")

            # ---------- 3. 子菜單（視圖/樓層/資料） ----------
            children = [
                ("視圖", "menu.peopleCountView", "people-count/view", "PeopleCountView", "FundViewOutlined", 1),
                ("樓層", "menu.peopleCountFloor", "people-count/floor", "PeopleCountFloor", "AppstoreOutlined", 2),
                ("資料", "menu.peopleCountData", "people-count/data", "PeopleCountData", "TableOutlined", 3),
            ]
            for name, i18n_key, path, component, icon, sort in children:
                cid = _menu_id(cur, path=path, menu_type="C")
                if cid is None:
                    cid = next_id()
                    cur.execute(
                        """INSERT INTO sys_menu (id, parent_id, menu_name, i18n_key, path, component,
                                                 menu_type, permission, icon, sort, visible, status)
                           VALUES (%s, %s, %s, %s, %s, %s, 'C', '', %s, %s, 1, 1)""",
                        (cid, dir_id, name, i18n_key, path, component, icon, sort),
                    )
                    print(f"OK: 新建菜單 {name} id={cid}")

            # ---------- 4. 清理「設備」功能 ----------
            dev = _menu_id(cur, path="people-count/devices", menu_type="C")
            if dev:
                cur.execute("DELETE FROM sys_role_menu WHERE menu_id = %s", (dev,))
                cur.execute("DELETE FROM sys_menu WHERE id = %s", (dev,))
                print(f"OK: 已刪除設備菜單 id={dev}")
            cur.execute("DROP TABLE IF EXISTS people_count_device")
            print("OK: people_count_device 表已刪除")

            # ---------- 5. 授權給超級管理員角色（role_id=1） ----------
            cur.execute(
                """INSERT IGNORE INTO sys_role_menu (role_id, menu_id)
                   SELECT 1, id FROM sys_menu
                   WHERE parent_id = %s OR id = %s""",
                (dir_id, dir_id),
            )
            print("OK: 已授權超級管理員角色")

            # ---------- 6. 清理歷史大屏白名單（大屏功能已移除） ----------
            cur.execute("DELETE FROM sys_whitelist WHERE path IN ('/people-count/view', '/api/v1/people-count')")
            if cur.rowcount:
                print(f"OK: 已清理 {cur.rowcount} 筆大屏白名單")

            print("\n遷移完成。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()