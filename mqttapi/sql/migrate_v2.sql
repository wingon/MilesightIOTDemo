USE milesight;

ALTER TABLE tof
  ADD COLUMN IF NOT EXISTS device_name VARCHAR(128) NULL AFTER qos,
  ADD COLUMN IF NOT EXISTS device_mac VARCHAR(32) NULL AFTER device_sn,
  ADD COLUMN IF NOT EXISTS wlan_mac VARCHAR(32) NULL AFTER device_mac,
  ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45) NULL AFTER wlan_mac,
  ADD COLUMN IF NOT EXISTS custom_device_id VARCHAR(64) NULL AFTER ip_address,
  ADD COLUMN IF NOT EXISTS custom_site_id VARCHAR(64) NULL AFTER custom_device_id,
  ADD COLUMN IF NOT EXISTS running_time_sec INT UNSIGNED NULL AFTER custom_site_id,
  ADD COLUMN IF NOT EXISTS firmware_version VARCHAR(64) NULL AFTER running_time_sec,
  ADD COLUMN IF NOT EXISTS hardware_version VARCHAR(64) NULL AFTER firmware_version,
  ADD COLUMN IF NOT EXISTS trigger_time DATETIME(3) NULL AFTER hardware_version,
  ADD COLUMN IF NOT EXISTS start_time DATETIME(3) NULL AFTER trigger_time,
  ADD COLUMN IF NOT EXISTS end_time DATETIME(3) NULL AFTER start_time,
  ADD COLUMN IF NOT EXISTS time_zone VARCHAR(255) NULL AFTER end_time,
  ADD COLUMN IF NOT EXISTS dst_enable TINYINT(1) NULL AFTER time_zone,
  ADD COLUMN IF NOT EXISTS dst_status TINYINT(1) NULL AFTER dst_enable,
  ADD COLUMN IF NOT EXISTS line_trigger_data JSON NULL AFTER frame_counter,
  ADD COLUMN IF NOT EXISTS region_trigger_data JSON NULL AFTER line_trigger_data,
  ADD COLUMN IF NOT EXISTS region_count_data JSON NULL AFTER region_trigger_data,
  ADD COLUMN IF NOT EXISTS dwell_time_data JSON NULL AFTER region_count_data,
  ADD COLUMN IF NOT EXISTS dwell_start_time JSON NULL AFTER dwell_time_data,
  ADD COLUMN IF NOT EXISTS line_periodic_data JSON NULL AFTER dwell_start_time,
  ADD COLUMN IF NOT EXISTS line_total_data JSON NULL AFTER line_periodic_data,
  ADD COLUMN IF NOT EXISTS line_count_data JSON NULL AFTER line_total_data,
  ADD COLUMN IF NOT EXISTS region_periodic_data JSON NULL AFTER line_count_data,
  ADD COLUMN IF NOT EXISTS alarm_data JSON NULL AFTER region_periodic_data;

CREATE INDEX IF NOT EXISTS idx_start_time ON tof (start_time);
