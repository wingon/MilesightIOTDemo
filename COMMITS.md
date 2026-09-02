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
## 2026-08-25 12:07
feat: 5F 平面重排與設備格子綁定功能

### 5F 樓層平面調整
- buildingDemo shouldExcludeCell 外牆輪廓改為左側凹位 (8,1)(7,1)(6,1) 與右側凹位 (8,12)(8,11)(7,12)(7,11)(6,12)(6,11)，排除格由 7 增為 9
- migrate_building_structure.sql 種子格子同步排除 9 格（每層 87 格）；新增 migrate_5f_remove_indent_cells.sql（5F 停用 (6,1)/(6,11) 並移出 room_cell）與 migrate_5f_room_layout.sql（依平面圖重排 5F 11 間房 room_cell，共 87 格）

### 設備↔格子綁定（前後端 + 資料表）
- 新增 device_cell 資料表與 migrate_device_cell.sql / migrate_device_cell.py（冪等建立）
- db.py list_environment_devices 回傳 cell（綁定格子座標）與 room_id；新增 find_cell_by_row_col / device_exists / bind_device_cell / unbind_device_cell
- environment.py 新增 POST/DELETE /api/v1/environment/devices/{sn}/cell
- api/environment.ts 新增 DeviceCell、cell/room_id 欄位與 bind/unbind 呼叫；stores 新增 refreshEnvDevices / bindDeviceToCell / unbindDeviceFromCell / syncFloorLayoutFromDb
- Floor3D 新增 DeviceMarker 3D 標記（正常綠/異常紅），bindSn 時點擊格子 emit bindCell（含大廳格子）、游標變 cell 並顯示提示
- DeviceDetailPanel 新增綁定/解綁按鈕與綁定標籤、大廳/未綁定計數；FloorModelPanel 傳入 devices/bindSn/lobbyCount 並加「大廳」圖例與綁定提示
- FloorViewerView 設備數依格子歸屬房間統計（不再全塞 1 號房），區分大廳/未綁定設備；新增 pendingBindSn 綁定流程與 editDirty 離開編輯模式保存確認（Modal）
- i18n 新增綁定相關 12 組文案（bindStart/bindHint/bindClickCell/unbindCell/deviceBound/deviceBindFailed/deviceUnboundMsg/deviceUnbindFailed/cell/lobby 等，en.ts 與 zh-TW.ts 同步）


## 2026-08-26 12:20
feat: 3D 編輯工具重構、布局保存到 DB 與資料治理

### 3D 編輯工具重構（Building3D.vue）
- 新增拖曳添加格子功能：左側工具列顯示圆形/方形/三角形拖曳來源，拖到樓宇上即可放置（綠色可放、紅色已佔用）
- 可拖曳浮動工具面板（edit-tool-panel）：添加/刪除/撤回/關閉按鈕，面板可拖曳定位
- 新增格子形狀支援：cellEdit API 新增 shape 參數（Rect/Cylinder/Triangle），新增格子時可指定形狀
- 載入狀態：onMounted 平行 fetch 所有資料後再渲染 3D，避免畫面閃爍
- 撤回功能：前端 undoableOps 計數 + 後端 10 步撤回上限，支援旋轉/格子操作撤回
- 編輯完成對話框：可保存到 DB 或放棄（含確認提示），取消時自動恢復快照
- 格子刪除聯動清理：刪除格子時同步軟刪 room_cell、物理刪 device_cell，並記錄 undo 以便恢復
- 隱藏格子 overlay 顯示（is_active=0 的格子以半透明提示）

### 布局保存到資料庫（前後端）
- stores 新增 saveFloorLayoutToDb（原子替換整層樓 room_cell）+ saveLayoutSnapshot / restoreLayoutSnapshot
- building API 新增 POST /save-floor-layout（批量保存樓層佈局）
- FloorViewerView 編輯完成時自動保存到 DB，取消時恢復快照
- 設備數歸屬改為優先使用本地 layout 映射（反映用戶編輯後的最新狀態）

