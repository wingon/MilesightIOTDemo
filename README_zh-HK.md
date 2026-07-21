# MilesightAnalysis · 333 IOT Console

Milesight 設備 MQTT 上報 → 入庫 → FastAPI 查詢 → **333 IOT Console**（Vue）管理面板。

| 目錄 | 說明 |
|------|------|
| [`mqttapi/`](./mqttapi/) | Mosquitto 設定、MQTT 訂閱入庫（`subscriber.py`）、FastAPI（`api_server.py`）、Ubuntu 部署檔 |
| [`frontend/`](./frontend/) | 333 IOT Console（Vue 3 + Ant Design Vue） |

更細的 MQTT / 表結構說明見 [`mqttapi/README.md`](./mqttapi/README.md)；正式機架構與迭代見 [`mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_zh-HK.md`](./mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_zh-HK.md)。

英文版：[README.md](./README.md)

---

## 架構一覽

```text
感測器 / UG65 ──MQTT :1883──► Mosquitto
                                  │
                                  ▼
                           subscriber.py ──► MariaDB (tof / ug65)
                                                  │
前端 (Vite :3000 / Nginx :80) ◄── HTTP /api ── FastAPI :8000
```

| 組件 | 本機開發 | 正式部署（Ubuntu） |
|------|----------|-------------------|
| **MQTT Broker** | Docker Compose（`mqttapi/docker-compose.yml`） | `apt` 安裝 Mosquitto + systemd |
| **MQTT 入庫** | `python subscriber.py` | `milesight-mqtt-subscriber.service` |
| **API** | `python api_server.py`（`:8000`） | `milesight-api.service`（僅 `127.0.0.1:8000`） |
| **前端** | `npm run dev`（`:3000`，代理 `/api`） | Nginx 靜態 + 反代 `/api`、`/health` |
| **資料庫** | 本機 / 既有 MariaDB | 本機 MariaDB（建議只聽 `127.0.0.1`） |

**進程務必分開：** 訂閱入庫 ≠ Web API；兩者都連 MQTT / DB，但職責不同。

---

## 開發步驟（本機）

前提：Python 3.10+、Node.js 18+、Docker Desktop（跑 Mosquitto）、可連線的 MariaDB。

### 1. MQTT Broker（Mosquitto）

```powershell
cd mqttapi

# Windows 首次：生成 passwd（帳密預設 root / root）
docker run --rm -v "${PWD}/mosquitto:/mosquitto/config" eclipse-mosquitto:2 `
  sh -c "rm -f /mosquitto/config/passwd && mosquitto_passwd -b -c /mosquitto/config/passwd root root && chmod 644 /mosquitto/config/passwd"

docker compose up -d
```

Broker 對外埠：**1883**。設備端請填本機**區網 IP**（不要填 `127.0.0.1`，那是設備自己）。

### 2. 環境變數與資料庫

```powershell
cd mqttapi
copy .env.example .env
# 依實際編輯 MQTT_*、DB_*（預設連 127.0.0.1）

pip install -r requirements.txt
python init_db.py
```

### 3. MQTT 訂閱入庫

另開終端，保持運行：

```powershell
cd mqttapi
python subscriber.py
```

訂閱主題（見 `.env`）：

- People Counter / VS135 等：`em/+/status` → 表 `tof`
- UG65 閘道：`milesight/ug65/uplink/+` → 表 `ug65`

可選測試發布：

```powershell
python publisher_test.py --distance 1800 --temperature 24.5
```

### 4. FastAPI（後端）

再開一個終端：

```powershell
cd mqttapi
python api_server.py
```

| 項目 | URL |
|------|-----|
| Swagger | http://127.0.0.1:8000/docs |
| 健康檢查 | http://127.0.0.1:8000/health |
| 統計 | http://127.0.0.1:8000/api/v1/stats |

### 5. 前端（333 IOT Console）

```powershell
cd frontend
npm install
npm run dev
```

瀏覽器開啟：**http://127.0.0.1:3000**  
Vite 已將 `/api`、`/health` 代理到 `http://127.0.0.1:8000`。

常用腳本：

```powershell
npm run build        # 生產建置 → dist/
npm run build:prod
npm run preview      # 預覽建置結果
```

### 本機啟動檢查清單

1. `docker compose ps` — Mosquitto 在跑  
2. `subscriber.py` — 無連線錯誤  
3. `curl http://127.0.0.1:8000/health` — 正常  
4. 前端 `:3000` 能打開並拉到資料  

---

## 部署步驟（Ubuntu 正式機）

完整細節、防火牆、HTTPS、版本回滾見：  
[`mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_zh-HK.md`](./mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_zh-HK.md)  
（英文：[Architecture_and_Deployment_readme_en.md](./mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_en.md)）

路徑假設（可改）：

| 項目 | 路徑 |
|------|------|
| 程式碼 | `/opt/milesight/MilesightAnalysis` |
| Python venv | `/opt/milesight/venv` |
| Console | `/opt/milesight/console/current` → `releases/<ver>/` |
| mqttapi `.env` | `/opt/milesight/MilesightAnalysis/mqttapi/.env` |

### 0. 系統準備

