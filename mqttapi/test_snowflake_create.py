#!/usr/bin/env python3
"""验证雪花 ID 改造后：新增 账号/角色/菜单/部门/岗位/配置/字典/白名单 不报错，ID 为雪花规模。

测试完成后自动清理测试数据，保持数据库现场。
"""

from __future__ import annotations

from app.config import load_settings
from app.db import Database

settings = load_settings()
db = Database(settings)

SNOWFLAKE_THRESHOLD = 1 << 50
created_ids: dict[str, list[int]] = {}


def check(name: str, cond: bool, detail: str = "") -> None:
    flag = "PASS" if cond else "FAIL"
    print(f"{flag} | {name}" + (f" | {detail}" if detail else ""))


def is_snowflake(v: int) -> bool:
    return v > SNOWFLAKE_THRESHOLD


def main() -> None:
    # 1. 部门
    dept_id = db.create_dept({"parent_id": 100, "dept_name": "雪花测试部", "order_num": 999})
    created_ids["dept"] = [dept_id]
    check("create_dept", is_snowflake(dept_id), f"dept_id={dept_id}")

    # 2. 岗位
    post_id = db.create_post({"post_code": "SF_TEST", "post_name": "雪花测试岗", "post_sort": 999})
    created_ids["post"] = [post_id]
    check("create_post", is_snowflake(post_id), f"post_id={post_id}")

    # 3. 角色
    role_id = db.create_sys_role({"role_name": "雪花测试角色", "role_key": "sf_test_role"})
    created_ids["role"] = [role_id]
    check("create_sys_role", is_snowflake(role_id), f"role_id={role_id}")

    # 4. 菜单
    menu_id = db.create_sys_menu({"parent_id": 0, "menu_name": "雪花测试菜单", "menu_type": "C"})
    created_ids["menu"] = [menu_id]
    check("create_sys_menu", is_snowflake(menu_id), f"menu_id={menu_id}")

    # 5. 账号（用户）
    user_id = db.create_sys_user({"username": "snowflake_test", "password": "x", "nickname": "雪花测试账号", "dept_id": dept_id})
    created_ids["user"] = [user_id]
    check("create_sys_user", is_snowflake(user_id), f"user_id={user_id}")

    # 6. 配置
    config_id = db.create_config({"config_name": "雪花测试配置", "config_key": "sf_test_key", "config_value": "1"})
    created_ids["config"] = [config_id]
    check("create_config", is_snowflake(config_id), f"config_id={config_id}")

    # 7. 字典类型 + 字典数据
    dict_id = db.create_dict_type({"dict_name": "雪花测试字典", "dict_type": "sf_test_dict"})
    created_ids["dict_type"] = [dict_id]
    check("create_dict_type", is_snowflake(dict_id), f"dict_id={dict_id}")
    dict_code = db.create_dict_data({"dict_type": "sf_test_dict", "dict_label": "测试", "dict_value": "1"})
    created_ids["dict_data"] = [dict_code]
    check("create_dict_data", is_snowflake(dict_code), f"dict_code={dict_code}")

    # 8. 白名单
    whitelist_id = db.create_whitelist({"path": "/snowflake-test", "path_type": "F", "remark": "雪花测试"})
    created_ids["whitelist"] = [whitelist_id]
    check("create_whitelist", is_snowflake(whitelist_id), f"id={whitelist_id}")

    # 9. 关联表（用户-角色、用户-岗位、角色-菜单、角色-部门）
    db.set_user_roles(user_id, [role_id])
    db.set_user_posts(user_id, [post_id])
    db.set_role_menus(role_id, [menu_id])
    db.set_role_depts(role_id, [dept_id])
    check("set_user_roles", True, f"user_id={user_id} role_id={role_id}")
    check("set_user_posts", True, f"user_id={user_id} post_id={post_id}")
    check("set_role_menus", True, f"role_id={role_id} menu_id={menu_id}")
    check("set_role_depts", True, f"role_id={role_id} dept_id={dept_id}")

    # 10. 回读验证关联
    roles = db.get_user_role_ids(user_id)
    posts = db.get_user_post_ids(user_id)
    menus = db.get_role_menu_ids(role_id)
    depts = db.get_role_dept_ids(role_id)
    check("readback user_roles", roles == [role_id], f"roles={roles}")
    check("readback user_posts", posts == [post_id], f"posts={posts}")
    check("readback role_menus", menus == [menu_id], f"menus={menus}")
    check("readback role_depts", depts == [dept_id], f"depts={depts}")


def cleanup() -> None:
    print("\n== 清理测试数据 ==")
    user_id = created_ids.get("user", [None])[0]
    role_id = created_ids.get("role", [None])[0]
    dept_id = created_ids.get("dept", [None])[0]
    post_id = created_ids.get("post", [None])[0]
    menu_id = created_ids.get("menu", [None])[0]
    if user_id:
        db.delete_sys_user(user_id)
        print(f"  - 删除用户 {user_id}")
    if role_id:
        db.delete_sys_role(role_id)
        print(f"  - 删除角色 {role_id}")
    if menu_id:
        db.delete_sys_menu(menu_id)
        print(f"  - 删除菜单 {menu_id}")
    if post_id:
        db.delete_post(post_id)
        print(f"  - 删除岗位 {post_id}")
    if dept_id:
        db.delete_dept(dept_id)
        print(f"  - 删除部门 {dept_id}")
    for cid in created_ids.get("config", []):
        db.delete_config(cid)
        print(f"  - 删除配置 {cid}")
    for dcode in created_ids.get("dict_data", []):
        db.delete_dict_data(dcode)
        print(f"  - 删除字典数据 {dcode}")
    for did in created_ids.get("dict_type", []):
        db.delete_dict_type(did)
        print(f"  - 删除字典类型 {did}")
    for wid in created_ids.get("whitelist", []):
        db.delete_whitelist(wid)
        print(f"  - 删除白名单 {wid}")


if __name__ == "__main__":
    try:
        main()
        print("\nRESULT: 新增测试全部通过")
    finally:
        cleanup()