### 資料治理（WingOnIOT 風險修復）
- migrate_wingon_fixes.sql：表名統一小寫、Monitoring 改複合主鍵+按月分區、room_cell 加 is_deleted 軟刪+改唯一索引、device_cell 收斂為一設備一格(UNIQUE(sn))、building_cell 加 active_key 生成列+唯一索引
- migrate_wingon_trigger.sql：一格一房觸發器（R3）禁止同一格子被多個有效房間同時佔用
- migrate_remove_hidden_cells.sql：清理隱藏格子（is_active=0）的 room_cell 與 device_cell
- cleanup_wingon.py：資料治理定時任務（孤兒清理、超期軟刪物理刪除、分區維護與淘汰）
- migrate_wingon_fixes.py / test_wingon_fixes.py：遷移執行腳本與測試
- migrate_wingon_revert.sql：表名還原腳本（可選）

### DDL 同步（WingOnIOT_DDL_Data.sql）
- building_cell 新增 active_key 生成列 + uk_cell_active 唯一索引
- Environmental_Monitoring 改複合主鍵（id,toDateTime）+ 按月 RANGE 分區（p202603~p202608+pmax）
- room_cell 新增 is_deleted 軟刪欄位 + 唯一索引含 is_deleted + idx_cell_active
- device_cell 唯一索引改為 uk_device_sn（一設備一格）+ DDL 腳本中新增建表語句
- INSERT 語句改為指定欄位列表（避免新增欄位導致位置偏移）

### 其他改進
- EnvironmentDevice 新增 cell_lost 欄位（設備綁定已失效：目標格子已軟刪）
- DeviceDetailPanel：失效綁定顯示「格子已失效」+ 清除按鈕；bind/unbind 按鈕顯示條件調整
- FloorModelPanel：大廳圖例新增格子數顯示，count 樣式對齊
- 綁定設備時新增樓層一致性校驗（bind_device_cell 回傳 floor_mismatch）
- 大廳格子數 lobbyCellCount 計算（有效格子中不屬於任何房間的數量）
- unboundDevices 排除 cell_lost 設備，新增 lostDevices 計算
- pane-label 新增 user-select:none；.gitignore 新增 /.opencode/
- i18n 新增 ~20 組文案（dragSourceHint/addCellBtn/saveChangesKeep/savingLayout/undoLimitReached/cellLost/clearLostCell 等，en.ts 與 zh-TW.ts 同步）


## 2026-08-26 12:20
feat: 人數計數功能擴充與圖表展示

### 前端 API 與圖表
- api/peopleCount.ts 新增 PeopleCountStatsRow 介面與三組統計 fetch 函數：hourly / daily / channel，分別對應 /api/v1/people-count/stats/hourly、daily、channel
- frontend/src/utils/peopleCountCharts.ts（未追蹤）新增三組 ECharts 選項產生函數：buildHourlyBarOption / buildDailyTrendOption / buildChannelBarOption，支援進/出人數、日期趨勢、通道 Top 10 圖表
- frontend/src/components/ChartPanel.vue 新增 PieChart 匯入
- frontend/src/views/PeopleCountListView.vue 新增圖表展區（三卡片佈局），採用響應式 Grid：桌上型 3 卡 / 中型 2 卡 / 手機 1 卡，載入時平行抓取 hourly/daily/channel 三組統計資料並填入狀態
- frontend/src/views/DevicesManageView.vue 移除 max-width: 960px

### 環境色彩映射改進（envColor.ts）
- 棄用固定 5 段溫度區間，改為支援任意值連續插值的 lerpColor 函數，並新增 TEMPERATURE_ANCHORS / TEMPERATURE_GRADIENT_STOPS 常數（0/10/20/30/35°C 五檔錨點，與 3D 色帶與右下角圖例完全一致）
- 新增 temperatureColor 函數：根據值在錨點間線性插值，支援小數溫度點的精準顏色對應
- 重構 fixedTemperatureColor 使用新的 temperatureColor，humidityColor 改用多控點插值（低/中/高湿度分別對應不同亮度/饱和度），視覺過渡更平滑

### i18n 與頁面調整
- frontend/src/i18n/locales/en.ts / zh-TW.ts：新增 peopleCount 相關文案（進/出、圖表標題等）

### 後端
- mqttapi/app/api/routes/people_count.py 新增三組統計端點：/people-count/stats/hourly、daily、channel
- mqttapi/app/db.py 同步對應的 DB 查詢函數，支援依日期/小時/通道聚合進出人數

