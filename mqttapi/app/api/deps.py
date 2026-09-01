from functools import lru_cache

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, load_settings
from app.db import Database
from app.security import AuthError, decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def get_db() -> Database:
    return Database(get_settings())


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_db),
) -> dict:
    """Resolve the current logged-in user from Authorization: Bearer <token>.

    GET requests hitting a whitelisted backend API prefix (sys_whitelist.path_type='A')
    return an anonymous user (for large-screen read-only endpoints); all write methods
    (POST/PUT/PATCH/DELETE) still require login even when the path matches a whitelist
    prefix, preventing anonymous data mutation. Missing login / expired token / disabled
    account all raise AuthError.

    Returns the user dict (without the password hash).
    """
    if request.method == "GET" and db.is_api_whitelisted(request.url.path):
        return {"id": 0, "username": "anonymous", "nickname": "anonymous", "status": 1}
    if credentials is None:
        raise AuthError("未登录或登录凭证缺失")
    payload = decode_access_token(settings, credentials.credentials)
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        raise AuthError("无效的登录凭证")
    user = db.get_sys_user_by_id(user_id)
    if user is None:
        raise AuthError("用户不存在")
    if user.get("status") != 1:
        raise AuthError("账号已停用，请联系管理员", code=403)
    return user


def require_permission(permission: str):
    """Permission-check dependency factory: ``Depends(require_permission("system:user:list"))``.

    Super-admin role (admin) skips the check; normal users must have the permission
    marker in their merged permission set.
    """

    def checker(
        user: dict = Depends(get_current_user),
        db: Database = Depends(get_db),
    ) -> dict:
        if db.is_super_admin(user["id"]):
            return user
        perms = db.get_user_permissions(user["id"])
        if "*:*:*" in perms or permission in perms:
            return user
        raise AuthError(f"没有操作权限（{permission}）", code=403)

    return checker
