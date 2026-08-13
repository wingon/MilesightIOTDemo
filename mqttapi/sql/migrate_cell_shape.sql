USE WingOnIOT;

-- 3D 樓棟格子形狀設定表（DB 驅動，取代前端硬編碼 cellShapes）
--
-- 一行 = 一個 (row, col) 格子的形狀設定；多樓層共用同一設定時，
-- 樓層號以 JSON 陣列存於 floors 欄位，避免同一格子在每個樓層各佔一列。
--   floors = [3,4,5,6,7] 表示套用到 3~7F；[0]（或陣列中含 0）表示「所有樓層」。
--   3D 層號：1=B2/F, 2=B1/F, 3=G/F, 4=1/F ... 10=7/F, 11=ROOF
--
-- 本腳本可重複執行（冪等）：
--   1) 若現有表是舊版結構（floor_no 一列一樓層），會自動改名保留資料、
--      建立新表並把各樓層聚合為 JSON 陣列遷入；遷移完成後舊表保留為備份
--      （Building_Cell_Shape_old），確認無誤後可手動執行 DROP TABLE 刪除；
--   2) 若已是新結構或表不存在，直接沿用 / 建立並寫入種子資料。

-- ── 自動遷移：偵測舊版結構 ──────────────────────────────────────
SET @tbl_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
                   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Building_Cell_Shape');
SET @is_old = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Building_Cell_Shape'
                 AND COLUMN_NAME = 'floor_no');

