#!/usr/bin/env python3
"""WingOnIOT 风险修复后的增删改查回归测试（对真实库，测试后自动还原现场）。

覆盖：
  - 查询层回归（3D 楼宇图数据不变：building_cell 全表快照前后 diff）
  - R7  设备绑定/解绑（一设备一格）
  - R3  assign_room_cell 一格一房 + 触发器拦截直插
  - R4  房间软删/恢复（room_cell 级联软删/恢复）
  - R1/R2 cell_edit 软删格子联动清理关联 + undo 恢复
  - R8  表名小写后查询接口正常
"""

from __future__ import annotations

import pymysql

from app.config import load_settings
from app.db import Database

settings = load_settings()
db = Database(settings)

FAILED = []


def check(name: str, cond: bool, detail: str = "") -> bool:
    flag = "PASS" if cond else "FAIL"
    print(f"{flag} | {name}" + (f" | {detail}" if detail else ""))
    if not cond:
        FAILED.append(name)
    return cond


def conn() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=settings.wingon_db_host,
        port=settings.wingon_db_port,
        user=settings.wingon_db_user,
        password=settings.wingon_db_password,
        database=settings.wingon_db_name,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def cell_snapshot() -> list[tuple]:
    with conn() as c, c.cursor() as cur:
        cur.execute(
            """SELECT id, building_id, floor_id, row_no, col_no, x, y, z, length, width,
                      cell_height, rotation_xyz, is_active, shape, color, render_height,
                      is_deleted
               FROM building_cell ORDER BY id"""
        )
        rows = cur.fetchall()
        return [(tuple(sorted(r.items()))) for r in rows]


def room_snapshot() -> list[tuple]:
    with conn() as c, c.cursor() as cur:
        cur.execute(
            """SELECT id, room_id, building_id, floor_id, room_number, room_type, area, is_deleted
               FROM room ORDER BY id"""
        )
        rows = cur.fetchall()
        return [(tuple(sorted(r.items()))) for r in rows]


def room_cell_snapshot() -> list[tuple]:
    with conn() as c, c.cursor() as cur:
        cur.execute(
            """SELECT id, room_ref_id, floor_id, cell_id, is_deleted FROM room_cell ORDER BY id"""
        )
        rows = cur.fetchall()
        return [(tuple(sorted(r.items()))) for r in rows]


def device_cell_snapshot() -> list[tuple]:
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT id, sn, cell_id, floor_id FROM device_cell ORDER BY id")
        rows = cur.fetchall()
        return [(tuple(sorted(r.items()))) for r in rows]


