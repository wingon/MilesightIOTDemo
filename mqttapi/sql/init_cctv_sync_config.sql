-- ============================================================================
-- CCTV 人流統計定時同步參數（結合系統管理「參數設置」維護）
--   cctv.sync.enabled            ：同步總開關（Y 啟用 / N 停用）
--   cctv.sync.cron.anytime        ：按需同步當天資料（cron，5 段式）
--   cctv.sync.cron.yesterday     ：每天同步昨天完整 24h（cron，5 段式）
--   cctv.sync.cron.backfill      ：每天回填當月缺失日期（cron，5 段式）
-- 執行後可於前端「系統管理 > 參數設置」調整，cron 修改即時生效（熱更新）。
-- ============================================================================

INSERT INTO sys_config (config_name, config_key, config_value, config_type, create_by, create_time, remark) VALUES
('CCTV 人流同步開關', 'cctv.sync.enabled', 'Y', 'N', 'admin', NOW(), 'Y 啟用 / N 停用 CCTV 人流定時同步'),
('CCTV 定時同步 cron', 'cctv.sync.cron.anytime', '5 * * * *', 'N', 'admin', NOW(), '每小時 05 分同步當天資料'),
('CCTV 昨天補全 cron', 'cctv.sync.cron.yesterday', '5 0 * * *', 'N', 'admin', NOW(), '每天 00:05 同步昨天完整 24 小時'),
('CCTV 當月回填 cron', 'cctv.sync.cron.backfill', '10 0 * * *', 'N', 'admin', NOW(), '每天 00:10 回填當月缺失日期');
