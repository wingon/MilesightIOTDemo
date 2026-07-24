"""Lightweight Milesight EM400 / People Counter payload helpers."""

from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import datetime
from typing import Any

JSON_SECTION_KEYS = (
    "line_trigger_data",
    "region_trigger_data",
    "region_count_data",
    "dwell_time_data",
    "dwell_start_time",
    "line_periodic_data",
    "line_total_data",
    "line_count_data",
    "region_periodic_data",
    "alarm_data",
)


def _to_int16_le(data: bytes, offset: int) -> int:
    raw = int.from_bytes(data[offset : offset + 2], "little", signed=False)
    return raw - 0x10000 if raw > 0x7FFF else raw


def parse_iso_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    if text.endswith("-00:00"):
        text = text[:-6]
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def decode_channel_payload(hex_payload: str) -> dict[str, Any]:
    """Decode Channel+Type+Data hex blocks used by Milesight sensors."""
    payload = re.sub(r"[^0-9a-fA-F]", "", hex_payload or "")
    if not payload:
        return {}

    data = binascii.unhexlify(payload)
    result: dict[str, Any] = {}
    i = 0
    while i + 1 < len(data):
        channel = data[i]
        typ = data[i + 1]
        i += 2

        if channel == 0x01 and typ == 0x75 and i < len(data):
            result["battery"] = data[i]
            i += 1
        elif channel == 0x03 and typ == 0x67 and i + 1 < len(data):
            result["temperature"] = round(_to_int16_le(data, i) / 10, 1)
            i += 2
        elif channel == 0x04 and typ == 0x82 and i + 1 < len(data):
            result["distance"] = int.from_bytes(data[i : i + 2], "little")
            i += 2
        elif channel == 0x05 and typ == 0x00 and i < len(data):
            result["position"] = "tilt" if data[i] == 1 else "normal"
            i += 1
        elif channel == 0xFF and typ == 0x16 and i + 7 < len(data):
            result["sn"] = data[i : i + 8].hex()
            i += 8
        else:
            break
    return result


def decode_am319_payload(hex_payload: str) -> dict[str, Any]:
    """Decode Milesight AM307/AM319 IPSO channel payload to frontend field names."""
    payload = re.sub(r"[^0-9a-fA-F]", "", hex_payload or "")
    if not payload:
        return {}

    data = binascii.unhexlify(payload)
    result: dict[str, Any] = {}
    i = 0
    while i + 1 < len(data):
        channel = data[i]
        typ = data[i + 1]
        i += 2

        if channel == 0x01 and typ == 0x75 and i < len(data):
            result["battery"] = data[i]
            i += 1
        elif channel == 0x03 and typ == 0x67 and i + 1 < len(data):
            result["temperature"] = round(_to_int16_le(data, i) / 10, 1)
            i += 2
        elif channel == 0x04 and typ == 0x68 and i < len(data):
            result["humidity"] = data[i] / 2
            i += 1
        elif channel == 0x05 and typ == 0x00 and i < len(data):
            result["pir"] = data[i]
            i += 1
        elif channel == 0x06 and typ == 0xCB and i < len(data):
            result["light_level"] = data[i]
            i += 1
        elif channel == 0x07 and typ == 0x7D and i + 1 < len(data):
            result["co2"] = int.from_bytes(data[i : i + 2], "little")
            i += 2
        elif channel == 0x08 and typ == 0x7D and i + 1 < len(data):
            # Historical TVOC concentration (÷100)
            result["tvoc"] = round(int.from_bytes(data[i : i + 2], "little") / 100, 2)
            i += 2
        elif channel == 0x08 and typ == 0xE6 and i + 1 < len(data):
            # Newer firmware TVOC level (matches gateway decoded JSON integers)
            result["tvoc"] = int.from_bytes(data[i : i + 2], "little")
            i += 2
        elif channel == 0x09 and typ == 0x73 and i + 1 < len(data):
            result["pressure"] = round(int.from_bytes(data[i : i + 2], "little") / 10, 1)
            i += 2
        elif channel == 0x0A and typ == 0x7D and i + 1 < len(data):
            result["hcho"] = round(int.from_bytes(data[i : i + 2], "little") / 100, 2)
            i += 2
        elif channel == 0x0B and typ == 0x7D and i + 1 < len(data):
            result["pm2_5"] = int.from_bytes(data[i : i + 2], "little")
            i += 2
        elif channel == 0x0C and typ == 0x7D and i + 1 < len(data):
            result["pm10"] = int.from_bytes(data[i : i + 2], "little")
            i += 2
        else:
            break
    return result


def decode_nb_frame(hex_payload: str) -> dict[str, Any]:
    """Decode NB MQTT binary frame (StartID + header + TLV data part)."""
    payload = re.sub(r"[^0-9a-fA-F]", "", hex_payload or "")
    if len(payload) < 40:
        return {}

    data = binascii.unhexlify(payload)
    if data[0] != 0x02:
        return {}

    result: dict[str, Any] = {
        "frame_counter": int.from_bytes(data[6:10], "little"),
        "protocol_version": data[10],
    }

    sn_bytes = data[16:32]
    result["device_sn"] = bytes.fromhex(sn_bytes.hex()).decode("ascii", errors="ignore").strip("\x00")
    imei_bytes = data[32:47]
    result["imei"] = bytes.fromhex(imei_bytes.hex()).decode("ascii", errors="ignore").strip("\x00")
    if len(data) > 77:
        result["signal_asu"] = data[77]

    data_len = int.from_bytes(data[78:80], "little") if len(data) > 79 else 0
    if data_len and len(data) >= 80 + data_len:
        tlv = data[80 : 80 + data_len].hex()
        result.update(decode_channel_payload(tlv))
    return result


