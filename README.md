# MilesightAnalysis · 333 IOT Console

Milesight device MQTT uplink → database → FastAPI queries → **333 IOT Console** (Vue) admin panel.

| Directory | Description |
|-----------|-------------|
| [`mqttapi/`](./mqttapi/) | Mosquitto config, MQTT subscribe & ingest (`subscriber.py`), FastAPI (`api_server.py`), Ubuntu deploy files |
| [`frontend/`](./frontend/) | 333 IOT Console (Vue 3 + Ant Design Vue) |

For MQTT topics and table details, see [`mqttapi/README.md`](./mqttapi/README.md). For production architecture and iteration, see [`mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_zh-HK.md`](./mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_zh-HK.md) (English: [Architecture_and_Deployment_readme_en.md](./mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_en.md)).

Chinese (Hong Kong Traditional): [`README_zh-HK.md`](./README_zh-HK.md)

---

## Architecture Overview

```text
Sensors / UG65 ──MQTT :1883──► Mosquitto
                                  │
                                  ▼
                           subscriber.py ──► MariaDB (tof / ug65)
                                                  │
Frontend (Vite :3000 / Nginx :80) ◄── HTTP /api ── FastAPI :8000
```

| Component | Local development | Production (Ubuntu) |
|-----------|-------------------|---------------------|
| **MQTT Broker** | Docker Compose (`mqttapi/docker-compose.yml`) | `apt` Mosquitto + systemd |
| **MQTT ingest** | `python subscriber.py` | `milesight-mqtt-subscriber.service` |
| **API** | `python api_server.py` (`:8000`) | `milesight-api.service` (bind `127.0.0.1:8000` only) |
| **Frontend** | `npm run dev` (`:3000`, proxies `/api`) | Nginx static + reverse proxy `/api`, `/health` |
| **Database** | Local / existing MariaDB | Local MariaDB (prefer listen on `127.0.0.1` only) |

**Keep processes separate:** MQTT ingest ≠ Web API. Both talk to MQTT / DB, but they have different roles.

---

## Development (local)

Prerequisites: Python 3.10+, Node.js 18+, Docker Desktop (for Mosquitto), reachable MariaDB.

### 1. MQTT Broker (Mosquitto)

```powershell
cd mqttapi

# Windows first run: generate passwd (default credentials root / root)
docker run --rm -v "${PWD}/mosquitto:/mosquitto/config" eclipse-mosquitto:2 `
  sh -c "rm -f /mosquitto/config/passwd && mosquitto_passwd -b -c /mosquitto/config/passwd root root && chmod 644 /mosquitto/config/passwd"

docker compose up -d
```

Broker port: **1883**. On devices, use this machine’s **LAN IP** (not `127.0.0.1` — that is the device itself).

### 2. Environment and database

```powershell
cd mqttapi
copy .env.example .env
# Edit MQTT_* and DB_* as needed (defaults connect to 127.0.0.1)

pip install -r requirements.txt
python init_db.py
```

### 3. MQTT subscribe & ingest

Open another terminal and keep it running:

```powershell
cd mqttapi
python subscriber.py
```

Subscribed topics (see `.env`):

- People Counter / VS135 etc.: `em/+/status` → table `tof`
- UG65 / UG56 gateway: `milesight/ug65/uplink/+`, `milesight/ug56/uplink/+` → table `ug65`

Optional test publish:

```powershell
python publisher_test.py --distance 1800 --temperature 24.5
```

### 4. FastAPI (backend)

Open another terminal:

```powershell
cd mqttapi
python api_server.py
```

| Item | URL |
|------|-----|
| Swagger | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/health |
| Stats | http://127.0.0.1:8000/api/v1/stats |

### 5. Frontend (333 IOT Console)

```powershell
cd frontend
npm install
npm run dev
```

Open in browser: **http://127.0.0.1:3000**  
Vite proxies `/api` and `/health` to `http://127.0.0.1:8000`.

Common scripts:

```powershell
npm run build        # production build → dist/
npm run build:prod
npm run preview      # preview build output
```

### Local startup checklist

1. `docker compose ps` — Mosquitto is running  
2. `subscriber.py` — no connection errors  
3. `curl http://127.0.0.1:8000/health` — OK  
4. Frontend `:3000` loads and fetches data  

---

## Deployment (Ubuntu production)

