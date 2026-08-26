USE WingOnIOT;

-- ============================================================================
-- 删除隐藏格子（is_active=0）的迁移脚本
-- 
-- 处理逻辑：
-- 1. 删除与隐藏格子相关的 room_cell 记录（软删除）
-- 2. 删除与隐藏格子相关的 device_cell 记录（物理删除）
-- 3. 软删除隐藏格子（设置 is_deleted=1）
-- ============================================================================

-- 0. 统计要处理的隐藏格子数量
SELECT '隐藏格子统计' AS info, COUNT(*) AS hidden_cell_count
FROM building_cell 
WHERE is_active = 0 AND is_deleted = 0;

-- 1. 备份要删除的 room_cell 记录（用于审计）
CREATE TEMPORARY TABLE IF NOT EXISTS tmp_deleted_room_cell AS
SELECT rc.id, rc.room_ref_id, rc.floor_id, rc.cell_id, r.room_id,
       c.row_no, c.col_no, f.level, f.floor_name
FROM room_cell rc
JOIN room r ON r.id = rc.room_ref_id
JOIN building_cell c ON c.id = rc.cell_id
JOIN floor f ON f.id = rc.floor_id
WHERE rc.cell_id IN (
    SELECT id FROM building_cell 
    WHERE is_active = 0 AND is_deleted = 0
) AND rc.is_deleted = 0;

-- 显示要删除的 room_cell 记录
SELECT '要删除的 room_cell 记录' AS info, COUNT(*) AS record_count
FROM tmp_deleted_room_cell;

-- 2. 软删除与隐藏格子相关的 room_cell 记录
UPDATE room_cell 
SET is_deleted = 1 
WHERE cell_id IN (
    SELECT id FROM building_cell 
    WHERE is_active = 0 AND is_deleted = 0
) AND is_deleted = 0;

-- 3. 物理删除与隐藏格子相关的 device_cell 记录
-- 先显示要删除的 device_cell 记录
SELECT '要删除的 device_cell 记录' AS info, dc.sn, dc.cell_id, dc.floor_id,
       c.row_no, c.col_no, f.level, f.floor_name
FROM device_cell dc
JOIN building_cell c ON c.id = dc.cell_id
JOIN floor f ON f.id = dc.floor_id
WHERE dc.cell_id IN (
    SELECT id FROM building_cell 
    WHERE is_active = 0 AND is_deleted = 0
);

-- 执行删除
DELETE FROM device_cell 
WHERE cell_id IN (
    SELECT id FROM building_cell 
    WHERE is_active = 0 AND is_deleted = 0
);

-- 4. 软删除隐藏格子
UPDATE building_cell 
SET is_deleted = 1 
WHERE is_active = 0 AND is_deleted = 0;

-- 5. 清理临时表
DROP TEMPORARY TABLE IF EXISTS tmp_deleted_room_cell;

-- 6. 验证结果
SELECT '删除后统计' AS info, 
       (SELECT COUNT(*) FROM building_cell WHERE is_active = 0 AND is_deleted = 0) AS remaining_hidden_cells,
       (SELECT COUNT(*) FROM building_cell WHERE is_deleted = 0) AS active_cells;

-- 7. 显示剩余的隐藏格子（应该为0）
SELECT '剩余隐藏格子详情' AS info, c.id, c.floor_id, c.row_no, c.col_no, c.is_active, c.is_deleted,
       f.level, f.floor_name
FROM building_cell c
JOIN floor f ON f.id = c.floor_id
WHERE c.is_active = 0 AND c.is_deleted = 0;