#!/usr/bin/env python3
"""Subscribe TOF + LoRaWAN gateway (UG65/UG56) MQTT topics and persist to MariaDB."""

from __future__ import annotations

import json
import signal
import sys
import time

import paho.mqtt.client as mqtt

from app.config import load_settings
from app.db import Database
from app.decoder import parse_message
from app.ug65_decoder import is_lorawan_gateway_topic, parse_ug65_message

running = True


def stop_handler(signum, frame):
    global running
    running = False
    print(f"\nReceived signal {signum}, shutting down...")


def on_connect(client, userdata, flags, reason_code, properties=None):
    settings = userdata["settings"]
    if reason_code == 0:
        print(f"Connected to MQTT broker {settings.mqtt_host}:{settings.mqtt_port}")
        client.subscribe(settings.mqtt_topic, qos=settings.mqtt_qos)
        print(f"Subscribed TOF: {settings.mqtt_topic} (QoS {settings.mqtt_qos})")
        client.subscribe(settings.mqtt_ug65_topic, qos=settings.mqtt_ug65_qos)
        print(f"Subscribed UG65: {settings.mqtt_ug65_topic} (QoS {settings.mqtt_ug65_qos})")
        client.subscribe(settings.mqtt_ug56_topic, qos=settings.mqtt_ug56_qos)
        print(f"Subscribed UG56: {settings.mqtt_ug56_topic} (QoS {settings.mqtt_ug56_qos})")
    else:
        print(f"MQTT connect failed: {reason_code}")


def on_message(client, userdata, msg):
    db: Database = userdata["db"]
    try:
        if is_lorawan_gateway_topic(msg.topic):
            record = parse_ug65_message(msg.topic, msg.payload)
            record["qos"] = msg.qos
            row_id = db.insert_ug65(record)
            summary = {
                "table": "ug65",
                "gateway_model": record.get("gateway_model"),
                "id": row_id,
                "topic": record.get("topic"),
                "dev_eui": record.get("dev_eui"),
                "f_port": record.get("f_port"),
                "rssi": record.get("rssi"),
                "uplink_time": str(record.get("uplink_time")) if record.get("uplink_time") else None,
            }
        else:
            record = parse_message(msg.topic, msg.payload)
            record["qos"] = msg.qos
            row_id = db.insert_tof(record)
            summary = {
                "table": "tof",
                "id": row_id,
                "topic": record.get("topic"),
                "sn": record.get("device_sn"),
                "name": record.get("device_name"),
                "start_time": str(record.get("start_time")) if record.get("start_time") else None,
                "end_time": str(record.get("end_time")) if record.get("end_time") else None,
            }
        print(f"[saved] {json.dumps(summary, ensure_ascii=False)}")
    except Exception as exc:
        print(f"[error] topic={msg.topic} err={exc}", file=sys.stderr)


def main():
    global running
    settings = load_settings()
    db = Database(settings)

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.mqtt_client_id,
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    client.user_data_set({"settings": settings, "db": db})
    client.on_connect = on_connect
    client.on_message = on_message

    if settings.mqtt_tls:
        client.tls_set()

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    print("Starting Milesight MQTT subscriber (tof + ug65/ug56)...")
    print(f"Broker: {settings.mqtt_host}:{settings.mqtt_port}")
    print(f"MariaDB: {settings.db_host}:{settings.db_port}/{settings.db_name}")

    while running:
        try:
            client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
            client.loop_start()
            while running:
                time.sleep(0.5)
            client.loop_stop()
            client.disconnect()
            break
        except Exception as exc:
            print(f"Connection error: {exc}; retry in 5s", file=sys.stderr)
            time.sleep(5)

    print("Subscriber stopped.")


if __name__ == "__main__":
    main()
