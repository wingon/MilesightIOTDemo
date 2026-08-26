-- ============================================================================
-- room_cell 一格一房触发器（R3）：禁止同一格子被多个有效房间同时占用。
-- 整文件作为一条语句执行（含 BEGIN...END 内部分号）。
-- ============================================================================

CREATE TRIGGER `trg_room_cell_one_room` BEFORE INSERT ON `room_cell`
FOR EACH ROW
BEGIN
  IF NEW.`is_deleted` = 0 AND EXISTS (
    SELECT 1
    FROM `room_cell` rc
    JOIN `room` r ON r.id = rc.room_ref_id AND r.is_deleted = 0
    WHERE rc.cell_id = NEW.cell_id
      AND rc.floor_id = NEW.floor_id
      AND rc.is_deleted = 0
      AND rc.room_ref_id <> NEW.room_ref_id
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'cell already occupied by another active room';
  END IF;
END
