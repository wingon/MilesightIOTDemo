# 333 IOT Console

Vue 3 frontend for Milesight MQTT API (333 IOT Console).

Brand theme inspired by [333 Collins](https://333collins.com/) — charcoal / gold prestige palette via Ant Design `ConfigProvider`.

## i18n

- Default: **English** (`en`)
- Secondary: **繁體中文** (`zh-TW`)
- Switcher in the header; preference saved to `localStorage`

## Stack

- Vue 3 + TypeScript + Vite
- Ant Design Vue + Pinia + Vue Router + vue-i18n
- Axios (proxied to FastAPI `:8000`)

## Setup

```powershell
cd frontend
npm install
npm run dev
```

Ensure FastAPI is running:

```powershell
cd mqttapi
python api_server.py
```
