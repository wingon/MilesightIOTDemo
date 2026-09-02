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
        """WingOnIOT environment-monitoring DB connection (another database on the same MySQL instance)."""
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
    # WingOnIOT environment monitoring (Environment_Device / Environmental_Monitoring)
    # ------------------------------------------------------------------

    #: Deepest basement floor index of the current building (e.g. B2/F is the deepest -> 2).
    #: 3D level goes bottom-up: B2/F->1, B1/F->2, G/F->3, 1/F->4 ... 7/F->10 (section view: 2 basement + 8 above-ground)
    B_FLOOR_BASE = 2

    @staticmethod
    def floor_to_level(floor: str | None) -> int | None:
        """Map a WingOnIOT floor string to a 3D building level.

        - 'B1/F', 'B2/F' -> 2, 1 (basement floors stacked at the bottom)
        - 'G/F' -> 3 (ground floor)
        - '4/F', '5/F' -> 7, 8 (above-ground n/F -> n + 3, i.e. above 2 basements + ground floor)
        - None if the floor cannot be parsed
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
        """WingOnIOT environment device list, with each device's latest reading (median temp/humidity) and 3D level.

        - Devices without any reading have latest = null (LEFT JOIN)
        - level is parsed from floor (B2/F->1, B1/F->2, G/F->3, 4/F->7 ...)
        - cell: the cell the device is bound to (device_cell->building_cell); null = unbound (incl. lobby devices)
        - cell_lost: the device still has a binding in device_cell but the target cell is soft-deleted/missing
          (leftover binding). Then cell is always null (the cell cannot be located), and cell_lost=True
          lets the UI prompt and trigger cleanup.
        - room_id: the room the cell belongs to (reverse lookup via room_cell, room_id business key); null = lobby/corridor cell
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
            # cell_lost: the device still has a binding in device_cell but the target cell is soft-deleted/missing (leftover binding)
            item["cell_lost"] = cell_lost
            item["room_id"] = item.pop("room_id", None)
            result.append(item)
        # Sort by 3D level (no level last), same level by name — avoid string sorting scrambling B floors
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
        # Floor consistency check: the device's floor and the target cell's floor must match (only enforced when both are resolvable)
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
        """Paginated Environmental_Monitoring list (newest writes first)."""
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
        """Hourly enter/exit aggregation (for charts)."""
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
        """Daily enter/exit aggregation (for charts)."""
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
        """Channel enter/exit aggregation (for charts)."""
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

    def upsert_people_count_hourly(
        self,
        *,
        snowflake_id: int,
        date: date,
        hour: int,
        ip_address: str,
        channel_name: str,
        enter_count: int,
        exit_count: int,
    ) -> None:
        """UPSERT a single people_count_hourly row (INSERT ... ON DUPLICATE KEY UPDATE).

        The unique key (date, hour, ip_address) drives the upsert; the provided
        snowflake_id is only used on the initial insert.
        """
        sql = """
            INSERT INTO people_count_hourly
                (id, date, hour, ip_address, channel_name, enter_count, exit_count)
            VALUES
                (%(id)s, %(date)s, %(hour)s, %(ip_address)s, %(channel_name)s,
                 %(enter_count)s, %(exit_count)s)
            ON DUPLICATE KEY UPDATE
                channel_name = VALUES(channel_name),
                enter_count = VALUES(enter_count),
                exit_count = VALUES(exit_count),
                updated_at = NOW(3)
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "id": snowflake_id,
                    "date": date,
                    "hour": hour,
                    "ip_address": ip_address,
                    "channel_name": channel_name,
                    "enter_count": enter_count,
                    "exit_count": exit_count,
                })

    def get_existing_people_count_dates(
        self, year: int, month: int
    ) -> set[date]:
        """Return the set of dates that already have rows in the given month."""
        first = date(year, month, 1)
        if month == 12:
            last = date(year + 1, 1, 1)
        else:
            last = date(year, month + 1, 1)
        sql = """
            SELECT DISTINCT date
            FROM people_count_hourly
            WHERE date >= %(first)s AND date < %(last)s
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"first": first, "last": last})
                rows = cur.fetchall() or []
        return {r["date"] for r in rows}

    def get_existing_people_count_dates_range(
        self, date_from: date, date_to: date
    ) -> set[date]:
        """Return the set of dates in [date_from, date_to] that already have rows."""
        sql = """
            SELECT DISTINCT date
            FROM people_count_hourly
            WHERE date >= %(date_from)s AND date <= %(date_to)s
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"date_from": date_from, "date_to": date_to})
                rows = cur.fetchall() or []
        return {r["date"] for r in rows}

    def floor_environment_summary(self) -> list[dict[str, Any]]:
        """Per-floor aggregation: take each device's latest reading; floor temp/humidity is the median of that floor's devices."""
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
        # Sort by 3D level (no level last) — avoid string sorting scrambling B floors
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
        """Physically delete a room: room_cell is cleared by foreign-key cascade and its devices revert to the lobby.

        A room is just a cell set and can be rebuilt, so no soft-delete is used (no leftover dirty rows).
        Non-recoverable; confirm before deleting. Returns whether the room was found.
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
        """Atomically switch room↔cell occupancy (backend support for the R3 fix).

        - Target cell already occupied by this room -> remove the binding, return 'removed'
        - Target cell occupied by another room -> physically release it first, then occupy for this room, return 'added'
        - Target cell free -> occupy it, return 'added'
        - Room/cell invalid (missing or soft-deleted) -> return 'invalid'
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
                # Release other valid rooms' occupancy of this cell (physical delete, avoids one cell in multiple rooms)
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
        """Batch save the floor room↔cell layout (atomic replacement).

        layout: { room_id: [(row_no, col_no), ...], ... }
        1. Physically delete all room_cell rows of this floor
        2. Batch insert the new room_cell rows
        3. Return the number of inserted rows
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                # Get the id mapping of all valid rooms on this floor
                cur.execute(
                    "SELECT id, room_id FROM room WHERE floor_id = %s AND is_deleted = 0",
                    (floor_id,),
                )
                room_map = {r["room_id"]: int(r["id"]) for r in cur.fetchall()}

                # Get the id mapping of all valid cells on this floor
                cur.execute(
                    "SELECT id, row_no, col_no FROM building_cell WHERE floor_id = %s AND is_deleted = 0",
                    (floor_id,),
                )
                cell_map = {(int(c["row_no"]), int(c["col_no"])): int(c["id"]) for c in cur.fetchall()}

                # Physically delete all room_cell rows of this floor
                cur.execute("DELETE FROM room_cell WHERE floor_id = %s", (floor_id,))
                deleted = cur.rowcount

                # Batch insert the new room_cell rows
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
                    # Cascading cleanup of related bindings (R1/R2): soft-delete room_cell, physically delete device_cell, and record undo for recovery
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
                        # Restore room↔cell bindings soft-deleted by the cascade; skip if the cell was reassigned to the same room
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
                        # Restore device↔cell bindings physically deleted by the cascade; skip if the device was rebound
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

    # -- Facade appearance configuration ---------------------------------------------

    def get_facade_config(self) -> dict[str, Any] | None:
        """Get the facade config (single row); None if no record exists."""
        sql = "SELECT id, config_json FROM building_facade_config ORDER BY id ASC LIMIT 1"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
        if row is None:
            return None
        import json
        d = dict(row)
        if isinstance(d.get("config_json"), str):
            d["config_json"] = json.loads(d["config_json"])
        return d

    def save_facade_config(self, config: dict[str, Any]) -> int:
        """Save the facade config (UPSERT single row), returning its id."""
        import json
        payload = json.dumps(config, ensure_ascii=False)
        sql_check = "SELECT id FROM building_facade_config ORDER BY id ASC LIMIT 1"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_check)
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "UPDATE building_facade_config SET config_json = %s WHERE id = %s",
                        (payload, int(row["id"])),
                    )
                    return int(row["id"])
                else:
                    cur.execute(
                        "INSERT INTO building_facade_config (config_json) VALUES (%s)",
                        (payload,),
                    )
                    return cur.lastrowid

    # ------------------------------------------------------------------
    # Permission module (sys_user / sys_role / sys_menu / sys_oper_log)
    # Follows RuoYi-Vue RBAC: user-role-menu, where menu.permission is the button-level permission marker
    # ------------------------------------------------------------------

    SUPER_ADMIN_ROLE_KEY = "admin"

    # ---- Auth & current user ----

    def get_sys_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Look up a user by login name (includes the password hash)."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM sys_user WHERE username = %s",
                    (username,),
                )
                row = cur.fetchone()
        return dict(row) if row else None

    def get_sys_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        """Look up a user by ID (without the password hash)."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT u.id, u.dept_id, d.dept_name, u.username, u.nickname,
                              u.email, u.phone, u.avatar, u.status, u.remark,
                              u.created_at, u.updated_at
                       FROM sys_user u
                       LEFT JOIN sys_dept d ON d.dept_id = u.dept_id
                       WHERE u.id = %s""",
                    (user_id,),
                )
                row = cur.fetchone()
        return self._parse_json_fields(dict(row), ()) if row else None

    def get_user_role_keys(self, user_id: int) -> list[str]:
        """All role keys (role_key) of the user."""
        sql = """
            SELECT r.role_key
            FROM sys_role r
            JOIN sys_user_role ur ON ur.role_id = r.id
            WHERE ur.user_id = %(user_id)s AND r.status = 1
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"user_id": user_id})
                rows = cur.fetchall() or []
        return [str(r["role_key"]) for r in rows]

    def is_super_admin(self, user_id: int) -> bool:
        """Whether the user has the super-admin role (admin); super-admin skips all permission checks."""
        return self.SUPER_ADMIN_ROLE_KEY in self.get_user_role_keys(user_id)

    def get_user_permissions(self, user_id: int) -> list[str]:
        """Merged permission markers across all roles of the user (incl. button-level F).

        Super-admin returns ['*:*:*'] to mean full permissions.
        """
        if self.is_super_admin(user_id):
            return ["*:*:*"]
        sql = """
            SELECT DISTINCT m.permission
            FROM sys_menu m
            JOIN sys_role_menu rm ON rm.menu_id = m.id
            JOIN sys_user_role ur ON ur.role_id = rm.role_id
            JOIN sys_role r ON r.id = ur.role_id
            WHERE ur.user_id = %(user_id)s
              AND r.status = 1 AND m.status = 1
              AND m.permission IS NOT NULL AND m.permission <> ''
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"user_id": user_id})
                rows = cur.fetchall() or []
        return [str(r["permission"]) for r in rows]

    @staticmethod
    def build_menu_tree(menus: list[dict[str, Any]], parent_id: int = 0) -> list[dict[str, Any]]:
        """Build a tree from a flat menu list (sorted by sort asc, id asc)."""
        children = [m for m in menus if int(m.get("parent_id", 0)) == parent_id]
        for m in children:
            m["children"] = Database.build_menu_tree(menus, int(m["id"]))
        children.sort(key=lambda x: (x.get("sort") or 0, x.get("id") or 0))
        return children

    def get_user_menu_tree(self, user_id: int) -> list[dict[str, Any]]:
        """Menu tree visible to the current user (only directories M / menus C, for frontend dynamic routes and sidebar)."""
        if self.is_super_admin(user_id):
            clause = ""
            params: dict[str, Any] = {}
        else:
            clause = """AND m.id IN (
                SELECT rm.menu_id FROM sys_role_menu rm
                JOIN sys_user_role ur ON ur.role_id = rm.role_id
                JOIN sys_role r ON r.id = ur.role_id
                WHERE ur.user_id = %(user_id)s AND r.status = 1
            )"""
            params = {"user_id": user_id}
        sql = f"""
            SELECT m.id, m.parent_id, m.menu_name, m.i18n_key, m.path, m.component,
                   m.menu_type, m.permission, m.icon, m.sort, m.visible, m.status
            FROM sys_menu m
            WHERE m.menu_type IN ('M', 'C')
              AND m.visible = 1 AND m.status = 1
              {clause}
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() or []
        menus = [self._parse_json_fields(dict(r), ()) for r in rows]
        return self.build_menu_tree(menus)

    # ---- User management ----

    def list_sys_users(
        self,
        *,
        keyword: str | None = None,
        status: int | None = None,
        dept_id: int | None = None,
        scope_user_id: int | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Paginated user query, each row with role names (comma-joined) and dept name.

        dept_id accepts a dept-tree node and includes users under all its descendant departments (RuoYi behavior).
        When scope_user_id (the current logged-in user ID) is provided, visible scope is filtered by the
        user's role data_scope.
        """
        where = ["1=1"]
        params: dict[str, Any] = {}
        if keyword:
            where.append("(u.username LIKE %(kw)s OR u.nickname LIKE %(kw)s OR u.phone LIKE %(kw)s)")
            params["kw"] = f"%{keyword}%"
        if status is not None:
            where.append("u.status = %(status)s")
            params["status"] = status
        if dept_id:
            where.append(
                """(u.dept_id = %(dept_id)s OR u.dept_id IN (
                       SELECT dept_id FROM sys_dept
                       WHERE del_flag = '0'
                         AND FIND_IN_SET(%(dept_id)s, ancestors)
                   ))"""
            )
            params["dept_id"] = dept_id
        if scope_user_id is not None:
            scope_sql, scope_params = self.get_user_data_scope_clause(
                scope_user_id, alias="u", dept_col="dept_id", user_col="id"
            )
            if scope_sql:
                where.append(scope_sql)
                params.update(scope_params)
        clause = " AND ".join(where)
        params["limit"] = limit
        params["offset"] = offset
        sql = f"""
            SELECT u.id, u.dept_id, d.dept_name, u.username, u.nickname, u.email, u.phone, u.status,
                   u.remark, u.created_at, u.updated_at,
                   (SELECT GROUP_CONCAT(r.role_name SEPARATOR ', ')
                    FROM sys_user_role ur
                    JOIN sys_role r ON r.id = ur.role_id
                    WHERE ur.user_id = u.id) AS roles,
                   (SELECT GROUP_CONCAT(r.role_key SEPARATOR ',')
                    FROM sys_user_role ur
                    JOIN sys_role r ON r.id = ur.role_id
                    WHERE ur.user_id = u.id) AS role_keys
            FROM sys_user u
            LEFT JOIN sys_dept d ON d.dept_id = u.dept_id
            WHERE {clause}
            ORDER BY u.id ASC
            LIMIT %(limit)s OFFSET %(offset)s
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM sys_user u WHERE {clause}",
                    {k: v for k, v in params.items() if k not in ("limit", "offset")},
                )
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                cur.execute(sql, params)
                rows = cur.fetchall() or []
        return [self._parse_json_fields(dict(r), ()) for r in rows], total

    def create_sys_user(self, data: dict[str, Any]) -> int:
        """Create a user, returning the new user ID."""
        sql = """
            INSERT INTO sys_user (username, password, nickname, email, phone, dept_id, status, remark)
            VALUES (%(username)s, %(password)s, %(nickname)s, %(email)s, %(phone)s, %(dept_id)s, %(status)s, %(remark)s)
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "username": data["username"],
                    "password": data["password"],
                    "nickname": data.get("nickname"),
                    "email": data.get("email"),
                    "phone": data.get("phone"),
                    "dept_id": data.get("dept_id"),
                    "status": int(data.get("status", 1)),
                    "remark": data.get("remark"),
                })
                return int(cur.lastrowid)

    def update_sys_user(self, user_id: int, data: dict[str, Any]) -> bool:
        """Update user profile (without password); returns whether a row was matched."""
        fields = []
        params: dict[str, Any] = {"id": user_id}
        for key in ("nickname", "email", "phone", "status", "remark", "dept_id", "sex", "avatar"):
            if key in data:
                fields.append(f"{key} = %({key})s")
                params[key] = data[key]
        if not fields:
            return False
        sql = f"UPDATE sys_user SET {', '.join(fields)} WHERE id = %(id)s"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount > 0

    def reset_sys_user_password(self, user_id: int, new_password_hash: str) -> bool:
        """Reset the user's password (accepts a bcrypt hash)."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sys_user SET password = %s WHERE id = %s",
                    (new_password_hash, user_id),
                )
                return cur.rowcount > 0

    def delete_sys_user(self, user_id: int) -> bool:
        """Delete a user and clean up their role/post associations. Returns whether a row was matched."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_user_role WHERE user_id = %s", (user_id,))
                cur.execute("DELETE FROM sys_user_post WHERE user_id = %s", (user_id,))
                cur.execute("DELETE FROM sys_user WHERE id = %s", (user_id,))
                return cur.rowcount > 0

    def get_user_role_ids(self, user_id: int) -> list[int]:
        """User's role ID list (for selection echo)."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT role_id FROM sys_user_role WHERE user_id = %s",
                    (user_id,),
                )
                rows = cur.fetchall() or []
        return [int(r["role_id"]) for r in rows]

    def set_user_roles(self, user_id: int, role_ids: list[int]) -> None:
        """Replace all role bindings of the user."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_user_role WHERE user_id = %s", (user_id,))
                for rid in role_ids:
                    cur.execute(
                        "INSERT INTO sys_user_role (user_id, role_id) VALUES (%s, %s)",
                        (user_id, int(rid)),
                    )

    # ---- Role management ----

    def list_sys_roles(
        self,
        *,
        role_name: str | None = None,
        role_key: str | None = None,
        status: int | None = None,
        begin: str | None = None,
        end: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """Paginated role query (RuoYi query conditions: role name / permission key / status / created time)."""
        where = ["1=1"]
        params: dict[str, Any] = {}
        if role_name:
            where.append("role_name LIKE %(role_name)s")
            params["role_name"] = f"%{role_name}%"
        if role_key:
            where.append("role_key LIKE %(role_key)s")
            params["role_key"] = f"%{role_key}%"
        if status is not None:
            where.append("status = %(status)s")
            params["status"] = status
        if begin:
            where.append("DATE(created_at) >= %(begin)s")
            params["begin"] = begin
        if end:
            where.append("DATE(created_at) <= %(end)s")
            params["end"] = end
        clause = " AND ".join(where)
        params["limit"] = limit
        params["offset"] = offset
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM sys_role WHERE {clause}",
                    {k: v for k, v in params.items() if k not in ("limit", "offset")},
                )
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                cur.execute(
                    f"""SELECT id, role_name, role_key, sort, status, data_scope, remark, created_at, updated_at
                        FROM sys_role WHERE {clause} ORDER BY sort ASC, id ASC
                        LIMIT %(limit)s OFFSET %(offset)s""",
                    params,
                )
                rows = cur.fetchall() or []
        return [self._parse_json_fields(dict(r), ()) for r in rows], total

    def list_all_roles(self) -> list[dict[str, Any]]:
        """All enabled roles (for dropdowns / assignment)."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, role_name, role_key, sort, status, remark
                       FROM sys_role WHERE status = 1 ORDER BY sort ASC, id ASC"""
                )
                rows = cur.fetchall() or []
        return [dict(r) for r in rows]

    def get_sys_role(self, role_id: int) -> dict[str, Any] | None:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM sys_role WHERE id = %s",
                    (role_id,),
                )
                row = cur.fetchone()
        return dict(row) if row else None

    def get_sys_role_by_key(self, role_key: str) -> dict[str, Any] | None:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM sys_role WHERE role_key = %s",
                    (role_key,),
                )
                row = cur.fetchone()
        return dict(row) if row else None

    def create_sys_role(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO sys_role (role_name, role_key, sort, status, data_scope, remark)
            VALUES (%(role_name)s, %(role_key)s, %(sort)s, %(status)s, %(data_scope)s, %(remark)s)
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "role_name": data["role_name"],
                    "role_key": data["role_key"],
                    "sort": int(data.get("sort", 0)),
                    "status": int(data.get("status", 1)),
                    "data_scope": str(data.get("data_scope", "1")),
                    "remark": data.get("remark"),
                })
                return int(cur.lastrowid)

    def update_sys_role(self, role_id: int, data: dict[str, Any]) -> bool:
        fields = []
        params: dict[str, Any] = {"id": role_id}
        for key in ("role_name", "role_key", "sort", "status", "remark", "data_scope"):
            if key in data:
                fields.append(f"{key} = %({key})s")
                params[key] = data[key]
        if not fields:
            return False
        sql = f"UPDATE sys_role SET {', '.join(fields)} WHERE id = %(id)s"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount > 0

    def delete_sys_role(self, role_id: int) -> bool:
        """Delete a role and clean up its associations (user-role, role-menu, role-dept data permission)."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_role_menu WHERE role_id = %s", (role_id,))
                cur.execute("DELETE FROM sys_user_role WHERE role_id = %s", (role_id,))
                cur.execute("DELETE FROM sys_role_dept WHERE role_id = %s", (role_id,))
                cur.execute("DELETE FROM sys_role WHERE id = %s", (role_id,))
                return cur.rowcount > 0

    def get_role_menu_ids(self, role_id: int) -> list[int]:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT menu_id FROM sys_role_menu WHERE role_id = %s",
                    (role_id,),
                )
                rows = cur.fetchall() or []
        return [int(r["menu_id"]) for r in rows]

    def set_role_menus(self, role_id: int, menu_ids: list[int]) -> None:
        """Replace all menu grants of the role."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_role_menu WHERE role_id = %s", (role_id,))
                for mid in menu_ids:
                    cur.execute(
                        "INSERT INTO sys_role_menu (role_id, menu_id) VALUES (%s, %s)",
                        (role_id, int(mid)),
                    )

    # ---- Role data permission (data_scope / sys_role_dept) ----

    def get_role_dept_ids(self, role_id: int) -> list[int]:
        """Dept ID list selected by the role's custom data permission."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT dept_id FROM sys_role_dept WHERE role_id = %s",
                    (role_id,),
                )
                rows = cur.fetchall() or []
        return [int(r["dept_id"]) for r in rows]

    def set_role_depts(self, role_id: int, dept_ids: list[int]) -> None:
        """Replace the dept set of the role's custom data permission."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_role_dept WHERE role_id = %s", (role_id,))
                for did in dept_ids:
                    cur.execute(
                        "INSERT INTO sys_role_dept (role_id, dept_id) VALUES (%s, %s)",
                        (role_id, int(did)),
                    )

    def delete_role_depts(self, role_id: int) -> None:
        """Clean up the role's dept data-permission associations when the role is deleted."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_role_dept WHERE role_id = %s", (role_id,))

    def get_user_role_data_scopes(self, user_id: int) -> list[dict[str, Any]]:
        """All (role_id, data_scope) of the user's enabled roles."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT r.id AS role_id, r.data_scope
                       FROM sys_user_role ur
                       JOIN sys_role r ON r.id = ur.role_id
                       WHERE ur.user_id = %(user_id)s AND r.status = 1""",
                    {"user_id": user_id},
                )
                rows = cur.fetchall() or []
        return [dict(r) for r in rows]

    def get_user_data_scope_clause(
        self,
        user_id: int,
        *,
        alias: str = "u",
        dept_col: str = "dept_id",
        user_col: str = "id",
    ) -> tuple[str, dict[str, Any]]:
        """Generate the WHERE fragment and params for data permission (data_scope).

        Multi-role merge (RuoYi behavior): if any role is "all" (1), no filter is applied;
        otherwise the constraints of each role are OR-merged. Super-admin or no-role users
        are not filtered.

        Returns ("", {}) to mean no filtering; otherwise a ("(...)", params) fragment that
        the caller appends to the AND condition list (table alias via `alias`).
        """
        if self.is_super_admin(user_id):
            return "", {}
        scopes = self.get_user_role_data_scopes(user_id)
        if not scopes:
            return "", {}
        if any(s["data_scope"] == "1" for s in scopes):
            return "", {}
        user = self.get_sys_user_by_id(user_id)
        user_dept_id = int(user["dept_id"]) if user and user.get("dept_id") else None

        or_parts: list[str] = []
        params: dict[str, Any] = {}
        for i, s in enumerate(scopes):
            scope = s["data_scope"]
            role_id = s["role_id"]
            if scope == "2":
                or_parts.append(
                    f"{alias}.{dept_col} IN "
                    f"(SELECT dept_id FROM sys_role_dept WHERE role_id = %(scope_role_{i})s)"
                )
                params[f"scope_role_{i}"] = role_id
            elif scope == "3":
                if user_dept_id is not None:
                    or_parts.append(f"{alias}.{dept_col} = %(scope_dept)s")
                    params["scope_dept"] = user_dept_id
            elif scope == "4":
                if user_dept_id is not None:
                    or_parts.append(
                        f"({alias}.{dept_col} = %(scope_dept)s OR {alias}.{dept_col} IN ("
                        f"SELECT dept_id FROM sys_dept WHERE del_flag = '0' "
                        f"AND FIND_IN_SET(%(scope_dept)s, ancestors)))"
                    )
                    params["scope_dept"] = user_dept_id
            elif scope == "5":
                or_parts.append(f"{alias}.{user_col} = %(scope_user)s")
                params["scope_user"] = user_id
        if not or_parts:
            return "", {}
        return "(" + " OR ".join(or_parts) + ")", params

    # ---- Menu management ----

    def list_all_menus(self) -> list[dict[str, Any]]:
        """All menus (incl. buttons), returned as a tree."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, parent_id, menu_name, i18n_key, path, component,
                              menu_type, permission, icon, sort, visible, status,
                              remark, created_at, updated_at
                       FROM sys_menu ORDER BY sort ASC, id ASC"""
                )
                rows = cur.fetchall() or []
        menus = [self._parse_json_fields(dict(r), ()) for r in rows]
        return self.build_menu_tree(menus)

    def get_sys_menu(self, menu_id: int) -> dict[str, Any] | None:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sys_menu WHERE id = %s", (menu_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def count_sys_menu_children(self, menu_id: int) -> int:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM sys_menu WHERE parent_id = %s",
                    (menu_id,),
                )
                return int((cur.fetchone() or {}).get("cnt") or 0)

    def create_sys_menu(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO sys_menu (parent_id, menu_name, i18n_key, path, component,
                                  menu_type, permission, icon, sort, visible, status, remark)
            VALUES (%(parent_id)s, %(menu_name)s, %(i18n_key)s, %(path)s, %(component)s,
                    %(menu_type)s, %(permission)s, %(icon)s, %(sort)s, %(visible)s, %(status)s, %(remark)s)
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "parent_id": int(data.get("parent_id", 0)),
                    "menu_name": data["menu_name"],
                    "i18n_key": data.get("i18n_key"),
                    "path": data.get("path"),
                    "component": data.get("component"),
                    "menu_type": data.get("menu_type", "C"),
                    "permission": data.get("permission"),
                    "icon": data.get("icon"),
                    "sort": int(data.get("sort", 0)),
                    "visible": int(data.get("visible", 1)),
                    "status": int(data.get("status", 1)),
                    "remark": data.get("remark"),
                })
                return int(cur.lastrowid)

    def update_sys_menu(self, menu_id: int, data: dict[str, Any]) -> bool:
        fields = []
        params: dict[str, Any] = {"id": menu_id}
        for key in ("parent_id", "menu_name", "i18n_key", "path", "component",
                    "menu_type", "permission", "icon", "sort", "visible", "status", "remark"):
            if key in data:
                fields.append(f"{key} = %({key})s")
                params[key] = data[key]
        if not fields:
            return False
        sql = f"UPDATE sys_menu SET {', '.join(fields)} WHERE id = %(id)s"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount > 0

    def delete_sys_menu(self, menu_id: int) -> bool:
        """Delete a menu and clean up role authorization references. Returns whether a row was matched."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_role_menu WHERE menu_id = %s", (menu_id,))
                cur.execute("DELETE FROM sys_menu WHERE id = %s", (menu_id,))
                return cur.rowcount > 0

    # ---- Operation logs ----

    def insert_oper_log(self, entry: dict[str, Any]) -> None:
        sql = """
            INSERT INTO sys_oper_log (title, business_type, method, request_method,
                                      oper_url, oper_ip, oper_name, oper_param,
                                      json_result, status, error_msg)
            VALUES (%(title)s, %(business_type)s, %(method)s, %(request_method)s,
                    %(oper_url)s, %(oper_ip)s, %(oper_name)s, %(oper_param)s,
                    %(json_result)s, %(status)s, %(error_msg)s)
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "title": entry.get("title") or "",
                    "business_type": int(entry.get("business_type", 0)),
                    "method": entry.get("method") or "",
                    "request_method": entry.get("request_method") or "",
                    "oper_url": entry.get("oper_url") or "",
                    "oper_ip": entry.get("oper_ip") or "",
                    "oper_name": entry.get("oper_name") or "",
                    "oper_param": entry.get("oper_param") or "",
                    "json_result": entry.get("json_result") or "",
                    "status": int(entry.get("status", 1)),
                    "error_msg": entry.get("error_msg") or "",
                })

    def list_oper_logs(
        self,
        *,
        title: str | None = None,
        oper_name: str | None = None,
        business_type: int | None = None,
        status: int | None = None,
        begin: str | None = None,
        end: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["1=1"]
        params: dict[str, Any] = {}
        if title:
            where.append("title LIKE %(title)s")
            params["title"] = f"%{title}%"
        if oper_name:
            where.append("oper_name LIKE %(oper_name)s")
            params["oper_name"] = f"%{oper_name}%"
        if status is not None:
            where.append("status = %(status)s")
            params["status"] = status
        if business_type is not None:
            where.append("business_type = %(business_type)s")
            params["business_type"] = business_type
        if begin:
            where.append("oper_time >= %(begin)s")
            params["begin"] = begin
        if end:
            where.append("oper_time <= %(end)s")
            params["end"] = end
        clause = " AND ".join(where)
        params["limit"] = limit
        params["offset"] = offset
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM sys_oper_log WHERE {clause}",
                    {k: v for k, v in params.items() if k not in ("limit", "offset")},
                )
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                cur.execute(
                    f"""SELECT * FROM sys_oper_log WHERE {clause}
                        ORDER BY oper_time DESC, id DESC
                        LIMIT %(limit)s OFFSET %(offset)s""",
                    params,
                )
                rows = cur.fetchall() or []
        return [self._parse_json_fields(dict(r), ()) for r in rows], total

    def delete_oper_logs(self, ids: list[int]) -> int:
        if not ids:
            return 0
        marks = ", ".join(["%s"] * len(ids))
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM sys_oper_log WHERE id IN ({marks})", ids)
                return cur.rowcount

    def clean_oper_logs(self) -> int:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_oper_log")
                return cur.rowcount

    # ------------------------------------------------------------------
    # Dept management (sys_dept, RuoYi standard fields)
    # ------------------------------------------------------------------

    def list_depts(self) -> list[dict[str, Any]]:
        """Full dept list (undeleted); the frontend builds the tree from it."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT dept_id, parent_id, ancestors, dept_name, order_num,
                              leader, phone, email, status, del_flag,
                              create_time, update_time
                       FROM sys_dept WHERE del_flag = '0'
                       ORDER BY parent_id ASC, order_num ASC, dept_id ASC"""
                )
                rows = cur.fetchall() or []
        return [self._parse_json_fields(dict(r), ()) for r in rows]

    @staticmethod
    def build_dept_tree(depts: list[dict[str, Any]], parent_id: int = 0) -> list[dict[str, Any]]:
        """Build a tree from a flat dept list (RuoYi deptTreeselect format)."""
        children = [d for d in depts if int(d.get("parent_id", 0)) == parent_id]
        for d in children:
            d["children"] = Database.build_dept_tree(depts, int(d["dept_id"]))
        children.sort(key=lambda x: (x.get("order_num") or 0, x.get("dept_id") or 0))
        return children

    def get_dept_tree(self) -> list[dict[str, Any]]:
        """Full dept tree (for the data-permission dept tree selection)."""
        return self.build_dept_tree(self.list_depts())

    def get_dept_by_id(self, dept_id: int) -> dict[str, Any] | None:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM sys_dept WHERE dept_id = %s AND del_flag = '0'",
                    (dept_id,),
                )
                row = cur.fetchone()
        return dict(row) if row else None

    def _dept_ancestors(self, parent_id: int) -> str:
        """Compute the ancestors list from the parent dept ID."""
        if not parent_id or parent_id <= 0:
            return "0"
        parent = self.get_dept_by_id(parent_id)
        if not parent:
            return "0"
        return f"{parent.get('ancestors') or '0'},{parent_id}"

    def create_dept(self, data: dict[str, Any]) -> int:
        parent_id = int(data.get("parent_id") or 0)
        sql = """
            INSERT INTO sys_dept (parent_id, ancestors, dept_name, order_num, leader,
                                  phone, email, status, create_by, create_time)
            VALUES (%(parent_id)s, %(ancestors)s, %(dept_name)s, %(order_num)s,
                    %(leader)s, %(phone)s, %(email)s, %(status)s, %(create_by)s, NOW())
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "parent_id": parent_id,
                    "ancestors": self._dept_ancestors(parent_id),
                    "dept_name": data.get("dept_name"),
                    "order_num": int(data.get("order_num") or 0),
                    "leader": data.get("leader"),
                    "phone": data.get("phone"),
                    "email": data.get("email"),
                    "status": data.get("status", "0"),
                    "create_by": data.get("create_by") or "",
                })
                return int(cur.lastrowid)

    def update_dept(self, dept_id: int, data: dict[str, Any]) -> bool:
        fields = []
        params: dict[str, Any] = {"dept_id": dept_id}
        for key in ("dept_name", "order_num", "leader", "phone", "email", "status"):
            if key in data:
                fields.append(f"{key} = %({key})s")
                params[key] = int(data[key]) if key == "order_num" else data[key]
        if "update_by" in data:
            fields.append("update_by = %(update_by)s")
            params["update_by"] = data["update_by"]
        if not fields:
            return False
        fields.append("update_time = NOW()")
        sql = f"UPDATE sys_dept SET {', '.join(fields)} WHERE dept_id = %(dept_id)s"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount > 0

    def has_children_dept(self, dept_id: int) -> bool:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM sys_dept WHERE parent_id = %s AND del_flag = '0'",
                    (dept_id,),
                )
                return int((cur.fetchone() or {}).get("cnt") or 0) > 0

    def dept_has_users(self, dept_id: int) -> bool:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM sys_user WHERE dept_id = %s",
                    (dept_id,),
                )
                return int((cur.fetchone() or {}).get("cnt") or 0) > 0

    def delete_dept(self, dept_id: int) -> bool:
        """Soft-delete a dept (del_flag='2'). Returns False if it has child depts or users."""
        if self.has_children_dept(dept_id) or self.dept_has_users(dept_id):
            return False
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sys_dept SET del_flag = '2' WHERE dept_id = %s",
                    (dept_id,),
                )
                return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Post management (sys_post, RuoYi standard fields)
    # ------------------------------------------------------------------

    def list_posts(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["1=1"]
        params: dict[str, Any] = {}
        if keyword:
            where.append("(post_code LIKE %(kw)s OR post_name LIKE %(kw)s)")
            params["kw"] = f"%{keyword}%"
        if status is not None and status != "":
            where.append("status = %(status)s")
            params["status"] = status
        clause = " AND ".join(where)
        params["limit"] = limit
        params["offset"] = offset
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM sys_post WHERE {clause}",
                    {k: v for k, v in params.items() if k not in ("limit", "offset")},
                )
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                cur.execute(
                    f"""SELECT post_id, post_code, post_name, post_sort, status,
                               create_time, remark
                        FROM sys_post WHERE {clause}
                        ORDER BY post_sort ASC, post_id ASC
                        LIMIT %(limit)s OFFSET %(offset)s""",
                    params,
                )
                rows = cur.fetchall() or []
        return [self._parse_json_fields(dict(r), ()) for r in rows], total

    def get_post_by_id(self, post_id: int) -> dict[str, Any] | None:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sys_post WHERE post_id = %s", (post_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def get_post_by_code(self, post_code: str) -> dict[str, Any] | None:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sys_post WHERE post_code = %s", (post_code,))
                row = cur.fetchone()
        return dict(row) if row else None

    def create_post(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO sys_post (post_code, post_name, post_sort, status, create_by, create_time, remark)
            VALUES (%(post_code)s, %(post_name)s, %(post_sort)s, %(status)s, %(create_by)s, NOW(), %(remark)s)
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "post_code": data["post_code"],
                    "post_name": data["post_name"],
                    "post_sort": int(data.get("post_sort") or 0),
                    "status": data.get("status", "0"),
                    "create_by": data.get("create_by") or "",
                    "remark": data.get("remark"),
                })
                return int(cur.lastrowid)

    def update_post(self, post_id: int, data: dict[str, Any]) -> bool:
        fields = []
        params: dict[str, Any] = {"post_id": post_id}
        for key in ("post_code", "post_name", "post_sort", "status", "remark"):
            if key in data:
                fields.append(f"{key} = %({key})s")
                params[key] = int(data[key]) if key == "post_sort" else data[key]
        if "update_by" in data:
            fields.append("update_by = %(update_by)s")
            params["update_by"] = data["update_by"]
        if not fields:
            return False
        fields.append("update_time = NOW()")
        sql = f"UPDATE sys_post SET {', '.join(fields)} WHERE post_id = %(post_id)s"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount > 0

    def delete_post(self, post_id: int) -> bool:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_user_post WHERE post_id = %s", (post_id,))
                cur.execute("DELETE FROM sys_post WHERE post_id = %s", (post_id,))
                return cur.rowcount > 0

    def get_user_post_ids(self, user_id: int) -> list[int]:
        """User's post ID list (for selection echo)."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT post_id FROM sys_user_post WHERE user_id = %s",
                    (user_id,),
                )
                rows = cur.fetchall() or []
        return [int(r["post_id"]) for r in rows]

    def set_user_posts(self, user_id: int, post_ids: list[int]) -> None:
        """Replace all post bindings of the user."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_user_post WHERE user_id = %s", (user_id,))
                for pid in post_ids:
                    cur.execute(
                        "INSERT INTO sys_user_post (user_id, post_id) VALUES (%s, %s)",
                        (user_id, int(pid)),
                    )

    # ------------------------------------------------------------------
    # Login logs (sys_login_log, RuoYi standard fields)
    # ------------------------------------------------------------------

    def record_login_log(
        self,
        *,
        user_name: str,
        ipaddr: str = "",
        login_location: str = "",
        browser: str = "",
        os: str = "",
        status: str = "0",
        msg: str = "",
    ) -> None:
        sql = """
            INSERT INTO sys_login_log (user_name, ipaddr, login_location, browser, os, status, msg, login_time)
            VALUES (%(user_name)s, %(ipaddr)s, %(login_location)s, %(browser)s, %(os)s, %(status)s, %(msg)s, NOW())
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "user_name": user_name,
                    "ipaddr": ipaddr,
                    "login_location": login_location,
                    "browser": browser,
                    "os": os,
                    "status": status,
                    "msg": msg,
                })

    def list_login_logs(
        self,
        *,
        user_name: str | None = None,
        status: str | None = None,
        begin: str | None = None,
        end: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["1=1"]
        params: dict[str, Any] = {}
        if user_name:
            where.append("user_name LIKE %(user_name)s")
            params["user_name"] = f"%{user_name}%"
        if status is not None and status != "":
            where.append("status = %(status)s")
            params["status"] = status
        if begin:
            where.append("login_time >= %(begin)s")
            params["begin"] = begin
        if end:
            where.append("login_time <= %(end)s")
            params["end"] = end
        clause = " AND ".join(where)
        params["limit"] = limit
        params["offset"] = offset
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM sys_login_log WHERE {clause}",
                    {k: v for k, v in params.items() if k not in ("limit", "offset")},
                )
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                cur.execute(
                    f"""SELECT * FROM sys_login_log WHERE {clause}
                        ORDER BY login_time DESC, info_id DESC
                        LIMIT %(limit)s OFFSET %(offset)s""",
                    params,
                )
                rows = cur.fetchall() or []
        return [self._parse_json_fields(dict(r), ()) for r in rows], total

    def delete_login_logs(self, ids: list[int]) -> int:
        if not ids:
            return 0
        marks = ", ".join(["%s"] * len(ids))
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM sys_login_log WHERE info_id IN ({marks})", ids)
                return cur.rowcount

    def clean_login_logs(self) -> int:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_login_log")
                return cur.rowcount

    # ------------------------------------------------------------------
    # Parameter settings (sys_config, RuoYi standard fields)
    # ------------------------------------------------------------------

    def list_configs(
        self,
        *,
        keyword: str | None = None,
        config_type: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["1=1"]
        params: dict[str, Any] = {}
        if keyword:
            where.append("(config_name LIKE %(kw)s OR config_key LIKE %(kw)s)")
            params["kw"] = f"%{keyword}%"
        if config_type is not None and config_type != "":
            where.append("config_type = %(config_type)s")
            params["config_type"] = config_type
        clause = " AND ".join(where)
        params["limit"] = limit
        params["offset"] = offset
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM sys_config WHERE {clause}",
                    {k: v for k, v in params.items() if k not in ("limit", "offset")},
                )
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                cur.execute(
                    f"""SELECT config_id, config_name, config_key, config_value,
                               config_type, create_time, remark
                        FROM sys_config WHERE {clause}
                        ORDER BY config_id ASC
                        LIMIT %(limit)s OFFSET %(offset)s""",
                    params,
                )
                rows = cur.fetchall() or []
        return [self._parse_json_fields(dict(r), ()) for r in rows], total

    def get_config_by_id(self, config_id: int) -> dict[str, Any] | None:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sys_config WHERE config_id = %s", (config_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def get_config_by_key(self, config_key: str) -> dict[str, Any] | None:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sys_config WHERE config_key = %s", (config_key,))
                row = cur.fetchone()
        return dict(row) if row else None

    def create_config(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO sys_config (config_name, config_key, config_value, config_type, create_by, create_time, remark)
            VALUES (%(config_name)s, %(config_key)s, %(config_value)s, %(config_type)s, %(create_by)s, NOW(), %(remark)s)
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "config_name": data.get("config_name"),
                    "config_key": data.get("config_key"),
                    "config_value": data.get("config_value"),
                    "config_type": data.get("config_type", "N"),
                    "create_by": data.get("create_by") or "",
                    "remark": data.get("remark"),
                })
                return int(cur.lastrowid)

    def update_config(self, config_id: int, data: dict[str, Any]) -> bool:
        fields = []
        params: dict[str, Any] = {"config_id": config_id}
        for key in ("config_name", "config_key", "config_value", "config_type", "remark"):
            if key in data:
                fields.append(f"{key} = %({key})s")
                params[key] = data[key]
        if "update_by" in data:
            fields.append("update_by = %(update_by)s")
            params["update_by"] = data["update_by"]
        if not fields:
            return False
        fields.append("update_time = NOW()")
        sql = f"UPDATE sys_config SET {', '.join(fields)} WHERE config_id = %(config_id)s"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount > 0

    def delete_config(self, config_id: int) -> bool:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_config WHERE config_id = %s", (config_id,))
                return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Dict management (sys_dict_type / sys_dict_data, RuoYi standard fields)
    # ------------------------------------------------------------------

    def list_dict_types(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["1=1"]
        params: dict[str, Any] = {}
        if keyword:
            where.append("(dict_name LIKE %(kw)s OR dict_type LIKE %(kw)s)")
            params["kw"] = f"%{keyword}%"
        if status is not None and status != "":
            where.append("status = %(status)s")
            params["status"] = status
        clause = " AND ".join(where)
        params["limit"] = limit
        params["offset"] = offset
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM sys_dict_type WHERE {clause}",
                    {k: v for k, v in params.items() if k not in ("limit", "offset")},
                )
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                cur.execute(
                    f"""SELECT dict_id, dict_name, dict_type, status, create_time, remark
                        FROM sys_dict_type WHERE {clause}
                        ORDER BY dict_id ASC
                        LIMIT %(limit)s OFFSET %(offset)s""",
                    params,
                )
                rows = cur.fetchall() or []
        return [self._parse_json_fields(dict(r), ()) for r in rows], total

    def get_dict_type_by_id(self, dict_id: int) -> dict[str, Any] | None:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sys_dict_type WHERE dict_id = %s", (dict_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def get_dict_type_by_type(self, dict_type: str) -> dict[str, Any] | None:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sys_dict_type WHERE dict_type = %s", (dict_type,))
                row = cur.fetchone()
        return dict(row) if row else None

    def create_dict_type(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO sys_dict_type (dict_name, dict_type, status, create_by, create_time, remark)
            VALUES (%(dict_name)s, %(dict_type)s, %(status)s, %(create_by)s, NOW(), %(remark)s)
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "dict_name": data.get("dict_name"),
                    "dict_type": data.get("dict_type"),
                    "status": data.get("status", "0"),
                    "create_by": data.get("create_by") or "",
                    "remark": data.get("remark"),
                })
                return int(cur.lastrowid)

    def update_dict_type(self, dict_id: int, data: dict[str, Any]) -> bool:
        fields = []
        params: dict[str, Any] = {"dict_id": dict_id}
        for key in ("dict_name", "dict_type", "status", "remark"):
            if key in data:
                fields.append(f"{key} = %({key})s")
                params[key] = data[key]
        if "update_by" in data:
            fields.append("update_by = %(update_by)s")
            params["update_by"] = data["update_by"]
        if not fields:
            return False
        fields.append("update_time = NOW()")
        sql = f"UPDATE sys_dict_type SET {', '.join(fields)} WHERE dict_id = %(dict_id)s"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount > 0

    def delete_dict_type(self, dict_id: int) -> bool:
        """Delete a dict type and its data."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT dict_type FROM sys_dict_type WHERE dict_id = %s", (dict_id,))
                row = cur.fetchone()
                if row:
                    cur.execute("DELETE FROM sys_dict_data WHERE dict_type = %s", (row["dict_type"],))
                cur.execute("DELETE FROM sys_dict_type WHERE dict_id = %s", (dict_id,))
                return cur.rowcount > 0

    def list_dict_data(
        self,
        *,
        dict_type: str | None = None,
        dict_label: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["1=1"]
        params: dict[str, Any] = {}
        if dict_type:
            where.append("dict_type = %(dict_type)s")
            params["dict_type"] = dict_type
        if dict_label:
            where.append("dict_label LIKE %(dict_label)s")
            params["dict_label"] = f"%{dict_label}%"
        if status is not None and status != "":
            where.append("status = %(status)s")
            params["status"] = status
        clause = " AND ".join(where)
        params["limit"] = limit
        params["offset"] = offset
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM sys_dict_data WHERE {clause}",
                    {k: v for k, v in params.items() if k not in ("limit", "offset")},
                )
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                cur.execute(
                    f"""SELECT dict_code, dict_sort, dict_label, dict_value, dict_type,
                               css_class, list_class, is_default, status, create_time, remark
                        FROM sys_dict_data WHERE {clause}
                        ORDER BY dict_sort ASC, dict_code ASC
                        LIMIT %(limit)s OFFSET %(offset)s""",
                    params,
                )
                rows = cur.fetchall() or []
        return [self._parse_json_fields(dict(r), ()) for r in rows], total

    def get_dict_data_by_id(self, dict_code: int) -> dict[str, Any] | None:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sys_dict_data WHERE dict_code = %s", (dict_code,))
                row = cur.fetchone()
        return dict(row) if row else None

    def create_dict_data(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO sys_dict_data (dict_sort, dict_label, dict_value, dict_type,
                                       css_class, list_class, is_default, status,
                                       create_by, create_time, remark)
            VALUES (%(dict_sort)s, %(dict_label)s, %(dict_value)s, %(dict_type)s,
                    %(css_class)s, %(list_class)s, %(is_default)s, %(status)s,
                    %(create_by)s, NOW(), %(remark)s)
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "dict_sort": int(data.get("dict_sort") or 0),
                    "dict_label": data.get("dict_label"),
                    "dict_value": data.get("dict_value"),
                    "dict_type": data.get("dict_type"),
                    "css_class": data.get("css_class"),
                    "list_class": data.get("list_class"),
                    "is_default": data.get("is_default", "N"),
                    "status": data.get("status", "0"),
                    "create_by": data.get("create_by") or "",
                    "remark": data.get("remark"),
                })
                return int(cur.lastrowid)

    def update_dict_data(self, dict_code: int, data: dict[str, Any]) -> bool:
        fields = []
        params: dict[str, Any] = {"dict_code": dict_code}
        for key in ("dict_sort", "dict_label", "dict_value", "dict_type",
                    "css_class", "list_class", "is_default", "status", "remark"):
            if key in data:
                fields.append(f"{key} = %({key})s")
                params[key] = int(data[key]) if key == "dict_sort" else data[key]
        if "update_by" in data:
            fields.append("update_by = %(update_by)s")
            params["update_by"] = data["update_by"]
        if not fields:
            return False
        fields.append("update_time = NOW()")
        sql = f"UPDATE sys_dict_data SET {', '.join(fields)} WHERE dict_code = %(dict_code)s"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount > 0

    def delete_dict_data(self, dict_code: int) -> bool:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_dict_data WHERE dict_code = %s", (dict_code,))
                return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Access whitelist (sys_whitelist: login-free paths such as large-screen views)
    # ------------------------------------------------------------------

    def list_whitelists(
        self,
        *,
        keyword: str | None = None,
        path_type: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        where = ["1=1"]
        params: dict[str, Any] = {}
        if keyword:
            where.append("(path LIKE %(kw)s OR remark LIKE %(kw)s)")
            params["kw"] = f"%{keyword}%"
        if path_type is not None and path_type != "":
            where.append("path_type = %(path_type)s")
            params["path_type"] = path_type
        clause = " AND ".join(where)
        params["limit"] = limit
        params["offset"] = offset
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM sys_whitelist WHERE {clause}",
                    {k: v for k, v in params.items() if k not in ("limit", "offset")},
                )
                total = int((cur.fetchone() or {}).get("cnt") or 0)
                cur.execute(
                    f"""SELECT id, path, path_type, remark, status, create_time, update_time
                        FROM sys_whitelist WHERE {clause}
                        ORDER BY id ASC
                        LIMIT %(limit)s OFFSET %(offset)s""",
                    params,
                )
                rows = cur.fetchall() or []
        return [self._parse_json_fields(dict(r), ()) for r in rows], total

    def get_whitelist_by_id(self, whitelist_id: int) -> dict[str, Any] | None:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sys_whitelist WHERE id = %s", (whitelist_id,))
                row = cur.fetchone()
        return dict(row) if row else None

    def create_whitelist(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO sys_whitelist (path, path_type, remark, status)
            VALUES (%(path)s, %(path_type)s, %(remark)s, %(status)s)
        """
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "path": data.get("path"),
                    "path_type": data.get("path_type", "F"),
                    "remark": data.get("remark"),
                    "status": data.get("status", "0"),
                })
                return int(cur.lastrowid)

    def update_whitelist(self, whitelist_id: int, data: dict[str, Any]) -> bool:
        fields = []
        params: dict[str, Any] = {"id": whitelist_id}
        for key in ("path", "path_type", "remark", "status"):
            if key in data:
                fields.append(f"{key} = %({key})s")
                params[key] = data[key]
        if not fields:
            return False
        fields.append("update_time = NOW()")
        sql = f"UPDATE sys_whitelist SET {', '.join(fields)} WHERE id = %(id)s"
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount > 0

    def delete_whitelist(self, whitelist_id: int) -> bool:
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sys_whitelist WHERE id = %s", (whitelist_id,))
                return cur.rowcount > 0

    def get_whitelist_paths(self, path_type: str) -> list[str]:
        """Enabled whitelist path list (prefix matching)."""
        with self.wingon_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT path FROM sys_whitelist WHERE path_type = %s AND status = '0' ORDER BY id",
                    (path_type,),
                )
                rows = cur.fetchall() or []
        return [str(r["path"]) for r in rows]

    def is_api_whitelisted(self, path: str) -> bool:
        """Whether the backend API path matches a whitelist prefix (path_type='A')."""
        for prefix in self.get_whitelist_paths("A"):
            if prefix and path.startswith(prefix):
                return True
        return False