### ChartPanel 微調
- frontend/src/components/ChartPanel.vue 新增 PieChart 匯入（支援產生圓餅圖）

### 小調整
- frontend/src/components/ChartPanel.vue：移除 max-width: 960px（DevicesManageView）

### 其他
- frontend/src/utils/peopleCountCharts.ts（未追蹤）匯出 buildHourlyBarOption / buildDailyTrendOption / buildChannelBarOption 三組 ECharts 選項產生函數

## 2026-08-26 12:20
feat: 人數計數功能擴充與圖表展示

### 前端 API 與圖表
- api/peopleCount.ts 新增 PeopleCountStatsRow 介面與三組統計 fetch 函數：hourly / daily / channel
- frontend/src/utils/peopleCountCharts.ts（未追蹤）新增三組 ECharts 選項產生函數：buildHourlyBarOption / buildDailyTrendOption / buildChannelBarOption
- frontend/src/components/ChartPanel.vue 新增 PieChart 匯入
- frontend/src/views/PeopleCountListView.vue 新增圖表展區（三卡片響應式佈局），載入時平行抓取 hourly/daily/channel 三組統計資料
- frontend/src/views/DevicesManageView.vue 移除 max-width: 960px

### 環境色彩映射改進（envColor.ts）
- 棄用固定 5 段溫度區間，改為支援任意值連續插值的 lerpColor 函數，並新增 TEMPERATURE_ANCHORS / TEMPERATURE_GRADIENT_STOPS 常數
- 新增 temperatureColor 函數：根據值在錨點間線性插值
- 重構 fixedTemperatureColor 使用新的 temperatureColor，humidityColor 改用多控點插值，視覺過渡更平滑

### 後端
- mqttapi/app/api/routes/people_count.py 新增三組統計端點：hourly/daily/channel
- mqttapi/app/db.py 同步對應的 DB 查詢函數

### i18n 與頁面調整
- i18n 新增 peopleCount 相關文案

### ChartPanel 微調
- ChartPanel 新增 PieChart 匯入

### 小調整
- DevicesManageView 移除 max-width: 960px

### 其他
- peopleCountCharts.ts（未追蹤）匯出三組 ECharts 選項產生函數





## 2026-08-30 10:30
refactor: 外觀組件遷移、地下層對齊與 i18n 控制面板

### 組件遷移與路由重整
- BuildingFacade3D 從 demo/building-facade/ 遷移至 components/building/，導入 vue-i18n
- FacadeDemoView 重命名為 BuildingViewerOldView（舊版保留供日後切換）
- facadeSnapshot.ts 遷移至 utils/；demo/rendering.png 刪除
- router 新增 building-viewer-old 路由，building-facade-demo 重定向至 /building-viewer

### 地下層與視覺調整
- 新增 UNDERGROUND_OFFSET = -2*SLAB，B2/B1/G 樓層 Y 坐標對齊地面 y=0
- 地面材質改為淺白色（行人道色），地下層從側面可見
- ROOF_Y 改為 (FLOOR_COUNT-3)*SLAB + FLOOR_H 計算
- core 位置與所有樓層座標均加入 UNDERGROUND_OFFSET 偏移

### 語言與跨頁同步
- MainLayout：watch pageTitle → document.title 即時同步（切換語言後頁面標題即時更新）
- stores/app.ts：新增 storage 事件監聽，PC 端切換語言後大屏自動跟隨（跨分頁同步）
- BuildingViewerView：改用 @/components/building/BuildingFacade3D，標題改為 i18n

### 控制面板 i18n（~50 組新文案）
- en.ts / zh-TW.ts：新增 panelTitle/scene/windowDirection/windowWidth/windowHeight/rawMode/coloring/clickCreateWindows/hideFloorLines/showFloorLines/hideColLines/showColLines/clearAll/outlineOn/outlineOff/resetView/clickFloorHint/debugInfo/cellEditor/exitEdit/addBtn/deleteBtn/undoBtn/doneBtn/editAddHint/editDeleteHint/loading/missingBuildingId/deleteFailed/cellDeleted/noDeleteChange/noUndo/undone/debugFace/debugCoord/debugHeight/debugNormal/debugApprox/faceUnknown/faceRoof/faceSlope/faceEast/faceWest/faceSouth/faceNorth