def extract_hex_payload(message: str | bytes | dict | list) -> str:
    if isinstance(message, bytes):
        try:
            message = message.decode("utf-8")
        except UnicodeDecodeError:
            return message.hex()

    if isinstance(message, dict):
        for key in ("data", "payload", "payload_hex", "hex", "raw"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                if key == "data":
                    try:
                        return base64.b64decode(value).hex()
                    except (binascii.Error, ValueError):
                        return re.sub(r"[^0-9a-fA-F]", "", value)
                return re.sub(r"[^0-9a-fA-F]", "", value)
        return ""

    if isinstance(message, str):
        text = message.strip()
        if not text:
            return ""
        if text.startswith("{"):
            try:
                return extract_hex_payload(json.loads(text))
            except json.JSONDecodeError:
                pass
        return re.sub(r"[^0-9a-fA-F]", "", text)

    return ""


def flatten_milesight_json(parsed: dict[str, Any]) -> dict[str, Any]:
    """Extract structured People Counter fields from nested JSON uplink."""
    result: dict[str, Any] = {}
    device_info = parsed.get("device_info") or {}
    time_info = parsed.get("time_info") or {}

    if isinstance(device_info, dict):
        result["device_name"] = device_info.get("device_name")
        result["device_sn"] = device_info.get("device_sn")
        result["device_mac"] = device_info.get("device_mac")
        result["wlan_mac"] = device_info.get("wlan_mac")
        result["ip_address"] = device_info.get("ip_address")
        result["custom_device_id"] = device_info.get("custom_device_id")
        result["custom_site_id"] = device_info.get("custom_site_id")
        result["running_time_sec"] = device_info.get("running_time")
        result["firmware_version"] = device_info.get("firmware_version")
        result["hardware_version"] = device_info.get("hardware_version")

    if isinstance(time_info, dict):
        result["trigger_time"] = parse_iso_datetime(time_info.get("trigger_time"))
        result["start_time"] = parse_iso_datetime(time_info.get("start_time"))
        result["end_time"] = parse_iso_datetime(time_info.get("end_time"))
        result["time_zone"] = time_info.get("time_zone")
        if time_info.get("enable_dst") is not None:
            result["dst_enable"] = int(bool(time_info.get("enable_dst")))
        if time_info.get("dst_status") is not None:
            result["dst_status"] = int(bool(time_info.get("dst_status")))

    for key in JSON_SECTION_KEYS:
        if key in parsed and parsed[key] is not None:
            result[key] = parsed[key]

    return result


def parse_message(topic: str, payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8", errors="replace").strip()
    result: dict[str, Any] = {
        "topic": topic,
        "raw_message": text,
        "device_name": None,
        "device_sn": None,
        "device_mac": None,
        "wlan_mac": None,
        "ip_address": None,
        "custom_device_id": None,
        "custom_site_id": None,
        "running_time_sec": None,
        "firmware_version": None,
        "hardware_version": None,
        "trigger_time": None,
        "start_time": None,
        "end_time": None,
        "time_zone": None,
        "dst_enable": None,
        "dst_status": None,
        "imei": None,
        "battery_pct": None,
        "temperature_c": None,
        "distance_mm": None,
        "position_status": None,
        "signal_asu": None,
        "frame_counter": None,
        "payload_hex": None,
        "payload_json": None,
    }
    for key in JSON_SECTION_KEYS:
        result[key] = None

    parts = topic.split("/")
    if len(parts) >= 3 and parts[0] == "em":
        result["device_sn"] = parts[1]

    parsed_json: dict[str, Any] | None = None
    if text.startswith("{"):
        try:
            parsed_json = json.loads(text)
            result["payload_json"] = parsed_json
        except json.JSONDecodeError:
            parsed_json = None

    if parsed_json:
        structured = flatten_milesight_json(parsed_json)
        for key, value in structured.items():
            if value is not None:
                result[key] = value

        for src, dst in (
            ("sn", "device_sn"),
            ("device_sn", "device_sn"),
            ("imei", "imei"),
            ("battery", "battery_pct"),
            ("temperature", "temperature_c"),
            ("distance", "distance_mm"),
            ("position", "position_status"),
            ("signal", "signal_asu"),
            ("frame_counter", "frame_counter"),
        ):
            if parsed_json.get(src) is not None and result.get(dst) is None:
                result[dst] = parsed_json[src]

    hex_payload = extract_hex_payload(parsed_json or text)
    result["payload_hex"] = hex_payload or None

    decoded = decode_nb_frame(hex_payload) if hex_payload else {}
    if not decoded and hex_payload:
        decoded = decode_channel_payload(hex_payload)

    mapping = {
        "device_sn": "device_sn",
        "imei": "imei",
        "battery": "battery_pct",
        "temperature": "temperature_c",
        "distance": "distance_mm",
        "position": "position_status",
        "signal_asu": "signal_asu",
        "frame_counter": "frame_counter",
    }
    for src, dst in mapping.items():
        if decoded.get(src) is not None:
            result[dst] = decoded[src]

    if result["payload_json"] is None and decoded:
        result["payload_json"] = decoded

    return result
