# 人流計數可視化圖表 — 數據計算邏輯說明

> 適用頁面：`/people-count/view`（視圖頁）
> 查詢條件範例：2026-09-02 00:00 ~ 2026-09-08 23:00
> 數據源：`people_count_hourly` 表（由 CCTV 攝影機 ISAPI 每小時同步）

---

## 數據流概述

```
Milesight 攝影機 (ISAPI)
    ↓ cctv_sync.py — fetch_camera_day() 拉取逐時進出數據
    ↓ db.py — upsert_people_count_hourly() 寫入 MySQL
MySQL: people_count_hourly 表
    ↓ db.py — _load_people_count_rows() 查詢明細
    ↓ people_count_aggregate.py — aggregate() 聚合計算
GET /api/v1/people-count/stats/overview
    ↓ 前端 peopleCountAggregateCharts.ts — build*Option() 生成 ECharts 配置
    ↓ ChartPanel.vue 渲染
页面顯示 7 個圖表 + 6 個 KPI
```

**關鍵表結構** `people_count_hourly`：

| 欄位 | 類型 | 說明 |
|------|------|------|
| date | DATE | 日期 |
| hour | INT | 小時 (0-23) |
| channel_name | VARCHAR | 通道名稱（如 "G/F Lift"） |
| ip_address | VARCHAR | 攝影機 IP |
| enter_count | INT | 該小時進入人數 |
| exit_count | INT | 該小時離開人數 |

---

## 通用聚合邏輯

所有圖表共用同一個 API 端點 `GET /api/v1/people-count/stats/overview`，後端 `aggregate()` 函數計算以下內容：

1. **過濾**：按日期範圍、時段範圍、通道名、IP 地址過濾原始明細
2. **日期範圍語義**：跨多日時，首日 `hour >= hour_from`、末日 `hour <= hour_to`、中間日全天
3. **缺失日補 0**：確保日期連續（趨勢圖不跳點）

---

## 各圖表詳細計算

### 圖表 1：每日進出趨勢

- **展示**：雙折線圖（進入 + 離開），帶區域填充和數值標籤
- **數據字段**：`ov.daily[].enter`、`ov.daily[].exit`
- **計算方式**：
  ```
  對每個日期 d：
    enter(d) = SUM(所有 channel_name 在日期 d 的 enter_count)
    exit(d)  = SUM(所有 channel_name 在日期 d 的 exit_count)
    total(d) = enter(d) + exit(d)
  ```
- **缺失日處理**：若某日無數據，enter/exit/total 均補 0
- **X 軸**：日期（MM-DD 格式），間距均勻

> **注意**：此圖與「每日進入與離開」數據完全相同，僅視覺呈現不同（折線 vs 柱狀）。已合併刪除。

---

### 圖表 2：24 時進出人數

- **展示**：分組柱狀圖（進入 + 離開），帶數值標籤
- **數據字段**：`ov.hour[].enter`、`ov.hour[].exit`
- **計算方式**：
  ```
  對每個小時 h (0-23)：
    enter(h) = SUM(所有日期、所有 channel 在該小時 h 的 enter_count)
    exit(h)  = SUM(所有日期、所有 channel 在該小時 h 的 exit_count)
  ```
- **性質**：所有天的合計（非日均），數值會較大
- **顯示限制**：若超過 6 個時段，僅顯示最近 6 個（避免標籤擁擠）

---

### 圖表 3：各通道總流量 Top 5

- **展示**：分組橫條圖（進入 + 離開），按通道名排列
- **數據字段**：`ov.channel[0:5]`
- **計算方式**：
  ```
  對每個通道 ch：
    enter(ch) = SUM(該通道所有日期所有小時的 enter_count)
    exit(ch)  = SUM(該通道所有日期所有小時的 exit_count)
    total(ch) = enter(ch) + exit(ch)

  排序：按 total 降序，取前 5 個通道
  ```
- **注意**：圖表顯示的是各通道的 enter 和 exit 分開的色條，但排序依據是 total

---

### 圖表 4：各樓層人次分布（不含樓梯）

- **展示**：分組柱狀圖（進入 + 離開），按樓層排列
- **數據字段**：`ov.floor[].enter`、`ov.floor[].exit`
- **計算方式**：
  ```
  對每個樓層 f（B1/F, G/F, 1/F ~ 6/F）：
    enter(f) = SUM(所有「非樓梯」且 floor_of(ch)=f 的通道的 enter)
    exit(f)  = SUM(所有「非樓梯」且 floor_of(ch)=f 的通道的 exit)
    total(f) = enter(f) + exit(f)
  ```
- **排除樓梯的原因**：樓梯通道關聯兩個樓層（如 "G/F <-> B1/F"），若不排除會導致重複計算
- **樓層解析**：`floor_of()` 從通道名開頭提取樓層（正則 `^(B1/F|G/F|[0-6]/F)`）
- **包含的通道類型**：電梯 (lift) + 出入口/大堂 (entrance)，不含樓梯 (stairs)

**G/F 的 37,373 組成**（enter + exit 合計）：

| 通道名 | 類型 |
|--------|------|
| G/F 吳松街出口 (CS) | 出入口 |
| G/F Lift | 電梯 |
| G/F 正門出口 01 | 出入口 |
| G/F 職員出口 | 出入口 |
| G/F 輪椅出口 | 出入口 |
| G/F 正門出口 02 | 出入口 |
| G/F 近隧道出口 | 出入口 |

以上 7 個通道的 SUM(enter + exit) = 37,373

---

### 圖表 5：通道類型分布

