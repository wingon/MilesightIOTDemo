"""认证模块：登录 / 登出 / 当前用户信息 / 动态路由菜单。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.db import Database
from app.security import AuthError, create_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, description="登录账号")
    password: str = Field(..., min_length=1, max_length=72, description="密码")


def _parse_ua(ua: str) -> tuple[str, str]:
    """极简 User-Agent 解析：返回 (browser, os)。"""
    ua = ua or ""
    if "Edg" in ua:
        browser = "Edge"
    elif "Chrome" in ua:
        browser = "Chrome"
    elif "Firefox" in ua:
        browser = "Firefox"
    elif "Safari" in ua:
        browser = "Safari"
    else:
        browser = "Unknown"
    if "Windows" in ua:
        os_name = "Windows"
    elif "Mac OS" in ua or "Macintosh" in ua:
        os_name = "macOS"
    elif "Android" in ua:
        os_name = "Android"
    elif "iPhone" in ua or "iPad" in ua:
        os_name = "iOS"
    elif "Linux" in ua:
        os_name = "Linux"
    else:
        os_name = "Unknown"
    return browser, os_name


@router.post("/login")
def login(body: LoginRequest, request: Request, db: Database = Depends(get_db)) -> dict[str, Any]:
    """用户登录：校验账号密码，签发 JWT Token，并记录登录日志。"""
    ua = request.headers.get("user-agent", "")
    browser, os_name = _parse_ua(ua)
    ipaddr = request.client.host if request.client else ""
    user = db.get_sys_user_by_username(body.username)
    if user is None or not verify_password(body.password, user.get("password") or ""):
        db.record_login_log(
            user_name=body.username, ipaddr=ipaddr, browser=browser, os=os_name,
            status="1", msg="用户名或密码错误",
        )
        raise AuthError("用户名或密码错误", code=401)
    if int(user.get("status", 1)) != 1:
        db.record_login_log(
            user_name=body.username, ipaddr=ipaddr, browser=browser, os=os_name,
            status="1", msg="账号已停用",
        )
        raise AuthError("账号已停用，请联系管理员", code=403)
    token = create_access_token(
        db.settings,
        int(user["id"]),
        str(user["username"]),
    )
    db.record_login_log(
        user_name=body.username, ipaddr=ipaddr, browser=browser, os=os_name,
        status="0", msg="登录成功",
    )
    return {"token": token}


@router.get("/whitelist")
def whitelist(db: Database = Depends(get_db)) -> list[str]:
    """公开接口：启用中的前端路由白名单（免登录路径前缀，供前端路由守卫读取）。"""
    return db.get_whitelist_paths("F")


@router.post("/logout")
def logout() -> dict[str, str]:
    """登出（无状态 JWT，前端清除本地 token 即可）。"""
    return {"message": "ok"}


@router.get("/userinfo")
def userinfo(
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    """当前用户信息：基本信息 + 角色 + 权限标识集合。"""
    roles = db.get_user_role_keys(int(user["id"]))
    permissions = db.get_user_permissions(int(user["id"]))
    return {
        "user": {
            "id": user["id"],
            "username": user["username"],
            "nickname": user.get("nickname"),
            "avatar": user.get("avatar"),
        },
        "roles": roles,
        "permissions": permissions,
    }


@router.get("/routes")
def routes(
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> list[dict[str, Any]]:
    """当前用户可见的菜单树（用于前端动态路由与侧边栏渲染）。"""
    return db.get_user_menu_tree(int(user["id"]))
