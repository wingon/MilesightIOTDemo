USE WingOnIOT;

-- 幕墙外观配置表（窗户方向、尺寸、逐格开关）
-- 存储为 JSON，单一配置行，GET/POST 读写

CREATE TABLE IF NOT EXISTS building_facade_config (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  config_json JSON NOT NULL
              COMMENT '幕墙配置：{orientation, widthRatio, heightRatio, cellWindows:{}}',
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
              ON UPDATE CURRENT_TIMESTAMP(3),

  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
