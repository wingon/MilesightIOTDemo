-- ============================================================================
-- 設備關聯格子遷移腳本
--   表：device_cell
--
-- 用途：讓 Environment_Device 直接關聯到具體格子（building_cell），
--       使大廳／開放區域的設備也能精確定位（設備掛格子）。
--       與 room_cell 同構：一設備可對多格，一格可對多設備。
--
-- 冪等：可重複執行（IF NOT EXISTS）。
-- 注意：連接到 WingOnIOT 庫執行（與 building_cell / room_cell 同庫）。
-- ============================================================================

CREATE TABLE IF NOT EXISTS `device_cell` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主鍵',
  `sn` varchar(20) NOT NULL COMMENT '設備序列號（Environment_Device.sn）',
  `cell_id` bigint(20) unsigned NOT NULL COMMENT '格子外鍵',
  `floor_id` bigint(20) unsigned NOT NULL COMMENT '樓層外鍵，保證同樓層',
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) COMMENT '創建時間',
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3) COMMENT '最後更新時間',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_device_cell` (`sn`,`cell_id`,`floor_id`),
  KEY `idx_cell_id` (`cell_id`,`floor_id`),
  KEY `idx_floor_id` (`floor_id`),
  CONSTRAINT `fk_dc_cell` FOREIGN KEY (`cell_id`, `floor_id`) REFERENCES `building_cell` (`id`, `floor_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_dc_sn` FOREIGN KEY (`sn`) REFERENCES `Environment_Device` (`sn`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='設備關聯格子表';
