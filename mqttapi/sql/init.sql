CREATE DATABASE IF NOT EXISTS milesight
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE milesight;

CREATE TABLE IF NOT EXISTS tof (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  received_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  topic VARCHAR(255) NOT NULL,
  qos TINYINT UNSIGNED NULL,

  -- device_info (Device Info)
  device_name VARCHAR(128) NULL,
  device_sn VARCHAR(32) NULL,
  device_mac VARCHAR(32) NULL,
  wlan_mac VARCHAR(32) NULL,
  ip_address VARCHAR(45) NULL,
  custom_device_id VARCHAR(64) NULL,
  custom_site_id VARCHAR(64) NULL,
  running_time_sec INT UNSIGNED NULL,
  firmware_version VARCHAR(64) NULL,
  hardware_version VARCHAR(64) NULL,

  -- time_info (Time Info)
  trigger_time DATETIME(3) NULL,
  start_time DATETIME(3) NULL,
  end_time DATETIME(3) NULL,
  time_zone VARCHAR(255) NULL,
  dst_enable TINYINT(1) NULL,
  dst_status TINYINT(1) NULL,

  -- legacy flat / binary TOF fields (EM400 distance sensor)
  imei VARCHAR(20) NULL,
  battery_pct TINYINT UNSIGNED NULL,
  temperature_c DECIMAL(7, 2) NULL,
  distance_mm INT NULL,
  position_status VARCHAR(32) NULL,
  signal_asu TINYINT UNSIGNED NULL,
  frame_counter INT UNSIGNED NULL,

  -- array sections (custom uplink content)
  line_trigger_data JSON NULL,
  region_trigger_data JSON NULL,
  region_count_data JSON NULL,
  dwell_time_data JSON NULL,
  dwell_start_time JSON NULL,
  line_periodic_data JSON NULL,
  line_total_data JSON NULL,
  line_count_data JSON NULL,
  region_periodic_data JSON NULL,
  alarm_data JSON NULL,

  payload_hex TEXT NULL,
  payload_json JSON NULL,
  raw_message MEDIUMTEXT NULL,

  PRIMARY KEY (id),
  KEY idx_received_at (received_at),
  KEY idx_device_sn (device_sn),
  KEY idx_start_time (start_time),
  KEY idx_distance_mm (distance_mm)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ug65 table: see init_ug65.sql
