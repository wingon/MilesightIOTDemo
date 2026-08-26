-- ============================================================================
-- WingOnIOT 隐藏风险修复迁移（一次性，非幂等，执行前请备份）
--   1. environmental_monitoring 改复合主键并启用按月 RANGE 分区
--   2. room_cell  加 is_deleted 软删字段 + 改唯一索引（R1/R2/R4/R5）
--   3. device_cell 收敛为"一设备一格"（R7）：唯一索引 UNIQUE(sn)
--   4. building_cell 加 active_key 生成列 + 唯一索引（R2 加严：同坐标至多一个 active 行）
--   触发器（一格一房 R3）见 migrate_wingon_trigger.sql
--   表名还原见 migrate_wingon_revert.sql
-- ============================================================================

-- 1a. Environmental_Monitoring：复合主键（分区键必须包含在唯一索引中）
ALTER TABLE `Environmental_Monitoring`
  DROP PRIMARY KEY,
  ADD PRIMARY KEY (`id`, `toDateTime`);

-- 1b. Environmental_Monitoring：按月 RANGE 分区
ALTER TABLE `Environmental_Monitoring`
  PARTITION BY RANGE (TO_DAYS(`toDateTime`)) (
    PARTITION p202603 VALUES LESS THAN (TO_DAYS('2026-04-01')),
    PARTITION p202604 VALUES LESS THAN (TO_DAYS('2026-05-01')),
    PARTITION p202605 VALUES LESS THAN (TO_DAYS('2026-06-01')),
    PARTITION p202606 VALUES LESS THAN (TO_DAYS('2026-07-01')),
    PARTITION p202607 VALUES LESS THAN (TO_DAYS('2026-08-01')),
    PARTITION p202608 VALUES LESS THAN (TO_DAYS('2026-09-01')),
    PARTITION pmax VALUES LESS THAN MAXVALUE
  );

-- 3. room_cell：加软删字段，唯一索引含 is_deleted（软删后可重建）
ALTER TABLE `room_cell`
  ADD COLUMN `is_deleted` tinyint(4) NOT NULL DEFAULT 0 COMMENT '邏輯刪除：0=正常，1=已刪除' AFTER `cell_id`,
  DROP INDEX `uk_room_cell`,
  ADD UNIQUE KEY `uk_room_cell` (`room_ref_id`, `floor_id`, `cell_id`, `is_deleted`),
  ADD KEY `idx_cell_active` (`cell_id`, `floor_id`, `is_deleted`);

-- 4. device_cell：一设备一格
ALTER TABLE `device_cell`
  DROP INDEX `uk_device_cell`,
  ADD UNIQUE KEY `uk_device_sn` (`sn`);

-- 5. building_cell：同坐标至多一个 active 行（生成列唯一索引，NULL 不参与唯一）
ALTER TABLE `building_cell`
  ADD COLUMN `active_key` varchar(80) GENERATED ALWAYS AS (
    IF(`is_deleted` = 0, CONCAT(`floor_id`, '#', `row_no`, '#', `col_no`), NULL)
  ) STORED AFTER `is_deleted`,
  ADD UNIQUE KEY `uk_cell_active` (`active_key`);
