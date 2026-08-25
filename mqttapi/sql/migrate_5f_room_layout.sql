-- ============================================================================
-- 5F 房間佈局更新腳本
-- 根據平面圖重新分配房間-單元格映射
--
-- 房間佈局（8×12 網格）：
--   Row 1-2: 上部功能區（樓梯、機電、電梯、儲物）
--   Row 3-5: 中部主要區域（倉庫、主工作區、辦公區）
--   Row 6-8: 下部設備區域
--
-- 注意：此腳本僅影響 5F（level=6），其他樓層不變
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. 找到 5F 的 floor_id（level=6 對應 3D 層號 8）
-- ----------------------------------------------------------------------------
SET @target_floor_id = (SELECT id FROM floor WHERE level = 6 AND is_deleted = 0 LIMIT 1);

-- ----------------------------------------------------------------------------
-- 2. 清除 5F 現有的 room_cell 映射
-- ----------------------------------------------------------------------------
DELETE FROM room_cell WHERE floor_id = @target_floor_id;

-- ----------------------------------------------------------------------------
-- 3. 重新定義 5F 的房間（11 間，匹配平面圖）
--    room_number 1-11 對應前端 FLOOR_ROOMS 的 index
-- ----------------------------------------------------------------------------

-- Room 1: 樓梯間 A（左上角）
-- 位置：Row 1-2, Col 1-2（4 個單元格）
INSERT INTO room_cell (room_ref_id, floor_id, cell_id)
SELECT r.id, r.floor_id, c.id
FROM room r
JOIN building_cell c ON c.floor_id = r.floor_id AND c.is_deleted = 0
WHERE r.floor_id = @target_floor_id
  AND r.room_number = '1'
  AND r.is_deleted = 0
  AND ((c.row_no = 1 AND c.col_no IN (1, 2))
    OR (c.row_no = 2 AND c.col_no IN (1, 2)));

-- Room 2: 機電房（左上中部）
-- 位置：Row 1-2, Col 3-4（4 個單元格）
INSERT INTO room_cell (room_ref_id, floor_id, cell_id)
SELECT r.id, r.floor_id, c.id
FROM room r
JOIN building_cell c ON c.floor_id = r.floor_id AND c.is_deleted = 0
WHERE r.floor_id = @target_floor_id
  AND r.room_number = '2'
  AND r.is_deleted = 0
  AND ((c.row_no = 1 AND c.col_no IN (3, 4))
    OR (c.row_no = 2 AND c.col_no IN (3, 4)));

-- Room 3: 電梯區 A（中上左）
-- 位置：Row 1-2, Col 5-6（4 個單元格）
INSERT INTO room_cell (room_ref_id, floor_id, cell_id)
SELECT r.id, r.floor_id, c.id
FROM room r
JOIN building_cell c ON c.floor_id = r.floor_id AND c.is_deleted = 0
WHERE r.floor_id = @target_floor_id
  AND r.room_number = '3'
  AND r.is_deleted = 0
  AND ((c.row_no = 1 AND c.col_no IN (5, 6))
    OR (c.row_no = 2 AND c.col_no IN (5, 6)));

-- Room 4: 電梯區 B / 儲物間（中上右）
-- 位置：Row 1-2, Col 7-8（4 個單元格）
INSERT INTO room_cell (room_ref_id, floor_id, cell_id)
SELECT r.id, r.floor_id, c.id
FROM room r
JOIN building_cell c ON c.floor_id = r.floor_id AND c.is_deleted = 0
WHERE r.floor_id = @target_floor_id
  AND r.room_number = '4'
  AND r.is_deleted = 0
  AND ((c.row_no = 1 AND c.col_no IN (7, 8))
    OR (c.row_no = 2 AND c.col_no IN (7, 8)));

-- Room 5: 儲物間 / 樓梯（右上中部）
-- 位置：Row 1-2, Col 9-10（4 個單元格）
INSERT INTO room_cell (room_ref_id, floor_id, cell_id)
SELECT r.id, r.floor_id, c.id
FROM room r
JOIN building_cell c ON c.floor_id = r.floor_id AND c.is_deleted = 0
WHERE r.floor_id = @target_floor_id
  AND r.room_number = '5'
  AND r.is_deleted = 0
  AND ((c.row_no = 1 AND c.col_no IN (9, 10))
    OR (c.row_no = 2 AND c.col_no IN (9, 10)));

-- Room 6: 樓梯間 B（右上角）
-- 位置：Row 1-2, Col 11-12（4 個單元格）
INSERT INTO room_cell (room_ref_id, floor_id, cell_id)
SELECT r.id, r.floor_id, c.id
FROM room r
JOIN building_cell c ON c.floor_id = r.floor_id AND c.is_deleted = 0
WHERE r.floor_id = @target_floor_id
  AND r.room_number = '6'
  AND r.is_deleted = 0
  AND ((c.row_no = 1 AND c.col_no IN (11, 12))
    OR (c.row_no = 2 AND c.col_no IN (11, 12)));