### 小調整
- 部分硬編碼訊息改為 i18n（savedSuccess/changesDiscarded）
- autoRotate 預設值：大屏模式（ls-on）預設開啟，普通模式關閉

### 注意
- db_backup/ 目錄不應提交（包含 SQL 備份檔案）

## 2026-08-30 10:30
refactor: 外觀組件遷移、地下層對齊與 i18n 控制面板


## 2026-08-30 11:00
fix: 弱化切角著色與移除懸停凸出效果

- 切角凹槽處溫濕度著色向混凝土米灰靠攏（lerp 55%），保留可辨識傾向但不再濃烈刺眼
- 自發光強度由 0.15 降為 0.05，避免同色樓層在切角處連成一片黃綠色塊
- 移除 updateHoverHighlight 的懸停凸出邏輯：樓層不再縮放放大、不再顯示金色高亮盒，懸停僅保留提示 toast 與指針變化


## 2026-08-31 12:00
feat: RBAC 權限系統 v0.1

### 後端認證與安全
- security.py：bcrypt 密碼哈希（rounds=10）+ JWT Token 生成/校驗（PyJWT + bcrypt）
- deps.py：get_current_user 依賴注入，解析 JWT 取得當前用戶/角色/權限
- auth.py：登入（bcrypt 校驗 + 產生 JWT + 記錄登入日誌）/ 登出 / 當前用戶資訊 / 動態路由選單

### 後端系統管理 API（12 個路由模組）
- system_user.py：用戶 CRUD、角色分配、密碼重置
- system_role.py：角色 CRUD、選單權限分配、部門分配、數據範圍（data_scope）
- system_menu.py：選單 CRUD（樹形結構，M=目錄/C=菜單/F=按鈕）
- system_dept.py：部門 CRUD（樹形結構，ancestors 祖級列表）
- system_dict.py：字典類型與字典資料管理
- system_config.py：參數設定
- system_post.py：崗位管理
- system_profile.py：個人資料
- system_log.py：操作日誌
- system_login_log.py：登入日誌
- system_whitelist.py：前端路由白名單管理
- operlog.py：操作日誌裝飾器（自動記錄用戶/操作/結果）

### 後端資料庫
- db.py 新增 ~1500 行：sys_user/sys_role/sys_menu/sys_dept/sys_post/sys_dict/sys_config/sys_oper_log/sys_login_log/sys_user_role/sys_role_menu/sys_role_dept/sys_user_post/sys_role_data_scope 共15 張表的完整 CRUD
- init_sys_permission.sql：核心 RBAC 表（user/role/menu/user_role/role_menu/oper_log）
- init_sys_manage.sql：擴展表（dept/post/user_post/login_log/config/dict/dict_data/whitelist）+ sys_user 新增性別欄位
- init_role_data_scope.sql：角色數據範圍（data_scope 1~5）+ sys_role_dept
- migrate_role_data_scope.py / test_role_api.py / test_data_scope.py / test_permission_chain.py / test_iot_auth.py

### 前端認證流程
- api/http.ts：JWT Token 自動附加 Authorization header；401 自動跳轉登入頁
- api/auth.ts：login/getUserInfo/logout/getFrontWhitelist API
- stores/user.ts：token/userInfo/roles/permissions 狀態管理
- stores/permission.ts：動態路由生成（generateRoutes）、權限檢查（hasPermission/hasAnyPermission）
- utils/whitelist.ts：前端路由白名單快取與前綴匹配
- utils/permission.ts：v-permission 按鈕級權限指令（無權限時移除元素）
- router/index.ts：路由守衛（未登入→白名單檢查→登入頁；已登入→動態路由加載→權限過濾）

### 前端系統管理頁面
- views/LoginView.vue：登入頁（品牌色漸層背景 + 記住帳號）
- views/ProfileView.vue：個人資料（密碼修改、基本資料編輯）
- views/NotFoundView.vue：404 頁面
- views/system/SystemUserView.vue：用戶管理（表格+搜尋+角色分配+密碼重置）
- views/system/SystemRoleView.vue：角色管理（選單權限樹、部門分配、數據範圍）
- views/system/SystemMenuView.vue：選單管理（樹形表格、圖標選擇、權限標識）
- views/system/SystemDeptView.vue：部門管理（樹形表格）
- views/system/SystemDictView.vue：字典管理（類型+資料兩層）
- views/system/SystemConfigView.vue：參數設定
- views/system/SystemPostView.vue：崗位管理
- views/system/SystemLogView.vue：操作日誌
- views/system/SystemLoginLogView.vue：登入日誌
- views/system/SystemWhitelistView.vue：白名單管理

