import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    mqtt_client_id: str
    mqtt_topic: str
    mqtt_qos: int
    mqtt_ug65_topic: str
    mqtt_ug65_qos: int
    mqtt_ug56_topic: str
    mqtt_ug56_qos: int
    mqtt_tls: bool
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    # WingOnIOT 环境监测库（默认同一 MySQL 实例，仅库名不同）
    wingon_db_host: str
    wingon_db_port: int
    wingon_db_user: str
    wingon_db_password: str
    wingon_db_name: str
    # JWT 认证
    jwt_secret: str
    jwt_algorithm: str
    jwt_expire_minutes: int


def load_settings() -> Settings:
    return Settings(
        mqtt_host=os.getenv("MQTT_HOST", "127.0.0.1"),
        mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
        mqtt_username=os.getenv("MQTT_USERNAME", "root"),
        mqtt_password=os.getenv("MQTT_PASSWORD", "root"),
        mqtt_client_id=os.getenv("MQTT_CLIENT_ID", "milesight-mqtt-api-sub"),
        mqtt_topic=os.getenv("MQTT_TOPIC", "em/+/status"),
        mqtt_qos=int(os.getenv("MQTT_QOS", "1")),
        mqtt_ug65_topic=os.getenv("MQTT_UG65_TOPIC", "milesight/ug65/uplink/+"),
        mqtt_ug65_qos=int(os.getenv("MQTT_UG65_QOS", "1")),
        mqtt_ug56_topic=os.getenv("MQTT_UG56_TOPIC", "milesight/ug56/uplink/+"),
        mqtt_ug56_qos=int(os.getenv("MQTT_UG56_QOS", "1")),
        mqtt_tls=_bool(os.getenv("MQTT_TLS"), False),
        db_host=os.getenv("DB_HOST", "127.0.0.1"),
        db_port=int(os.getenv("DB_PORT", "3306")),
        db_user=os.getenv("DB_USER", "root"),
        db_password=os.getenv("DB_PASSWORD", "root"),
        db_name=os.getenv("DB_NAME", "milesight"),
        # WingOnIOT 库默认复用同一实例的账号，仅库名不同，可单独覆盖
        wingon_db_host=os.getenv("WINGON_DB_HOST", "127.0.0.1"),
        wingon_db_port=int(os.getenv("WINGON_DB_PORT", "3306")),
        wingon_db_user=os.getenv("WINGON_DB_USER", "root"),
        wingon_db_password=os.getenv("WINGON_DB_PASSWORD", "root"),
        wingon_db_name=os.getenv("WINGON_DB_NAME", "WingOnIOT"),
        jwt_secret=os.getenv("JWT_SECRET", "wingon-iot-dev-secret-change-me"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        jwt_expire_minutes=int(os.getenv("JWT_EXPIRE_MINUTES", "720")),
    )
