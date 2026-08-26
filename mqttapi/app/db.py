import json
import logging
import re
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from .config import Settings
from .decoder import JSON_SECTION_KEYS

logger = logging.getLogger(__name__)

TOF_JSON_COLUMNS = (
    *JSON_SECTION_KEYS,
    "payload_json",
)
UG65_JSON_COLUMNS = (
    "rx_info_json",
    "tx_info_json",
    "payload_json",
)

# In-memory undo stack shared across Database instances (module-level).
# Holds the last cell_edit / reset_grid_extras operations so they can be undone
# by later requests. Capacity is capped at UNDO_LIMIT (oldest entries are dropped).
_UNDO_STACK: list[dict[str, Any]] = []
# Maximum number of undoable operations kept in the stack (10-step undo).
_UNDO_LIMIT = 10


def _push_undo(ops: list[dict[str, Any]], affected: int) -> None:
    """Append an undo record, dropping the oldest entry when over the limit."""
    _UNDO_STACK.append({"ops": ops, "affected": affected})
    if len(_UNDO_STACK) > _UNDO_LIMIT:
        _UNDO_STACK.pop(0)


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings

    @contextmanager
    def connection(self):
        conn = pymysql.connect(
            host=self.settings.db_host,
            port=self.settings.db_port,
            user=self.settings.db_user,
            password=self.settings.db_password,
            database=self.settings.db_name,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
        )
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def wingon_connection(self):
        """WingOnIOT 环境监测库连接（同一 MySQL 实例的另一个库）。"""
        conn = pymysql.connect(
            host=self.settings.wingon_db_host,
            port=self.settings.wingon_db_port,
            user=self.settings.wingon_db_user,
            password=self.settings.wingon_db_password,
            database=self.settings.wingon_db_name,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
        )
        try:
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _json_value(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value

    @staticmethod
    def _parse_json_fields(row: dict[str, Any] | None, columns: tuple[str, ...]) -> dict[str, Any] | None:
        if row is None:
            return None
        for key in columns:
            value = row.get(key)
            if isinstance(value, str):
                try:
                    row[key] = json.loads(value)
                except json.JSONDecodeError:
                    pass
            elif isinstance(value, Decimal):
                row[key] = float(value)
        for key, value in list(row.items()):
            if isinstance(value, Decimal):
                row[key] = float(value)
            elif isinstance(value, datetime):
                row[key] = value.isoformat(sep=" ")
        return row

    def insert_tof(self, record: dict[str, Any]) -> int:
        payload_json = self._json_value(record.get("payload_json"))
        json_sections = {
            key: self._json_value(record.get(key)) for key in JSON_SECTION_KEYS
        }

        sql = """
            INSERT INTO tof (
                topic, qos,
                device_name, device_sn, device_mac, wlan_mac, ip_address,
                custom_device_id, custom_site_id, running_time_sec,
                firmware_version, hardware_version,
                trigger_time, start_time, end_time, time_zone, dst_enable, dst_status,
                imei, battery_pct, temperature_c, distance_mm, position_status,
                signal_asu, frame_counter,
                line_trigger_data, region_trigger_data, region_count_data,
                dwell_time_data, dwell_start_time, line_periodic_data, line_total_data,
                line_count_data, region_periodic_data, alarm_data,
                payload_hex, payload_json, raw_message
            ) VALUES (
                %(topic)s, %(qos)s,
                %(device_name)s, %(device_sn)s, %(device_mac)s, %(wlan_mac)s, %(ip_address)s,
                %(custom_device_id)s, %(custom_site_id)s, %(running_time_sec)s,
                %(firmware_version)s, %(hardware_version)s,
                %(trigger_time)s, %(start_time)s, %(end_time)s, %(time_zone)s,
                %(dst_enable)s, %(dst_status)s,
                %(imei)s, %(battery_pct)s, %(temperature_c)s, %(distance_mm)s, %(position_status)s,
                %(signal_asu)s, %(frame_counter)s,
                %(line_trigger_data)s, %(region_trigger_data)s, %(region_count_data)s,
                %(dwell_time_data)s, %(dwell_start_time)s, %(line_periodic_data)s, %(line_total_data)s,
                %(line_count_data)s, %(region_periodic_data)s, %(alarm_data)s,
                %(payload_hex)s, %(payload_json)s, %(raw_message)s
            )
        """
        params = {
            "topic": record.get("topic"),
            "qos": record.get("qos"),
            "device_name": record.get("device_name"),
            "device_sn": record.get("device_sn"),
            "device_mac": record.get("device_mac"),
            "wlan_mac": record.get("wlan_mac"),
            "ip_address": record.get("ip_address"),
            "custom_device_id": record.get("custom_device_id"),
            "custom_site_id": record.get("custom_site_id"),
            "running_time_sec": record.get("running_time_sec"),
            "firmware_version": record.get("firmware_version"),
            "hardware_version": record.get("hardware_version"),
            "trigger_time": record.get("trigger_time"),
            "start_time": record.get("start_time"),
            "end_time": record.get("end_time"),
            "time_zone": record.get("time_zone"),
            "dst_enable": record.get("dst_enable"),
            "dst_status": record.get("dst_status"),
            "imei": record.get("imei"),
            "battery_pct": record.get("battery_pct"),
            "temperature_c": record.get("temperature_c"),
            "distance_mm": record.get("distance_mm"),
            "position_status": record.get("position_status"),
            "signal_asu": record.get("signal_asu"),
            "frame_counter": record.get("frame_counter"),
            "payload_hex": record.get("payload_hex"),
            "payload_json": payload_json,
            "raw_message": record.get("raw_message"),
            **json_sections,
        }
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return int(cur.lastrowid)

    def update_tof_from_record(self, row_id: int, record: dict[str, Any]) -> None:
        payload_json = self._json_value(record.get("payload_json"))
        json_sections = {
            key: self._json_value(record.get(key)) for key in JSON_SECTION_KEYS
        }

        sql = """
            UPDATE tof SET
                device_name=%(device_name)s, device_sn=%(device_sn)s,
                device_mac=%(device_mac)s, wlan_mac=%(wlan_mac)s, ip_address=%(ip_address)s,
                custom_device_id=%(custom_device_id)s, custom_site_id=%(custom_site_id)s,
                running_time_sec=%(running_time_sec)s,
                firmware_version=%(firmware_version)s, hardware_version=%(hardware_version)s,
                trigger_time=%(trigger_time)s, start_time=%(start_time)s, end_time=%(end_time)s,
                time_zone=%(time_zone)s, dst_enable=%(dst_enable)s, dst_status=%(dst_status)s,
                imei=%(imei)s, battery_pct=%(battery_pct)s, temperature_c=%(temperature_c)s,
                distance_mm=%(distance_mm)s, position_status=%(position_status)s,
                signal_asu=%(signal_asu)s, frame_counter=%(frame_counter)s,
                line_trigger_data=%(line_trigger_data)s, region_trigger_data=%(region_trigger_data)s,
                region_count_data=%(region_count_data)s, dwell_time_data=%(dwell_time_data)s,
                dwell_start_time=%(dwell_start_time)s, line_periodic_data=%(line_periodic_data)s,
                line_total_data=%(line_total_data)s, line_count_data=%(line_count_data)s,
                region_periodic_data=%(region_periodic_data)s, alarm_data=%(alarm_data)s,
                payload_hex=%(payload_hex)s, payload_json=%(payload_json)s
            WHERE id=%(id)s
        """
        params = {
            "id": row_id,
            "device_name": record.get("device_name"),
            "device_sn": record.get("device_sn"),
            "device_mac": record.get("device_mac"),
            "wlan_mac": record.get("wlan_mac"),
            "ip_address": record.get("ip_address"),
            "custom_device_id": record.get("custom_device_id"),
            "custom_site_id": record.get("custom_site_id"),
            "running_time_sec": record.get("running_time_sec"),
            "firmware_version": record.get("firmware_version"),
            "hardware_version": record.get("hardware_version"),
            "trigger_time": record.get("trigger_time"),
            "start_time": record.get("start_time"),
            "end_time": record.get("end_time"),
            "time_zone": record.get("time_zone"),
            "dst_enable": record.get("dst_enable"),
            "dst_status": record.get("dst_status"),
            "imei": record.get("imei"),
            "battery_pct": record.get("battery_pct"),
            "temperature_c": record.get("temperature_c"),
            "distance_mm": record.get("distance_mm"),
            "position_status": record.get("position_status"),
            "signal_asu": record.get("signal_asu"),
            "frame_counter": record.get("frame_counter"),
            "payload_hex": record.get("payload_hex"),
            "payload_json": payload_json,
            **json_sections,
        }
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)

    def insert_ug65(self, record: dict[str, Any]) -> int:
        payload_json = self._json_value(record.get("payload_json"))
        rx_info_json = self._json_value(record.get("rx_info_json"))
        tx_info_json = self._json_value(record.get("tx_info_json"))

        sql = """
            INSERT INTO ug65 (
                topic, qos,
                application_id, application_name, device_name, dev_eui, uplink_time,
                f_cnt, f_port, payload_base64, payload_hex,
                gateway_mac, gateway_name, gateway_model, rssi, lora_snr,
                frequency_hz, spread_factor, bandwidth_khz,
                rx_info_json, tx_info_json, payload_json, raw_message
            ) VALUES (
                %(topic)s, %(qos)s,
                %(application_id)s, %(application_name)s, %(device_name)s, %(dev_eui)s, %(uplink_time)s,
                %(f_cnt)s, %(f_port)s, %(payload_base64)s, %(payload_hex)s,
                %(gateway_mac)s, %(gateway_name)s, %(gateway_model)s, %(rssi)s, %(lora_snr)s,
                %(frequency_hz)s, %(spread_factor)s, %(bandwidth_khz)s,
                %(rx_info_json)s, %(tx_info_json)s, %(payload_json)s, %(raw_message)s
            )
        """
        params = {
            "topic": record.get("topic"),
            "qos": record.get("qos"),
            "application_id": record.get("application_id"),
            "application_name": record.get("application_name"),
            "device_name": record.get("device_name"),
            "dev_eui": record.get("dev_eui"),
            "uplink_time": record.get("uplink_time"),
            "f_cnt": record.get("f_cnt"),
            "f_port": record.get("f_port"),
            "payload_base64": record.get("payload_base64"),
            "payload_hex": record.get("payload_hex"),
            "gateway_mac": record.get("gateway_mac"),
            "gateway_name": record.get("gateway_name"),
            "gateway_model": record.get("gateway_model"),
            "rssi": record.get("rssi"),
            "lora_snr": record.get("lora_snr"),
            "frequency_hz": record.get("frequency_hz"),
            "spread_factor": record.get("spread_factor"),
            "bandwidth_khz": record.get("bandwidth_khz"),
            "rx_info_json": rx_info_json,
            "tx_info_json": tx_info_json,
            "payload_json": payload_json,
            "raw_message": record.get("raw_message"),
        }
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return int(cur.lastrowid)

    def ping(self) -> bool:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                return cur.fetchone() is not None

    def get_stats(self) -> dict[str, Any]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS cnt, MAX(received_at) AS last_at FROM tof")
                tof = cur.fetchone() or {}
                cur.execute("SELECT COUNT(*) AS cnt, MAX(received_at) AS last_at FROM ug65")
                ug65 = cur.fetchone() or {}
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT device_sn) AS cnt
                    FROM tof WHERE device_sn IS NOT NULL AND device_sn <> ''
                    """
                )
                tof_devices = cur.fetchone() or {}
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT dev_eui) AS cnt
                    FROM ug65 WHERE dev_eui IS NOT NULL AND dev_eui <> ''
                    """
                )
                ug65_devices = cur.fetchone() or {}
        return {
            "tof": {
                "total_rows": int(tof.get("cnt") or 0),
                "device_count": int(tof_devices.get("cnt") or 0),
                "last_received_at": (
                    tof["last_at"].isoformat(sep=" ") if tof.get("last_at") else None
                ),
            },
            "ug65": {
                "total_rows": int(ug65.get("cnt") or 0),
                "device_count": int(ug65_devices.get("cnt") or 0),
                "last_received_at": (
                    ug65["last_at"].isoformat(sep=" ") if ug65.get("last_at") else None
                ),
            },
        }

    def list_tof(
        self,
        *,
        device_sn: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int | None = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["1=1"]
        params: dict[str, Any] = {}
        if device_sn:
            where.append("device_sn = %(device_sn)s")
            params["device_sn"] = device_sn
        if since:
            where.append("received_at >= %(since)s")
            params["since"] = since
        if until:
            where.append("received_at <= %(until)s")
            params["until"] = until
        clause = " AND ".join(where)

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) AS cnt FROM tof WHERE {clause}", params)
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                sql = f"""
                    SELECT *
                    FROM tof
                    WHERE {clause}
                    ORDER BY id DESC
                """
                if limit is not None:
                    params["limit"] = limit
                    params["offset"] = offset
                    sql += " LIMIT %(limit)s OFFSET %(offset)s"
                cur.execute(sql, params)
                rows = cur.fetchall() or []
        return (
            [self._parse_json_fields(dict(row), TOF_JSON_COLUMNS) for row in rows],
            total,
        )

    def get_tof(self, row_id: int) -> dict[str, Any] | None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM tof WHERE id = %s", (row_id,))
                row = cur.fetchone()
        return self._parse_json_fields(dict(row), TOF_JSON_COLUMNS) if row else None

    def latest_tof_received_at(self, *, device_sn: str | None = None) -> datetime | None:
        where = ["1=1"]
        params: dict[str, Any] = {}
        if device_sn:
            where.append("device_sn = %(device_sn)s")
            params["device_sn"] = device_sn
        clause = " AND ".join(where)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT MAX(received_at) AS latest_received_at FROM tof WHERE {clause}",
                    params,
                )
                row = cur.fetchone() or {}
        latest = row.get("latest_received_at")
        return latest if isinstance(latest, datetime) else None

    def list_tof_devices(self) -> list[dict[str, Any]]:
        sql = """
            SELECT
                device_sn,
                MAX(device_name) AS device_name,
                MAX(device_mac) AS device_mac,
                MAX(ip_address) AS ip_address,
                COUNT(*) AS uplink_count,
                MAX(received_at) AS last_received_at
            FROM tof
            WHERE device_sn IS NOT NULL AND device_sn <> ''
            GROUP BY device_sn
            ORDER BY last_received_at DESC
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall() or []
        result = []
        for row in rows:
            item = dict(row)
            if item.get("last_received_at"):
                item["last_received_at"] = item["last_received_at"].isoformat(sep=" ")
            item["uplink_count"] = int(item.get("uplink_count") or 0)
            result.append(item)
        return result

    def list_ug65(
        self,
        *,
        dev_eui: str | None = None,
        gateway_model: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int | None = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["1=1"]
        params: dict[str, Any] = {}
        if dev_eui:
            where.append("dev_eui = %(dev_eui)s")
            params["dev_eui"] = dev_eui.upper()
        if gateway_model:
            where.append("gateway_model = %(gateway_model)s")
            params["gateway_model"] = gateway_model.lower()
        if since:
            where.append("received_at >= %(since)s")
            params["since"] = since
        if until:
            where.append("received_at <= %(until)s")
            params["until"] = until
        clause = " AND ".join(where)

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) AS cnt FROM ug65 WHERE {clause}", params)
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                sql = f"""
                    SELECT *
                    FROM ug65
                    WHERE {clause}
                    ORDER BY id DESC
                """
                if limit is not None:
                    params["limit"] = limit
                    params["offset"] = offset
                    sql += " LIMIT %(limit)s OFFSET %(offset)s"
                cur.execute(sql, params)
                rows = cur.fetchall() or []
        return (
            [self._parse_json_fields(dict(row), UG65_JSON_COLUMNS) for row in rows],
            total,
        )

    def get_ug65(self, row_id: int) -> dict[str, Any] | None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM ug65 WHERE id = %s", (row_id,))
                row = cur.fetchone()
        return self._parse_json_fields(dict(row), UG65_JSON_COLUMNS) if row else None

    def latest_ug65_received_at(
        self,
        *,
        dev_eui: str | None = None,
        gateway_model: str | None = None,
    ) -> datetime | None:
        where = ["1=1"]
        params: dict[str, Any] = {}
        if dev_eui:
            where.append("dev_eui = %(dev_eui)s")
            params["dev_eui"] = dev_eui.upper()
        if gateway_model:
            where.append("gateway_model = %(gateway_model)s")
            params["gateway_model"] = gateway_model.lower()
        clause = " AND ".join(where)
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT MAX(received_at) AS latest_received_at FROM ug65 WHERE {clause}",
                    params,
                )
                row = cur.fetchone() or {}
        latest = row.get("latest_received_at")
        return latest if isinstance(latest, datetime) else None

    def list_ug65_devices(self) -> list[dict[str, Any]]:
        sql = """
            SELECT
                dev_eui,
                MAX(device_name) AS device_name,
                MAX(application_name) AS application_name,
                MAX(gateway_model) AS last_gateway_model,
                COUNT(*) AS uplink_count,
                MAX(received_at) AS last_received_at,
                MAX(rssi) AS last_rssi
            FROM ug65
            WHERE dev_eui IS NOT NULL AND dev_eui <> ''
            GROUP BY dev_eui
            ORDER BY last_received_at DESC
        """
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall() or []
        result = []
        for row in rows:
            item = dict(row)
            if item.get("last_received_at"):
                item["last_received_at"] = item["last_received_at"].isoformat(sep=" ")
            item["uplink_count"] = int(item.get("uplink_count") or 0)
            result.append(item)
        return result

    # ------------------------------------------------------------------
    # WingOnIOT 环境监测（Environment_Device / Environmental_Monitoring）
    # ------------------------------------------------------------------

    #: 当前建筑最大地下层编号（如 B2/F 为最深 → 2）。
    #: 3D 层号自下而上：B2/F→1、B1/F→2、G/F→3、1/F→4 … 7/F→10（剖面图：地下 2 层 + 地上 8 层）
    B_FLOOR_BASE = 2

    @staticmethod
    def floor_to_level(floor: str | None) -> int | None:
        """把 WingOnIOT 楼层字符串映射为 3D 楼栋层号。

        - 'B1/F'、'B2/F' → 2、1（地下层从下往上压到楼栋底部）
        - 'G/F' → 3（地面层）
        - '4/F'、'5/F' → 7、8（地上 n/F → n + 3，即 地下2层 + 地面层 之上）
        - 无法解析返回 None
        """
        if not floor:
            return None
        value = str(floor).strip().upper()
        m = re.fullmatch(r"B(\d+)/F", value)
        if m:
            return Database.B_FLOOR_BASE - int(m.group(1)) + 1
        if value in ("G/F", "G", "GROUND", "GROUND/F"):
            return Database.B_FLOOR_BASE + 1
        m = re.fullmatch(r"(\d+)/F", value)
        if m:
            return Database.B_FLOOR_BASE + 1 + int(m.group(1))
        try:
            return Database.B_FLOOR_BASE + 1 + int(value)
        except ValueError:
            return None

    def list_environment_devices(self) -> list[dict[str, Any]]:
        """WingOnIOT 环境设备列表，附每台设备最新一条监测（中位温湿度）与 3D 层号。

        - 无监测记录的设备 latest 字段为 null（LEFT JOIN）
        - level 由 floor 解析（B2/F→1、B1/F→2、G/F→3、4/F→7 …）
        - cell：设备绑定的格子（device_cell→building_cell）；null = 未绑定（含大厅设备）
        - cell_lost：设备在 device_cell 留有绑定但目标格子已软删/不存在（残留绑定）。
          此时 cell 一定为 null（格子无效无法定位），cell_lost=True 可用于 UI 提示并触发清理。
        - room_id：格子所属房间（room_cell 反查，room_id 业务键）；null = 大厅/走廊格子
        """
        sql = """
            SELECT d.sn, d.name, d.deviceName, d.model, d.floor, d.location, d.macAddress,
                   l.toDateTime, l.temperatureMedian, l.humidityMedian,
                   dc.cell_id AS cell_id, c.row_no, c.col_no, c.x AS cell_x, c.y AS cell_z,
                   IF(dc.cell_id IS NOT NULL AND c.id IS NULL, 1, 0) AS cell_lost,
                   rrc.room_id AS room_id
            FROM Environment_Device d
            LEFT JOIN (
                SELECT m.sn, m.toDateTime, m.temperatureMedian, m.humidityMedian
                FROM (
                    SELECT m2.*,
                           ROW_NUMBER() OVER (
                               PARTITION BY sn ORDER BY InsertAt DESC, id DESC
                           ) AS rn
                    FROM Environmental_Monitoring m2
                ) m
                WHERE m.rn = 1
            ) l ON l.sn = d.sn
            LEFT JOIN (
                SELECT dc.sn, dc.cell_id, dc.floor_id,
                       ROW_NUMBER() OVER (PARTITION BY dc.sn ORDER BY dc.id DESC) AS rn
                FROM device_cell dc
            ) dc ON dc.sn = d.sn AND dc.rn = 1
            LEFT JOIN building_cell c
                   ON c.id = dc.cell_id AND c.floor_id = dc.floor_id AND c.is_deleted = 0
            LEFT JOIN (
                SELECT rc.cell_id, rc.floor_id, MIN(r.room_id) AS room_id
                FROM room_cell rc
                JOIN room r ON r.id = rc.room_ref_id AND r.is_deleted = 0
                WHERE rc.is_deleted = 0
                GROUP BY rc.cell_id, rc.floor_id
            ) rrc ON rrc.cell_id = c.id AND rrc.floor_id = c.floor_id
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall() or []
        result = []
        for row in rows:
            item = self._parse_json_fields(dict(row), ())
            item["level"] = self.floor_to_level(item.get("floor"))
            cell_id = item.pop("cell_id", None)
            cell_lost = int(item.pop("cell_lost", 0) or 0) == 1
            if cell_id is not None and not cell_lost:
                item["cell"] = {
                    "cell_id": int(cell_id),
                    "row_no": int(item.pop("row_no") or 0),
                    "col_no": int(item.pop("col_no") or 0),
                    "x": float(item.pop("cell_x") or 0),
                    "z": float(item.pop("cell_z") or 0),
                }
            else:
                item.pop("row_no", None)
                item.pop("col_no", None)
                item.pop("cell_x", None)
                item.pop("cell_z", None)
                item["cell"] = None
            # cell_lost: 设备在 device_cell 里留有绑定，但目标格子已软删/不存在（残留绑定）
            item["cell_lost"] = cell_lost
            item["room_id"] = item.pop("room_id", None)
            result.append(item)
        # 按 3D 层号排序（无层号排最后），同层按名称 —— 避免字符串排序把 B 层排乱
        result.sort(
            key=lambda x: (
                x.get("level") is None,
                x.get("level") or 0,
                x.get("floor") or "",
                x.get("name") or "",
            )
        )
        return result

    def find_cell_by_row_col(self, floor_id: int, row_no: int, col_no: int) -> dict[str, Any] | None:
        """Find an active cell by floor + row/col (used by device-cell binding)."""
        sql = """
            SELECT id, floor_id, row_no, col_no
            FROM building_cell
            WHERE floor_id = %(floor_id)s
              AND row_no = %(row_no)s
              AND col_no = %(col_no)s
              AND is_deleted = 0
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    {"floor_id": floor_id, "row_no": row_no, "col_no": col_no},
                )
                row = cur.fetchone()
        return dict(row) if row else None

    def device_exists(self, sn: str) -> bool:
        """Whether the device SN exists in Environment_Device."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM Environment_Device WHERE sn = %s", (sn,))
                return cur.fetchone() is not None

    def bind_device_cell(self, sn: str, floor_id: int, row_no: int, col_no: int) -> str:
        """Bind a device to a grid cell, replacing any existing binding of the device.

        Returns one of:
          "ok"               - bound successfully (old binding, if any, replaced)
          "device_not_found" - the SN does not exist in Environment_Device
          "cell_not_found"   - no active cell at (floor_id, row_no, col_no)
          "floor_mismatch"   - the device's floor differs from the cell's floor (both resolvable)
        """
        if not self.device_exists(sn):
            return "device_not_found"
        cell = self.find_cell_by_row_col(floor_id, row_no, col_no)
        if cell is None:
            return "cell_not_found"
        # 楼层一致性校验：设备所在楼层与目标格子所在楼层必须一致（仅两侧均可解析时强制）
        if self._device_floor_matches_cell(sn, floor_id) is False:
            return "floor_mismatch"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM device_cell WHERE sn = %s", (sn,))
                cur.execute(
                    "INSERT INTO device_cell (sn, cell_id, floor_id) VALUES (%s, %s, %s)",
                    (sn, cell["id"], cell["floor_id"]),
                )
        return "ok"

    def _device_floor_matches_cell(self, sn: str, cell_floor_id: int) -> bool:
        """Whether the device's floor (WingOn floor string) matches the cell's floor.

        Both sides are mapped to the same 3D-layer number (floor_to_level /
        floor_level_to_3d). Returns True when either side cannot be resolved
        (no information to compare) so the bind is allowed.
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT floor FROM Environment_Device WHERE sn = %s", (sn,))
                row = cur.fetchone()
                device_floor = (row or {}).get("floor") if row else None
                cur.execute(
                    "SELECT level FROM floor WHERE id = %s AND is_deleted = 0",
                    (cell_floor_id,),
                )
                frow = cur.fetchone()
                floor_level = (
                    int(frow["level"]) if frow and frow.get("level") is not None else None
                )
        device_level = self.floor_to_level(device_floor)
        grid_level = self.floor_level_to_3d(floor_level) if floor_level is not None else None
        if device_level is None or grid_level is None:
            return True
        return device_level == grid_level

    def unbind_device_cell(self, sn: str) -> bool:
        """Remove all cell bindings of a device. Returns True when a binding was removed."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM device_cell WHERE sn = %s", (sn,))
                return cur.rowcount > 0

    def list_environment_monitoring(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Environmental_Monitoring 分页列表（最新写入在前）。"""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS cnt FROM Environmental_Monitoring")
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                sql = """
                    SELECT *
                    FROM Environmental_Monitoring
                    ORDER BY InsertAt DESC, id DESC
                    LIMIT %(limit)s OFFSET %(offset)s
                """
                cur.execute(sql, {"limit": limit, "offset": offset})
                rows = cur.fetchall() or []
        return (
            [self._parse_json_fields(dict(r), ()) for r in rows],
            total,
        )

    # ------------------------------------------------------------------
    # WingOnIOT people count (people_count_hourly)
    # ------------------------------------------------------------------

    def list_people_count_hourly(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        hour: int | None = None,
        ip_address: str | None = None,
        channel_name: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Paginated people_count_hourly list with optional filters.

        Supported filters map to the following indexes so the WHERE clause can
        be answered by an index range scan:
          - (date, channel_name, hour) via idx_date_channel_hour
          - (date, hour, ip_address) via uk_date_hour_ip
        """
        where = ["1=1"]
        params: dict[str, Any] = {}
        if date_from is not None:
            where.append("date >= %(date_from)s")
            params["date_from"] = date_from
        if date_to is not None:
            where.append("date <= %(date_to)s")
            params["date_to"] = date_to
        if hour is not None:
            where.append("hour = %(hour)s")
            params["hour"] = hour
        if ip_address:
            where.append("ip_address = %(ip_address)s")
            params["ip_address"] = ip_address
        if channel_name:
            where.append("channel_name = %(channel_name)s")
            params["channel_name"] = channel_name
        clause = " AND ".join(where)
        params["limit"] = limit
        params["offset"] = offset

        # Pick the best index for the active filters and force it. The table is
        # small, so without FORCE INDEX the optimizer may fall back to a full
        # table scan even though an index range scan is available.
        if channel_name:
            # (date, channel_name, hour) covers channel_name + date + hour
            force_index = "FORCE INDEX (idx_date_channel_hour)"
        else:
            # (date, hour, ip_address) covers date + hour + ip_address
            force_index = "FORCE INDEX (uk_date_hour_ip)"

        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM people_count_hourly {force_index} WHERE {clause}",
                    params,
                )
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                sql = f"""
                    SELECT *
                    FROM people_count_hourly {force_index}
                    WHERE {clause}
                    ORDER BY date DESC, hour DESC, id DESC
                    LIMIT %(limit)s OFFSET %(offset)s
                """
                cur.execute(sql, params)
                rows = cur.fetchall() or []
        return (
            [self._parse_json_fields(dict(row), ()) for row in rows],
            total,
        )

    def list_people_count_channels(self) -> list[str]:
        """Distinct channel_name values for the filter dropdown (uses index)."""
        sql = """
            SELECT DISTINCT channel_name
            FROM people_count_hourly
            ORDER BY channel_name
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall() or []
        return [str(r["channel_name"]) for r in rows]

    def people_count_hourly_stats(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        hour: int | None = None,
        ip_address: str | None = None,
        channel_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """按小时聚合进出人数（图表用）。"""
        where = ["1=1"]
        params: dict[str, Any] = {}
        if date_from is not None:
            where.append("date >= %(date_from)s")
            params["date_from"] = date_from
        if date_to is not None:
            where.append("date <= %(date_to)s")
            params["date_to"] = date_to
        if hour is not None:
            where.append("hour = %(hour)s")
            params["hour"] = hour
        if ip_address:
            where.append("ip_address = %(ip_address)s")
            params["ip_address"] = ip_address
        if channel_name:
            where.append("channel_name = %(channel_name)s")
            params["channel_name"] = channel_name
        clause = " AND ".join(where)
        sql = f"""
            SELECT hour,
                   SUM(enter_count) AS enter_count,
                   SUM(exit_count) AS exit_count
            FROM people_count_hourly
            WHERE {clause}
            GROUP BY hour
            ORDER BY hour
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() or []
        return [dict(r) for r in rows]

    def people_count_daily_stats(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        hour: int | None = None,
        ip_address: str | None = None,
        channel_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """按日期聚合进出人数（图表用）。"""
        where = ["1=1"]
        params: dict[str, Any] = {}
        if date_from is not None:
            where.append("date >= %(date_from)s")
            params["date_from"] = date_from
        if date_to is not None:
            where.append("date <= %(date_to)s")
            params["date_to"] = date_to
        if hour is not None:
            where.append("hour = %(hour)s")
            params["hour"] = hour
        if ip_address:
            where.append("ip_address = %(ip_address)s")
            params["ip_address"] = ip_address
        if channel_name:
            where.append("channel_name = %(channel_name)s")
            params["channel_name"] = channel_name
        clause = " AND ".join(where)
        sql = f"""
            SELECT date,
                   SUM(enter_count) AS enter_count,
                   SUM(exit_count) AS exit_count
            FROM people_count_hourly
            WHERE {clause}
            GROUP BY date
            ORDER BY date
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() or []
        return [dict(r) for r in rows]

    def people_count_channel_stats(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        hour: int | None = None,
        ip_address: str | None = None,
        channel_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """按通道聚合进出人数（图表用）。"""
        where = ["1=1"]
        params: dict[str, Any] = {}
        if date_from is not None:
            where.append("date >= %(date_from)s")
            params["date_from"] = date_from
        if date_to is not None:
            where.append("date <= %(date_to)s")
            params["date_to"] = date_to
        if hour is not None:
            where.append("hour = %(hour)s")
            params["hour"] = hour
        if ip_address:
            where.append("ip_address = %(ip_address)s")
            params["ip_address"] = ip_address
        if channel_name:
            where.append("channel_name = %(channel_name)s")
            params["channel_name"] = channel_name
        clause = " AND ".join(where)
        sql = f"""
            SELECT channel_name,
                   SUM(enter_count) AS enter_count,
                   SUM(exit_count) AS exit_count
            FROM people_count_hourly
            WHERE {clause}
            GROUP BY channel_name
            ORDER BY enter_count + exit_count DESC
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() or []
        return [dict(r) for r in rows]

    def floor_environment_summary(self) -> list[dict[str, Any]]:
        """按楼层聚合：每台设备取最新一条监测记录，楼层温度/湿度为该层设备中位值均值。"""
        sql = """
            SELECT d.floor AS floor,
                   COUNT(DISTINCT d.sn) AS device_count,
                   ROUND(AVG(l.temperatureMedian), 1) AS temperature,
                   ROUND(AVG(l.humidityMedian), 1) AS humidity,
                   MAX(l.InsertAt) AS updated_at
            FROM Environment_Device d
            JOIN (
                SELECT m.sn, m.temperatureMedian, m.humidityMedian, m.InsertAt
                FROM (
                    SELECT m2.*,
                           ROW_NUMBER() OVER (
                               PARTITION BY sn ORDER BY InsertAt DESC, id DESC
                           ) AS rn
                    FROM Environmental_Monitoring m2
                ) m
                WHERE m.rn = 1
            ) l ON l.sn = d.sn
            GROUP BY d.floor
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall() or []
        result = []
        for row in rows:
            item = self._parse_json_fields(dict(row), ())
            item["level"] = self.floor_to_level(item.get("floor"))
            result.append(item)
        # 按 3D 层号排序（无层号排最后）—— 避免字符串排序把 B 层排乱
        result.sort(
            key=lambda x: (
                x.get("level") is None,
                x.get("level") or 0,
                x.get("floor") or "",
            )
        )
        return result

    # ------------------------------------------------------------------
    # 3D building structure (WingOnIOT.building / floor / building_cell / room / room_cell)
    # Cell shapes are driven by the building_cell table (replacing the old building_cell_shape)
    # ------------------------------------------------------------------

    @staticmethod
    def floor_level_to_3d(level: int) -> int:
        """Map floor.level (real floor number) to the 3D building level (1..11).

        floor.level semantics:
          -2=B2/F->1, -1=B1/F->2, 1=G/F->3, 2=1/F->4 ... 8=7/F->10, 9=ROOF->11
        """
        if level < 0:
            return level + 3
        if level == 9:  # ROOF
            return 11
        return level + 2

    def list_buildings(self) -> list[dict[str, Any]]:
        """Enabled buildings (soft-delete aware)."""
        sql = """
            SELECT id, name, code, address, description
            FROM building
            WHERE is_deleted = 0
            ORDER BY id ASC
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall() or []
        return [self._parse_json_fields(dict(row), ()) for row in rows]

    def list_floors(self, building_id: int | None = None) -> list[dict[str, Any]]:
        """Floors of a building (soft-delete aware); level_3d is the 3D level (1..11)."""
        where = ["f.is_deleted = 0"]
        params: dict[str, Any] = {}
        if building_id is not None:
            where.append("f.building_id = %(building_id)s")
            params["building_id"] = building_id
        clause = " AND ".join(where)
        sql = f"""
            SELECT f.id, f.building_id, f.row_amount, f.column_amount, f.level, f.floor_name
            FROM floor f
            WHERE {clause}
            ORDER BY f.level ASC
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() or []
        result = []
        for row in rows:
            item = self._parse_json_fields(dict(row), ())
            item["level_3d"] = self.floor_level_to_3d(int(item["level"]))
            result.append(item)
        return result

    def list_cell_shapes(self, building_id: int | None = None) -> list[dict[str, Any]]:
        """Enabled cell shape settings driven by building_cell (replaces building_cell_shape).

        Maps building_cell columns to the frontend CellShapeConfig shape:
          row_no->row, col_no->col, floor.level->floor (3D), shape,
          rotation_xyz->rotation, color, render_height->height.
        x/y/z are the DB world coordinates (x=col-axis, y=row-axis, z=vertical height);
        the frontend uses them for mesh positioning.
        is_active=0 is exposed as shape='Hidden'.
        Soft-delete aware: only non-deleted cells of non-deleted floors/buildings are returned.
        """
        where = ["c.is_deleted = 0", "f.is_deleted = 0", "b.is_deleted = 0"]
        params: dict[str, Any] = {}
        if building_id is not None:
            where.append("c.building_id = %(building_id)s")
            params["building_id"] = building_id
        clause = " AND ".join(where)
        sql = f"""
            SELECT
                c.row_no,
                c.col_no,
                f.level,
                c.floor_id,
                c.x,
                c.y,
                c.z,
                c.shape,
                c.rotation_xyz,
                c.color,
                c.render_height,
                c.is_active
            FROM building_cell c
            JOIN floor f ON f.id = c.floor_id
            JOIN building b ON b.id = c.building_id
            WHERE {clause}
            ORDER BY f.level ASC, c.row_no ASC, c.col_no ASC
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() or []

        result: list[dict[str, Any]] = []
        for row in rows:
            item = self._parse_json_fields(dict(row), ())
            shape = item.get("shape") or "Rect"
            # is_active=0 -> Hidden (not rendered); NULL treated as active
            is_active = item.get("is_active")
            if is_active is not None and int(is_active) == 0:
                shape = "Hidden"
            result.append({
                "row": int(item["row_no"]),
                "col": int(item["col_no"]),
                "floor": self.floor_level_to_3d(int(item["level"])),
                "floor_id": int(item["floor_id"]),
                "x": float(item["x"]),
                "y": float(item["y"]),
                "z": float(item["z"]),
                "shape": shape,
                "rotation": item.get("rotation_xyz"),
                "color": item.get("color"),
                "height": item.get("render_height"),
            })
        return result

    def list_floor_cells(self, floor_id: int) -> list[dict[str, Any]]:
        """All non-deleted cells of a floor (requires the floor not soft-deleted)."""
        sql = """
            SELECT c.id, c.building_id, c.floor_id, c.row_no, c.col_no,
                   c.x, c.y, c.z, c.length, c.width, c.cell_height, c.rotation_xyz,
                   c.is_active, c.shape, c.color, c.render_height
            FROM building_cell c
            JOIN floor f ON f.id = c.floor_id AND f.is_deleted = 0
            WHERE c.floor_id = %(floor_id)s AND c.is_deleted = 0
            ORDER BY c.row_no ASC, c.col_no ASC
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"floor_id": floor_id})
                rows = cur.fetchall() or []
        return [self._parse_json_fields(dict(row), ()) for row in rows]

    def list_floor_rooms(self, floor_id: int) -> list[dict[str, Any]]:
        """Rooms of a floor plus their occupied cells (via room_cell).

        Soft-delete aware: skips deleted floor/rooms/cells; returns each room
        with its cell list (row/col) ready for the frontend room layout.
        """
        rooms_sql = """
            SELECT r.id, r.room_id, r.building_id, r.floor_id, r.room_number, r.room_type, r.area
            FROM room r
            JOIN floor f ON f.id = r.floor_id AND f.is_deleted = 0
            WHERE r.floor_id = %(floor_id)s AND r.is_deleted = 0
            ORDER BY r.id ASC
        """
        relations_sql = """
            SELECT rc.room_ref_id, c.row_no, c.col_no
            FROM room_cell rc
            JOIN room r ON r.id = rc.room_ref_id AND r.is_deleted = 0
            JOIN building_cell c ON c.id = rc.cell_id AND c.is_deleted = 0
            JOIN floor f ON f.id = rc.floor_id AND f.is_deleted = 0
            WHERE rc.floor_id = %(floor_id)s AND rc.is_deleted = 0
            ORDER BY rc.room_ref_id ASC, c.row_no ASC, c.col_no ASC
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(rooms_sql, {"floor_id": floor_id})
                room_rows = cur.fetchall() or []
                cur.execute(relations_sql, {"floor_id": floor_id})
                rel_rows = cur.fetchall() or []

        rooms = [self._parse_json_fields(dict(r), ()) for r in room_rows]
        by_ref = {r["id"]: r for r in rooms}
        for r in rooms:
            r["cells"] = []
        for rel in rel_rows:
            room = by_ref.get(rel["room_ref_id"])
            if room is None:
                continue
            room["cells"].append({"row": int(rel["row_no"]), "col": int(rel["col_no"])})
        return rooms

    def delete_room(self, room_id: str) -> bool:
        """物理删除房间：room_cell 由外键级联清空，其上设备归属自动变回大厅。

        房间 = 格子集合，可重建，因此不做软删（不留伪删除脏数据）。
        不可恢复，删除前请确认。返回是否命中房间。
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM room WHERE room_id = %s",
                    (room_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return False
                cur.execute("DELETE FROM room WHERE id = %s", (int(row["id"]),))
        return True

    def assign_room_cell(self, room_id: str, floor_id: int, row_no: int, col_no: int) -> str:
        """原子切换房间↔格子占用（R3 修复的后端支撑）。

        - 目标格子已被该房间占用 → 移除该绑定，返回 'removed'
        - 目标格子被其他房间占用 → 先物理释放再占给当前房间，返回 'added'
        - 目标格子空闲 → 占用，返回 'added'
        - 房间/格子无效（不存在或已软删）→ 返回 'invalid'
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM room WHERE room_id = %s AND is_deleted = 0",
                    (room_id,),
                )
                room = cur.fetchone()
                if room is None:
                    return "invalid"
                rid = int(room["id"])
                cur.execute(
                    """SELECT id FROM building_cell
                       WHERE floor_id = %s AND row_no = %s AND col_no = %s AND is_deleted = 0""",
                    (floor_id, row_no, col_no),
                )
                cell = cur.fetchone()
                if cell is None:
                    return "invalid"
                cid = int(cell["id"])
                cur.execute(
                    """SELECT id FROM room_cell
                       WHERE room_ref_id = %s AND floor_id = %s AND cell_id = %s AND is_deleted = 0""",
                    (rid, floor_id, cid),
                )
                existing = cur.fetchone()
                if existing is not None:
                    cur.execute("DELETE FROM room_cell WHERE id = %s", (int(existing["id"]),))
                    return "removed"
                # 释放其他有效房间对该格子的占用（物理删，避免一格多房）
                cur.execute(
                    """DELETE FROM room_cell
                       WHERE floor_id = %s AND cell_id = %s AND room_ref_id <> %s AND is_deleted = 0""",
                    (floor_id, cid, rid),
                )
                cur.execute(
                    "INSERT INTO room_cell (room_ref_id, floor_id, cell_id) VALUES (%s, %s, %s)",
                    (rid, floor_id, cid),
                )
        return "added"

    def save_floor_layout(self, floor_id: int, layout: dict[str, list[tuple[int, int]]]) -> int:
        """批量保存楼层房间↔格子布局（原子替换）。

        layout: { room_id: [(row_no, col_no), ...], ... }
        1. 物理删除该楼层所有 room_cell 记录
        2. 批量插入新的 room_cell 记录
        3. 返回插入的记录数
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                # 获取该楼层所有有效房间的 id 映射
                cur.execute(
                    "SELECT id, room_id FROM room WHERE floor_id = %s AND is_deleted = 0",
                    (floor_id,),
                )
                room_map = {r["room_id"]: int(r["id"]) for r in cur.fetchall()}

                # 获取该楼层所有有效格子的 id 映射
                cur.execute(
                    "SELECT id, row_no, col_no FROM building_cell WHERE floor_id = %s AND is_deleted = 0",
                    (floor_id,),
                )
                cell_map = {(int(c["row_no"]), int(c["col_no"])): int(c["id"]) for c in cur.fetchall()}

                # 物理删除该楼层所有 room_cell 记录
                cur.execute("DELETE FROM room_cell WHERE floor_id = %s", (floor_id,))
                deleted = cur.rowcount

                # 批量插入新的 room_cell 记录
                inserted = 0
                for room_id, cells in layout.items():
                    rid = room_map.get(room_id)
                    if rid is None:
                        continue
                    for row_no, col_no in cells:
                        cid = cell_map.get((row_no, col_no))
                        if cid is None:
                            continue
                        cur.execute(
                            "INSERT INTO room_cell (room_ref_id, floor_id, cell_id) VALUES (%s, %s, %s)",
                            (rid, floor_id, cid),
                        )
                        inserted += 1

                return inserted

    def update_cell_rotation(
        self, floor_id: int, row_no: int, col_no: int, rotation_xyz: str | None
    ) -> bool:
        """Update rotation_xyz for a single cell. Returns True if a row was updated.

        The previous rotation is recorded on the undo stack so a rotation change
        can be reverted by undo_last_edit (action == "rotation").
        """
        sql = """
            UPDATE building_cell
            SET rotation_xyz = %(rotation)s
            WHERE floor_id = %(floor_id)s
              AND row_no = %(row_no)s
              AND col_no = %(col_no)s
              AND is_deleted = 0
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                # Snapshot the current rotation before overwriting it
                cur.execute(
                    """SELECT id, rotation_xyz FROM building_cell
                       WHERE floor_id = %(floor_id)s
                         AND row_no = %(row_no)s
                         AND col_no = %(col_no)s
                         AND is_deleted = 0""",
                    {"floor_id": floor_id, "row_no": row_no, "col_no": col_no},
                )
                row = cur.fetchone()
                if row is None:
                    return False
                cur.execute(sql, {
                    "rotation": rotation_xyz,
                    "floor_id": floor_id,
                    "row_no": row_no,
                    "col_no": col_no,
                })
                if cur.rowcount <= 0:
                    return False
                _push_undo(
                    [{"action": "rotation", "id": int(row["id"]), "old_rotation": row.get("rotation_xyz")}],
                    1,
                )
                return True

    def update_all_cells_rotation(
        self, building_id: int, rotation_xyz: str | None
    ) -> int:
        """Update rotation_xyz for all non-deleted cells of a building. Returns affected count."""
        sql = """
            UPDATE building_cell
            SET rotation_xyz = %(rotation)s
            WHERE building_id = %(building_id)s
              AND is_deleted = 0
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "rotation": rotation_xyz,
                    "building_id": building_id,
                })
                return cur.rowcount

    def cell_edit(
        self,
        building_id: int,
        row_no: int,
        col_no: int,
        action: str,
        scope: str,
        floor_id: int | None = None,
        shape: str | None = None,
    ) -> dict[str, Any]:
        """Add or delete cells (single / row / col).

        - add: ensure cells exist with the given shape (default 'Rect'; update shape if
          non-matching, un-delete if soft-deleted, insert if absent)
        - delete: soft-delete matching cells (is_deleted=1)
        """
        # Normalise the requested shape (only the three renderable grid shapes are allowed)
        add_shape = shape if shape in ("Rect", "Cylinder", "Triangle") else "Rect"
        affected = 0
        undo_ops: list[dict[str, Any]] = []

        if action == "delete":
            where = ["building_id = %(bid)s", "is_deleted = 0"]
            params: dict[str, Any] = {"bid": building_id}
            if scope == "single":
                where.append("floor_id = %(fid)s")
                where.append("row_no = %(row)s")
                where.append("col_no = %(col)s")
                params.update({"fid": floor_id, "row": row_no, "col": col_no})
            elif scope == "row":
                # limit to the current floor, otherwise a whole row across all
                # floors gets deleted (far more than the user expects)
                where.append("floor_id = %(fid)s")
                where.append("row_no = %(row)s")
                params.update({"fid": floor_id, "row": row_no})
            elif scope == "col":
                # col scope = same (row, col) across ALL floors (vertical pillar)
                where.append("row_no = %(row)s")
                where.append("col_no = %(col)s")
                params.update({"row": row_no, "col": col_no})

            with self.wingon_connection() as conn:
                with conn.cursor() as cur:
                    # Snapshot before delete
                    snap_sql = f"SELECT id, floor_id, row_no, col_no, shape, rotation_xyz, color, render_height, is_active FROM building_cell WHERE {' AND '.join(where)}"
                    cur.execute(snap_sql, params)
                    cell_ids: list[int] = []
                    for s in cur.fetchall() or []:
                        undo_ops.append({
                            "action": "restore",
                            "id": int(s["id"]),
                            "shape": s.get("shape"),
                            "rotation_xyz": s.get("rotation_xyz"),
                            "color": s.get("color"),
                            "render_height": s.get("render_height"),
                            "is_active": int(s.get("is_active", 1)),
                        })
                        cell_ids.append(int(s["id"]))
                    # 联动清理关联绑定（R1/R2）：room_cell 软删、device_cell 物理删，并记录 undo 以便恢复
                    if cell_ids:
                        placeholders = ",".join(["%s"] * len(cell_ids))
                        cur.execute(
                            f"SELECT id, room_ref_id, floor_id, cell_id FROM room_cell WHERE cell_id IN ({placeholders}) AND is_deleted = 0",
                            cell_ids,
                        )
                        for rc in cur.fetchall() or []:
                            undo_ops.append({
                                "action": "restore_room_cell",
                                "id": int(rc["id"]),
                                "room_ref_id": int(rc["room_ref_id"]),
                                "floor_id": int(rc["floor_id"]),
                                "cell_id": int(rc["cell_id"]),
                            })
                        cur.execute(
                            f"UPDATE room_cell SET is_deleted = 1 WHERE cell_id IN ({placeholders}) AND is_deleted = 0",
                            cell_ids,
                        )
                        cur.execute(
                            f"SELECT sn, cell_id, floor_id FROM device_cell WHERE cell_id IN ({placeholders})",
                            cell_ids,
                        )
                        for dc in cur.fetchall() or []:
                            undo_ops.append({
                                "action": "restore_device_cell",
                                "sn": dc["sn"],
                                "cell_id": int(dc["cell_id"]),
                                "floor_id": int(dc["floor_id"]),
                            })
                        cur.execute(
                            f"DELETE FROM device_cell WHERE cell_id IN ({placeholders})",
                            cell_ids,
                        )
                    cur.execute(f"UPDATE building_cell SET is_deleted = 1 WHERE {' AND '.join(where)}", params)
                    affected = cur.rowcount

            _push_undo(undo_ops, affected)
            return {"ok": True, "affected": affected}

        # action == "add"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, level FROM floor WHERE building_id = %(bid)s AND is_deleted = 0 ORDER BY level",
                    {"bid": building_id},
                )
                floors = cur.fetchall() or []

        if not floors:
            return {"ok": False, "affected": 0, "error": "No floors found"}

        if scope == "single":
            pairs = [(row_no, col_no)]
        elif scope == "row":
            pairs = [(row_no, c) for c in range(1, 13)]
        elif scope == "col":
            # col scope = same (row, col) across ALL floors
            pairs = [(row_no, col_no)]
        elif scope in ("append_row", "append_col"):
            # Append a new row (below the current bottom) or a new column
            # (to the right of the current edge) across every floor.
            with self.wingon_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT MAX(row_no) AS mr, MAX(col_no) AS mc FROM building_cell WHERE building_id = %(bid)s AND is_deleted = 0",
                        {"bid": building_id},
                    )
                    max_row_col = cur.fetchone()
            max_row = int(max_row_col["mr"] or 0)
            max_col = int(max_row_col["mc"] or 0)
            if scope == "append_row":
                new_row = max_row + 1
                pairs = [(new_row, c) for c in range(1, max_col + 1)]
            else:
                new_col = max_col + 1
                pairs = [(r, new_col) for r in range(1, max_row + 1)]
        else:
            return {"ok": False, "affected": 0, "error": f"Unknown scope: {scope}"}

        for fl in floors:
            fid = int(fl["id"])
            if scope == "single" and fid != floor_id:
                continue
            level = int(fl["level"])
            if level < 0:
                level_3d = level + 3
            elif level == 9:
                level_3d = 11
            else:
                level_3d = level + 2
            z_val = round((level_3d - 1) * 0.84 + 0.38, 3)

            for (r, c) in pairs:
                with self.wingon_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id, shape, is_active FROM building_cell WHERE floor_id = %(fid)s AND row_no = %(row)s AND col_no = %(col)s AND is_deleted = 0",
                            {"fid": fid, "row": r, "col": c},
                        )
                        existing = cur.fetchone()
                        if existing:
                            old_shape = existing.get("shape")
                            old_active = int(existing.get("is_active", 1) or 1)
                            if (old_shape and old_shape != add_shape) or old_active == 0:
                                undo_ops.append({
                                    "action": "update_shape",
                                    "id": int(existing["id"]),
                                    "old_shape": old_shape,
                                    "old_active": old_active,
                                })
                                cur.execute(
                                    "UPDATE building_cell SET shape = %(shape)s, is_active = 1 WHERE id = %(id)s",
                                    {"id": int(existing["id"]), "shape": add_shape},
                                )
                                affected += 1
                            continue

                        cur.execute(
                            "SELECT id FROM building_cell WHERE floor_id = %(fid)s AND row_no = %(row)s AND col_no = %(col)s AND is_deleted = 1",
                            {"fid": fid, "row": r, "col": c},
                        )
                        deleted_row = cur.fetchone()
                        if deleted_row:
                            undo_ops.append({"action": "re_delete", "id": int(deleted_row["id"])})
                            cur.execute(
                                """UPDATE building_cell
                                   SET is_deleted = 0, shape = %(shape)s, is_active = 1
                                   WHERE id = %(id)s""",
                                {"id": int(deleted_row["id"]), "shape": add_shape},
                            )
                            affected += 1
                        else:
                            x_val = round((c - 6.5) * 1.15, 3)
                            y_val = round((r - 4.5) * 1.15, 3)
                            cur.execute(
                                """INSERT INTO building_cell
                                   (building_id, floor_id, row_no, col_no, x, y, z,
                                    length, width, cell_height, rotation_xyz,
                                    is_active, shape, color, render_height, is_deleted)
                                   VALUES (%(bid)s, %(fid)s, %(row)s, %(col)s,
                                           %(x)s, %(y)s, %(z)s,
                                           1.150, 1.150, 0.000, NULL,
                                           1, %(shape)s, NULL, NULL, 0)""",
                                {"bid": building_id, "fid": fid, "row": r, "col": c,
                                 "x": x_val, "y": y_val, "z": z_val, "shape": add_shape},
                            )
                            undo_ops.append({"action": "delete_new", "id": cur.lastrowid})
                            affected += 1

        _push_undo(undo_ops, affected)
        return {"ok": True, "affected": affected}

    def undo_last_edit(self) -> dict[str, Any]:
        """Undo the last cell_edit operation."""
        if not _UNDO_STACK:
            return {"ok": False, "affected": 0, "error": "Nothing to undo"}

        last = _UNDO_STACK.pop()
        ops = last["ops"]
        affected = 0

        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                for op in ops:
                    if op["action"] == "delete_new":
                        cur.execute("DELETE FROM building_cell WHERE id = %(id)s", {"id": op["id"]})
                        affected += cur.rowcount
                    elif op["action"] == "re_delete":
                        cur.execute("UPDATE building_cell SET is_deleted = 1 WHERE id = %(id)s", {"id": op["id"]})
                        affected += cur.rowcount
                    elif op["action"] == "restore":
                        cur.execute(
                            """UPDATE building_cell SET is_deleted = 0, shape = %(shape)s,
                               rotation_xyz = %(rotation)s, color = %(color)s,
                               render_height = %(rh)s, is_active = %(active)s
                               WHERE id = %(id)s""",
                            {"id": op["id"], "shape": op["shape"],
                             "rotation": op["rotation_xyz"], "color": op["color"],
                             "rh": op["render_height"], "active": op["is_active"]},
                        )
                        affected += cur.rowcount
                    elif op["action"] == "update_shape":
                        cur.execute(
                            "UPDATE building_cell SET shape = %(shape)s, is_active = %(active)s WHERE id = %(id)s",
                            {"id": op["id"], "shape": op["old_shape"], "active": op.get("old_active", 1)},
                        )
                        affected += cur.rowcount
                    elif op["action"] == "rotation":
                        cur.execute(
                            "UPDATE building_cell SET rotation_xyz = %(rotation)s WHERE id = %(id)s",
                            {"id": op["id"], "rotation": op.get("old_rotation")},
                        )
                        affected += cur.rowcount
                    elif op["action"] == "restore_room_cell":
                        # 恢复被联动软删的房间↔格子绑定；若该格已被重新分配给同房间则跳过
                        cur.execute(
                            """SELECT id FROM room_cell
                               WHERE room_ref_id = %(room_ref_id)s AND floor_id = %(floor_id)s
                                 AND cell_id = %(cell_id)s AND is_deleted = 0""",
                            {"room_ref_id": op["room_ref_id"],
                             "floor_id": op["floor_id"],
                             "cell_id": op["cell_id"]},
                        )
                        if cur.fetchone() is None:
                            cur.execute(
                                "UPDATE room_cell SET is_deleted = 0 WHERE id = %(id)s",
                                {"id": op["id"]},
                            )
                            affected += cur.rowcount
                    elif op["action"] == "restore_device_cell":
                        # 恢复被联动物理删除的设备↔格子绑定；若设备已重新绑定则跳过
                        cur.execute(
                            "SELECT id FROM device_cell WHERE sn = %s",
                            (op["sn"],),
                        )
                        if cur.fetchone() is None:
                            cur.execute(
                                "INSERT INTO device_cell (sn, cell_id, floor_id) VALUES (%s, %s, %s)",
                                (op["sn"], op["cell_id"], op["floor_id"]),
                            )
                            affected += 1

        return {"ok": True, "affected": affected}

    def reset_grid_extras(self, building_id: int) -> dict[str, Any]:
        """Soft-delete every cell beyond the base 8x12 grid (row>8 or col>12).

        Undo restores all removed cells.
        """
        where = "building_id = %(bid)s AND is_deleted = 0 AND (row_no > 8 OR col_no > 12)"
        undo_ops: list[dict[str, Any]] = []
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id, shape, rotation_xyz, color, render_height, is_active FROM building_cell WHERE {where}",
                    {"bid": building_id},
                )
                for s in cur.fetchall() or []:
                    undo_ops.append({
                        "action": "restore",
                        "id": int(s["id"]),
                        "shape": s.get("shape"),
                        "rotation_xyz": s.get("rotation_xyz"),
                        "color": s.get("color"),
                        "render_height": s.get("render_height"),
                        "is_active": int(s.get("is_active", 1)),
                    })
                cur.execute(
                    f"UPDATE building_cell SET is_deleted = 1 WHERE {where}",
                    {"bid": building_id},
                )
                affected = cur.rowcount

        _push_undo(undo_ops, affected)
        return {"ok": True, "affected": affected}

    def update_col_cells_rotation(
        self, building_id: int, col_no: int, rotation_xyz: str | None
    ) -> int:
        """Update rotation_xyz for all non-deleted cells of a given column. Returns affected count."""
        sql = """
            UPDATE building_cell
            SET rotation_xyz = %(rotation)s
            WHERE building_id = %(building_id)s
              AND col_no = %(col_no)s
              AND is_deleted = 0
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "rotation": rotation_xyz,
                    "building_id": building_id,
                    "col_no": col_no,
                })
                return cur.rowcount
