CREATE TABLE IF NOT EXISTS ug65 (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  received_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  topic VARCHAR(255) NOT NULL,
  qos TINYINT UNSIGNED NULL,

  application_id INT UNSIGNED NULL,
  application_name VARCHAR(128) NULL,
  device_name VARCHAR(64) NULL,
  dev_eui VARCHAR(32) NULL,
  uplink_time DATETIME(3) NULL,

  f_cnt INT UNSIGNED NULL,
  f_port TINYINT UNSIGNED NULL,
  payload_base64 TEXT NULL,
  payload_hex TEXT NULL,

  gateway_mac VARCHAR(32) NULL,
  gateway_name VARCHAR(128) NULL,
  gateway_model VARCHAR(16) NULL,
  rssi SMALLINT NULL,
  lora_snr DECIMAL(5, 1) NULL,
  frequency_hz INT UNSIGNED NULL,
  spread_factor TINYINT UNSIGNED NULL,
  bandwidth_khz SMALLINT UNSIGNED NULL,

  rx_info_json JSON NULL,
  tx_info_json JSON NULL,
  payload_json JSON NULL,
  raw_message MEDIUMTEXT NULL,

  PRIMARY KEY (id),
  KEY idx_received_at (received_at),
  KEY idx_dev_eui (dev_eui),
  KEY idx_gateway_model (gateway_model),
  KEY idx_uplink_time (uplink_time),
  KEY idx_f_port (f_port)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
