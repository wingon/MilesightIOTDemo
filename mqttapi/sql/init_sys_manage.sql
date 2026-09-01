-- ============================================================================
-- WingOnIOT 权限模块扩展：部门 / 岗位 / 登录日志 / 参数设置 / 字典管理 / 白名单
--
-- 参照 RuoYi-Vue 标准字段（dept_id、post_id、config_id、dict_id、del_flag 等）。
-- 执行方式：在数据库管理工具中执行本文件，或用 python 脚本逐条执行。
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. 部门表 sys_dept（若依标准字段）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_dept (
    dept_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '部门ID',
    parent_id BIGINT NOT NULL DEFAULT 0 COMMENT '父部门ID',
    ancestors VARCHAR(50) NOT NULL DEFAULT '' COMMENT '祖级列表',
    dept_name VARCHAR(30) NOT NULL DEFAULT '' COMMENT '部门名称',
    order_num INT NOT NULL DEFAULT 0 COMMENT '显示顺序',
    leader VARCHAR(20) DEFAULT NULL COMMENT '负责人',
    phone VARCHAR(11) DEFAULT NULL COMMENT '联系电话',
    email VARCHAR(50) DEFAULT NULL COMMENT '邮箱',
    status CHAR(1) NOT NULL DEFAULT '0' COMMENT '部门状态（0正常 1停用）',
    del_flag CHAR(1) NOT NULL DEFAULT '0' COMMENT '删除标志（0存在 2删除）',
    create_by VARCHAR(64) DEFAULT '' COMMENT '创建者',
    create_time DATETIME DEFAULT NULL COMMENT '创建时间',
    update_by VARCHAR(64) DEFAULT '' COMMENT '更新者',
    update_time DATETIME DEFAULT NULL COMMENT '更新时间',
    PRIMARY KEY (dept_id),
    KEY idx_parent_id (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='部门表';

-- ----------------------------------------------------------------------------
-- 2. 岗位表 sys_post（若依标准字段）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_post (
    post_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '岗位ID',
    post_code VARCHAR(64) NOT NULL COMMENT '岗位编码',
    post_name VARCHAR(50) NOT NULL COMMENT '岗位名称',
    post_sort INT NOT NULL COMMENT '显示顺序',
    status CHAR(1) NOT NULL DEFAULT '0' COMMENT '状态（0正常 1停用）',
    create_by VARCHAR(64) DEFAULT '' COMMENT '创建者',
    create_time DATETIME DEFAULT NULL COMMENT '创建时间',
    update_by VARCHAR(64) DEFAULT '' COMMENT '更新者',
    update_time DATETIME DEFAULT NULL COMMENT '更新时间',
    remark VARCHAR(500) DEFAULT NULL COMMENT '备注',
    PRIMARY KEY (post_id),
    UNIQUE KEY uk_post_code (post_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='岗位信息表';

-- ----------------------------------------------------------------------------
-- 3. 用户与岗位关联表 sys_user_post
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_user_post (
    user_id BIGINT NOT NULL COMMENT '用户ID',
    post_id BIGINT NOT NULL COMMENT '岗位ID',
    PRIMARY KEY (user_id, post_id),
    KEY idx_post_id (post_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户与岗位关联表';

-- ----------------------------------------------------------------------------
-- 4. 登录日志表 sys_login_log（若依标准字段）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_login_log (
    info_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '访问ID',
    user_name VARCHAR(50) DEFAULT '' COMMENT '用户账号',
    ipaddr VARCHAR(128) DEFAULT '' COMMENT '登录IP地址',
    login_location VARCHAR(255) DEFAULT '' COMMENT '登录地点',
    browser VARCHAR(50) DEFAULT '' COMMENT '浏览器类型',
    os VARCHAR(50) DEFAULT '' COMMENT '操作系统',
    status CHAR(1) DEFAULT '0' COMMENT '登录状态（0成功 1失败）',
    msg VARCHAR(255) DEFAULT '' COMMENT '提示消息',
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '访问时间',
    PRIMARY KEY (info_id),
    KEY idx_login_time (login_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统访问记录';

-- ----------------------------------------------------------------------------
-- 5. 参数配置表 sys_config（若依标准字段）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_config (
    config_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '参数主键',
    config_name VARCHAR(100) DEFAULT '' COMMENT '参数名称',
    config_key VARCHAR(100) DEFAULT '' COMMENT '参数键名',
    config_value VARCHAR(500) DEFAULT '' COMMENT '参数键值',
    config_type CHAR(1) DEFAULT 'N' COMMENT '系统内置（Y是 N否）',
    create_by VARCHAR(64) DEFAULT '' COMMENT '创建者',
    create_time DATETIME DEFAULT NULL COMMENT '创建时间',
    update_by VARCHAR(64) DEFAULT '' COMMENT '更新者',
    update_time DATETIME DEFAULT NULL COMMENT '更新时间',
    remark VARCHAR(500) DEFAULT NULL COMMENT '备注',
    PRIMARY KEY (config_id),
    UNIQUE KEY uk_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='参数配置表';

-- ----------------------------------------------------------------------------
-- 6. 字典类型表 sys_dict_type（若依标准字段）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_dict_type (
    dict_id BIGINT NOT NULL AUTO_INCREMENT COMMENT '字典主键',
    dict_name VARCHAR(100) DEFAULT '' COMMENT '字典名称',
    dict_type VARCHAR(100) DEFAULT '' COMMENT '字典类型',
    status CHAR(1) DEFAULT '0' COMMENT '状态（0正常 1停用）',
    create_by VARCHAR(64) DEFAULT '' COMMENT '创建者',
    create_time DATETIME DEFAULT NULL COMMENT '创建时间',
    update_by VARCHAR(64) DEFAULT '' COMMENT '更新者',
    update_time DATETIME DEFAULT NULL COMMENT '更新时间',
    remark VARCHAR(500) DEFAULT NULL COMMENT '备注',
    PRIMARY KEY (dict_id),
    UNIQUE KEY uk_dict_type (dict_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='字典类型表';

-- ----------------------------------------------------------------------------
-- 7. 字典数据表 sys_dict_data（若依标准字段）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_dict_data (
    dict_code BIGINT NOT NULL AUTO_INCREMENT COMMENT '字典编码',
    dict_sort INT NOT NULL DEFAULT 0 COMMENT '字典排序',
    dict_label VARCHAR(100) NOT NULL DEFAULT '' COMMENT '字典标签',
    dict_value VARCHAR(100) NOT NULL DEFAULT '' COMMENT '字典键值',
    dict_type VARCHAR(100) NOT NULL DEFAULT '' COMMENT '字典类型',
    css_class VARCHAR(100) DEFAULT NULL COMMENT '样式属性',
    list_class VARCHAR(100) DEFAULT NULL COMMENT '表格回显样式',
    is_default CHAR(1) NOT NULL DEFAULT 'N' COMMENT '是否默认（Y是 N否）',
    status CHAR(1) NOT NULL DEFAULT '0' COMMENT '状态（0正常 1停用）',
    create_by VARCHAR(64) DEFAULT '' COMMENT '创建者',
    create_time DATETIME DEFAULT NULL COMMENT '创建时间',
    update_by VARCHAR(64) DEFAULT '' COMMENT '更新者',
    update_time DATETIME DEFAULT NULL COMMENT '更新时间',
    remark VARCHAR(500) DEFAULT NULL COMMENT '备注',
    PRIMARY KEY (dict_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='字典数据表';

-- ----------------------------------------------------------------------------
-- 8. 访问白名单表 sys_whitelist（本项目自定义：大屏等免登录路径）
--    path_type: F=前端路由前缀（免登录访问页面） A=后端API前缀（免认证访问数据）
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_whitelist (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    path VARCHAR(255) NOT NULL COMMENT '白名单路径（前缀匹配）',
    path_type CHAR(1) NOT NULL DEFAULT 'F' COMMENT '类型（F=前端路由 A=后端API）',
    remark VARCHAR(200) DEFAULT NULL COMMENT '备注',
    status CHAR(1) NOT NULL DEFAULT '0' COMMENT '状态（0正常 1停用）',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_path_type (path, path_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='访问白名单表';

-- ----------------------------------------------------------------------------
-- 9. sys_user 增加部门归属 dept_id（若依标准字段，列名对齐）
-- ----------------------------------------------------------------------------
ALTER TABLE sys_user ADD COLUMN dept_id BIGINT DEFAULT NULL COMMENT '部门ID' AFTER id;
ALTER TABLE sys_user ADD COLUMN sex VARCHAR(1) DEFAULT '2' COMMENT '性别(0=男 1=女 2=未知)' AFTER avatar;

-- ============================================================================
-- 初始数据
-- ============================================================================

-- 部門（貼合本項目的永安集團組織，祖級列表若依格式）
INSERT INTO sys_dept (dept_id, parent_id, ancestors, dept_name, order_num, leader, phone, email, status, del_flag, create_by, create_time) VALUES
(100, 0, '0', '永安集團', 0, '管理員', '15888888888', 'admin@wingon.com', '0', '0', 'admin', NOW()),
(101, 100, '0,100', '深圳總公司', 1, '管理員', '15888888888', 'sz@wingon.com', '0', '0', 'admin', NOW()),
(102, 100, '0,100', '香港分公司', 2, '管理員', '15888888888', 'hk@wingon.com', '0', '0', 'admin', NOW()),
(103, 101, '0,100,101', '研發部門', 1, '王工', '15888888888', 'dev@wingon.com', '0', '0', 'admin', NOW()),
(104, 101, '0,100,101', '市場部門', 2, '李經理', '15888888888', 'mk@wingon.com', '0', '0', 'admin', NOW()),
(105, 101, '0,100,101', '測試部門', 3, '趙工', '15888888888', 'qa@wingon.com', '0', '0', 'admin', NOW()),
(106, 101, '0,100,101', '財務部門', 4, '陳主管', '15888888888', 'fin@wingon.com', '0', '0', 'admin', NOW()),
(107, 101, '0,100,101', '運維部門', 5, '張工', '15888888888', 'ops@wingon.com', '0', '0', 'admin', NOW()),
(108, 102, '0,100,102', '市場部門', 1, '劉經理', '15888888888', 'mkhk@wingon.com', '0', '0', 'admin', NOW()),
(109, 102, '0,100,102', '財務部門', 2, '陳主管', '15888888888', 'finhk@wingon.com', '0', '0', 'admin', NOW());

-- 崗位（若依預設崗位）
INSERT INTO sys_post (post_id, post_code, post_name, post_sort, status, create_by, create_time, remark) VALUES
(1, 'ceo', '董事長', 1, '0', 'admin', NOW(), ''),
(2, 'se', '項目經理', 2, '0', 'admin', NOW(), ''),
(3, 'hr', '人力資源', 3, '0', 'admin', NOW(), ''),
(4, 'user', '普通員工', 4, '0', 'admin', NOW(), '');

-- 管理員歸屬：admin 用戶 -> 研發部門 + 董事長崗位
UPDATE sys_user SET dept_id = 103 WHERE id = 1;
INSERT INTO sys_user_post (user_id, post_id) VALUES (1, 1);

-- 參數設置（若依常用參數）
INSERT INTO sys_config (config_id, config_name, config_key, config_value, config_type, create_by, create_time, remark) VALUES
(1, '用戶管理-用戶初始密碼', 'sys.user.initPassword', '123456', 'Y', 'admin', NOW(), '初始化密碼 123456'),
(2, '主框架頁-系統名稱', 'sys.index.title', '永安 IoT 控制台', 'Y', 'admin', NOW(), '系統名稱'),
(3, '主框架頁-頂部導航條背景色', 'sys.index.skinName', 'default', 'Y', 'admin', NOW(), '前端皮膚');

-- 字典類型（若依常用字典）
INSERT INTO sys_dict_type (dict_id, dict_name, dict_type, status, create_by, create_time, remark) VALUES
(1, '用戶性別', 'sys_user_sex', '0', 'admin', NOW(), '用戶性別列表'),
(2, '系統正常停用', 'sys_normal_disable', '0', 'admin', NOW(), '系統正常停用列表'),
(3, '系統是否', 'sys_yes_no', '0', 'admin', NOW(), '系統是否列表'),
(4, '操作類型', 'sys_oper_type', '0', 'admin', NOW(), '操作類型列表'),
(5, '系統狀態', 'sys_success_fail', '0', 'admin', NOW(), '系統狀態列表'),
(6, '選單狀態', 'sys_show_hide', '0', 'admin', NOW(), '選單狀態列表');

-- 字典數據
INSERT INTO sys_dict_data (dict_code, dict_sort, dict_label, dict_value, dict_type, list_class, is_default, status, create_by, create_time, remark) VALUES
(1, 1, '男', '0', 'sys_user_sex', '', 'N', '0', 'admin', NOW(), '性別男'),
(2, 2, '女', '1', 'sys_user_sex', '', 'N', '0', 'admin', NOW(), '性別女'),
(3, 3, '未知', '2', 'sys_user_sex', '', 'N', '0', 'admin', NOW(), '性別未知'),
(4, 1, '正常', '0', 'sys_normal_disable', 'primary', 'Y', '0', 'admin', NOW(), '正常狀態'),
(5, 2, '停用', '1', 'sys_normal_disable', 'danger', 'N', '0', 'admin', NOW(), '停用狀態'),
(6, 1, '是', 'Y', 'sys_yes_no', 'primary', 'Y', '0', 'admin', NOW(), '系統是否-是'),
(7, 2, '否', 'N', 'sys_yes_no', 'danger', 'N', '0', 'admin', NOW(), '系統是否-否'),
(8, 1, '新增', '1', 'sys_oper_type', 'primary', 'N', '0', 'admin', NOW(), '新增操作'),
(9, 2, '修改', '2', 'sys_oper_type', 'primary', 'N', '0', 'admin', NOW(), '修改操作'),
(10, 3, '刪除', '3', 'sys_oper_type', 'danger', 'N', '0', 'admin', NOW(), '刪除操作'),
(11, 4, '授權', '4', 'sys_oper_type', 'warning', 'N', '0', 'admin', NOW(), '授權操作'),
(12, 5, '匯出', '5', 'sys_oper_type', 'primary', 'N', '0', 'admin', NOW(), '匯出操作'),
(13, 6, '匯入', '6', 'sys_oper_type', 'primary', 'N', '0', 'admin', NOW(), '匯入操作'),
(14, 7, '強退', '7', 'sys_oper_type', 'danger', 'N', '0', 'admin', NOW(), '強退操作'),
(15, 8, '生成代碼', '8', 'sys_oper_type', 'primary', 'N', '0', 'admin', NOW(), '生成代碼操作'),
(16, 9, '清空數據', '9', 'sys_oper_type', 'danger', 'N', '0', 'admin', NOW(), '清空數據操作'),
(17, 1, '成功', '0', 'sys_success_fail', 'primary', 'N', '0', 'admin', NOW(), '成功狀態'),
(18, 2, '失敗', '1', 'sys_success_fail', 'danger', 'N', '0', 'admin', NOW(), '失敗狀態'),
(19, 1, '顯示', '0', 'sys_show_hide', 'primary', 'N', '0', 'admin', NOW(), '顯示狀態'),
(20, 2, '隱藏', '1', 'sys_show_hide', 'danger', 'N', '0', 'admin', NOW(), '隱藏狀態');

-- 白名單（大屏免登入展示：樓宇可視化 + 其數據接口）
INSERT INTO sys_whitelist (id, path, path_type, remark, status) VALUES
(1, '/building-viewer', 'F', '樓宇可視化大屏（前端路由免登入）', '0'),
(2, '/api/v1/building', 'A', '樓宇可視化數據接口', '0'),
(3, '/api/v1/environment', 'A', '環境監測數據接口', '0'),
(4, '/api/v1/facade', 'A', '幕牆配置數據接口', '0');

-- ============================================================================
-- 選單擴展：日誌管理目錄 + 部門/崗位/字典/參數/白名單/登入日誌
-- ============================================================================

-- 日誌管理目錄（掛到系統管理 id=22 下，sort=99）
INSERT INTO sys_menu (id, parent_id, menu_name, i18n_key, path, component, menu_type, permission, icon, sort, visible, status) VALUES
(61, 22, '日誌管理', 'system.logMenu', '', '', 'M', '', 'LogoutOutlined', 99, 1, 1);

-- 操作日誌歸入日誌管理目錄
UPDATE sys_menu SET parent_id = 61, sort = 1 WHERE id = 38;

-- 新增系統管理子選單與按鈕
INSERT INTO sys_menu (id, parent_id, menu_name, i18n_key, path, component, menu_type, permission, icon, sort, visible, status) VALUES
(100, 22, '部門管理', 'system.dept', 'system/dept', 'system/DeptManage', 'C', 'system:dept:list', 'ClusterOutlined', 4, 1, 1),
(101, 100, '部門新增', '', '', '', 'F', 'system:dept:add', '', 1, 1, 1),
(102, 100, '部門修改', '', '', '', 'F', 'system:dept:edit', '', 2, 1, 1),
(103, 100, '部門刪除', '', '', '', 'F', 'system:dept:remove', '', 3, 1, 1),
(110, 22, '崗位管理', 'system.post', 'system/post', 'system/PostManage', 'C', 'system:post:list', 'IdcardOutlined', 5, 1, 1),
(111, 110, '崗位新增', '', '', '', 'F', 'system:post:add', '', 1, 1, 1),
(112, 110, '崗位修改', '', '', '', 'F', 'system:post:edit', '', 2, 1, 1),
(113, 110, '崗位刪除', '', '', '', 'F', 'system:post:remove', '', 3, 1, 1),
(120, 22, '字典管理', 'system.dict', 'system/dict', 'system/DictManage', 'C', 'system:dict:list', 'BookOutlined', 6, 1, 1),
(121, 120, '字典類型新增', '', '', '', 'F', 'system:dict:add', '', 1, 1, 1),
(122, 120, '字典類型修改', '', '', '', 'F', 'system:dict:edit', '', 2, 1, 1),
(123, 120, '字典類型刪除', '', '', '', 'F', 'system:dict:remove', '', 3, 1, 1),
(124, 120, '字典數據新增', '', '', '', 'F', 'system:dict:addData', '', 4, 1, 1),
(125, 120, '字典數據修改', '', '', '', 'F', 'system:dict:editData', '', 5, 1, 1),
(126, 120, '字典數據刪除', '', '', '', 'F', 'system:dict:removeData', '', 6, 1, 1),
(130, 22, '參數設置', 'system.config', 'system/config', 'system/ConfigManage', 'C', 'system:config:list', 'SettingOutlined', 7, 1, 1),
(131, 130, '參數新增', '', '', '', 'F', 'system:config:add', '', 1, 1, 1),
(132, 130, '參數修改', '', '', '', 'F', 'system:config:edit', '', 2, 1, 1),
(133, 130, '參數刪除', '', '', '', 'F', 'system:config:remove', '', 3, 1, 1),
(140, 22, '白名單設置', 'system.whitelist', 'system/whitelist', 'system/WhitelistManage', 'C', 'system:whitelist:list', 'SafetyCertificateOutlined', 8, 1, 1),
(141, 140, '白名單新增', '', '', '', 'F', 'system:whitelist:add', '', 1, 1, 1),
(142, 140, '白名單修改', '', '', '', 'F', 'system:whitelist:edit', '', 2, 1, 1),
(143, 140, '白名單刪除', '', '', '', 'F', 'system:whitelist:remove', '', 3, 1, 1),
(150, 61, '登入日誌', 'system.loginLog', 'system/login-log', 'system/LoginLog', 'C', 'system:loginlog:list', 'LoginOutlined', 2, 1, 1),
(151, 150, '日誌刪除', '', '', '', 'F', 'system:loginlog:remove', '', 1, 1, 1),
(152, 150, '日誌清空', '', '', '', 'F', 'system:loginlog:clean', '', 2, 1, 1);

-- 超級管理員角色授予全部新增選單權限
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 1, id FROM sys_menu WHERE id >= 61 AND id NOT IN (
    SELECT menu_id FROM sys_role_menu WHERE role_id = 1
);
