from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends

from app.api.deps import get_db
from app.config import load_settings
from app.db import Database

router = APIRouter(tags=["system"])


@router.get("/health")
def health(db: Database = Depends(get_db)) -> dict[str, Any]:
    ok = db.ping()
    return {
        "status": "ok" if ok else "degraded",
        "database": "up" if ok else "down",
        "service": "milesight-mqtt-api",
    }


@router.post("/api/v1/mqtt/test")
def mqtt_test(payload: dict[str, Any] | None = Body(default=None)) -> dict[str, Any]:
    """Try a short MQTT broker connect (demo connectivity check)."""
    settings = load_settings()
    device_sn = (payload or {}).get("device_sn") or ""
    try:
        import time

        import paho.mqtt.client as mqtt

        result: dict[str, Any] = {"ok": False, "device_sn": device_sn or None}

        def on_connect(client: Any, _userdata: Any, _flags: Any, reason_code: Any, _props: Any = None) -> None:
            rc = int(getattr(reason_code, "value", reason_code))
            result["ok"] = rc == 0
            result["reason_code"] = rc
            client.disconnect()

        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"milesight-mqtt-test-{device_sn or 'probe'}",
            protocol=mqtt.MQTTv311,
        )
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        client.on_connect = on_connect
        if settings.mqtt_tls:
            client.tls_set()
        client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=10)
        client.loop_start()
        for _ in range(20):
            if "reason_code" in result or result["ok"]:
                break
            time.sleep(0.1)
        client.loop_stop()
        try:
            client.disconnect()
        except Exception:
            pass

        result["broker"] = f"{settings.mqtt_host}:{settings.mqtt_port}"
        if "reason_code" not in result and not result["ok"]:
            result["error"] = "connect timeout"
        return result
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "device_sn": device_sn or None,
            "broker": f"{settings.mqtt_host}:{settings.mqtt_port}",
            "error": str(exc),
        }


@router.get("/api/v1/stats")
def stats(db: Database = Depends(get_db)) -> dict[str, Any]:
    return db.get_stats()
