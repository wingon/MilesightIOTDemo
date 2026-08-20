USE WingOnIOT;

-- ============================================================================
-- 表名小寫化遷移腳本
--
-- 將 3D 樓棟相關的 7 張表由「駝峰/大寫」命名改為全小寫，
-- 與 WingOnIOT_DDL_Data.sql 及後端 SQL（db.py / migrate_building_structure.sql）保持一致：
--
--   Building                 -> building
--   Building_Cell            -> building_cell
--   Building_Cell_Shape_old  -> building_cell_shape_old
--   Building_Cell_Shape_old2 -> building_cell_shape_old2
--   Floor                    -> floor
--   Room                     -> room
--   Room_Cell                -> room_cell
--
-- 冪等：可重複執行；若已為小寫（或表不存在）則自動跳過，不報錯。
-- 注意：在 Linux 上 MySQL/MariaDB 表名區分大小寫，執行新版代碼前須先執行本腳本。
-- 單條 RENAME TABLE 同時重命名所有表，MySQL/MariaDB 會自動同步更新外鍵引用。
-- ============================================================================

-- 偵測：是否存在舊（大寫）表 / 是否已存在新（小寫）表
SET @has_old = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME IN ('Building','Building_Cell','Building_Cell_Shape_old',
                         'Building_Cell_Shape_old2','Floor','Room','Room_Cell')
);
SET @has_new = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME IN ('building','building_cell','building_cell_shape_old',
                         'building_cell_shape_old2','floor','room','room_cell')
);

-- 只有當「存在舊表且不存在新表」時才執行重命名，否則直接跳過（冪等）
SET @sql = IF(@has_old > 0 AND @has_new = 0,
    'RENAME TABLE
       `Building` TO `building`,
       `Building_Cell` TO `building_cell`,
       `Building_Cell_Shape_old` TO `building_cell_shape_old`,
       `Building_Cell_Shape_old2` TO `building_cell_shape_old2`,
       `Floor` TO `floor`,
       `Room` TO `room`,
       `Room_Cell` TO `room_cell`',
    'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- 確認結果：列出當前存在的小寫表
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('building','building_cell','building_cell_shape_old',
                     'building_cell_shape_old2','floor','room','room_cell')
ORDER BY TABLE_NAME;