Full details, firewall, HTTPS, and rollback:  
[`mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_zh-HK.md`](./mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_zh-HK.md)  
(English: [Architecture_and_Deployment_readme_en.md](./mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_en.md))

Assumed paths (adjust as needed):

| Item | Path |
|------|------|
| Code | `/opt/milesight/MilesightAnalysis` |
| Python venv | `/opt/milesight/venv` |
| Console | `/opt/milesight/console/current` → `releases/<ver>/` |
| mqttapi `.env` | `/opt/milesight/MilesightAnalysis/mqttapi/.env` |

### 0. System prep

```bash
sudo apt update
sudo apt install -y nginx mosquitto mosquitto-clients \
  mariadb-server python3-venv python3-pip rsync
sudo systemctl enable --now nginx mosquitto mariadb

sudo useradd -r -m -d /opt/milesight -s /bin/bash milesight || true
# Place this repo at /opt/milesight/MilesightAnalysis
sudo chown -R milesight:milesight /opt/milesight
```

> On production, use **apt Mosquitto** — do **not** run Docker Mosquitto on port 1883.

### 1. MariaDB

```bash
sudo mysql -e "CREATE DATABASE IF NOT EXISTS milesight CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
# Create app user and grant privileges (use a strong password in production)

cd /opt/milesight/MilesightAnalysis/mqttapi
sudo -u milesight cp -n .env.example .env
# Edit .env: MQTT_HOST=127.0.0.1, DB_*, match Mosquitto credentials
```

### 2. MQTT (Mosquitto via apt)

```bash
sudo cp /opt/milesight/MilesightAnalysis/mqttapi/deploy/ubuntu/mosquitto/milesight.conf \
  /etc/mosquitto/conf.d/milesight.conf

sudo mosquitto_passwd -b -c /etc/mosquitto/passwd root root   # change password in production
sudo chown root:mosquitto /etc/mosquitto/passwd
sudo chmod 640 /etc/mosquitto/passwd

sudo systemctl restart mosquitto
ss -lntp | grep 1883   # should be 0.0.0.0:1883
```

On devices, set Broker to **Ubuntu LAN IP:1883**. Firewall must allow `1883/tcp` (and `80`/`443`).

### 3. API + MQTT Subscriber (systemd)

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

Run **only one** `milesight-mqtt-subscriber` instance; `MQTT_CLIENT_ID` must be unique on the broker.

### 4. Frontend build + Nginx

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

Browser: `http://<ubuntu-lan-ip>/`  
Same-origin `/api` requests are proxied by Nginx to FastAPI.

### 5. Day-to-day ops (summary)

```bash
sudo journalctl -u mosquitto -f
sudo journalctl -u milesight-api -f
sudo journalctl -u milesight-mqtt-subscriber -f

sudo systemctl restart milesight-api milesight-mqtt-subscriber
```

| What to update | How |
|----------------|-----|
| **Frontend** | New `releases/<ver>` → switch `current` symlink (rollback-friendly) |
| **API / Subscriber** | `git pull`, then `systemctl restart` the matching services |
| **Mosquitto** | Change conf / passwd, then `systemctl restart mosquitto` |

Do **not** put `.env`, Mosquitto passwords, or DB secrets into each frontend release directory.

---

## Device MQTT checklist

| Item | Recommendation |
|------|----------------|
| Broker address | **LAN IP** of the host running Mosquitto |
| Port | `1883` |
| Credentials | Match `passwd` / `.env` (dev default `root`/`root`) |
| VS135 etc. topic | `em/<device-SN>/status` |
| UG65 / UG56 topic | `milesight/ug65/uplink/+` or `milesight/ug56/uplink/+` (configure on gateway) |
| TLS | Usually off for LAN development |

---

## Related docs

| Doc | Contents |
|-----|----------|
| [`mqttapi/README.md`](./mqttapi/README.md) | MQTT topics, schema, local quick start, API list |
| [`mqttapi/README_en.md`](./mqttapi/README_en.md) | Same (English) |
| [`mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_zh-HK.md`](./mqttapi/deploy/ubuntu/Architecture_and_Deployment_readme_zh-HK.md) | Full Ubuntu deploy and release iteration |
| [`frontend/README.md`](./frontend/README.md) | Frontend stack and i18n notes |
| [`README_zh-HK.md`](./README_zh-HK.md) | This overview (Hong Kong Traditional Chinese) |
