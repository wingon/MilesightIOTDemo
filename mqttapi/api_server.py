#!/usr/bin/env python3
"""Run FastAPI with: python api_server.py  (or uvicorn app.api.main:app --reload)"""

import logging
import sys

import uvicorn

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def _setup_logging() -> None:
    """配置 root logger，確保業務 logger（app.*）的 info 日誌輸出到控制台。"""
    root = logging.getLogger()
    if any(getattr(h, "_cctv_configured", False) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    handler._cctv_configured = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    # 降低第三方庫日誌噪音
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


if __name__ == "__main__":
    _setup_logging()
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )