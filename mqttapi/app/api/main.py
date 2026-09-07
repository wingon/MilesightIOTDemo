"""FastAPI application for Milesight MQTT API / IOT Console backend.

啟動時掛載 APScheduler，執行 CCTV 人流統計定時同步任務：
  - 啟動時立即執行一次當天同步
  - 按 cron 同步當天（cron 可熱更新，無需重啟）
  - 每天 00:05 同步昨天完整 24h（cron 可熱更新）
  - 每天 00:10 回填當月缺失日期（cron 可熱更新）
所有任務受參數設定 cctv.sync.enabled 控制（Y 啟用 / N 停用）。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# JS Number.MAX_SAFE_INTEGER = 2^53 - 1；超过该值的整数（雪花 ID）在浏览器解析 JSON 时会丢失精度，
# 需要统一序列化为字符串，避免前端路由 name / 业务 id 冲突。
JS_SAFE_INTEGER_MAX = (1 << 53) - 1


def _safe_serialize(obj: Any) -> Any:
    """递归将超过 JS 安全整数范围的 int 转为字符串，其余原样返回。"""
    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return str(obj) if abs(obj) > JS_SAFE_INTEGER_MAX else obj
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    return obj


class SafeJSONResponse(JSONResponse):
    """默认 JSON 响应：将超大整数（雪花 ID）序列化为字符串，防止前端精度丢失。"""

    def render(self, content: Any) -> bytes:
        return json.dumps(
            _safe_serialize(content),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")

from app import cctv_sync
from app.api.router import api_router
from app.config import load_settings
from app.db import Database
from app.security import AuthError
from app.snowflake import init_snowflake

logger = logging.getLogger(__name__)

# cron 配置：job_id -> (config_key, 預設 cron)
_CRON_JOBS: dict[str, tuple[str, str]] = {
    "anytime": ("cctv.sync.cron.anytime", "5 * * * *"),
    "yesterday": ("cctv.sync.cron.yesterday", "5 0 * * *"),
    "backfill": ("cctv.sync.cron.backfill", "10 0 * * *"),
}

# 業務執行函式：job_id -> (db, settings) -> dict
_BUSINESS: dict[str, object] = {
    "anytime": cctv_sync.sync_today,
    "yesterday": cctv_sync.sync_yesterday,
    "backfill": cctv_sync.backfill_current_month,
}

_scheduler: BackgroundScheduler | None = None
_cron_watcher_stop = threading.Event()
_cron_watcher_thread: threading.Thread | None = None


def _read_cron(db: Database, key: str, default: str) -> str:
    row = db.get_config_by_key(key)
    expr = ((row or {}).get("config_value") or "").strip()
    if not expr:
        return default
    try:
        CronTrigger.from_crontab(expr)
        return expr
    except Exception:
        logger.warning("非法 cron 表示式 %r for %s，回退預設 %r", expr, key, default)
        return default


def _sync_enabled(db: Database) -> bool:
    row = db.get_config_by_key(cctv_sync.CONFIG_ENABLED)
    return ((row or {}).get("config_value") or "Y").strip().upper() == "Y"


def _make_job_runner(scheduler: BackgroundScheduler, db: Database, settings, job_id: str):
    """回傳 job 執行函式：檢查開關，執行業務。"""
    key, default = _CRON_JOBS[job_id]
    business = _BUSINESS[job_id]

    def runner() -> None:
        try:
            # 開關控制
            if not _sync_enabled(db):
                logger.info("[CCTV] 同步已停用，跳過 %s", job_id)
                return
            logger.info("[CCTV] 定時任務 %s 開始執行", job_id)
            business(db, settings)
            logger.info("[CCTV] 定時任務 %s 執行完成", job_id)
        except Exception as exc:
            logger.exception("[CCTV] 定時任務 %s 執行失敗: %s", job_id, exc)

    return runner


def _cron_watcher(db: Database, scheduler: BackgroundScheduler):
    """後台線程：每 10 秒檢查 DB 中 cron 配置，有變化立即重新排程。"""
    last_crons: dict[str, str] = {}
    # 初始讀取
    for job_id in _CRON_JOBS:
        key, default = _CRON_JOBS[job_id]
        last_crons[job_id] = _read_cron(db, key, default)

    logger.info("[CCTV] cron 監聽線程已啟動，初始排程: %s", last_crons)

    while not _cron_watcher_stop.is_set():
        _cron_watcher_stop.wait(10)
        if _cron_watcher_stop.is_set():
            break
        try:
            for job_id in _CRON_JOBS:
                key, default = _CRON_JOBS[job_id]
                current = _read_cron(db, key, default)
                if current != last_crons.get(job_id):
                    try:
                        scheduler.reschedule_job(
                            job_id, trigger=CronTrigger.from_crontab(current)
                        )
                        logger.info(
                            "[CCTV] cron %s 已從 %s 熱更新為 %s",
                            job_id, last_crons[job_id], current,
                        )
                        last_crons[job_id] = current
                    except Exception as exc:
                        logger.warning("[CCTV] reschedule %s 失敗: %s", job_id, exc)
        except Exception as exc:
            logger.warning("[CCTV] cron 監聽線程異常: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler, _cron_watcher_thread
    settings = load_settings()
    db = Database(settings)

    # 依設定初始化雪花 ID worker_id（多實例部署時各實例配不同值）
    init_snowflake(settings.snowflake_worker_id)

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    _scheduler = scheduler

    for job_id in _CRON_JOBS:
        key, default = _CRON_JOBS[job_id]
        expr = _read_cron(db, key, default)
        scheduler.add_job(
            _make_job_runner(scheduler, db, settings, job_id),
            trigger=CronTrigger.from_crontab(expr),
            id=job_id,
            name=f"cctv-sync-{job_id}",
            replace_existing=True,
        )

    scheduler.start()
    logger.info("[CCTV] APScheduler 已啟動，定時同步已註冊")

    # 啟動 cron 監聽線程（輪詢 DB 變化，實現真正的熱更新）
    _cron_watcher_stop.clear()
    _cron_watcher_thread = threading.Thread(
        target=_cron_watcher, args=(db, scheduler),
        daemon=True, name="cctv-cron-watcher",
    )
    _cron_watcher_thread.start()

    # 啟動時立即執行一次當天同步（受開關控制），放入後台線程避免阻塞啟動
    if _sync_enabled(db):
        def _startup_sync():
            try:
                logger.info("[CCTV] 啟動立即執行當天同步（後台）")
                cctv_sync.sync_today(db, settings)
            except Exception as exc:
                logger.exception("[CCTV] 啟動時同步失敗: %s", exc)
        threading.Thread(target=_startup_sync, daemon=True, name="cctv-startup-sync").start()

    try:
        yield
    finally:
        _cron_watcher_stop.set()
        if _cron_watcher_thread is not None:
            _cron_watcher_thread.join(timeout=5)
            _cron_watcher_thread = None
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
            _scheduler = None
        logger.info("[CCTV] APScheduler 已關閉")


app = FastAPI(
    title="Milesight MQTT API",
    description="REST API for tof / ug65 uplink data. Backend for IOT Console.",
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=SafeJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    return JSONResponse(status_code=exc.code, content={"detail": exc.message})


app.include_router(api_router)


@app.get("/")
def root():
    return {
        "service": "milesight-mqtt-api",
        "docs": "/docs",
        "health": "/health",
        "stats": "/api/v1/stats",
    }