- **展示**：甜甜圈圖（圓環），帶百分比標籤
- **數據字段**：`ov.channelType[]`
- **分類邏輯**（`channel_type()` 函數）：

  | 條件 | 分類結果 | 標籤 |
  |------|---------|------|
  | 通道名含 `"lift"`（不區分大小寫） | `lift` | 電梯 |
  | 通道名含 `<`、`>`、`(up`、`(dw`、`→`、`←` | `stairs` | 樓梯 |
  | 其他 | `entrance` | 出入口/大堂 |

- **計算方式**：
  ```
  對每種類型 t (lift/stairs/entrance)：
    total(t) = SUM(所有歸類為 t 的通道的 enter + exit)
    count(t) = 歸類為 t 的通道數量
  ```

**29 台攝影機分類結果**：

| 類型 | 標籤 | 數量 | 通道列表 |
|------|------|------|---------|
| lift | 電梯 | 8 | 各樓層 Lift |
| stairs | 樓梯 | 14 | 含 `<-`/`->`/`↔`/`→`/`←` 符號的樓梯通道 |
| entrance | 出入口/大堂 | 7 | 正門出口、吳松街出口、大廈大堂、職員出口、輪椅出口、近隧道出口 |

---

### 圖表 6：每日進入與離開

- **展示**：分組柱狀圖（進入 + 離開），tooltip 顯示淨流（進−出）
- **數據字段**：`ov.daily[].enter`、`ov.daily[].exit`
- **計算方式**：與「每日進出趨勢」完全相同
  ```
  對每個日期 d：
    enter(d) = SUM(所有 channel 在日期 d 的 enter_count)
    exit(d)  = SUM(所有 channel 在日期 d 的 exit_count)
    net(d)   = enter(d) - exit(d)   // 顯示在 tooltip
  ```

---

### 圖表 7：星期 × 小時熱力

- **展示**：熱力圖（色階表達流量大小）
- **數據字段**：`ov.weekdayHour[]`
- **計算方式**：
  ```
  對每組 (weekday, hour)：
    total(w, h) = SUM(所有屬於星期 w 的日期、小時 h 的 enter + exit)
                  ÷ 星期 w 出現的天數

  即：該星期幾 × 該小時的「日均總人次」
  ```
- **性質**：日均值（非總量），不同星期的天數不同時會自動調整

---

### 圖表 8：累計人次

- **展示**：面積折線圖，帶數值標籤和尾端標籤
- **數據字段**：`ov.daily[].total`
- **計算方式**：
  ```
  cumulative(第1天) = total(第1天)
  cumulative(第2天) = cumulative(第1天) + total(第2天)
  cumulative(第n天) = cumulative(第n-1天) + total(第n天)
  ```
- **標籤間隔**：點數 ≤ 7 時每個點都顯示標籤；點數 > 7 時自動計算間隔避免重疊
- **尾端標籤**：最後一個點以 `endLabel` 在右側顯示累計總值

---

## KPI 卡片計算

| KPI | 計算方式 |
|-----|---------|
| 統計總人次 | `SUM(all enter) + SUM(all exit)` |
| 平均每日人次 | `total_people ÷ 天數` |
| 單日最多人次 | `max(daily[].total)` |
| 最繁忙時段 | `max(hour[].total)` 對應的 hour |
| 最多人流通道 | `channel[0]`（按 total 降序第一） |
| 最多人流樓層 | `max(floor[].total)` 對應的 floor |

---

## 通道名稱與樓層對應表

| 樓層 | 通道名 |
|------|--------|
| B1/F | B1/F <- G/F (dw)、B1/F Lift |
| G/F | G/F 吳松街出口 (CS)、G/F Lift、G/F 正門出口 01、G/F 職員出口、G/F <- B1/F (up)、G/F 輪椅出口、G/F 正門出口 02、G/F 近隧道出口 |
| 1/F | 1/F Lift、1/F <- G/F (up)、1/F -> G/F (dw) |
| 2/F | 2/F <- 1/F (up)、2/F 大廈大堂、2/F Lift、2/F <-> 1/F (up/dw)、2/F -> 1/F (dw) |
| 3/F | 3/F Lift、3/F -> 2/F (dw)、3/F <- 2/F (up) |
| 4/F | 4/F Lift、4/F → 5/F (up)、4/F → 3/F (dw) |
| 5/F | 5/F Lift、5/F <- 4/F (up)、5/F -> 4/F (dw) |
| 6/F | 6/F <- 5/F (up)、6/F Lift、6/F -> 5/F (dw) |

---

## 常見疑問

### Q: 為什麼「各樓層人次分布」的數字比「每日進出趨勢」大？

A: 兩者的度量維度不同：
- 「每日進出趨勢」的進入人數 = **全部樓層所有通道**的 enter 總和
- 「各樓層人次分布」的樓層數字 = **該樓層所有非樓梯通道**的 enter + exit 總和

例如 G/F 的 37,373 = 該樓層 7 個通道的 (enter + exit)，而「每日進入」的 32,815 是全部通道的 enter 總和。exit 部分使得樓層數字更大。

### Q: 為什麼「各通道總流量 Top 5」的 G/F 通道只有 14,083，但樓層分布顯示 37,373？

A: Top 5 顯示的是**單一最高通道**的 enter 數據，而樓層分布是**該樓層全部通道**的 enter + exit 總和。14,083 只是 G/F 其中一個通道的 enter，37,373 是 G/F 全部 7 個通道的 enter + exit。

### Q: 樓梯通道的數據去哪了？

A: 樓梯通道（如 "G/F <-> B1/F"）被排除在「各樓層人次分布」之外，因為它關聯兩個樓層，直接計入會導致重複計算。樓梯數據單獨出現在：
- 「通道類型分布」甜甜圈圖（stairs 分類）
- 樓梯流向桑基圖（如有啟用）
- 「各通道總流量 Top 5」（如流量夠大）
