"""操作日志辅助：把一次请求写入 sys_oper_log。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request

from app.db import Database

# 业务类型枚举（与 RuoYi business_type 对齐）
BT_OTHER = 0
BT_INSERT = 1
BT_UPDATE = 2
BT_DELETE = 3
BT_AUTHORIZE = 4

_MAX_PARAM_LEN = 2000


def _truncate(value: Any) -> str | None:
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text[:_MAX_PARAM_LEN]


def record_operlog(
    db: Database,
    request: Request,
    user: dict,
    *,
    title: str,
    business_type: int = BT_OTHER,
    status: int = 1,
    param: Any = None,
    result: Any = None,
    error_msg: str | None = None,
) -> None:
    """记录一条操作日志（尽量不抛异常，避免影响主流程）。"""
    try:
        db.insert_oper_log({
            "title": title,
            "business_type": business_type,
            "method": f"{request.method} {request.url.path}",
            "request_method": request.method,
            "oper_url": request.url.path,
            "oper_ip": request.client.host if request.client else "",
            "oper_name": str(user.get("username", "")),
            "oper_param": _truncate(param),
            "json_result": _truncate(result),
            "status": status,
            "error_msg": error_msg,
        })
    except Exception:  # noqa: BLE001 日志写入失败不影响业务
        pass