-- Room 7: 倉庫區域（左側大區域）
-- 位置：Row 3-5, Col 1-4（12 個單元格）
INSERT INTO room_cell (room_ref_id, floor_id, cell_id)
SELECT r.id, r.floor_id, c.id
FROM room r
JOIN building_cell c ON c.floor_id = r.floor_id AND c.is_deleted = 0
WHERE r.floor_id = @target_floor_id
  AND r.room_number = '7'
  AND r.is_deleted = 0
  AND c.row_no IN (3, 4, 5)
  AND c.col_no IN (1, 2, 3, 4);

-- Room 8: 主工作區（中間大區域）
-- 位置：Row 3-5, Col 5-8（12 個單元格）
INSERT INTO room_cell (room_ref_id, floor_id, cell_id)
SELECT r.id, r.floor_id, c.id
FROM room r
JOIN building_cell c ON c.floor_id = r.floor_id AND c.is_deleted = 0
WHERE r.floor_id = @target_floor_id
  AND r.room_number = '8'
  AND r.is_deleted = 0
  AND c.row_no IN (3, 4, 5)
  AND c.col_no IN (5, 6, 7, 8);

-- Room 9: 辦公區（右側大區域）
-- 位置：Row 3-5, Col 9-12（12 個單元格）
INSERT INTO room_cell (room_ref_id, floor_id, cell_id)
SELECT r.id, r.floor_id, c.id
FROM room r
JOIN building_cell c ON c.floor_id = r.floor_id AND c.is_deleted = 0
WHERE r.floor_id = @target_floor_id
  AND r.room_number = '9'
  AND r.is_deleted = 0
  AND c.row_no IN (3, 4, 5)
  AND c.col_no IN (9, 10, 11, 12);

-- Room 10: 設備區 西南（左下區域）
-- 位置：
--   Row 6: Col 2-5（4 個單元格，排除 col 1 凹位）
--   Row 7: Col 2-7（6 個單元格，排除 col 1 切角）
--   Row 8: Col 2-7（6 個單元格，排除 col 1 切角）
-- 共 16 個單元格
INSERT INTO room_cell (room_ref_id, floor_id, cell_id)
SELECT r.id, r.floor_id, c.id
FROM room r
JOIN building_cell c ON c.floor_id = r.floor_id AND c.is_deleted = 0
WHERE r.floor_id = @target_floor_id
  AND r.room_number = '10'
  AND r.is_deleted = 0
  AND (
    (c.row_no = 6 AND c.col_no IN (2, 3, 4, 5))
    OR (c.row_no = 7 AND c.col_no IN (2, 3, 4, 5, 6, 7))
    OR (c.row_no = 8 AND c.col_no IN (2, 3, 4, 5, 6, 7))
  );

-- Room 11: 設備區 東南（右下區域）
-- 位置：
--   Row 6: Col 6-10（5 個單元格，排除 col 11 凹位 和 col 12 切角）
--   Row 7: Col 8-10（3 個單元格，排除 cols 11,12 切角）
--   Row 8: Col 8-9（2 個單元格，排除 cols 10,11,12 切角）
-- 共 10 個單元格
INSERT INTO room_cell (room_ref_id, floor_id, cell_id)
SELECT r.id, r.floor_id, c.id
FROM room r
JOIN building_cell c ON c.floor_id = r.floor_id AND c.is_deleted = 0
WHERE r.floor_id = @target_floor_id
  AND r.room_number = '11'
  AND r.is_deleted = 0
  AND (
    (c.row_no = 6 AND c.col_no IN (6, 7, 8, 9, 10))
    OR (c.row_no = 7 AND c.col_no IN (8, 9, 10))
    OR (c.row_no = 8 AND c.col_no IN (8, 9))
  );

-- ----------------------------------------------------------------------------
-- 4. 驗證結果
-- ----------------------------------------------------------------------------
-- 預期：每個房間的單元格數量
-- Room 1: 4 cells (樓梯間 A)
-- Room 2: 4 cells (機電房)
-- Room 3: 4 cells (電梯區 A)
-- Room 4: 4 cells (電梯區 B)
-- Room 5: 4 cells (儲物間)
-- Room 6: 4 cells (樓梯間 B)
-- Room 7: 12 cells (倉庫)
-- Room 8: 12 cells (主工作區)
-- Room 9: 12 cells (辦公區)
-- Room 10: 16 cells (設備區 西南)
-- Room 11: 10 cells (設備區 東南)
-- 總計: 87 cells ✓

SELECT
  r.room_number,
  COUNT(rc.id) AS cell_count
FROM room r
LEFT JOIN room_cell rc ON rc.room_ref_id = r.id AND rc.floor_id = r.floor_id
WHERE r.floor_id = @target_floor_id AND r.is_deleted = 0
GROUP BY r.room_number
ORDER BY CAST(r.room_number AS UNSIGNED);
