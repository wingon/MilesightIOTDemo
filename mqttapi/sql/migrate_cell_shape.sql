USE WingOnIOT;

-- 3D 樓棟格子形狀設定表（DB 驅動，取代前端硬編碼 cellShapes）
--
-- 一行 = 一個 (row, col, floor) 的形狀配置，與前端 CellShapeConfig 一一對應。
-- floor_no = 0 表示「所有樓層」；具體樓層號則只在該層生效。
--   3D 層號：1=B2/F, 2=B1/F, 3=G/F, 4=1/F ... 10=7/F, 11=ROOF
CREATE TABLE IF NOT EXISTS Building_Cell_Shape (
  id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  row_no      TINYINT UNSIGNED NOT NULL COMMENT '格子行號，1-based，1~8（南→北）',
  col_no      TINYINT UNSIGNED NOT NULL COMMENT '格子列號，1-based，1~12（西→東）',
  floor_no    TINYINT UNSIGNED NOT NULL DEFAULT 0
              COMMENT '3D 層號：1=B2/F, 2=B1/F, 3=G/F, 4=1/F…10=7/F, 11=ROOF；0=所有樓層',
  shape       VARCHAR(16) NOT NULL DEFAULT 'Rect'
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
  UNIQUE KEY uk_cell (row_no, col_no, floor_no),
  KEY idx_enabled (is_enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 初始化資料：把原本前端硬編碼的 3 條設定搬進 DB（G/F~4/F 即 3D 層號 3~7），共 15 行
--   (8,11) G/F~4/F → Triangle
--   (7,11) G/F~4/F → Rect
--   (7,12) G/F~4/F → Triangle
INSERT INTO Building_Cell_Shape (row_no, col_no, floor_no, shape, rotation)
SELECT 8, 11, n, 'Triangle', '0,0,0'
  FROM (SELECT 3 n UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7) f
UNION ALL
SELECT 7, 11, n, 'Rect', '0,0,0'
  FROM (SELECT 3 n UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7) f
UNION ALL
SELECT 7, 12, n, 'Triangle', '0,0,0'
  FROM (SELECT 3 n UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7) f;
