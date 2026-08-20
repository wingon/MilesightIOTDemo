USE WingOnIOT;

-- ============================================================================
-- 3D 樓棟結構種子 + 遷移腳本
--   表：building / floor / building_cell / room / room_cell
--
-- 用途：把 3D 樓棟結構數據從「前端硬編碼 buildingDemo.ts」遷移到 DB 驅動，
--       並把舊的 building_cell_shape_old2 形狀配置遷移到 building_cell 表。
--
-- 冪等：可重複執行（先清空 5 張結構表再重灌，舊配置從 *_old2 遷移）。
-- 注意：本腳本會清空 building / floor / building_cell / room / room_cell 現有數據。
--
-- floor.level（真實樓層號）→ 前端 3D 層號映射：
--   -2=B2/F→1, -1=B1/F→2, 1=G/F→3, 2=1/F→4 ... 8=7/F→10, 9=ROOF→11
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 0. 擴展 floor.level 約束，允許 -2..9（含 6/F=7、7/F=8、ROOF=9）
-- ----------------------------------------------------------------------------
SET @has_level_chk = (
    SELECT COUNT(*) FROM information_schema.CHECK_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'floor'
      AND CONSTRAINT_NAME = 'chk_level_valid'
);
SET @sql = IF(@has_level_chk > 0,
    'ALTER TABLE floor DROP CONSTRAINT chk_level_valid',
    'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

ALTER TABLE floor ADD CONSTRAINT chk_level_valid
    CHECK (level IN (-2,-1,1,2,3,4,5,6,7,8,9));

-- ----------------------------------------------------------------------------
-- 1. 清空結構表（重灌，保證冪等；按外鍵依賴順序刪除）
-- ----------------------------------------------------------------------------
SET FOREIGN_KEY_CHECKS = 0;
DELETE FROM room_cell;
DELETE FROM room;
DELETE FROM building_cell;
DELETE FROM floor;
DELETE FROM building;
SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------------------------------------------------------
-- 2. 樓棟 building（1 棟）
-- ----------------------------------------------------------------------------
INSERT INTO building (name, code, address, description, is_deleted)
VALUES ('WingOn 大樓', 'WINGON', NULL, NULL, 0);

-- ----------------------------------------------------------------------------
-- 3. 樓層 floor（11 層）
-- ----------------------------------------------------------------------------
INSERT INTO floor (building_id, row_amount, column_amount, level, floor_name, is_deleted)
SELECT b.id, 8, 12, f.level, f.floor_name, 0
FROM building b
CROSS JOIN (
    SELECT -2 AS level, 'B2/F' AS floor_name
    UNION ALL SELECT -1, 'B1/F'
    UNION ALL SELECT  1, 'G/F'
    UNION ALL SELECT  2, '1/F'
    UNION ALL SELECT  3, '2/F'
    UNION ALL SELECT  4, '3/F'
    UNION ALL SELECT  5, '4/F'
    UNION ALL SELECT  6, '5/F'
    UNION ALL SELECT  7, '6/F'
    UNION ALL SELECT  8, '7/F'
    UNION ALL SELECT  9, 'ROOF'
) f
WHERE b.is_deleted = 0;

-- ----------------------------------------------------------------------------
-- 4. 格子 building_cell（每層 8×12 網格，排除外牆切角 7 格 = 89 格/層）
--    切角排除：(8,1)(7,1)（左下）與 (8,12)(8,11)(7,12)(7,11)(6,12)（右下）
-- ----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS seed_building_cells;
DELIMITER $$
CREATE PROCEDURE seed_building_cells()
BEGIN
    DECLARE v_building_id BIGINT UNSIGNED;
    DECLARE v_floor_id BIGINT UNSIGNED;
    DECLARE v_level SMALLINT;
    DECLARE v_level_3d SMALLINT;
    DECLARE v_z DECIMAL(10,3);
    DECLARE v_done INT DEFAULT 0;
    DECLARE cur CURSOR FOR SELECT id, level FROM floor WHERE is_deleted = 0 ORDER BY level;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

    SELECT id INTO v_building_id FROM building WHERE is_deleted = 0 ORDER BY id LIMIT 1;

    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO v_floor_id, v_level;
        IF v_done THEN LEAVE read_loop; END IF;

        -- floor.level -> 3D 層號（與後端 floor_level_to_3d 一致）：-2..9 -> 1..11
        SET v_level_3d = CASE
            WHEN v_level < 0 THEN v_level + 3
            WHEN v_level = 9 THEN 11
            ELSE v_level + 2
        END;
        -- z = 垂直高度（世界 y）：樓層堆疊 (level_3d-1)*0.84 + FLOOR_H/2(0.38)
        SET v_z = ROUND((v_level_3d - 1) * 0.84 + 0.38, 3);

        INSERT INTO building_cell
            (building_id, floor_id, row_no, col_no, x, y, z, length, width,
             cell_height, rotation_xyz, is_active, shape, color, render_height, is_deleted)
        SELECT v_building_id, v_floor_id, r.n, c.n,
               ROUND((c.n - 6.5) * 1.15, 3) AS x,
               ROUND((r.n - 4.5) * 1.15, 3) AS y,
               v_z AS z,
               1.150 AS length, 1.150 AS width,
               0.000 AS cell_height, NULL AS rotation_xyz,
               1 AS is_active, 'Rect' AS shape, NULL AS color, NULL AS render_height, 0 AS is_deleted
        FROM (SELECT 1 n UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
              UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8) r
        CROSS JOIN (SELECT 1 n UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
                    UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8
                    UNION ALL SELECT 9 UNION ALL SELECT 10 UNION ALL SELECT 11 UNION ALL SELECT 12) c
        WHERE NOT (
            (r.n = 8 AND c.n = 1) OR (r.n = 7 AND c.n = 1) OR
            (r.n = 8 AND c.n = 12) OR (r.n = 8 AND c.n = 11) OR
            (r.n = 7 AND c.n = 12) OR (r.n = 7 AND c.n = 11) OR
            (r.n = 6 AND c.n = 12)
        );
    END LOOP;
    CLOSE cur;
END$$
DELIMITER ;

CALL seed_building_cells();
DROP PROCEDURE IF EXISTS seed_building_cells;

-- ----------------------------------------------------------------------------
-- 5. 遷移舊形狀配置 building_cell_shape_old2 → building_cell
--    舊 floors 為 3D 層號陣列，映射到 floor.level：
--      3D 1→-2, 2→-1, 3→1, 4→2, 5→3, 6→4, 7→5
-- ----------------------------------------------------------------------------
-- (1,1) 所有樓層 → 顏色 #4CAF50（綠色）
UPDATE building_cell SET color = '#4CAF50' WHERE row_no = 1 AND col_no = 1 AND is_deleted = 0;

-- (2,3) 3D 層 1（B2/F = level -2）→ Rect + 旋轉 0,0.785,0 + 顏色 #FF9800 + 高度 1.5
UPDATE building_cell c
JOIN floor f ON f.id = c.floor_id
SET c.shape = 'Rect', c.rotation_xyz = '0,0.785,0', c.color = '#FF9800', c.render_height = 1.5
WHERE c.row_no = 2 AND c.col_no = 3 AND f.level = -2 AND c.is_deleted = 0;

-- (7,11)(7,12)(8,11) 為外牆切角格子（building_cell 不存在），遷移無效，跳過。

-- ----------------------------------------------------------------------------
-- 6. 形狀演示種子（驗證形狀/切割/隱藏驅動，便於測試）
-- ----------------------------------------------------------------------------
-- (3,2) 所有樓層 → Triangle（三角形切割）
UPDATE building_cell SET shape = 'Triangle' WHERE row_no = 3 AND col_no = 2 AND is_deleted = 0;

-- (5,4) G/F(level 1) ~ 4/F(level 5) → Hidden（隱藏不渲染，驗證 is_active）
UPDATE building_cell c
JOIN floor f ON f.id = c.floor_id
SET c.is_active = 0
WHERE c.row_no = 5 AND c.col_no = 4 AND f.level IN (1,2,3,4,5) AND c.is_deleted = 0;

-- ----------------------------------------------------------------------------
-- 7. 房間 room（每層 11 間，room_number 1..11 對應前端 FLOOR_ROOMS 的 index）
-- ----------------------------------------------------------------------------
INSERT INTO room (room_id, building_id, floor_id, room_number, room_type, area, is_deleted)
SELECT CONCAT('room-', f.id, '-', n.num), f.building_id, f.id, CAST(n.num AS CHAR), NULL, NULL, 0
FROM floor f
CROSS JOIN (
    SELECT 1 num UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4
    UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8
    UNION ALL SELECT 9 UNION ALL SELECT 10 UNION ALL SELECT 11
) n
WHERE f.is_deleted = 0;

-- ----------------------------------------------------------------------------
-- 8. 房間-格子關係 room_cell（JOIN building_cell 自動過濾切角格子）
-- ----------------------------------------------------------------------------
INSERT INTO room_cell (room_ref_id, floor_id, cell_id)
SELECT r.id, r.floor_id, c.id
FROM room r
JOIN building_cell c ON c.floor_id = r.floor_id AND c.is_deleted = 0
JOIN (
    SELECT 1 room_no, 1 row_no, 1 col_no
    UNION ALL SELECT 1,1,2 UNION ALL SELECT 1,2,1 UNION ALL SELECT 1,2,2
    UNION ALL SELECT 1,3,1 UNION ALL SELECT 1,3,2
    UNION ALL SELECT 2,2,3 UNION ALL SELECT 2,2,4 UNION ALL SELECT 2,3,3
    UNION ALL SELECT 2,3,4 UNION ALL SELECT 2,3,5
    UNION ALL SELECT 3,2,5 UNION ALL SELECT 3,2,6
    UNION ALL SELECT 4,2,7 UNION ALL SELECT 4,2,8
    UNION ALL SELECT 5,3,6 UNION ALL SELECT 5,3,7 UNION ALL SELECT 5,3,8
    UNION ALL SELECT 6,2,9 UNION ALL SELECT 6,2,10 UNION ALL SELECT 6,2,11
    UNION ALL SELECT 6,3,10 UNION ALL SELECT 6,3,11 UNION ALL SELECT 6,3,12
    UNION ALL SELECT 7,4,5 UNION ALL SELECT 7,4,6 UNION ALL SELECT 7,5,5
    UNION ALL SELECT 7,5,6 UNION ALL SELECT 7,6,5 UNION ALL SELECT 7,6,6
    UNION ALL SELECT 8,4,9 UNION ALL SELECT 8,4,10 UNION ALL SELECT 8,5,9
    UNION ALL SELECT 8,5,10 UNION ALL SELECT 8,6,9 UNION ALL SELECT 8,6,10
    UNION ALL SELECT 9,7,5 UNION ALL SELECT 9,7,6 UNION ALL SELECT 9,8,5
    UNION ALL SELECT 9,8,6
    UNION ALL SELECT 10,7,8 UNION ALL SELECT 10,7,9 UNION ALL SELECT 10,8,8
    UNION ALL SELECT 10,8,9
    UNION ALL SELECT 11,7,10 UNION ALL SELECT 11,7,11 UNION ALL SELECT 11,7,12
    UNION ALL SELECT 11,8,10 UNION ALL SELECT 11,8,11 UNION ALL SELECT 11,8,12
) def ON def.row_no = c.row_no AND def.col_no = c.col_no
     AND def.room_no = CAST(r.room_number AS UNSIGNED)
WHERE r.is_deleted = 0;
