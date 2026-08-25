-- ============================================================================
-- 5F 移除 Row 6, Col 1 和 Row 6, Col 11 兩個單元格
-- 這兩個位置在平面圖中是凹進去的區域
-- ============================================================================

SET @target_floor_id = (SELECT id FROM floor WHERE level = 6 AND is_deleted = 0 LIMIT 1);

-- 1. 將這兩個 building_cell 標記為 is_active = 0（不渲染）
UPDATE building_cell
SET is_active = 0
WHERE floor_id = @target_floor_id
  AND ((row_no = 6 AND col_no = 1) OR (row_no = 6 AND col_no = 11))
  AND is_deleted = 0;

-- 2. 從 room_cell 中移除這兩個單元格
DELETE FROM room_cell
WHERE floor_id = @target_floor_id
  AND cell_id IN (
    SELECT id FROM building_cell
    WHERE floor_id = @target_floor_id
      AND ((row_no = 6 AND col_no = 1) OR (row_no = 6 AND col_no = 11))
      AND is_deleted = 0
  );

-- 3. 驗證：Room 10 應該從 17 減少到 16 cells，Room 11 應該從 11 減少到 10 cells
SELECT
  r.room_number,
  COUNT(rc.id) AS cell_count
FROM room r
LEFT JOIN room_cell rc ON rc.room_ref_id = r.id AND rc.floor_id = r.floor_id
WHERE r.floor_id = @target_floor_id AND r.is_deleted = 0
GROUP BY r.room_number
ORDER BY CAST(r.room_number AS UNSIGNED);