-- 舊表改名（先清除可能殘留的同名舊表，避免 RENAME 衝突）
SET @sql = IF(@tbl_exists = 1 AND @is_old = 1,
              'DROP TABLE IF EXISTS Building_Cell_Shape_old', 'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @sql = IF(@tbl_exists = 1 AND @is_old = 1,
              'RENAME TABLE Building_Cell_Shape TO Building_Cell_Shape_old', 'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- ── 建立新表 ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Building_Cell_Shape (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  row_no      TINYINT UNSIGNED NOT NULL COMMENT '格子行號，1-based，1~8（南→北）',
  col_no      TINYINT UNSIGNED NOT NULL COMMENT '格子列號，1-based，1~12（西→東）',
  floors      JSON NOT NULL
              COMMENT '套用樓層的 JSON 陣列，如 [3,4,5,6,7]；[0] 或含 0 = 所有樓層',
  shape       VARCHAR(16) NULL DEFAULT 'Rect'
              COMMENT '形狀類型：Rect | Cylinder | Triangle | Hidden（隱藏不渲染）',
  rotation    VARCHAR(32) NULL COMMENT '旋轉弧度 x,y,z（如 0,0.785,0）；NULL=0,0,0',
  color       VARCHAR(32) NULL COMMENT '自訂顏色（如 #4CAF50）；NULL=按溫濕度著色',
  height      DECIMAL(6,3) NULL COMMENT '自訂高度（世界單位）；NULL=預設樓層高度',
  sort_order  INT NOT NULL DEFAULT 0 COMMENT '同格子多配置時優先級，小者優先',
  is_enabled  TINYINT(1) NOT NULL DEFAULT 1 COMMENT '0=停用，API 不回傳',
  created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  updated_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
              ON UPDATE CURRENT_TIMESTAMP(3),

  PRIMARY KEY (id),
  UNIQUE KEY uk_cell (row_no, col_no),
  KEY idx_enabled (is_enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── 聚合遷移（若剛從舊表改名而來）────────────────────────────────
-- 同一 (row, col) 的樓層合併為 JSON 陣列；若該格曾設 floor_no=0（所有樓層），
-- 整組合併為 [0]。JSON_ARRAYAGG 的樓層順序不保證，後端展開時會重新排序。
-- 若同一 (row, col) 原本存在多組不同設定（不同 shape 等），遷移會自動中止並
-- 保留舊表（Building_Cell_Shape_old），需先人工合併後再重新執行本腳本。
SET @has_old_data = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
                     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Building_Cell_Shape_old');

-- 衝突偵測：同一 (row, col) 是否有多組不同設定（動態執行，避免舊表不存在時報錯）
-- 先按配置 GROUP BY 得到每個 (row,col) 的配置組，再判斷組數是否 > 1
SET @sql = IF(@has_old_data = 1,
              'SET @conflict = (SELECT COUNT(*) FROM (SELECT row_no, col_no FROM (SELECT row_no, col_no FROM Building_Cell_Shape_old GROUP BY row_no, col_no, shape, rotation, color, height, sort_order, is_enabled) g GROUP BY row_no, col_no HAVING COUNT(*) > 1) c)',
              'SET @conflict = 0');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- 遷移條件：有舊表 且 無衝突 且 新表為空（新表已有資料代表已遷移過，避免重複）
SET @new_rows = (SELECT COUNT(*) FROM Building_Cell_Shape);
SET @do_migrate = IF(@has_old_data = 1 AND @conflict = 0 AND @new_rows = 0, 1, 0);

-- 符合條件才執行聚合遷移
SET @sql = IF(@do_migrate = 1,
              'INSERT INTO Building_Cell_Shape
                 (row_no, col_no, floors, shape, rotation, color, height, sort_order, is_enabled)
               SELECT row_no, col_no,
                      CASE WHEN SUM(floor_no = 0) > 0 THEN ''[0]'' ELSE JSON_ARRAYAGG(floor_no) END,
                      shape, rotation, color, height, sort_order, is_enabled
               FROM Building_Cell_Shape_old
               GROUP BY row_no, col_no, shape, rotation, color, height, sort_order, is_enabled',
              'SELECT 1');
PREPARE s FROM @sql;
EXECUTE s;
-- 記錄遷移是否真正成功（插入行數，須在 DEALLOCATE 前取值）
SET @migrated = IF(@do_migrate = 1, ROW_COUNT(), 0);
DEALLOCATE PREPARE s;

-- 衝突時輸出提示（舊表保留，等待人工合併後重跑）
SET @sql = IF(@has_old_data = 1 AND @conflict > 0,
              'SELECT ''警告：同一 (row,col) 存在多組不同設定，遷移已跳過；舊表 Building_Cell_Shape_old 已保留，請人工合併後再執行本腳本'' AS migrate_warning',
              'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- 遷移成功：保留舊表為備份，提示可手動清理
SET @sql = IF(@migrated > 0,
              'SELECT ''遷移完成：舊資料已遷入 Building_Cell_Shape；備份表 Building_Cell_Shape_old 已保留，確認無誤後可手動執行 DROP TABLE Building_Cell_Shape_old'' AS migrate_info',
              'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- ── 種子測試資料（僅在「無舊表」或「遷移無衝突」時寫入）────────
-- 衝突時不寫種子，避免 API 以預設形狀頂替舊表真實配置；人工合併後重跑本腳本即可。
--   (8,11) 3~7F → Triangle   （原 5 列合併為 1 列）
--   (7,11) 3~7F → Rect
--   (7,12) 3~7F → Triangle
--   (1, 1) 所有樓層 → Cylinder（floors=[0]）
--   (2, 3) 僅 1F → Rect，附自訂旋轉/顏色/高度
--   (6, 5) 2~3F → Triangle，但停用（is_enabled=0，API 不回傳）
SET @seed_ok = IF(@has_old_data = 0 OR @conflict = 0, 1, 0);
SET @sql = IF(@seed_ok = 1,
              'INSERT IGNORE INTO Building_Cell_Shape (row_no, col_no, floors, shape, rotation, color, height, sort_order, is_enabled) VALUES
                 (8, 11, ''[3,4,5,6,7]'',   ''Triangle'', ''0,0,0'',     NULL,      NULL,  0, 1),
                 (7, 11, ''[3,4,5,6,7]'',   ''Rect'',     ''0,0,0'',     NULL,      NULL,  0, 1),
                 (7, 12, ''[3,4,5,6,7]'',   ''Triangle'', ''0,0,0'',     NULL,      NULL,  0, 1),
                 (1,  1, ''[0]'',           ''Cylinder'', NULL,        ''#4CAF50'', NULL,  1, 1),
                 (2,  3, ''[1]'',           ''Rect'',     ''0,0.785,0'', ''#FF9800'', 1.5,  2, 1),
                 (6,  5, ''[2,3]'',         ''Triangle'', ''0,0,0'',     NULL,      NULL,  0, 0)',
              'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- 常用查詢範例（僅供參考，後端已實作）：
--   某格子的設定：   SELECT * FROM Building_Cell_Shape WHERE row_no = 8 AND col_no = 11;
--   某樓層生效的格子： SELECT * FROM Building_Cell_Shape WHERE JSON_CONTAINS(floors, '3');
--   啟用中的設定：   SELECT * FROM Building_Cell_Shape WHERE is_enabled = 1;
--   每個格子佔用幾個樓層： SELECT row_no, col_no, JSON_LENGTH(floors) AS floor_count
--                            FROM Building_Cell_Shape;
