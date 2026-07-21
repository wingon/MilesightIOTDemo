#!/usr/bin/env python3
"""Publish a sample Milesight-style TOF MQTT message for local testing."""

import argparse
import json
import time

import paho.mqtt.client as mqtt

from app.config import load_settings


def main():
    parser = argparse.ArgumentParser(description="Publish test TOF MQTT message")
    parser.add_argument("--sn", default="6748d11290120003", help="Device serial number")
    parser.add_argument("--distance", type=int, default=2116, help="Distance in mm")
    parser.add_argument("--temperature", type=float, default=25.7, help="Temperature in C")
    parser.add_argument("--battery", type=int, default=92, help="Battery percent")
    args = parser.parse_args()

    settings = load_settings()
    topic = f"em/{args.sn}/status"
    payload = {
        "sn": args.sn,
        "battery": args.battery,
        "temperature": args.temperature,
        "distance": args.distance,
        "position": "normal",
        "timestamp": int(time.time()),
    }

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"test-publisher-{int(time.time())}",
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
    client.loop_start()
    time.sleep(0.3)

    info = client.publish(topic, json.dumps(payload), qos=settings.mqtt_qos)
    info.wait_for_publish()
    print(f"Published to {topic}: {payload}")
    time.sleep(0.2)
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
