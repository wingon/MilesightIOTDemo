"""Parse Milesight UG65 LoRaWAN gateway MQTT uplink JSON."""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from .decoder import parse_iso_datetime


def _first_rx_info(parsed: dict[str, Any]) -> dict[str, Any]:
    rx_info = parsed.get("rxInfo") or parsed.get("rxinfo") or []
    if isinstance(rx_info, list) and rx_info:
        first = rx_info[0]
        return first if isinstance(first, dict) else {}
    return {}


def _tx_info(parsed: dict[str, Any]) -> dict[str, Any]:
    tx_info = parsed.get("txInfo") or parsed.get("txinfo") or {}
    return tx_info if isinstance(tx_info, dict) else {}


def _dev_eui_from_topic(topic: str) -> str | None:
    parts = topic.strip("/").split("/")
    if len(parts) >= 4 and parts[0] == "milesight" and parts[1] == "ug65" and parts[2] == "uplink":
        eui = parts[3].strip()
        return eui.upper() if eui else None
    return None


def parse_ug65_message(topic: str, payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8", errors="replace").strip()
    result: dict[str, Any] = {
        "topic": topic,
        "raw_message": text,
        "application_id": None,
        "application_name": None,
        "device_name": None,
        "dev_eui": None,
        "uplink_time": None,
        "f_cnt": None,
        "f_port": None,
        "payload_base64": None,
        "payload_hex": None,
        "gateway_mac": None,
        "gateway_name": None,
        "rssi": None,
        "lora_snr": None,
        "frequency_hz": None,
        "spread_factor": None,
        "bandwidth_khz": None,
        "rx_info_json": None,
        "tx_info_json": None,
        "payload_json": None,
    }

    if not text.startswith("{"):
        return result

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return result

    if not isinstance(parsed, dict):
        return result

    result["payload_json"] = parsed
    result["application_id"] = parsed.get("applicationID") or parsed.get("applicationId")
    result["application_name"] = parsed.get("applicationName")
    result["device_name"] = parsed.get("deviceName")
    result["dev_eui"] = parsed.get("devEUI") or parsed.get("devEui")
    result["uplink_time"] = parse_iso_datetime(parsed.get("time"))
    result["f_cnt"] = parsed.get("fCnt") or parsed.get("fcnt")
    result["f_port"] = parsed.get("fPort") or parsed.get("fport")

    data_b64 = parsed.get("data")
    if isinstance(data_b64, str) and data_b64.strip():
        result["payload_base64"] = data_b64.strip()
        try:
            result["payload_hex"] = base64.b64decode(data_b64).hex()
        except (binascii.Error, ValueError):
            pass

    rx0 = _first_rx_info(parsed)
    if rx0:
        result["gateway_mac"] = rx0.get("mac")
        result["gateway_name"] = rx0.get("name")
        result["rssi"] = rx0.get("rssi")
        snr = rx0.get("loRaSNR") if rx0.get("loRaSNR") is not None else rx0.get("loraSNR")
        result["lora_snr"] = snr
        result["rx_info_json"] = parsed.get("rxInfo") or parsed.get("rxinfo")

    tx = _tx_info(parsed)
    if tx:
        result["frequency_hz"] = tx.get("frequency")
        data_rate = tx.get("dataRate") or tx.get("datarate") or {}
        if isinstance(data_rate, dict):
            result["spread_factor"] = data_rate.get("spreadFactor") or data_rate.get("sf")
            bw = data_rate.get("bandwidth")
            if bw is not None:
                result["bandwidth_khz"] = int(bw)
        result["tx_info_json"] = tx

    if not result["dev_eui"]:
        result["dev_eui"] = _dev_eui_from_topic(topic)

    return result
