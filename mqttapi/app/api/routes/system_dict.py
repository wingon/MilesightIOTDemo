"""字典管理：字典类型 CRUD + 字典数据 CRUD。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db, require_permission
from app.api.operlog import BT_DELETE, BT_INSERT, BT_UPDATE, record_operlog
from app.db import Database
from app.security import AuthError

router = APIRouter(prefix="/api/v1/system/dict", tags=["system-dict"])


class DictTypeBody(BaseModel):
    dict_name: str = Field(..., min_length=1, max_length=100, description="字典名称")
    dict_type: str = Field(..., min_length=1, max_length=100, description="字典类型")
    status: str = Field("0", description="状态（0正常 1停用）")
    remark: str | None = Field(None, max_length=500)


class DictDataBody(BaseModel):
    dict_sort: int = Field(0, ge=0, description="字典排序")
    dict_label: str = Field(..., min_length=1, max_length=100, description="字典标签")
    dict_value: str = Field(..., min_length=1, max_length=100, description="字典键值")
    dict_type: str = Field(..., min_length=1, max_length=100, description="字典类型")
    css_class: str | None = Field(None, max_length=100)
    list_class: str | None = Field(None, max_length=100)
    is_default: str = Field("N", description="是否默认（Y是 N否）")
    status: str = Field("0", description="状态（0正常 1停用）")
    remark: str | None = Field(None, max_length=500)


# ---------- 字典类型 ----------

@router.get("/type/list")
def list_dict_types(
    dict_name: str | None = Query(None, max_length=100),
    dict_type: str | None = Query(None, max_length=100),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:dict:list")),
) -> dict[str, Any]:
    rows, total = db.list_dict_types(
        keyword=(dict_name or dict_type),
        status=status,
        offset=offset,
        limit=limit,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.post("/type")
def create_dict_type(
    body: DictTypeBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:dict:add")),
) -> dict[str, Any]:
    if db.get_dict_type_by_type(body.dict_type) is not None:
        raise AuthError("字典类型已存在", code=400)
    dict_id = db.create_dict_type({
        **body.model_dump(),
        "create_by": user["username"],
    })
    record_operlog(
        db, request, user, title="字典管理", business_type=BT_INSERT,
        param=body.model_dump(), result={"dict_id": dict_id},
    )
    return {"dict_id": dict_id}


@router.put("/type/{dict_id}")
def update_dict_type(
    dict_id: int,
    body: DictTypeBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:dict:edit")),
) -> dict[str, Any]:
    if db.get_dict_type_by_id(dict_id) is None:
        raise AuthError("字典类型不存在", code=404)
    db.update_dict_type(dict_id, {
        **body.model_dump(),
        "update_by": user["username"],
    })
    record_operlog(
        db, request, user, title="字典管理", business_type=BT_UPDATE,
        param={"dict_id": dict_id, **body.model_dump()},
    )
    return {"ok": True}


@router.delete("/type/{dict_id}")
def delete_dict_type(
    dict_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:dict:remove")),
) -> dict[str, Any]:
    if db.get_dict_type_by_id(dict_id) is None:
        raise AuthError("字典类型不存在", code=404)
    db.delete_dict_type(dict_id)
    record_operlog(
        db, request, user, title="字典管理", business_type=BT_DELETE,
        param={"dict_id": dict_id},
    )
    return {"ok": True}


# ---------- 字典数据 ----------

@router.get("/data/list")
def list_dict_data(
    dict_type: str | None = Query(None, max_length=100),
    dict_label: str | None = Query(None, max_length=100),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:dict:list")),
) -> dict[str, Any]:
    rows, total = db.list_dict_data(
        dict_type=dict_type,
        dict_label=dict_label,
        status=status,
        offset=offset,
        limit=limit,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.post("/data")
def create_dict_data(
    body: DictDataBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:dict:addData")),
) -> dict[str, Any]:
    dict_code = db.create_dict_data({
        **body.model_dump(),
        "create_by": user["username"],
    })
    record_operlog(
        db, request, user, title="字典数据", business_type=BT_INSERT,
        param=body.model_dump(), result={"dict_code": dict_code},
    )
    return {"dict_code": dict_code}


@router.put("/data/{dict_code}")
def update_dict_data(
    dict_code: int,
    body: DictDataBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:dict:editData")),
) -> dict[str, Any]:
    if db.get_dict_data_by_id(dict_code) is None:
        raise AuthError("字典数据不存在", code=404)
    db.update_dict_data(dict_code, {
        **body.model_dump(),
        "update_by": user["username"],
    })
    record_operlog(
        db, request, user, title="字典数据", business_type=BT_UPDATE,
        param={"dict_code": dict_code, **body.model_dump()},
    )
    return {"ok": True}


@router.delete("/data/{dict_code}")
def delete_dict_data(
    dict_code: int,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:dict:removeData")),
) -> dict[str, Any]:
    if db.get_dict_data_by_id(dict_code) is None:
        raise AuthError("字典数据不存在", code=404)
    db.delete_dict_data(dict_code)
    record_operlog(
        db, request, user, title="字典数据", business_type=BT_DELETE,
        param={"dict_code": dict_code},
    )
    return {"ok": True}
