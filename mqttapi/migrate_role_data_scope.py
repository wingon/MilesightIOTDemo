from app.config import load_settings
from app.db import Database

s = load_settings()
db = Database(s)
with db.wingon_connection() as conn:
    cur = conn.cursor()
    # 1. 检查 data_scope 列是否存在
    cur.execute("SHOW COLUMNS FROM sys_role LIKE 'data_scope'")
    if cur.fetchone() is None:
        cur.execute(
            "ALTER TABLE sys_role ADD COLUMN data_scope CHAR(1) NOT NULL DEFAULT '1' "
            "COMMENT '数据范围（1全部 2自定义 3本部门 4本部门及以下 5仅本人）' AFTER status"
        )
        print("[OK] sys_role.data_scope added")
    else:
        print("[SKIP] sys_role.data_scope exists")

    # 2. 检查 sys_role_dept 表
    cur.execute("SHOW TABLES LIKE 'sys_role_dept'")
    if cur.fetchone() is None:
        cur.execute(
            "CREATE TABLE sys_role_dept ("
            "role_id BIGINT NOT NULL,"
            "dept_id BIGINT NOT NULL,"
            "PRIMARY KEY (role_id, dept_id),"
            "KEY idx_dept_id (dept_id)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci "
            "COMMENT='角色和部门关联表（数据权限）'"
        )
        print("[OK] sys_role_dept table created")
    else:
        print("[SKIP] sys_role_dept table exists")

    # 3. 修正空值
    cur.execute("UPDATE sys_role SET data_scope = '1' WHERE data_scope IS NULL OR data_scope = ''")
    conn.commit()
    print("[OK] data_scope defaulted")

# 验证
with db.wingon_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT id, role_name, data_scope FROM sys_role")
    for r in cur.fetchall():
        print("  role:", r["id"], r["role_name"], "scope=", r["data_scope"])
