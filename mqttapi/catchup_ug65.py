#!/usr/bin/env python3
"""One-shot: listen for UG65/UG56 MQTT messages and insert into ug65 table."""

import json
import time

import paho.mqtt.client as mqtt

from app.config import load_settings
from app.db import Database
from app.ug65_decoder import parse_ug65_message

settings = load_settings()
db = Database(settings)
count = 0


def on_message(client, userdata, msg):
    global count
    record = parse_ug65_message(msg.topic, msg.payload)
    record["qos"] = msg.qos
    row_id = db.insert_ug65(record)
    count += 1
    print(
        f"[{record.get('gateway_model') or 'gw'}] id={row_id} "
        f"topic={msg.topic} dev_eui={record.get('dev_eui')}"
    )
    print(json.dumps(record.get("payload_json"), ensure_ascii=False))


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="ug65-ug56-catchup-once",
    protocol=mqtt.MQTTv311,
)
client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
client.on_message = on_message
client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=60)
client.subscribe(settings.mqtt_ug65_topic, qos=settings.mqtt_ug65_qos)
client.subscribe(settings.mqtt_ug56_topic, qos=settings.mqtt_ug56_qos)
print(f"Listening {settings.mqtt_ug65_topic} + {settings.mqtt_ug56_topic} for 30s...")
client.loop_start()
time.sleep(30)
client.loop_stop()
client.disconnect()
print(f"Done. Inserted {count} message(s).")
