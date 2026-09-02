# CCTV 人流統計同步功能開發說明 <a id="chinese-version"></a>

> 🌐 **[English](#english-version)** | **[繁體中文（當前）](#chinese-version)** | [← 返回專案根目錄](../../README_zh-HK.md)

## 目錄

- [1. 功能概述](#1-功能概述)
- [2. 同步機制](#2-同步機制)
- [3. 資料表結構](#3-資料表結構)
- [4. API 接口說明](#4-api-接口說明)
- [5. 頁面操作（設定定時時間）](#5-頁面操作設定定時時間)
- [6. 並發安全性（雙實例）](#6-並發安全性雙實例)
- [7. 本次同步使用的檔案修改說明](#7-本次同步使用的檔案修改說明)
- [8. 後端日誌](#8-後端日誌)
- [9. 測試建議](#9-測試建議)
- [10. 已知限制](#10-已知限制)

---

## 1. 功能概述

從 Milesight 網路攝影機（CCTV）透過 ISAPI 拉取逐小時的進入 / 離開人數，寫入 `WingOnIOT` 資料庫的 `people_count_hourly` 表，供 `/people-count` 頁面查詢與圖表統計。

### 資料流

```
Milesight 攝影機 (30 台)
   │  HTTP ISAPI (Digest 認證)
   ▼
cctv_sync.py ──► people_count_hourly 表 (UPSERT)
                     │
                     ▼
        /api/v1/people-count/* 查詢接口 ──► 前端頁面
```

### 核心特性

- **資料來源**：30 台攝影機，列表硬編碼於 `cctv_sync.py` 的 `CCTV_CAMERAS`
- **帳號密碼**：來自 `.env` 的 `CCTV_USERNAME` / `CCTV_PASSWORD`
- **主鍵**：雪花演算法 ID（`app/snowflake.py`）
- **寫入方式**：`INSERT ... ON DUPLICATE KEY UPDATE`（UPSERT），天然冪等
- **唯一索引**：`uk_date_hour_ip (date, hour, ip_address)`，防止同一天同一小時同一攝影機重複
- **定時任務**：APScheduler 排程，cron 表達式可**熱更新**（無需重啟服務）

---

## 2. 同步機制

### 2.1 三種同步方式

| 方式 | 觸發 | 同步內容 | 說明 |
|------|------|---------|------|
| 即時同步 | 服務啟動時 | 當天資料 | 後台線程執行，不阻塞啟動 |
| 定時同步 | APScheduler cron | 當天 / 昨天 / 當月回填 | 三個獨立 job |
| 手動同步 | HTTP API | 單天 / 日期範圍回填 | 需登入 + 開關啟用 |

### 2.2 定時任務（cron 熱更新）

在 `app/api/main.py` 註冊了三個 cron job，全部由 `_cron_watcher` 後台線程監控（每 10 秒檢查一次 DB 中的 `sys_config`，發現變化立即重新排程）：

| job_id | 對應參數鍵 | 預設 cron | 執行內容 |
|--------|-----------|-----------|---------|
| `anytime` | `cctv.sync.cron.anytime` | `5 * * * *`（每小時第 5 分） | 同步當天 `sync_today` |
| `yesterday` | `cctv.sync.cron.yesterday` | `5 0 * * *`（每天 00:05） | 同步昨天完整 24h `sync_yesterday` |
| `backfill` | `cctv.sync.cron.backfill` | `10 0 * * *`（每天 00:10） | 回填當月缺失日期 `backfill_current_month` |

**執行邏輯**（每個 job runner）：
1. 檢查總開關 `cctv.sync.enabled`，為 `N` 時跳過
2. 印出 `[CCTV] 定時任務 {job_id} 開始執行`
3. 執行業務函式
4. 印出 `[CCTV] 定時任務 {job_id} 執行完成`

**熱更新機制**：
- `_cron_watcher` 線程每 10 秒讀取 DB 中三個 cron 參數
- 與記憶體中的上次值比較，有變化立即 `reschedule_job`
- 印出 `[CCTV] cron {job_id} 已從 {舊} 熱更新為 {新}`
- **修改 cron 後無需重啟服務**（實測約 10~12 秒內生效）

**並行行為**：APScheduler 使用 `ThreadPoolExecutor` 線程池執行，三個 job 各自獨立、互不阻塞。同一 job 預設 `max_instances=1`，若上一次同步（30 台約 60 秒）未完成，下一次觸發會跳過，防止自衝突。

---

## 3. 資料表結構

### 3.1 people_count_hourly

| 欄位 | 型態 | 說明 |
|------|------|------|
| `id` | BIGINT | 雪花演算法主鍵（非自增） |
| `date` | DATE | 日期 |
| `hour` | TINYINT | 小時 0-23 |
| `ip_address` | VARCHAR | 攝影機 IP |
| `channel_name` | VARCHAR | 攝影機名稱 |
| `enter_count` | INT | 該小時進入人數 |
| `exit_count` | INT | 該小時離開人數 |
| `updated_at` | DATETIME | 更新時間 |

**索引**：
- `PRIMARY (id)` — 唯一
- `uk_date_hour_ip (date, hour, ip_address)` — **唯一**，驅動 UPSERT，防止重複
- `idx_date_channel_hour (date, channel_name, hour)` — 非唯一，加速過濾查詢

#### DDL

```sql
CREATE TABLE `people_count_hourly` (
  `id` bigint(20) unsigned NOT NULL COMMENT '雪花演算法主鍵（64 位元，由應用程式產生）',
  `date` date NOT NULL COMMENT '統計日期（YYYY-MM-DD）',
  `hour` tinyint(4) NOT NULL COMMENT '小時（0~23，0 代表 00:00~01:00）',
  `ip_address` varchar(20) NOT NULL COMMENT '攝影機 IP 位址',
  `channel_name` varchar(64) NOT NULL COMMENT '通道名稱（如 1/F Lift）',
  `enter_count` int(11) NOT NULL DEFAULT 0 COMMENT '該小時進入人數',
  `exit_count` int(11) NOT NULL DEFAULT 0 COMMENT '該小時離開人數',
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) COMMENT '建立時間',
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3) COMMENT '更新時間（最後同步時刻）',
  PRIMARY KEY (`id`) COMMENT '雪花主鍵',
  UNIQUE KEY `uk_date_hour_ip` (`date`,`hour`,`ip_address`) COMMENT '同日同時同機唯一鍵，防止重複資料（UPSERT 用）',
  KEY `idx_date_channel_hour` (`date`,`channel_name`,`hour`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='CCTV 人流統計小時明細表（每小時同步，只寫入已結束的小時）';
```

### 3.2 參數設置表 sys_config（新增 4 筆）

| config_name | config_key | 預設值 | 說明 |
|-------------|-----------|--------|------|
| CCTV 人流同步開關 | `cctv.sync.enabled` | `Y` | Y 啟用 / N 停用 |
| CCTV 定時同步 cron | `cctv.sync.cron.anytime` | `5 * * * *` | 按 cron 同步當天 |
| CCTV 昨天補全 cron | `cctv.sync.cron.yesterday` | `5 0 * * *` | 每天 00:05 同步昨天 |
| CCTV 當月回填 cron | `cctv.sync.cron.backfill` | `10 0 * * *` | 每天 00:10 回填當月 |

初始化 SQL：`mqttapi/sql/init_cctv_sync_config.sql`

---

## 4. API 接口說明

所有接口需登入後帶 `Authorization: Bearer <token>`。

### 4.1 登入取得 Token

```http
POST /api/v1/auth/login
Content-Type: application/json

{"username": "admin", "password": "<密碼>"}
```

回應：
```json
{"token": "eyJhbGciOiJIUzI1NiIs..."}
```

### 4.2 手動同步

#### 單天同步（同步執行）

```http
POST /api/v1/people-count/sync
Authorization: Bearer <token>
Content-Type: application/json

{"date": "2026-09-01"}
```

- `date` 缺省為今天
- 同步執行，回應為同步統計：

```json
{"date": "2026-09-01", "cameras": 30, "rows": 720, "failed": []}
```

#### 範圍回填（後台執行）

```http
POST /api/v1/people-count/sync
Authorization: Bearer <token>
Content-Type: application/json

{"date_from": "2026-01-01", "date_to": "2026-06-30"}
```

回應（立即返回 `task_id`，後台執行）：
```json
{
  "task_id": "3ad1c6e820844b95974231432ee5b026",
  "date_from": "2026-01-01",
  "date_to": "2026-06-30",
  "status": "running",
  "message": "範圍回填已於後台開始執行，可查詢 /api/v1/people-count/sync/status/{task_id}"
}
```

**參數校驗規則**：

| 情境 | 回應 |
|------|------|
| 只傳 `date_from` 或 `date_to` | 400 必須同時提供兩者 |
| `date_from` > `date_to` | 400 不能晚於 |
| 範圍 > 183 天（6 個月） | 400 查詢範圍超出限制 |
| 總開關為 N | 400 同步已停用 |
| 未登入 | 401 |

#### 查詢回填進度

```http
GET /api/v1/people-count/sync/status/{task_id}
Authorization: Bearer <token>
```

回應：
```json
{
  "task_id": "...",
  "date_from": "2026-01-01",
  "date_to": "2026-06-30",
  "status": "running",        // running / done / failed
  "progress": 33,             // 百分比 0-100
  "done_days": 1,             // 已完成天數
  "total_days": 3,            // 總待同步天數（啟動即已知）
  "current_date": "2026-08-26", // 當前正在同步的日期
  "started_at": "...",
  "result": null,             // 完成後填充
  "error": null
}
```

> 注意：任務狀態存於記憶體，服務重啟後丟失（可重跑，已有日期自動跳過）。

### 4.3 查詢接口（既有功能）

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/v1/people-count/hourly` | 分頁查詢（date_from/date_to/hour/ip_address/channel_name/limit/offset） |
| GET | `/api/v1/people-count/channels` | 攝影機清單（下拉選單） |
| GET | `/api/v1/people-count/stats/hourly` | 逐小時統計（圖表） |
| GET | `/api/v1/people-count/stats/daily` | 每日統計（圖表） |
| GET | `/api/v1/people-count/stats/channel` | 分通道統計（圖表） |

---

## 5. 頁面操作（設定定時時間）

### 5.1 進入參數設置頁

前端選單：**系統管理 > 參數設置**（路由 `system/config`，組件 `system/ConfigManage.vue`）

### 5.2 三個 cron 的設定方式

1. 在參數設置頁找到以下三筆設定
2. 點擊「編輯」，修改「參數值」（config_value）為想要的 **5 段式 cron 表達式**
3. 儲存後 **無需重啟服務**，約 10~12 秒內自動生效（`_cron_watcher` 熱更新）

| 參數名稱 | 參數鍵 | 建議值 |
|---------|--------|--------|
| CCTV 定時同步 cron | `cctv.sync.cron.anytime` | `5 * * * *` |
| CCTV 昨天補全 cron | `cctv.sync.cron.yesterday` | `5 0 * * *` |
| CCTV 當月回填 cron | `cctv.sync.cron.backfill` | `10 0 * * *` |

### 5.3 cron 表達式範例

| 表達式 | 含義 | 注意 |
|--------|------|------|
| `*/1 * * * *` | 每分鐘執行 | 30 台同步約 60 秒，不建議長期使用 |
| `*/5 * * * *` | 每 5 分鐘的第 0 分執行 | 觸發點為 0,5,10,15... |
| `5 * * * *` | 每小時第 5 分執行 | 預設值 |
| `*/10 * * * *` | 每 10 分鐘執行 | 觸發點為 0,10,20,30,40,50 |
| `5 0 * * *` | 每天 00:05 執行 | yesterday 預設 |

> **重要**：cron 是**時間點匹配**，不是「從修改時間延遲 N 分鐘」。例如 11:27 修改為 `*/5`，下一個觸發點是 11:30。

### 5.4 總開關

參數設置中的「CCTV 人流同步開關」（`cctv.sync.enabled`）：
- `Y`：啟用定時同步與手動同步
- `N`：停用（定時任務跳過，手動同步接口回 400）

---

## 6. 並發安全性（雙實例）

### 6.1 設計保障

表使用 `uk_date_hour_ip (date, hour, ip_address)` 唯一索引，寫入使用 UPSERT：

```sql
INSERT INTO people_count_hourly (id, date, hour, ip_address, channel_name, enter_count, exit_count)
VALUES (...)
ON DUPLICATE KEY UPDATE
    channel_name = VALUES(channel_name),
    enter_count  = VALUES(enter_count),   -- 覆蓋賦值，非累加
    exit_count   = VALUES(exit_count),
    updated_at   = NOW(3)
```

- **不疊加**：`VALUES(enter_count)` 是覆蓋賦值，不是 `enter_count + VALUES(...)`
- **不混合**：InnoDB 行級鎖，多實例併發寫同一行時串行執行，每次 UPDATE 整行一次性賦值
- **單實例防重疊**：APScheduler `max_instances=1`，同一 job 不會並發重入

### 6.2 並發測試結果（實測）

用多進程模擬多實例同時 UPSERT 同一行（date=2026-09-01, hour=8, ip=10.98.127.26），各實例寫入不同值：

| 場景 | 寫入次數 | 最終行數 | 最終值 | 結論 |
|------|---------|---------|--------|------|
| 3 實例 × 50 次 | 150 | 1 | 其中一實例的完整對 (10,5) | ✅ |
| 4 實例 × 50 次 | 200 | 1 | 完整對 (33,17) | ✅ |
| 4 實例 × 200 次 | 800 | 1 | 完整對 (7,99) | ✅ |
| 4 實例 × 500 次 | 2000 | 1 | 完整對 (10,5) | ✅ |

**驗證結論**：
- 行數始終 = 1（無疊加，即使 2000 次並發寫入仍是 1 行）
- 最終值 = 某實例寫入的**完整 (enter, exit) 對**（無混合錯亂）
- 最終值 ≠ 各實例之和（非累加）
- 所有實例零報錯（無鎖死、無異常）

**雙實例部署注意**：
- 兩實例 `.env` 的 `SNOWFLAKE_WORKER_ID` 必須不同（如 1 和 2），避免雪花 ID 衝突造成不必要的鎖等待（不會產生髒數據，但性能更好）
- 若兩實例拉取同一批攝影機，會雙倍消耗攝影機頻寬與 DB 寫入壓力，建議僅一實例跑定時任務或拆分配置

---

## 7. 本次同步使用的檔案修改說明

### 新增檔案

| 檔案 | 說明 |
|------|------|
| `mqttapi/app/cctv_sync.py` | **核心同步服務**：攝影機清單、ISAPI 拉取（`fetch_camera_day`）、單天同步（`sync_date`）、當天/昨天/當月回填/範圍回填（`sync_today`/`sync_yesterday`/`backfill_current_month`/`sync_date_range`） |
| `mqttapi/app/snowflake.py` | 雪花演算法 ID 產生器（`Snowflake` 類、`next_id()`、`init_snowflake(worker_id)`） |
| `mqttapi/sql/init_cctv_sync_config.sql` | 初始化 4 筆 `sys_config` 參數 |

### 修改檔案

| 檔案 | 修改內容 |
|------|---------|
| `mqttapi/app/config.py` | `Settings` 新增 `cctv_username`、`cctv_password`、`snowflake_worker_id` 欄位 |
| `mqttapi/app/db.py` | 新增 `upsert_people_count_hourly`（UPSERT 寫入）、`get_existing_people_count_dates`（當月已有日期）、`get_existing_people_count_dates_range`（範圍已有日期） |
| `mqttapi/app/api/main.py` | lifespan 掛載 APScheduler 三個 cron job；`_cron_watcher` 線程熱更新；啟動時後台立即同步；[CCTV] 前綴日誌 |
| `mqttapi/app/api/routes/people_count.py` | 新增 `POST /people-count/sync`（單天 + 範圍回填）、`GET /people-count/sync/status/{task_id}`（進度查詢）；`PeopleCountSyncBody` 模型 |
| `mqttapi/api_server.py` | 配置 root logger，使 `[CCTV]` info 日誌輸出到控制台 |
| `mqttapi/requirements.txt` | 新增 `APScheduler`、`requests`、`xmltodict` |
| `.env` | 新增 `CCTV_USERNAME`、`CCTV_PASSWORD`、`SNOWFLAKE_WORKER_ID=1` |

### 依賴套件

```
APScheduler   # 定時任務
requests      # HTTP 請求（攝影機 ISAPI）
xmltodict     # XML 回應解析
```

### 資料庫變更

1. 執行 `mqttapi/sql/init_cctv_sync_config.sql` 寫入參數設定
2. 確認 `people_count_hourly` 表存在 `uk_date_hour_ip` 唯一索引（UPSERT 依賴）

---

## 8. 後端日誌

### 8.1 日誌配置

`api_server.py` 啟動時配置 root logger（`INFO` 級別），所有 `[CCTV]` 前綴日誌輸出到控制台。第三方庫（`apscheduler`、`urllib3`）降為 `WARNING` 降低噪音。

### 8.2 日誌範例

```
2026-09-02 11:24:36 | INFO | app.api.main | [CCTV] APScheduler 已啟動，定時同步已註冊
2026-09-02 11:24:37 | INFO | app.api.main | [CCTV] cron 監聽線程已啟動，初始排程: {...}
2026-09-02 11:25:00 | INFO | app.api.main | [CCTV] 定時任務 anytime 開始執行
2026-09-02 11:25:42 | INFO | app.cctv_sync | CCTV sync 2026-09-02: 30 cameras, 720 rows, 0 failed
2026-09-02 11:25:42 | INFO | app.api.main | [CCTV] 定時任務 anytime 執行完成
```

### 8.3 常見日誌訊息

| 訊息 | 含義 |
|------|------|
| `[CCTV] 定時任務 {job} 開始執行` | cron 觸發，開始同步 |
| `[CCTV] 定時任務 {job} 執行完成` | 同步完成 |
| `[CCTV] 定時任務 {job} 執行失敗: {err}` | 同步異常（附堆疊） |
| `[CCTV] cron {job} 已從 {a} 熱更新為 {b}` | 頁面修改 cron 已生效 |
| `[CCTV] 同步已停用，跳過 {job}` | 總開關為 N |
| `CCTV sync {date}: {n} cameras, {m} rows, {f} failed` | 單天同步統計，failed 為連線失敗的攝影機名稱 |

---

## 9. 測試建議

### 9.1 驗證熱更新

1. 啟動服務，確認日誌 `[CCTV] cron 監聽線程已啟動`
2. 頁面修改任意 cron（如 `cctv.sync.cron.anytime` 改為 `*/5 * * * *`）
3. 10~12 秒內日誌出現 `[CCTV] cron anytime 已從 5 * * * * 熱更新為 */5 * * * *`
4. 到下一個 5 分鐘觸發點觀察 `開始執行`

### 9.2 驗證範圍回填

```bash
# 1. 登入
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<密碼>"}'
# 2. 觸發範圍回填
curl -X POST http://localhost:8000/api/v1/people-count/sync \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"date_from":"2026-08-01","date_to":"2026-08-31"}'
# 3. 查詢進度（每幾秒查一次）
curl http://localhost:8000/api/v1/people-count/sync/status/<task_id> \
  -H "Authorization: Bearer <token>"
```

### 9.3 驗證並發安全

可用多進程同時對同一 `(date, hour, ip_address)` 執行 `upsert_people_count_hourly`，確認：
- 最終行數為 1
- 最終 enter/exit 值為某一次寫入的完整對
- 無異常拋出

---

## 10. 已知限制

- 範圍回填任務狀態存於記憶體（`_SYNC_TASKS`），服務重啟後丟失，但可重跑（已有日期自動跳過）
- 攝影機清單硬編碼於 `cctv_sync.py`，新增/刪除攝影機需改碼
- 同步進行中的小時（如今天 8 點，攝影機仍在統計）時，值可能隨攝影機端快照變化，屬資料源性質，非系統缺陷
- `cctv.sync.cron.anytime` 若設為 `*/1`，每次約 60 秒的 30 台全量同步可能跨越分鐘邊界，`max_instances=1` 會跳過重疊觸發



---

## English Version <a id="english-version"></a>

> 🌐 **[English](#english-version)** | [繁體中文（上方完整內容）](#chinese-version)

## Table of Contents

- [1. Overview](#1-overview)
- [2. Sync Mechanism](#2-sync-mechanism)
- [3. Database Schema](#3-database-schema)
- [4. API Reference](#4-api-reference)
- [5. Page Settings (Scheduling)](#5-page-settings-scheduling)
- [6. Concurrency Safety (Dual-Instance)](#6-concurrency-safety-dual-instance)
- [7. File Changes](#7-file-changes)
- [8. Backend Logs](#8-backend-logs)
- [9. Testing Suggestions](#9-testing-suggestions)
- [10. Known Limitations](#10-known-limitations)

---

## 1. Overview

CCTV People Count Sync pulls hourly enter/exit counts from Milesight cameras via ISAPI and writes them to the `people_count_hourly` table in the `WingOnIOT` database, enabling queries and charts on the `/people-count` page.

### Data Flow

```
Milesight Cameras (30 units)
   │  HTTP ISAPI (Digest Auth)
   ▼
cctv_sync.py ──► people_count_hourly table (UPSERT)
                     │
                     ▼
        /api/v1/people-count/* API ──► Frontend Page
```

### Key Features

- **Data Source**: 30 cameras, hardcoded in `cctv_sync.py` as `CCTV_CAMERAS`
- **Credentials**: From `.env` via `CCTV_USERNAME` / `CCTV_PASSWORD`
- **Primary Key**: Snowflake ID (`app/snowflake.py`)
- **Write Method**: `INSERT ... ON DUPLICATE KEY UPDATE` (UPSERT), naturally idempotent
- **Unique Index**: `uk_date_hour_ip (date, hour, ip_address)` prevents duplicate rows for the same camera/hour
- **Scheduled Tasks**: APScheduler with cron expressions that can be **hot-reloaded** (no restart needed)

---

## 2. Sync Mechanism

### 2.1 Three Sync Modes

| Mode | Trigger | Sync Content | Description |
|------|---------|-------------|-------------|
| Immediate Sync | On service startup | Today's data | Background thread, non-blocking |
| Scheduled Sync | APScheduler cron | Today / Yesterday / Monthly backfill | Three independent jobs |
| Manual Sync | HTTP API | Single day / Date range backfill | Requires login + switch enabled |

### 2.2 Scheduled Tasks (Cron Hot-Reload)

Three cron jobs are registered in `app/api/main.py`, all monitored by the `_cron_watcher` background thread (checks DB `sys_config` every 10 seconds, reschedules immediately on change):

| Job ID | Config Key | Default Cron | Action |
|--------|-----------|-------------|--------|
| `anytime` | `cctv.sync.cron.anytime` | `5 * * * *` (5th minute of every hour) | Sync today `sync_today` |
| `yesterday` | `cctv.sync.cron.yesterday` | `5 0 * * *` (00:05 daily) | Sync yesterday full 24h `sync_yesterday` |
| `backfill` | `cctv.sync.cron.backfill` | `10 0 * * *` (00:10 daily) | Backfill missing dates this month `backfill_current_month` |

**Execution Logic** (each job runner):
1. Check master switch `cctv.sync.enabled`; skip if `N`
2. Log `[CCTV] 定時任務 {job_id} 開始執行`
3. Execute business function
4. Log `[CCTV] 定時任務 {job_id} 執行完成`

**Hot-Reload Mechanism**:
- `_cron_watcher` thread reads three cron params from DB every 10 seconds
- Compares with last known values; if changed, immediately calls `reschedule_job`
- Logs `[CCTV] cron {job_id} 已從 {old} 熱更新為 {new}`
- **No restart needed after changing cron** (takes effect in ~10-12 seconds)

**Parallelism**: APScheduler uses `ThreadPoolExecutor`; three jobs run independently. Same job defaults to `max_instances=1`, so if the previous sync (~60s for 30 cameras) isn't finished, the next trigger is skipped.

---

## 3. Database Schema

### 3.1 people_count_hourly

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGINT | Snowflake primary key (non-auto-increment) |
| `date` | DATE | Date |
| `hour` | TINYINT | Hour 0-23 |
| `ip_address` | VARCHAR | Camera IP |
| `channel_name` | VARCHAR | Camera name |
| `enter_count` | INT | Hourly enter count |
| `exit_count` | INT | Hourly exit count |
| `updated_at` | DATETIME | Last update time |

**Indexes**:
- `PRIMARY (id)` — unique
- `uk_date_hour_ip (date, hour, ip_address)` — **unique**, drives UPSERT, prevents duplicates
- `idx_date_channel_hour (date, channel_name, hour)` — non-unique, speeds up filtered queries

#### DDL

```sql
CREATE TABLE `people_count_hourly` (
  `id` bigint(20) unsigned NOT NULL COMMENT 'Snowflake primary key (64-bit, generated by application)',
  `date` date NOT NULL COMMENT 'Statistics date (YYYY-MM-DD)',
  `hour` tinyint(4) NOT NULL COMMENT 'Hour (0~23, 0 represents 00:00~01:00)',
  `ip_address` varchar(20) NOT NULL COMMENT 'Camera IP address',
  `channel_name` varchar(64) NOT NULL COMMENT 'Channel name (e.g., 1/F Lift)',
  `enter_count` int(11) NOT NULL DEFAULT 0 COMMENT 'Hourly enter count',
  `exit_count` int(11) NOT NULL DEFAULT 0 COMMENT 'Hourly exit count',
  `created_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) COMMENT 'Created time',
  `updated_at` datetime(3) NOT NULL DEFAULT current_timestamp(3) ON UPDATE current_timestamp(3) COMMENT 'Updated time (last sync timestamp)',
  PRIMARY KEY (`id`) COMMENT 'Snowflake primary key',
  UNIQUE KEY `uk_date_hour_ip` (`date`,`hour`,`ip_address`) COMMENT 'Unique key per date/hour/camera, prevents duplicates (for UPSERT)',
  KEY `idx_date_channel_hour` (`date`,`channel_name`,`hour`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_uca1400_ai_ci COMMENT='CCTV people count hourly detail table (synced hourly, only writes completed hours)';
```

### 3.2 sys_config (4 new rows)

| config_name | config_key | Default | Description |
|-------------|-----------|---------|-------------|
| CCTV Sync Switch | `cctv.sync.enabled` | `Y` | Y=enabled / N=disabled |
| CCTV Anytime Cron | `cctv.sync.cron.anytime` | `5 * * * *` | Sync today by cron |
| CCTV Yesterday Cron | `cctv.sync.cron.yesterday` | `5 0 * * *` | Sync yesterday at 00:05 |
| CCTV Backfill Cron | `cctv.sync.cron.backfill` | `10 0 * * *` | Backfill this month at 00:10 |

Init SQL: `mqttapi/sql/init_cctv_sync_config.sql`

---

## 4. API Reference

All endpoints require `Authorization: Bearer <token>` after login.

### 4.1 Get Token

```http
POST /api/v1/auth/login
Content-Type: application/json

{"username": "admin", "password": "<password>"}
```

Response:
```json
{"token": "eyJhbGciOiJIUzI1NiIs..."}
```

### 4.2 Manual Sync

#### Single Day Sync (synchronous)

```http
POST /api/v1/people-count/sync
Authorization: Bearer <token>
Content-Type: application/json

{"date": "2026-09-01"}
```

- `date` defaults to today
- Executes synchronously; response contains sync stats:

```json
{"date": "2026-09-01", "cameras": 30, "rows": 720, "failed": []}
```

#### Range Backfill (background execution)

```http
POST /api/v1/people-count/sync
Authorization: Bearer <token>
Content-Type: application/json

{"date_from": "2026-01-01", "date_to": "2026-06-30"}
```

Response (returns `task_id` immediately, runs in background):
```json
{
  "task_id": "3ad1c6e820844b95974231432ee5b026",
  "date_from": "2026-01-01",
  "date_to": "2026-06-30",
  "status": "running",
  "message": "Range backfill started in background, query /api/v1/people-count/sync/status/{task_id}"
}
```

**Validation Rules**:

| Scenario | Response |
|----------|----------|
| Only `date_from` or `date_to` provided | 400 Both required |
| `date_from` > `date_to` | 400 Invalid range |
| Range > 183 days (6 months) | 400 Range limit exceeded |
| Master switch is N | 400 Sync disabled |
| Not logged in | 401 |

#### Query Backfill Progress

```http
GET /api/v1/people-count/sync/status/{task_id}
Authorization: Bearer <token>
```

Response:
```json
{
  "task_id": "...",
  "date_from": "2026-01-01",
  "date_to": "2026-06-30",
  "status": "running",
  "progress": 33,
  "done_days": 1,
  "total_days": 3,
  "current_date": "2026-08-26",
  "started_at": "...",
  "result": null,
  "error": null
}
```

> Note: Task state is in-memory, lost on service restart (can be re-run; existing dates are skipped automatically).

### 4.3 Query Endpoints (existing)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/people-count/hourly` | Paginated list (date_from/date_to/hour/ip_address/channel_name/limit/offset) |
| GET | `/api/v1/people-count/channels` | Camera list (for filter dropdown) |
| GET | `/api/v1/people-count/stats/hourly` | Hourly aggregation (chart) |
| GET | `/api/v1/people-count/stats/daily` | Daily aggregation (chart) |
| GET | `/api/v1/people-count/stats/channel` | Per-channel aggregation (chart) |

---

## 5. Page Settings (Scheduling)

### 5.1 Access Config Page

Frontend menu: **System Management > Config Settings** (route `system/config`, component `system/ConfigManage.vue`)

### 5.2 Setting the Three Crons

1. Find the three entries on the Config Settings page
2. Click "Edit", change "Config Value" (config_value) to a **5-field cron expression**
3. After saving, **no restart needed** — takes effect in ~10-12 seconds (`_cron_watcher` hot-reload)

| Config Name | Config Key | Suggested Value |
|-------------|-----------|----------------|
| CCTV Anytime Cron | `cctv.sync.cron.anytime` | `5 * * * *` |
| CCTV Yesterday Cron | `cctv.sync.cron.yesterday` | `5 0 * * *` |
| CCTV Backfill Cron | `cctv.sync.cron.backfill` | `10 0 * * *` |

### 5.3 Cron Expression Examples

| Expression | Meaning | Note |
|-----------|---------|------|
| `*/1 * * * *` | Every minute | ~60s for 30 cameras; not recommended long-term |
| `*/5 * * * *` | Every 5 minutes (at 0,5,10,...) | Triggers at 0,5,10,15,... |
| `5 * * * *` | Every hour at :05 | Default |
| `*/10 * * * *` | Every 10 minutes | Triggers at 0,10,20,30,40,50 |
| `5 0 * * *` | Daily at 00:05 | yesterday default |

> **Important**: Cron is a **time-point match**, NOT "delay N minutes from edit time". E.g., editing to `*/5` at 11:27 triggers next at 11:30.

### 5.4 Master Switch

"CCTV People Count Sync Switch" (`cctv.sync.enabled`) in Config Settings:
- `Y`: Enable scheduled sync and manual sync
- `N`: Disable (scheduled tasks skip; manual sync API returns 400)

---

## 6. Concurrency Safety (Dual-Instance)

### 6.1 Design Guarantee

The table uses the unique index `uk_date_hour_ip (date, hour, ip_address)` with UPSERT:

```sql
INSERT INTO people_count_hourly (id, date, hour, ip_address, channel_name, enter_count, exit_count)
VALUES (...)
ON DUPLICATE KEY UPDATE
    channel_name = VALUES(channel_name),
    enter_count  = VALUES(enter_count),   -- overwrite, not accumulate
    exit_count   = VALUES(exit_count),
    updated_at   = NOW(3)
```

- **No accumulation**: `VALUES(enter_count)` is assignment, not `enter_count + VALUES(...)`
- **No mixing**: InnoDB row-level lock serializes concurrent UPSERTs on the same row; each UPDATE sets all columns atomically
- **Single-instance dedup**: APScheduler `max_instances=1` prevents re-entrant execution

### 6.2 Concurrency Test Results (Actual)

Multi-process simulation: multiple instances UPSERT the same row (date=2026-09-01, hour=8, ip=10.98.127.26) with different values:

| Scenario | Writes | Final Rows | Final Value | Result |
|----------|--------|-----------|-------------|--------|
| 3 instances × 50 | 150 | 1 | Complete pair (10,5) from one instance | ✅ |
| 4 instances × 50 | 200 | 1 | Complete pair (33,17) | ✅ |
| 4 instances × 200 | 800 | 1 | Complete pair (7,99) | ✅ |
| 4 instances × 500 | 2000 | 1 | Complete pair (10,5) | ✅ |

**Verified Conclusions**:
- Row count always = 1 (no accumulation; 2000 concurrent writes still = 1 row)
- Final value = **complete (enter, exit) pair** from one instance (no mixing)
- Final value ≠ sum of all instances (not accumulated)
- All instances: zero errors (no deadlocks, no exceptions)

**Dual-Instance Deployment Notes**:
- Each instance must have a different `SNOWFLAKE_WORKER_ID` in `.env` (e.g., 1 and 2) to avoid unnecessary lock contention
- If both instances pull the same cameras, bandwidth and DB write load double; consider running cron on only one instance or splitting camera lists

---

## 7. File Changes

### New Files

| File | Description |
|------|-------------|
| `mqttapi/app/cctv_sync.py` | **Core sync service**: camera list, ISAPI fetch (`fetch_camera_day`), single-day sync (`sync_date`), today/yesterday/monthly/range backfill functions |
| `mqttapi/app/snowflake.py` | Snowflake ID generator (`Snowflake` class, `next_id()`, `init_snowflake(worker_id)`) |
| `mqttapi/sql/init_cctv_sync_config.sql` | Initialize 4 `sys_config` rows |

### Modified Files

| File | Changes |
|------|---------|
| `mqttapi/app/config.py` | Added `cctv_username`, `cctv_password`, `snowflake_worker_id` to `Settings` |
| `mqttapi/app/db.py` | Added `upsert_people_count_hourly` (UPSERT), `get_existing_people_count_dates`, `get_existing_people_count_dates_range` |
| `mqttapi/app/api/main.py` | Lifespan registers 3 APScheduler cron jobs; `_cron_watcher` thread hot-reload; startup immediate sync in background; `[CCTV]` prefixed logs |
| `mqttapi/app/api/routes/people_count.py` | Added `POST /people-count/sync` (single-day + range backfill), `GET /people-count/sync/status/{task_id}` (progress); `PeopleCountSyncBody` model |
| `mqttapi/api_server.py` | Configured root logger so `[CCTV]` info logs output to console |
| `mqttapi/requirements.txt` | Added `APScheduler`, `requests`, `xmltodict` |
| `.env` | Added `CCTV_USERNAME`, `CCTV_PASSWORD`, `SNOWFLAKE_WORKER_ID=1` |

### Dependencies

```
APScheduler   # Scheduled tasks
requests      # HTTP requests (camera ISAPI)
xmltodict     # XML response parsing
```

### Database Changes

1. Execute `mqttapi/sql/init_cctv_sync_config.sql` to seed config parameters
2. Confirm `people_count_hourly` has the `uk_date_hour_ip` unique index (required by UPSERT)

---

## 8. Backend Logs

### 8.1 Configuration

`api_server.py` configures the root logger at `INFO` level on startup. All `[CCTV]`-prefixed logs are output to console. Third-party libraries (`apscheduler`, `urllib3`) are set to `WARNING` to reduce noise.

### 8.2 Log Example

```
2026-09-02 11:24:36 | INFO | app.api.main | [CCTV] APScheduler started, scheduled syncs registered
2026-09-02 11:24:37 | INFO | app.api.main | [CCTV] Cron watcher thread started, initial schedule: {...}
2026-09-02 11:25:00 | INFO | app.api.main | [CCTV] Scheduled task anytime started
2026-09-02 11:25:42 | INFO | app.cctv_sync | CCTV sync 2026-09-02: 30 cameras, 720 rows, 0 failed
2026-09-02 11:25:42 | INFO | app.api.main | [CCTV] Scheduled task anytime completed
```

### 8.3 Common Log Messages

| Message | Meaning |
|---------|---------|
| `[CCTV] 定時任務 {job} 開始執行` | Cron triggered, sync started |
| `[CCTV] 定時任務 {job} 執行完成` | Sync completed |
| `[CCTV] 定時任務 {job} 執行失敗: {err}` | Sync failed (with stack trace) |
| `[CCTV] cron {job} 已從 {a} 熱更新為 {b}` | Page cron change took effect |
| `[CCTV] 同步已停用，跳過 {job}` | Master switch is N |
| `CCTV sync {date}: {n} cameras, {m} rows, {f} failed` | Single-day sync stats; failed = cameras with connection errors |

---

## 9. Testing Suggestions

### 9.1 Verify Hot-Reload

1. Start service; confirm log `[CCTV] cron 監聽線程已啟動`
2. Change any cron on the config page (e.g., `cctv.sync.cron.anytime` to `*/5 * * * *`)
3. Within 10-12 seconds, log shows `[CCTV] cron anytime 已從 5 * * * * 熱更新為 */5 * * * *`
4. Observe `開始執行` at the next 5-minute trigger point

### 9.2 Verify Range Backfill

```bash
# 1. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<password>"}'
# 2. Trigger range backfill
curl -X POST http://localhost:8000/api/v1/people-count/sync \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"date_from":"2026-08-01","date_to":"2026-08-31"}'
# 3. Query progress (check every few seconds)
curl http://localhost:8000/api/v1/people-count/sync/status/<task_id> \
  -H "Authorization: Bearer <token>"
```

### 9.3 Verify Concurrency Safety

Run `upsert_people_count_hourly` on the same `(date, hour, ip_address)` from multiple processes simultaneously; confirm:
- Final row count = 1
- Final enter/exit is a complete pair from one write
- No exceptions thrown

---

## 10. Known Limitations

- Range backfill task state is in-memory (`_SYNC_TASKS`), lost on restart (can be re-run; existing dates auto-skip)
- Camera list is hardcoded in `cctv_sync.py`; adding/removing cameras requires code change
- Syncing an in-progress hour (e.g., today's hour 8 while cameras still counting) may yield values that change with the camera's snapshot — this is a data source characteristic, not a system bug
- If `cctv.sync.cron.anytime` is set to `*/1`, the ~60s full sync of 30 cameras may overlap the next minute; `max_instances=1` skips overlapping triggers
