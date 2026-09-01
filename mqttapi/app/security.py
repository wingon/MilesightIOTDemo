"""认证安全工具：bcrypt 密码哈希 + JWT Token 生成/校验。

参照 RuoYi-Vue 的认证思路（无状态 JWT + bcrypt 存储密码），
技术选型为 PyJWT + bcrypt（兼容 Python 3.13）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config import Settings

logger = logging.getLogger(__name__)

# bcrypt 只处理前 72 字节，超过的部分静默截断会带来安全隐患，直接拒绝。
_BCRYPT_MAX_BYTES = 72


class AuthError(Exception):
    """认证/授权相关错误（携带面向 API 层的错误码与消息）。"""

    def __init__(self, message: str, code: int = 401):
        super().__init__(message)
        self.code = code
        self.message = message


def hash_password(password: str) -> str:
    """生成 bcrypt 哈希（rounds=10，与初始数据脚本保持一致）。"""
    data = password.encode("utf-8")
    if len(data) > _BCRYPT_MAX_BYTES:
        raise AuthError("密码长度不能超过 72 字节", code=400)
    return bcrypt.hashpw(data, bcrypt.gensalt(rounds=10)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(settings: Settings, user_id: int, username: str) -> str:
    """签发 JWT Token。

    payload:
      - sub: 用户 ID
      - username: 登录账号
      - iat / exp: 签发时间 / 过期时间
    """
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(settings: Settings, token: str) -> dict[str, Any]:
    """校验并解析 JWT Token，失败抛出 AuthError（401）。"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("登录已过期，请重新登录") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("无效的登录凭证") from exc
    return payload
