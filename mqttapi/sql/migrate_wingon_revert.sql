-- ============================================================================
-- WingOnIOT 表名还原迁移脚本（一次性）
--   将表名从环境监测小写风格还原为首字母大写风格，与其他系统保持一致：
--     environment_device       -> Environment_Device
--     environmental_monitoring -> Environmental_Monitoring
--   MySQL 会自动更新外键引用，device_cell 的 FK 无需手动修改。
--   幂等：若目标表已存在则跳过（不报错）。
-- ============================================================================

-- 还原表名
RENAME TABLE `environment_device` TO `Environment_Device`,
             `environmental_monitoring` TO `Environmental_Monitoring`;
