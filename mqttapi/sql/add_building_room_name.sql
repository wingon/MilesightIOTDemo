-- ============================================================================
-- 房间自定义名称 migration：为 building_room 新增可空列 room_name
--   用途：前端「樓層詳情 - 房間」允许用户自建/删除/命名房间。
--         room_number 仍作为稳定序号（决定颜色/编号/3D 归属），
--         用户可自定义的显示名称存放在 room_name（可空，空则回退「房間 N」）。
--   幂等：可重复执行（先检查列是否存在，不存在才 ADD）。
--   执行：mysql -u<user> -p WingOnIOT < add_building_room_name.sql
-- ============================================================================

USE WingOnIOT;

SET @has_col = (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'building_room'
      AND COLUMN_NAME = 'room_name'
);

SET @sql = IF(@has_col = 0,
    'ALTER TABLE building_room ADD COLUMN room_name VARCHAR(100) NULL DEFAULT NULL COMMENT ''房间名称'' AFTER room_number',
    'SELECT 1');
PREPARE s FROM @sql;
EXECUTE s;
DEALLOCATE PREPARE s;
