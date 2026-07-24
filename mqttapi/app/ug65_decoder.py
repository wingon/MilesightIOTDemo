"""Parse Milesight LoRaWAN gateway MQTT uplink JSON (UG65 / UG56)."""

from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import timezone
from typing import Any

from .decoder import decode_am319_payload, parse_iso_datetime

# Topic: milesight/{ug65|ug56}/uplink/<devEUI>
_GATEWAY_TOPIC_RE = re.compile(
    r"^milesight/(?P<model>ug65|ug56)/uplink(?:/(?P<eui>[^/]+))?$",
    re.IGNORECASE,
)


def is_lorawan_gateway_topic(topic: str) -> bool:
    return _GATEWAY_TOPIC_RE.match(topic.strip()) is not None


def gateway_model_from_topic(topic: str) -> str | None:
    match = _GATEWAY_TOPIC_RE.match(topic.strip())
    if not match:
        return None
    return match.group("model").lower()


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
    match = _GATEWAY_TOPIC_RE.match(topic.strip())
    if not match:
        return None
    eui = (match.group("eui") or "").strip()
    return eui.upper() if eui else None


def parse_ug65_message(topic: str, payload: bytes) -> dict[str, Any]:
    """Parse UG65/UG56 uplink; kept name for call-site compatibility."""
    text = payload.decode("utf-8", errors="replace").strip()
    result: dict[str, Any] = {
        "topic": topic,
        "raw_message": text,
        "gateway_model": gateway_model_from_topic(topic),
        "application_id": None,
        "application_name": None,
        "device_name": None,
        "dev_eui": _dev_eui_from_topic(topic),
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
    result["dev_eui"] = (
        parsed.get("devEUI") or parsed.get("devEui") or result["dev_eui"]
    )
    result["uplink_time"] = parse_iso_datetime(
        parsed.get("gatewayTime") or parsed.get("time")
    )
    if result["uplink_time"] is not None and result["uplink_time"].tzinfo is not None:
        result["uplink_time"] = result["uplink_time"].astimezone(timezone.utc).replace(
            tzinfo=None
        )
    result["f_cnt"] = parsed.get("fCnt") or parsed.get("fcnt")
    result["f_port"] = parsed.get("fPort") or parsed.get("fport")

    data_b64 = parsed.get("data")
    if isinstance(data_b64, str) and data_b64.strip():
        result["payload_base64"] = data_b64.strip()
        try:
            result["payload_hex"] = base64.b64decode(data_b64).hex()
        except (binascii.Error, ValueError):
            pass

    # ChirpStack-style uplink: sensor values live in base64 "data".
    # Merge decoded AM319 fields into payload_json for the frontend.
    already_decoded = any(
        key in parsed for key in ("temperature", "co2", "humidity", "pm2_5", "current")
    )
    if result.get("payload_hex") and not already_decoded:
        sensor = decode_am319_payload(result["payload_hex"])
        if sensor:
            merged = dict(parsed)
            merged.update(sensor)
            result["payload_json"] = merged

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

    if result["dev_eui"] and isinstance(result["dev_eui"], str):
        result["dev_eui"] = result["dev_eui"].strip().upper() or None

    return result