### 前端佈局與 UI
- MainLayout.vue 大幅重構（+691 行）：側邊欄可收合、Tab 頁籤導航、麵包屑、用戶下拉選單（個人資料/登入日誌/白名單/系統管理子選單）、全螢幕切換、語言切換、鎖屏入口
- stores/app.ts 新增 ~220 行：sidebarCollapsed/tabs/breadcrumbs/lockScreen 狀態、動態選單生成
- App.vue：整合鎖屏元件
- components/LockScreen.vue：鎖屏畫面（密碼解鎖）
- components/LayoutSettings.vue：佈局設定面板
- styles/global.less 新增 ~500 行：側邊欄/Tab/麵包屑/鎖屏/登入頁完整樣式

### i18n（~260 組新文案）
- en.ts / zh-TW.ts：login/common/profile/system 各模組完整中英文翻譯（~260 鍵）

### 其他
- package.json 新增 bcrypt 依賴
- requirements.txt 新增 bcrypt/pyjwt
- config.py 新增 JWT_SECRET/JWT_ALGORITHM/JWT_EXPIRE_MINUTES
- .env.example 新增 JWT 與超級管理員設定
- 已有路由（tof/ug65/vs135/building 等）加入權限檢查
- TofListView/Ug65ListView/Vs135ListView/DevicesManageView 等頁面加入 v-permission 指令
- SQL 文件結構
  - init_sys_permission.sql 核心 RBAC 表（user/role/menu/user_role/role_menu/oper_log）+ 管理員種子
  - init_sys_manage.sql 擴展表（dept/post/whitelist/config/dict/login_log）+ ALTER user 加 dept_id/sex + 擴展菜單
  - init_role_data_scope.sql 數據權限（ALTER role 加 data_scope + sys_role_dept 表）

## 2026-08-31 14:00
feat: CCTV 人流同步定時任務與雪花 ID

### CCTV 人流資料採集（cctv_sync.py，新檔案）
- 從 Milesight 攝影機 ISAPI 拉取逐小時進出人數（28 台攝影機，硬編碼 CCTV_CAMERAS）
- 使用 HTTPDigestAuth 認證，解析 XML 回應（xmltodict）
- UPSERT 至 people_count_hourly（以 snowflake ID 為主鍵，date+hour+ip_address 為唯一索引）
- 支援三種同步模式：sync_today（當天）、sync_yesterday（昨天完整 24h）、backfill_current_month（回填當月缺失日期）

### 雪花 ID 產生器（snowflake.py，新檔案）
- 64 位元雪花 ID（41 bit 時間戳 + 10 bit 機器 ID + 12 bit 序列號）
- 執行緒安全，自訂紀元 2023-01-01，模組級單例 + init_snowflake(worker_id)

### APScheduler 整合（main.py）
- 採用 FastAPI lifespan 啟動時註冊 BackgroundScheduler
- 三個 cron 任務：hourly（每小時 05 分同步當天）、yesterday（每天 00:05 同步昨天）、backfill（每天 00:10 回填當月）
- 支援 cron 熱更新：每次執行前從 sys_config 讀取最新 cron 表示式，變更時自動 reschedule
- 開關控制：cctv.sync.enabled（Y 啟用 / N 停用），停用時跳過執行
- 啟動時立即執行一次當天同步

### 手動同步 API
- POST /api/v1/people-count/sync：需登入（get_current_user），受 cctv.sync.enabled 控制
- 支援指定日期或預設今天

### 後端
- config.py 新增 cctv_username / cctv_password / snowflake_worker_id
- db.py 新增 upsert_people_count_hourly（INSERT ON DUPLICATE KEY UPDATE）與 get_existing_people_count_dates
- requirements.txt 新增 APScheduler / requests / xmltodict
- init_cctv_sync_config.sql：初始化 sys_config 中 CCTV 同步相關參數（開關 + 三組 cron）