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

## 2026-08-18 15:30
feat: 樓棟結構改為 DB 驅動，新增儲存格旋轉與編輯

- 以 Building / Floor / Building_Cell / Room / Room_Cell 取代舊 Building_Cell_Shape，前端 3D 樓棟改讀 DB 資料
- 新增 API：樓棟/樓層/格子/房間查詢、單格與整列旋轉、新增刪除格子（單格/整行/整列/追加行列）、撤回、還原網格
- 後端實作可撤回的格子編輯（記憶體 undo 堆疊）、軟刪感知查詢，並移除舊 Building_Cell_Shape 邏輯
- Building3D 支援 DB 座標/自訂顏色/自訂高度渲染，並新增旋轉面板（0~315°）與格子編輯面板
- 樓層檢視改由 DB 房間（Room / Room_Cell）驅動布局與圖例，新增 buildRoomMeta 房間元資料對應
- 移除舊版 milesight_data.sql，新增 WingOnIOT_DDL_Data.sql（生產備份）與 migrate_building_structure.sql（遷移腳本）

## 2026-08-20 15:22
refactor: 3D 樓棟相關資料表改為全小寫命名

- 將 Building / Floor / Building_Cell / Room / Room_Cell（及備份表）統一改為小寫：building / floor / building_cell / room / room_cell
- 同步更新後端 db.py 全部 SQL 查詢、building.py docstring、前端注釋中的資料表名稱
- 更新 WingOnIOT_DDL_Data.sql（生產備份）與 migrate_building_structure.sql、migrate_cell_shape.sql 表名
- 新增 migrate_lowercase_tables.sql：可重複執行的表名小寫化遷移腳本（偵測舊表自動 RENAME，Linux 大小寫敏感環境必用）

## 2026-08-20 16:35
feat: 新增人流時數統計頁面

- 後端新增 people_count 路由：GET /api/v1/people-count/hourly（分頁 + 日期/時段/通道/IP 篩選）、GET /api/v1/people-count/channels（通道下拉）
- db.py 新增 people_count_hourly 查詢，依篩選條件強制使用 idx_date_channel_hour / uk_date_hour_ip 索引
- 新增 SQL 索引遷移腳本（idx_date_channel_hour 複合索引）
- 前端新增 PeopleCountListView 頁面：日期範圍/時段/通道/IP 篩選、服務端分頁表格
- 新增 peopleCount.ts API、側欄選單與路由（/people-count），並補上 en / zh-TW i18n

## 2026-08-21 09:55
feat: 支援大屏（iframe 嵌入）模式

- 透過 URL 參數 ?ls=<scale> 啟動大屏模式：整頁 zoom 等比放大（預設 1.5、上限 3），用於 iframe 嵌入展示
- app store 新增 applyLargeScreenMode()：解析 ls 參數、寫入 --ls-scale CSS 變數，並在 main.ts 掛載前執行避免閃爍
- 大屏模式下隱藏側欄與 header，內容區去 margin 鋪滿視口；頁面高度依縮放比例折算避免捲軸
- global.less 新增 --ls-scale / --ls-content-offset 變數與 html.ls-on 規則；Building/Floor 檢視頁高度改用變數計算

## 2026-08-21 12:12
feat: 精修大屏模式與 3D 自動旋轉

- Building3D 新增自動旋轉：播放/暫停按鈕與速率滑桿（0.5×~4×）；大屏模式以固定週期旋轉並隱藏控制項
- 溫度色帶改為實際範圍 0/10/20/30/35°C（藍→青→黃→紅），圖例改為連續漸層色條並新增漸層節點
- 大屏模式新增卡片式版面（largeScreen.less）：標題卡/3D 卡/指標卡，隱藏操作列與提示，加入淡入動畫
- 樓宇檢視標題加入 Wing On Logo（僅大屏顯示）；i18n 新增旋轉控制文案、副標題改為永安貨倉大廈
- 側欄選單 hover/選中樣式與金色細滾動條、header 細節修飾；PC 端卡片/KPI/表格表頭精修（html:not(.ls-on) 隔離）

feat: PC 端与大屏的隔离方式

