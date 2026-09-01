-- ============================================================================
-- WingOnIOT 角色管理（若依 1:1）：数据权限
--
-- 1. sys_role 增加 data_scope 字段（数据范围：1全部 2自定义 3本部门 4本部门及以下 5仅本人）
-- 2. 新建 sys_role_dept 角色-部门关联表（data_scope=2 自定义时的部门集合）
-- 执行方式：mysql -uroot -proot WingOnIOT < init_role_data_scope.sql
-- ============================================================================

-- 1. sys_role 增加数据范围字段（默认'1'=全部数据权限，与若依一致）
ALTER TABLE sys_role ADD COLUMN data_scope CHAR(1) NOT NULL DEFAULT '1' COMMENT '数据范围（1全部 2自定义 3本部门 4本部门及以下 5仅本人）' AFTER status;

-- 2. 角色-部门关联表（自定义数据权限时选中的部门）
CREATE TABLE IF NOT EXISTS sys_role_dept (
    role_id BIGINT NOT NULL COMMENT '角色ID',
    dept_id BIGINT NOT NULL COMMENT '部门ID',
    PRIMARY KEY (role_id, dept_id),
    KEY idx_dept_id (dept_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色和部门关联表（数据权限）';

UPDATE sys_role SET data_scope = '1' WHERE data_scope IS NULL OR data_scope = '';