```bash
sudo apt update
sudo apt install -y nginx mosquitto mosquitto-clients \
  mariadb-server python3-venv python3-pip rsync
sudo systemctl enable --now nginx mosquitto mariadb

sudo useradd -r -m -d /opt/milesight -s /bin/bash milesight || true
# 將本倉庫放到 /opt/milesight/MilesightAnalysis
sudo chown -R milesight:milesight /opt/milesight
```

> 正式機 **Mosquitto 用 apt，不要再用 Docker** 佔 1883。

### 1. MariaDB

```bash
sudo mysql -e "CREATE DATABASE IF NOT EXISTS milesight CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
# 建立應用帳號並授權（正式環境請改強密碼）

cd /opt/milesight/MilesightAnalysis/mqttapi
sudo -u milesight cp -n .env.example .env
# 編輯 .env：MQTT_HOST=127.0.0.1、DB_*、與 Mosquitto 帳密一致
```

### 2. MQTT（Mosquitto apt）

```bash
sudo cp /opt/milesight/MilesightAnalysis/mqttapi/deploy/ubuntu/mosquitto/milesight.conf \
  /etc/mosquitto/conf.d/milesight.conf

sudo mosquitto_passwd -b -c /etc/mosquitto/passwd root root   # 正式請改密碼
sudo chown root:mosquitto /etc/mosquitto/passwd
sudo chmod 640 /etc/mosquitto/passwd

sudo systemctl restart mosquitto
ss -lntp | grep 1883   # 應為 0.0.0.0:1883
```

設備 Broker 填 **Ubuntu 區網 IP:1883**。防火牆需放行 `1883/tcp`（及 `80`/`443`）。

### 3. API + MQTT Subscriber（systemd）

```bash
sudo -u milesight python3 -m venv /opt/milesight/venv
sudo -u milesight /opt/milesight/venv/bin/pip install -U pip
sudo -u milesight /opt/milesight/venv/bin/pip install -r \
  /opt/milesight/MilesightAnalysis/mqttapi/requirements.txt

cd /opt/milesight/MilesightAnalysis/mqttapi
sudo -u milesight /opt/milesight/venv/bin/python init_db.py

sudo cp deploy/ubuntu/systemd/milesight-api.service /etc/systemd/system/
sudo cp deploy/ubuntu/systemd/milesight-mqtt-subscriber.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now milesight-api milesight-mqtt-subscriber
curl -s http://127.0.0.1:8000/health
```

`milesight-mqtt-subscriber` **只跑一個實例**；`MQTT_CLIENT_ID` 在 Broker 上必須唯一。

### 4. 前端建置 + Nginx

```bash
sudo mkdir -p /opt/milesight/console/releases
VER="console-$(date +%Y%m%d)_01"

cd /opt/milesight/MilesightAnalysis/frontend
npm ci
npm run build
sudo rsync -a --delete dist/ "/opt/milesight/console/releases/${VER}/"
sudo ln -sfn "/opt/milesight/console/releases/${VER}" /opt/milesight/console/current
sudo chown -R www-data:www-data /opt/milesight/console

sudo cp /opt/milesight/MilesightAnalysis/mqttapi/deploy/ubuntu/nginx/333-iot-console.conf \
  /etc/nginx/sites-available/333-iot-console.conf
sudo ln -sf /etc/nginx/sites-available/333-iot-console.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

瀏覽器：`http://<ubuntu-lan-ip>/`  
靜態站點同源請求 `/api`，由 Nginx 轉到 FastAPI。

### 5. 日常運維（摘要）

```bash
sudo journalctl -u mosquitto -f
sudo journalctl -u milesight-api -f
sudo journalctl -u milesight-mqtt-subscriber -f

sudo systemctl restart milesight-api milesight-mqtt-subscriber
```

| 更新對象 | 做法 |
|----------|------|
| **前端** | 新建 `releases/<ver>` → 切換 `current` 符號連結（可回滾） |
| **API / Subscriber** | `git pull` 後 `systemctl restart` 對應服務 |
| **Mosquitto** | 改 conf / passwd 後 `systemctl restart mosquitto` |

`.env`、Mosquitto 密碼、資料庫 **不要**打進每個前端 release 目錄。

---

## 設備 MQTT 填寫提醒

| 項目 | 建議 |
|------|------|
| Broker 地址 | 跑 Mosquitto 那台機器的**區網 IP** |
| 端口 | `1883` |
| 帳密 | 與 `passwd` / `.env` 一致（開發預設 `root`/`root`） |
| VS135 等主題 | `em/<設備SN>/status` |
| UG65 主題 | `milesight/ug65/uplink/+`（閘道側依實際配置） |
| TLS | 內網開發通常關閉 |

---

## 相關文件

| 文件 | 內容 |
|------|------|
| [`mqttapi/README.md`](./mqttapi/README.md) | MQTT 主題、表結構、本機快速開始、API 列表 |
| [`mqttapi/README_en.md`](./mqttapi/README_en.md) | 同上（英文） |
| [`mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_zh-HK.md`](./mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_zh-HK.md) | Ubuntu 完整部署與版本迭代 |
| [`frontend/README.md`](./frontend/README.md) | 前端 stack 與 i18n 簡述 |