def main() -> None:
    # ---------- 前置快照 ----------
    cells_before = cell_snapshot()
    rooms_before = room_snapshot()
    rc_before = room_cell_snapshot()
    dc_before = device_cell_snapshot()
    print(f"[snapshot] building_cell={len(cells_before)} room={len(rooms_before)} "
          f"room_cell={len(rc_before)} device_cell={len(dc_before)}")

    # ---------- 0. 查询层回归（表名小写后所有接口正常） ----------
    buildings = db.list_buildings()
    check("list_buildings", len(buildings) >= 1, f"count={len(buildings)}")

    floors = db.list_floors()
    check("list_floors", len(floors) >= 1, f"count={len(floors)}")

    shapes = db.list_cell_shapes()
    check("list_cell_shapes", len(shapes) > 0, f"count={len(shapes)}")

    floor0 = floors[0]
    cells = db.list_floor_cells(floor0["id"])
    check("list_floor_cells", isinstance(cells, list), f"floor={floor0['id']} cells={len(cells)}")

    rooms = db.list_floor_rooms(floor0["id"])
    check("list_floor_rooms", isinstance(rooms, list), f"rooms={len(rooms)}")

    env_devices = db.list_environment_devices()
    check("list_environment_devices", len(env_devices) == 25, f"count={len(env_devices)}")

    monitoring, total = db.list_environment_monitoring(limit=5)
    check("list_environment_monitoring", total > 0 and len(monitoring) <= 5,
          f"total={total} page={len(monitoring)}")

    summary = db.floor_environment_summary()
    check("floor_environment_summary", isinstance(summary, list), f"floors={len(summary)}")

    # ---------- 1. R7 设备绑定/解绑（一设备一格，表名小写后 FK 正常） ----------
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT sn, floor FROM Environment_Device ORDER BY sn LIMIT 1")
        dev = cur.fetchone()
        dev_sn = dev["sn"]
        dev_level = db.floor_to_level(dev["floor"])
        # 找与设备楼层一致的 floor_id（3D 层号匹配）
        cur.execute(
            "SELECT id, level FROM floor WHERE is_deleted = 0 ORDER BY level"
        )
        floors_all = cur.fetchall()
    matching_fid = next(
        (f["id"] for f in floors_all if db.floor_level_to_3d(int(f["level"])) == dev_level),
        None,
    )
    check("find matching floor for device", matching_fid is not None,
          f"sn={dev_sn} floor={dev['floor']} dev_level={dev_level} fid={matching_fid}")
    with conn() as c, c.cursor() as cur:
        cur.execute(
            """SELECT floor_id, row_no, col_no FROM building_cell
               WHERE floor_id = %s AND is_deleted = 0 AND shape <> 'Hidden'
               ORDER BY row_no, col_no LIMIT 2""",
            (matching_fid,),
        )
        c1, c2 = cur.fetchall()
    check("select two cells on matching floor", bool(c1) and bool(c2), f"c1={c1} c2={c2}")

    r = db.bind_device_cell(dev_sn, c1["floor_id"], c1["row_no"], c1["col_no"])
    check("bind_device_cell#1", r == "ok", f"result={r}")
    r = db.bind_device_cell(dev_sn, c2["floor_id"], c2["row_no"], c2["col_no"])
    check("bind_device_cell#2(replace)", r == "ok", f"result={r}")

    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM device_cell WHERE sn = %s", (dev_sn,))
        n = cur.fetchone()["cnt"]
        cur.execute(
            "SELECT cell_id FROM device_cell WHERE sn = %s ORDER BY id DESC LIMIT 1",
            (dev_sn,),
        )
        last_cell = cur.fetchone()["cell_id"]
    check("one_device_one_cell", n == 1, f"rows={n} (expect 1, replaced to cell {last_cell})")

    # 绑定到已软删格子
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT floor_id, row_no, col_no FROM building_cell WHERE is_deleted = 1 LIMIT 1")
        gone = cur.fetchone()
    if gone:
        r = db.bind_device_cell(dev_sn, gone["floor_id"], gone["row_no"], gone["col_no"])
        check("bind_device_cell->soft-deleted cell", r == "cell_not_found", f"result={r}")

    r = db.unbind_device_cell(dev_sn)
    check("unbind_device_cell", r is True, f"result={r}")
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM device_cell WHERE sn = %s", (dev_sn,))
        check("device_cell empty after unbind", cur.fetchone()["cnt"] == 0)

    # ---------- 2. R3 一格一房：assign_room_cell + 触发器 ----------
    # 找一个当前未被任何房间占用的 active 格子
    with conn() as c, c.cursor() as cur:
        cur.execute(
            """SELECT bc.floor_id, bc.row_no, bc.col_no FROM building_cell bc
               LEFT JOIN room_cell rc ON rc.cell_id = bc.id
                  AND rc.floor_id = bc.floor_id AND rc.is_deleted = 0
               JOIN floor f ON f.id = bc.floor_id AND f.is_deleted = 0
               WHERE bc.is_deleted = 0 AND bc.shape <> 'Hidden' AND rc.id IS NULL
               ORDER BY bc.floor_id, bc.row_no, bc.col_no LIMIT 1"""
        )
        free_cell = cur.fetchone()
        cur.execute(
            "SELECT room_id FROM room WHERE is_deleted = 0 AND floor_id = %s ORDER BY id LIMIT 2",
            (free_cell["floor_id"],),
        )
        room_rows = cur.fetchall()
    check("find free cell + two rooms", free_cell is not None and len(room_rows) == 2,
          f"cell={free_cell} rooms={[r['room_id'] for r in room_rows]}")
    roomA, roomB = room_rows[0]["room_id"], room_rows[1]["room_id"]
    fid, rrow, rcol = free_cell["floor_id"], free_cell["row_no"], free_cell["col_no"]

    r = db.assign_room_cell(roomA, fid, rrow, rcol)
    check("assign_room_cell(A)", r == "added", f"result={r}")
    with conn() as c, c.cursor() as cur:
        cur.execute(
            """SELECT rc.room_ref_id, r.room_id FROM room_cell rc
               JOIN room r ON r.id = rc.room_ref_id
               WHERE rc.cell_id = (SELECT id FROM building_cell WHERE floor_id=%s AND row_no=%s AND col_no=%s AND is_deleted=0)
                 AND rc.is_deleted = 0""",
            (fid, rrow, rcol),
        )
        owner = cur.fetchone()
    check("cell owned by A", owner is not None and owner["room_id"] == roomA,
          f"owner={owner}")

    # 直插 B 到同一格子 → 触发器必须拒绝
    trig_ok = False
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM room WHERE room_id = %s", (roomB,))
        bid = cur.fetchone()["id"]
        cur.execute("SELECT id FROM building_cell WHERE floor_id=%s AND row_no=%s AND col_no=%s AND is_deleted=0", (fid, rrow, rcol))
        cell_db_id = cur.fetchone()["id"]
        try:
            cur.execute(
                "INSERT INTO room_cell (room_ref_id, floor_id, cell_id) VALUES (%s, %s, %s)",
                (bid, fid, cell_db_id),
            )
        except pymysql.MySQLError as e:
            trig_ok = "already occupied" in str(e) or "45000" in str(e)
    check("trigger blocks two-room same cell", trig_ok)

    r = db.assign_room_cell(roomB, fid, rrow, rcol)
    check("assign_room_cell(B) steals", r == "added", f"result={r}")
    with conn() as c, c.cursor() as cur:
        cur.execute(
            """SELECT rc.room_ref_id, r.room_id FROM room_cell rc
               JOIN room r ON r.id = rc.room_ref_id
               WHERE rc.cell_id = (SELECT id FROM building_cell WHERE floor_id=%s AND row_no=%s AND col_no=%s AND is_deleted=0)
                 AND rc.is_deleted = 0""",
            (fid, rrow, rcol),
        )
        owner = cur.fetchone()
    check("cell owned by B (A released)", owner is not None and owner["room_id"] == roomB,
          f"owner={owner}")

    r = db.assign_room_cell(roomB, fid, rrow, rcol)
    check("assign_room_cell(B) removes", r == "removed", f"result={r}")
    with conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM room_cell WHERE floor_id=%s AND cell_id=%s AND is_deleted=0",
            (fid, cell_db_id),
        )
        check("free cell released", cur.fetchone()["cnt"] == 0)

    # ---------- 3. 房间物理删除（房间=格子集合，可重建，不留伪删除） ----------
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT MAX(id) AS max_id FROM room")
        tmp_rid = int(cur.fetchone()["max_id"]) + 1
        cur.execute("SELECT MIN(id) AS min_fid, building_id FROM floor WHERE is_deleted = 0")
        frow = cur.fetchone()
        test_fid = int(frow["min_fid"])
        test_bid = int(frow["building_id"])
        cur.execute(
            """SELECT bc.id, bc.floor_id, bc.row_no, bc.col_no FROM building_cell bc
               LEFT JOIN room_cell rc ON rc.cell_id = bc.id
                  AND rc.floor_id = bc.floor_id AND rc.is_deleted = 0
               WHERE bc.floor_id = %s AND bc.is_deleted = 0 AND bc.shape <> 'Hidden'
                 AND rc.id IS NULL
               LIMIT 1""",
            (test_fid,),
        )
        rcell = cur.fetchone()
        tmp_room_id = f"test-room-{tmp_rid}"
        cur.execute(
            """INSERT INTO room (room_id, building_id, floor_id, room_number, is_deleted)
               VALUES (%s, %s, %s, %s, 0)""",
            (tmp_room_id, test_bid, test_fid, f"TEST-{tmp_rid}"),
        )
    check("create temp room for delete test", rcell is not None,
          f"cell={rcell} tmp_room={tmp_room_id}")
    ar = db.assign_room_cell(tmp_room_id, rcell["floor_id"], rcell["row_no"], rcell["col_no"])
    check("assign cell to temp room", ar in ("added", "removed"), f"result={ar}")
    ok = db.delete_room(tmp_room_id)
    check("delete_room (physical)", ok, f"room={tmp_room_id}")
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM room WHERE room_id = %s", (tmp_room_id,))
        room_cnt = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM room_cell WHERE cell_id = %s", (rcell["id"],))
        rc_cnt = cur.fetchone()["cnt"]
    check("room row physically gone", room_cnt == 0, f"cnt={room_cnt}")
    check("room_cell cascade deleted", rc_cnt == 0, f"room_cell rows={rc_cnt}")
    rooms_after_del = [x["room_id"] for x in db.list_floor_rooms(test_fid)]
    check("deleted room excluded from floor rooms", tmp_room_id not in rooms_after_del)
    ok = db.delete_room(tmp_room_id)
    check("delete_room missing -> False", ok is False)

    # ---------- 4. R1/R2 cell_edit 软删格子联动清理 + undo ----------
    with conn() as c, c.cursor() as cur:
        cur.execute(
            """SELECT bc.id, bc.building_id, bc.floor_id, bc.row_no, bc.col_no, bc.shape, bc.is_active
               FROM building_cell bc
               LEFT JOIN room_cell rc ON rc.cell_id = bc.id AND rc.floor_id = bc.floor_id AND rc.is_deleted = 0
               LEFT JOIN device_cell dc ON dc.cell_id = bc.id
               WHERE bc.floor_id = %s AND bc.is_deleted = 0 AND bc.shape <> 'Hidden'
                 AND rc.id IS NULL AND dc.id IS NULL
               ORDER BY bc.floor_id, bc.row_no, bc.col_no LIMIT 1""",
            (matching_fid,),
        )
        victim = cur.fetchone()
        if victim is None:
            check("find cell_edit victim", False, "no clean cell to test")
            return
        victim_id = victim["id"]
    # 先给它绑一个设备 + 占一个房间，验证联动清理
    r = db.bind_device_cell(dev_sn, victim["floor_id"], victim["row_no"], victim["col_no"])
    check("bind device to victim", r == "ok", f"result={r}")
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT room_id FROM room WHERE is_deleted = 0 AND floor_id = %s ORDER BY id LIMIT 1", (matching_fid,))
        vr = cur.fetchone()
    ar = db.assign_room_cell(vr["room_id"], victim["floor_id"], victim["row_no"], victim["col_no"])
    check("assign room to victim", ar in ("added", "removed"), f"result={ar}")

    res = db.cell_edit(
        building_id=victim["building_id"], row_no=victim["row_no"], col_no=victim["col_no"],
        action="delete", scope="single", floor_id=victim["floor_id"],
    )
    check("cell_edit delete", res.get("ok") and res.get("affected") >= 1, f"res={res}")
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT is_deleted FROM building_cell WHERE id = %s", (victim_id,))
        cell_flag = cur.fetchone()["is_deleted"]
        cur.execute("SELECT COUNT(*) AS cnt FROM device_cell WHERE sn = %s", (dev_sn,))
        dc_cnt = cur.fetchone()["cnt"]
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM room_cell WHERE cell_id = %s AND is_deleted = 0",
            (victim_id,),
        )
        rc_active = cur.fetchone()["cnt"]
    check("cell soft-deleted", cell_flag == 1)
    check("device_cell cleaned up", dc_cnt == 0, f"device_cell rows={dc_cnt}")
    check("room_cell soft-cleaned", rc_active == 0, f"active_rc={rc_active}")

    res = db.undo_last_edit()
    check("undo restores cell + bindings", res.get("ok"), f"res={res}")
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT is_deleted FROM building_cell WHERE id = %s", (victim_id,))
        cell_flag = cur.fetchone()["is_deleted"]
        cur.execute("SELECT COUNT(*) AS cnt FROM device_cell WHERE sn = %s", (dev_sn,))
        dc_cnt = cur.fetchone()["cnt"]
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM room_cell WHERE cell_id = %s AND is_deleted = 0",
            (victim_id,),
        )
        rc_active = cur.fetchone()["cnt"]
    check("cell restored (is_deleted=0)", cell_flag == 0)
    check("device_cell restored", dc_cnt == 1, f"device_cell rows={dc_cnt}")
    check("room_cell restored", rc_active == 1, f"active_rc={rc_active}")

    # 清理测试痕迹：解绑设备、移除测试房间占用
    db.unbind_device_cell(dev_sn)
    with conn() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM room WHERE room_id = %s", (vr["room_id"],))
        vrid = cur.fetchone()["id"]
        cur.execute(
            "DELETE FROM room_cell WHERE room_ref_id = %s AND cell_id = %s",
            (vrid, victim_id),
        )

    # ---------- 5. 现场一致性：3D 楼宇图数据必须未变 ----------
    cells_after = cell_snapshot()
    rooms_after = room_snapshot()
    rc_after = room_cell_snapshot()
    dc_after = device_cell_snapshot()
    check("3D building_cell data unchanged", cells_after == cells_before,
          f"before={len(cells_before)} after={len(cells_after)}")
    check("room data unchanged", rooms_after == rooms_before)
    check("room_cell data unchanged", rc_after == rc_before)
    check("device_cell data unchanged", dc_after == dc_before)

    print()
    if FAILED:
        print(f"RESULT: {len(FAILED)} FAILED -> {FAILED}")
        raise SystemExit(1)
    print("RESULT: ALL TESTS PASSED")


if __name__ == "__main__":
    main()
