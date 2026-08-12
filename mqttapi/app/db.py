import json
import re
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from .config import Settings
from .decoder import JSON_SECTION_KEYS

TOF_JSON_COLUMNS = (
    *JSON_SECTION_KEYS,
    "payload_json",
)
UG65_JSON_COLUMNS = (
    "rx_info_json",
    "tx_info_json",
    "payload_json",
)


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
        """
        sql = """
            SELECT d.sn, d.name, d.deviceName, d.model, d.floor, d.location, d.macAddress,
                   l.toDateTime, l.temperatureMedian, l.humidityMedian
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
