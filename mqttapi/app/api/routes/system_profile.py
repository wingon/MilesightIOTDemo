"""当前用户个人信息：查看 / 更新 / 修改密码。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.api.operlog import BT_UPDATE, record_operlog
from app.db import Database
from app.security import hash_password, verify_password

router = APIRouter(prefix="/api/v1/system/user/profile", tags=["system-profile"])


class ProfileBody(BaseModel):
    nickName: str | None = Field(None, max_length=50)
    phonenumber: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=100)
    sex: str | None = Field(None, max_length=1)


class PasswordBody(BaseModel):
    oldPassword: str = Field(..., min_length=6, max_length=72)
    newPassword: str = Field(..., min_length=6, max_length=72)


@router.get("")
def get_profile(
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> dict:
    """获取当前用户个人资料。"""
    profile = db.get_sys_user_by_id(int(user["id"]))
    if not profile:
        return {"nickName": "", "phonenumber": "", "email": "", "sex": "2"}
    return {
        "nickName": profile.get("nickname") or "",
        "phonenumber": profile.get("phone") or "",
        "email": profile.get("email") or "",
        "sex": profile.get("sex") or "2",
    }


@router.put("")
def update_profile(
    body: ProfileBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> dict:
    """更新当前用户个人资料（任何登录用户可操作）。"""
    data: dict = {}
    if body.nickName is not None:
        data["nickname"] = body.nickName
    if body.phonenumber is not None:
        data["phone"] = body.phonenumber
    if body.email is not None:
        data["email"] = body.email
    if body.sex is not None:
        data["sex"] = body.sex
    if data:
        db.update_sys_user(int(user["id"]), data)
    record_operlog(
        db, request, user, title="个人资料", business_type=BT_UPDATE, param=data,
    )
    return {"ok": True}


@router.put("/password")
def update_password(
    body: PasswordBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> dict:
    """修改当前用户密码（需验证旧密码）。"""
    full_user = db.get_sys_user_by_username(user["username"])
    if not full_user or not verify_password(body.oldPassword, full_user.get("password") or ""):
        return {"ok": False, "detail": "旧密码不正确"}
    db.reset_sys_user_password(int(user["id"]), hash_password(body.newPassword))
    record_operlog(
        db, request, user, title="个人资料", business_type=BT_UPDATE,
        param={"operation": "修改密码"},
    )
    return {"ok": True}
