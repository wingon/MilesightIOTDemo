"""FastAPI application for Milesight MQTT API / IOT Console backend.

啟動時掛載 APScheduler，執行 CCTV 人流統計定時同步任務：
  - 啟動時立即執行一次當天同步
  - 每小時 05 分同步當天（cron 可熱更新）
  - 每天 00:05 同步昨天完整 24h（cron 可熱更新）
  - 每天 00:10 回填當月缺失日期（cron 可熱更新）
所有任務受參數設定 cctv.sync.enabled 控制（Y 啟用 / N 停用）。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import cctv_sync
from app.api.router import api_router
from app.config import load_settings
from app.db import Database
from app.security import AuthError
from app.snowflake import init_snowflake

logger = logging.getLogger(__name__)

# cron 配置：job_id -> (config_key, 預設 cron)
_CRON_JOBS: dict[str, tuple[str, str]] = {
    "hourly": ("cctv.sync.cron.hourly", "5 * * * *"),
    "yesterday": ("cctv.sync.cron.yesterday", "5 0 * * *"),
    "backfill": ("cctv.sync.cron.backfill", "10 0 * * *"),
}

# 業務執行函式：job_id -> (db, settings) -> dict
_BUSINESS: dict[str, object] = {
    "hourly": cctv_sync.sync_today,
    "yesterday": cctv_sync.sync_yesterday,
    "backfill": cctv_sync.backfill_current_month,
}

_scheduler: BackgroundScheduler | None = None


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
    """回傳 job 執行函式：先熱更新 cron，再檢查開關，最後執行業務。"""
    key, default = _CRON_JOBS[job_id]
    business = _BUSINESS[job_id]

    def runner() -> None:
        try:
            # 熱更新：若 cron 變更，重新排程
            new_expr = _read_cron(db, key, default)
            job = scheduler.get_job(job_id)
            if job is not None:
                try:
                    if str(job.trigger) != str(CronTrigger.from_crontab(new_expr)):
                        scheduler.reschedule_job(
                            job_id, trigger=CronTrigger.from_crontab(new_expr)
                        )
                        logger.info("cron %s 已熱更新為 %s", job_id, new_expr)
                except Exception as exc:
                    logger.warning("reschedule %s 失敗: %s", job_id, exc)
            # 開關控制
            if not _sync_enabled(db):
                logger.info("CCTV 人流同步已停用，跳過 %s", job_id)
                return
            business(db, settings)
        except Exception as exc:
            logger.exception("CCTV 同步任務 %s 執行失敗: %s", job_id, exc)

    return runner


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
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
    logger.info("APScheduler 已啟動，CCTV 人流定時同步已註冊")

    # 啟動時立即執行一次當天同步（受開關控制）
    try:
        if _sync_enabled(db):
            logger.info("啟動立即執行 CCTV 當天同步")
            cctv_sync.sync_today(db, settings)
    except Exception as exc:
        logger.exception("啟動時 CCTV 同步失敗: %s", exc)

    try:
        yield
    finally:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
            _scheduler = None
        logger.info("APScheduler 已關閉")


app = FastAPI(
    title="Milesight MQTT API",
    description="REST API for tof / ug65 uplink data. Backend for IOT Console.",
    version="1.0.0",
    lifespan=lifespan,
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
