-- ============================================================================
-- WingOnIOT 权限模块：sys_user / sys_role / sys_menu / sys_user_role /
-- sys_role_menu / sys_oper_log
--
-- 参照 RuoYi-Vue RBAC 模型设计（菜单即权限），适配本项目 MariaDB 命名规范。
-- 执行方式：
--   mysql -uroot -proot WingOnIOT < init_sys_permission.sql
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. 用户信息表
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_user (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '用户ID',
    username VARCHAR(50) NOT NULL COMMENT '登录账号',
    password VARCHAR(200) NOT NULL COMMENT '密码（bcrypt 哈希）',
    nickname VARCHAR(50) DEFAULT NULL COMMENT '昵称',
    email VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
    phone VARCHAR(20) DEFAULT NULL COMMENT '手机号',
    avatar VARCHAR(200) DEFAULT NULL COMMENT '头像地址',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态（1=正常 0=停用）',
    remark VARCHAR(200) DEFAULT NULL COMMENT '备注',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户信息表';

-- ----------------------------------------------------------------------------
-- 2. 角色信息表
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_role (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '角色ID',
    role_name VARCHAR(50) NOT NULL COMMENT '角色名称',
    role_key VARCHAR(50) NOT NULL COMMENT '角色权限字符串（如 admin）',
    sort INT NOT NULL DEFAULT 0 COMMENT '显示顺序',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态（1=正常 0=停用）',
    remark VARCHAR(200) DEFAULT NULL COMMENT '备注',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_role_key (role_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色信息表';

-- ----------------------------------------------------------------------------
-- 3. 菜单权限表（树形：parent_id 自关联；menu_type M=目录 C=菜单 F=按钮）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_menu (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '菜单ID',
    parent_id BIGINT NOT NULL DEFAULT 0 COMMENT '父菜单ID，0 表示根',
    menu_name VARCHAR(50) NOT NULL COMMENT '菜单名称',
    i18n_key VARCHAR(100) DEFAULT NULL COMMENT '国际化键，非空时优先于 menu_name',
    path VARCHAR(200) DEFAULT NULL COMMENT '路由地址',
    component VARCHAR(200) DEFAULT NULL COMMENT '前端组件路径（相对 src/views）',
    menu_type CHAR(1) NOT NULL DEFAULT 'C' COMMENT '菜单类型（M=目录 C=菜单 F=按钮）',
    permission VARCHAR(100) DEFAULT NULL COMMENT '权限标识（如 system:user:list）',
    icon VARCHAR(100) DEFAULT NULL COMMENT '菜单图标',
    sort INT NOT NULL DEFAULT 0 COMMENT '显示顺序',
    visible TINYINT NOT NULL DEFAULT 1 COMMENT '是否显示（1=显示 0=隐藏）',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态（1=正常 0=停用）',
    remark VARCHAR(200) DEFAULT NULL COMMENT '备注',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    KEY idx_parent_id (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='菜单权限表';

-- ----------------------------------------------------------------------------
-- 4. 用户和角色关联表
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_user_role (
    user_id BIGINT NOT NULL COMMENT '用户ID',
    role_id BIGINT NOT NULL COMMENT '角色ID',
    PRIMARY KEY (user_id, role_id),
    KEY idx_role_id (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户和角色关联表';

-- ----------------------------------------------------------------------------
-- 5. 角色和菜单关联表
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_role_menu (
    role_id BIGINT NOT NULL COMMENT '角色ID',
    menu_id BIGINT NOT NULL COMMENT '菜单ID',
    PRIMARY KEY (role_id, menu_id),
    KEY idx_menu_id (menu_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色和菜单关联表';

-- ----------------------------------------------------------------------------
-- 6. 操作日志记录表
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_oper_log (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '日志主键',
    title VARCHAR(50) DEFAULT '' COMMENT '模块标题',
    business_type TINYINT DEFAULT 0 COMMENT '业务类型（0=其它 1=新增 2=修改 3=删除 4=授权）',
    method VARCHAR(200) DEFAULT '' COMMENT '方法名称',
    request_method VARCHAR(10) DEFAULT '' COMMENT '请求方式',
    oper_url VARCHAR(255) DEFAULT '' COMMENT '请求URL',
    oper_ip VARCHAR(50) DEFAULT '' COMMENT '主机地址',
    oper_name VARCHAR(50) DEFAULT '' COMMENT '操作人员',
    oper_param TEXT COMMENT '请求参数',
    json_result TEXT COMMENT '返回参数',
    status TINYINT DEFAULT 1 COMMENT '操作状态（1=正常 0=异常）',
    error_msg TEXT COMMENT '错误消息',
    oper_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    PRIMARY KEY (id),
    KEY idx_oper_time (oper_time),
    KEY idx_oper_name (oper_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作日志记录表';

-- ============================================================================
-- 初始数据
-- ============================================================================

-- 超級管理員：admin / admin123（bcrypt 哈希，rounds=10）
INSERT INTO sys_user (id, username, password, nickname, remark, status)
VALUES (1, 'admin', '$2b$10$cG0BT3ORFQUTyMkeYVNrnOALZ7oompp1nGLRKbCIfbjDzB7WxmnEG', '超級管理員', '內建超級管理員', 1);

-- 超級管理員角色
INSERT INTO sys_role (id, role_name, role_key, sort, remark, status)
VALUES (1, '超級管理員', 'admin', 0, '內建超級管理員角色，擁有全部權限', 1);

-- 選單樹（id 固定，便於角色授權；22~30 為系統管理，1~21 為現有業務頁面）
INSERT INTO sys_menu (id, parent_id, menu_name, i18n_key, path, component, menu_type, permission, icon, sort, visible, status) VALUES
-- 系統管理（目錄）
(22, 0, '系統管理', 'system.title', '', '', 'M', '', 'SettingOutlined', 90, 1, 1),
-- 用戶管理
(23, 22, '用戶管理', 'system.user', 'system/user', 'system/UserManage', 'C', 'system:user:list', 'UserOutlined', 1, 1, 1),
(24, 23, '用戶新增', '', '', '', 'F', 'system:user:add', '', 1, 1, 1),
(25, 23, '用戶修改', '', '', '', 'F', 'system:user:edit', '', 2, 1, 1),
(26, 23, '用戶刪除', '', '', '', 'F', 'system:user:remove', '', 3, 1, 1),
(27, 23, '重置密碼', '', '', '', 'F', 'system:user:resetPwd', '', 4, 1, 1),
(28, 23, '分配角色', '', '', '', 'F', 'system:user:assignRole', '', 5, 1, 1),
-- 角色管理
(29, 22, '角色管理', 'system.role', 'system/role', 'system/RoleManage', 'C', 'system:role:list', 'TeamOutlined', 2, 1, 1),
(30, 29, '角色新增', '', '', '', 'F', 'system:role:add', '', 1, 1, 1),
(31, 29, '角色修改', '', '', '', 'F', 'system:role:edit', '', 2, 1, 1),
(32, 29, '角色刪除', '', '', '', 'F', 'system:role:remove', '', 3, 1, 1),
(33, 29, '角色授權', '', '', '', 'F', 'system:role:assignMenu', '', 4, 1, 1),
-- 選單管理
(34, 22, '選單管理', 'system.menu', 'system/menu', 'system/MenuManage', 'C', 'system:menu:list', 'MenuOutlined', 3, 1, 1),
(35, 34, '選單新增', '', '', '', 'F', 'system:menu:add', '', 1, 1, 1),
(36, 34, '選單修改', '', '', '', 'F', 'system:menu:edit', '', 2, 1, 1),
(37, 34, '選單刪除', '', '', '', 'F', 'system:menu:remove', '', 3, 1, 1),
-- 操作日誌
(38, 22, '操作日誌', 'system.operLog', 'system/log', 'system/OperLog', 'C', 'system:log:list', 'FileTextOutlined', 4, 1, 1),
(39, 38, '日誌刪除', '', '', '', 'F', 'system:log:remove', '', 1, 1, 1),
(40, 38, '日誌清空', '', '', '', 'F', 'system:log:clean', '', 2, 1, 1),
-- 儀表板
(1, 0, '儀表板', 'menu.dashboard', '/', 'DashboardView', 'C', '', 'DashboardOutlined', 0, 1, 1),
-- 樓宇監控（目錄）
(2, 0, '樓宇監控', 'menu.buildingMonitor', '', '', 'M', '', 'BankOutlined', 10, 1, 1),
(3, 2, '樓棟可視化', 'menu.buildingViewer', 'building-viewer', 'BuildingViewerView', 'C', '', 'BankOutlined', 1, 1, 1),
(4, 2, '設備管理', 'menu.devices', 'devices', 'DevicesManageView', 'C', '', 'ApiOutlined', 2, 1, 1),
(5, 2, '人流統計', 'menu.peopleCount', 'people-count', 'PeopleCountListView', 'C', '', 'DatabaseOutlined', 3, 1, 1),
(6, 2, 'ToF 列表', 'menu.tof', 'ct103', 'TofListView', 'C', '', 'ThunderboltOutlined', 4, 1, 1),
(7, 2, 'UG65 列表', 'menu.ug65', 'ug65', 'Ug65ListView', 'C', '', 'CloudOutlined', 5, 1, 1),
(8, 2, 'VS135 列表', 'menu.vs135', 'vs135', 'Vs135ListView', 'C', '', 'TeamOutlined', 6, 1, 1);

-- 超级管理员角色授予全部菜单权限（兼容已存在的数据，避免重复插入报错）
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 1, id FROM sys_menu WHERE id NOT IN (
    SELECT menu_id FROM sys_role_menu WHERE role_id = 1
);

-- 超級管理員綁定 admin 角色
INSERT INTO sys_user_role (user_id, role_id) VALUES (1, 1);