- 代碼位置：
  - frontend/src/stores/app.ts:27-41 — applyLargeScreenMode() 函式
  - frontend/src/styles/largeScreen.less — 大屏樣式覆蓋（新建檔案）
  - frontend/src/main.ts:9-10 — import './styles/global.less' + import './styles/largeScreen.less'
- 展示方式
  - {url}?ls=1.5 大屏模式（預設） 項目預設解析度：1920×1080。驗證通過：瀏覽器 1920×1080 viewport 無捲動條
  - PC端3D建筑可调节，大屏是硬编码

## 2026-08-21 16:15
feat: 精簡樓宇儀表板，新增 Ubuntu 部署腳本

- BuildingDashboardPanel 移除面板標頭（標題/副標/即時徽章）與健康概況區塊及底部提示，配合大屏卡片版面精簡
- 新增 Ubuntu 部署管理腳本 manage.sh：管理 subscriber / api_server 的 start / stop / restart / status（含 PID、日誌、殘留進程清理）
- 新增前端管理腳本 manage_frontend.sh：管理 vite 前端（npm run dev）的啟動/停止/重啟/狀態，自動定位 npm（含 nvm 路徑）

## 2026-08-24 09:31
feat: 大屏模式字級調校與儀表板復原

- BuildingDashboardPanel 復原面板標頭（標題/副標/LIVE 徽章）與健康概況區塊，並新增非 scoped 的 html.ls-on 字級覆寫
- DeviceDetailPanel 新增 html.ls-on 字級覆寫（裝置列表/數值/徽章等放大）
- largeScreen.less 大屏版面微調：標題/副標/KPI/表格字級加大，移除卡片 hover 位移，縮緊間距與內距
- 大屏模式隱藏 .dash .head，樓層清單區塊改為獨立捲動填滿剩餘高度
- Building3D 新增 點 3 秒內連擊 3 次 進入編輯模式（自動清零計時器），編輯模式下格子可點擊開啟編輯框
- pane-label 點擊事件觸發編輯提醒計數，超過 3 次後觸發 toggleEditMode() 並短暫高亮邊框（.pane-label.flash，邊框變金色 0.5 秒）
- BuildingViewerView 增加 onBeforeUnmount 清理定時器、EDIT_HINT_REQUIRED=3 邏輯、editHintCount/flash 狀態，並在 pane-label 加入 .flash 類別的 CSS 定義
- i18n 新增 13 組編輯相關文案：editHintTag、editModeOnTag、editModeOn、editModeOff、editDone、saveChangesTitle/content/ok/cancel/savedSuccess、changesDiscarded、discardFailed（en.ts 與 zh-TW.ts 同步）

## 2026-08-24 11:17
feat: 樓層溫濕度詳情彈窗與超標高亮

- stores/building.ts 新增 TEMP_THRESHOLD(28)/HUMIDITY_THRESHOLD(75) 常數與 FloorDeviceStats 介面，新增 floorDeviceStats 計算屬性（每層 max/min/avg 與超標傳感器 SN 清單）
- BuildingDashboardPanel 點擊樓層改為開啟詳情彈窗（Teleport），顯示溫/濕度 最高/最低/平均 及超標傳感器清單
- 列表溫/濕度欄改顯示最大值，超標樓層以紅（溫）/藍（濕）高亮並加 alert-temp-max / alert-humidity-max 樣式
- i18n 新增 metricTempMax/metricHumidityMax/detailTitle/detailMax/detailMin/detailAvg/detailExceeding（en.ts 與 zh-TW.ts 同步）

## 2026-08-24 16:22
refactor: 樓層點擊改直跳樓層視圖，超標高亮移入裝置面板

- BuildingDashboardPanel 移除樓層詳情彈窗（Teleport/modal 與相關 CSS），點擊樓層行改 emit enterFloor 直接跳轉樓層視圖
- BuildingViewerView 新增 onDashboardEnterFloor：點擊儀表板樓層呼叫 store.ensureFloor 後 router 跳轉 floor-viewer
- DeviceDetailPanel 匯入 TEMP/HUMIDITY 閾值，新增 isTempAbnormal/isHumidityAbnormal/isEnvAbnormal；envBlocks 將異常設備排最前
- 裝置溫/濕度數值超標時加 exceeding-temp / exceeding-humidity 紅/藍高亮（列表樓層仍保留 alert-temp-max / alert-humidity-max 底色）