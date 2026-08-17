# COMMITS

## 2026-08-13 12:08
feat: 品牌更名為永安貨倉大廈（Wing On Godown Building）

- 品牌名稱由「333 IOT Console」改為「Wing On Godown Building」／「永安貨倉大廈」
- 更新 favicon、頁面標題與側欄品牌顯示（新增 brandLine1 / brandLine2 i18n）
- 新增 wingon-logo.png 取代原 333-logo.png
- 隱藏選單中的 CT103 / UG65 / VS135 項目
- 樓宇總覽面板精簡為「樓層／連通／溫度／濕度」四欄，其餘指標欄位移除並註解保留
- Building_Cell_Shape 改為一格子一列，樓層以 JSON 陣列（floors）儲存，取代一樓層一列（floor_no）
- SQL 遷移腳本改為冪等：自動偵測舊表並聚合遷移，保留備份表供人工確認

## 2026-08-15 14:02
feat: 樓層檢視改顯示 WingOnIOT 真實設備

- FloorViewerView 進入樓層時拉取真實環境設備（fetchEnvDevices），設備面板不再顯示 demo
- 各房間設備數改由 DB 驅動（deviceCountMap，DB 無 room 欄位，預設全部歸入 room-1）

## 2026-08-17 23:13
feat: 樓層編輯支援牆體與拖曳移動，溫度改為固定五段色帶

- 新增自訂牆體：floorGridWall.ts 計算內外牆，編輯模式可拖曳放置垂直/水平牆、點選移除、拖曳移動
- 格子與牆體支援拖曳移動（含拖拽 ghost 預覽），moveRoomCell 保留房間歸屬並處理目標占用
- 樓層編輯加入牆體工具列與選中狀態（FloorModelPanel / i18n 新增相關文案）
- 溫度改為固定 5 段色帶（0/25/50/75/100，藍→青綠→黃→紅），圖例同步顯示刻度；濕度維持動態範圍
- 預設房間布局改為空白（不再預設格子，由使用者自行編輯），外圍輪廓依 G/F 平面圖調正斜切角
- 新增 G-F-floor-plan.html、gf_layout.html 平面圖參考與四表關聯生產版 DDL
