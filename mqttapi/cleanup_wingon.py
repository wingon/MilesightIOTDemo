#!/usr/bin/env python3
"""WingOnIOT 数据治理定时任务（建议每日运行）。

功能：
  1. 孤儿清理：删除 room_cell / device_cell 中指向"不存在或已软删格子"的残留（R1/R2 兜底）
  2. 超期软删清理：超过保留期（默认 90 天）的 building_cell / room / floor / building
     软删行物理删除（软删时间以 updated_at 为准）
  3. 分区维护：确保 environmental_monitoring 存在"当前月"分区（REORGANIZE pmax）
  4. 分区淘汰：--drop-partitions 删除超过 months-to-keep 的整月分区
     （配合 --downsample 时，先聚合到 environmental_monitoring_daily 再删除）

用法：
  python cleanup_wingon.py                 # 孤儿 + 超期软删 + 加分区（不删分区）
  python cleanup_wingon.py --drop-partitions
  python cleanup_wingon.py --drop-partitions --downsample
  python cleanup_wingon.py --dry-run
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

import pymysql

from app.config import load_settings

TABLE = "Environmental_Monitoring"
DAILY_TABLE = "Environmental_Monitoring_Daily"

DAILY_DDL = f"""
CREATE TABLE IF NOT EXISTS `{DAILY_TABLE}` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `sn` varchar(20) DEFAULT NULL,
  `toDateTime` datetime DEFAULT NULL,
  `temperatureMin` decimal(6,1) DEFAULT NULL,
  `temperatureMedian` decimal(6,1) DEFAULT NULL,
  `temperatureMax` decimal(6,1) DEFAULT NULL,
  `humidityMin` decimal(6,1) DEFAULT NULL,
  `humidityMedian` decimal(6,1) DEFAULT NULL,
  `humidityMax` decimal(6,1) DEFAULT NULL,
  `InsertAt` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sn_day` (`sn`,`toDateTime`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci ROW_FORMAT=DYNAMIC
"""


def month_idx(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def partitions(cur) -> list[tuple[str, int]]:
    """Return [(partition_name, month_idx), ...] excluding pmax."""
    cur.execute(
        "SELECT partition_name FROM information_schema.partitions "
        "WHERE table_schema = DATABASE() AND table_name = %s AND partition_name IS NOT NULL",
        (TABLE,),
    )
    result: list[tuple[str, int]] = []
    for row in cur.fetchall():
        name = row["partition_name"]
        if name == "pmax":
            continue
        try:
            y, m = int(name[1:5]), int(name[5:7])
        except (ValueError, IndexError):
            continue
        result.append((name, month_idx(y, m)))
    return result


def cleanup_orphans(cur, dry_run: bool = False) -> dict[str, int]:
    """物理删除指向不存在/软删格子的残留绑定。"""
    stats: dict[str, int] = {}
    if dry_run:
        cur.execute(
            """SELECT COUNT(*) AS cnt FROM room_cell rc
               LEFT JOIN building_cell c
                 ON c.id = rc.cell_id AND c.floor_id = rc.floor_id AND c.is_deleted = 0
               WHERE c.id IS NULL"""
        )
        stats["room_cell_orphans"] = int(cur.fetchone()["cnt"])
        cur.execute(
            """SELECT COUNT(*) AS cnt FROM device_cell dc
               LEFT JOIN building_cell c
                 ON c.id = dc.cell_id AND c.floor_id = dc.floor_id AND c.is_deleted = 0
               WHERE c.id IS NULL"""
        )
        stats["device_cell_orphans"] = int(cur.fetchone()["cnt"])
        return stats
    cur.execute(
        """DELETE rc FROM room_cell rc
           LEFT JOIN building_cell c
             ON c.id = rc.cell_id AND c.floor_id = rc.floor_id AND c.is_deleted = 0
           WHERE c.id IS NULL"""
    )
    stats["room_cell_orphans"] = cur.rowcount
    cur.execute(
        """DELETE dc FROM device_cell dc
           LEFT JOIN building_cell c
             ON c.id = dc.cell_id AND c.floor_id = dc.floor_id AND c.is_deleted = 0
           WHERE c.id IS NULL"""
    )
    stats["device_cell_orphans"] = cur.rowcount
    return stats


def cleanup_expired_soft_deletes(cur, retention_days: int, dry_run: bool = False) -> dict[str, int]:
    """物理删除超过保留期的软删行（先子后父，利用 FK CASCADE 清关联）。"""
    cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
    stats: dict[str, int] = {}
    for table in ("building_cell", "room", "floor", "building"):
        if dry_run:
            cur.execute(
                f"SELECT COUNT(*) AS cnt FROM {table} WHERE is_deleted = 1 AND updated_at < %(cutoff)s",
                {"cutoff": cutoff},
            )
            stats[table] = int(cur.fetchone()["cnt"])
        else:
            cur.execute(
                f"DELETE FROM {table} WHERE is_deleted = 1 AND updated_at < %(cutoff)s",
                {"cutoff": cutoff},
            )
            stats[table] = cur.rowcount
    return stats


def ensure_current_partition(cur, dry_run: bool = False) -> list[str]:
    """确保存在当前月份分区（数据进入 pmax 兜底前提前分裂）。"""
    now = datetime.now()
    cur_idx = month_idx(now.year, now.month)
    existing = dict(partitions(cur))
    if not existing:
        return ["no partitions found"]
    max_idx = max(existing.values())
    actions: list[str] = []
    if max_idx >= cur_idx:
        actions.append(f"partition up-to-date (max p{max_idx // 12}{max_idx % 12 + 1:02d})")
        return actions
    for idx in range(max_idx + 1, cur_idx + 1):
        y, m = idx // 12, idx % 12 + 1
        pname = f"p{y}{m:02d}"
        d = datetime(y, m, 1) + timedelta(days=32)
        bound = f"{d.year:04d}-{d.month:02d}-01"
        if dry_run:
            actions.append(f"would add {pname} (< {bound})")
            continue
        cur.execute(
            f"ALTER TABLE {TABLE} REORGANIZE PARTITION pmax INTO ("
            f"PARTITION {pname} VALUES LESS THAN (TO_DAYS('{bound}')), "
            f"PARTITION pmax VALUES LESS THAN MAXVALUE)"
        )
        actions.append(f"added {pname} (< {bound})")
    return actions


def downsample_partition(cur, pname: str) -> int:
    """把某分区聚合到日维度表。返回聚合行数。"""
    cur.execute(DAILY_DDL)
    sql = f"""
        INSERT INTO {DAILY_TABLE}
            (sn, toDateTime, temperatureMin, temperatureMedian, temperatureMax,
             humidityMin, humidityMedian, humidityMax)
        SELECT sn,
               DATE_FORMAT(toDateTime, '%Y-%m-%d 00:00:00'),
               MIN(temperatureMin), ROUND(AVG(temperatureMedian), 1), MAX(temperatureMax),
               MIN(humidityMin), ROUND(AVG(humidityMedian), 1), MAX(humidityMax)
        FROM {TABLE} PARTITION ({pname})
        GROUP BY sn, DATE_FORMAT(toDateTime, '%Y-%m-%d')
        ON DUPLICATE KEY UPDATE
            temperatureMedian = VALUES(temperatureMedian),
            humidityMedian = VALUES(humidityMedian)
    """
    cur.execute(sql)
    return cur.rowcount


def drop_expired_partitions(cur, keep_months: int, downsample: bool, dry_run: bool = False) -> list[str]:
    """删除超过 keep_months 个月的整月分区。返回动作列表。"""
    now = datetime.now()
    cutoff_idx = month_idx(now.year, now.month) - keep_months
    actions: list[str] = []
    for pname, idx in sorted(partitions(cur), key=lambda x: x[1]):
        if idx > cutoff_idx:
            continue
        if dry_run:
            actions.append(f"would drop {pname}")
            continue
        if downsample:
            n = downsample_partition(cur, pname)
            actions.append(f"downsampled {pname} -> {DAILY_TABLE} ({n} rows)")
        cur.execute(f"ALTER TABLE {TABLE} DROP PARTITION {pname}")
        actions.append(f"dropped {pname}")
    return actions


def main() -> None:
    parser = argparse.ArgumentParser(description="WingOnIOT data governance tasks")
    parser.add_argument("--dry-run", action="store_true", help="Only report, no writes")
    parser.add_argument("--soft-retention-days", type=int, default=90,
                        help="Soft-deleted rows older than this are physically removed")
    parser.add_argument("--months-to-keep", type=int, default=4,
                        help="Keep this many monthly partitions (old ones are dropped)")
    parser.add_argument("--drop-partitions", action="store_true",
                        help="Drop expired monthly partitions")
    parser.add_argument("--downsample", action="store_true",
                        help="Aggregate dropped partitions into the daily table first")
    args = parser.parse_args()

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
            orphan_stats = cleanup_orphans(cur, dry_run=args.dry_run)
            print("orphan cleanup: "
                  f"room_cell={orphan_stats['room_cell_orphans']}, "
                  f"device_cell={orphan_stats['device_cell_orphans']}")

            exp_stats = cleanup_expired_soft_deletes(
                cur, args.soft_retention_days, dry_run=args.dry_run
            )
            print("expired soft-delete cleanup "
                  f"(>{args.soft_retention_days}d): "
                  + ", ".join(f"{k}={v}" for k, v in exp_stats.items()))

            part_actions = ensure_current_partition(cur, dry_run=args.dry_run)
            print("partition ensure: " + "; ".join(part_actions))

            if args.drop_partitions:
                drop_actions = drop_expired_partitions(
                    cur, args.months_to_keep, args.downsample, dry_run=args.dry_run
                )
                print(f"partition expiry (keep {args.months_to_keep} months): "
                      + "; ".join(drop_actions) if drop_actions else "nothing to drop")
            elif args.downsample:
                print("--downsample requires --drop-partitions; ignored")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
