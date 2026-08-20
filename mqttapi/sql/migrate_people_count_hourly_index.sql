-- Add a composite index to support common filtered queries on people_count_hourly.
-- The index covers (date, channel_name, hour) so filters by date range combined
-- with channel_name / hour can be resolved with an index range scan instead of
-- a full table scan. The existing uk_date_hour_ip (date, hour, ip_address)
-- unique key already covers date + hour + ip_address lookups.
USE WingOnIOT;

ALTER TABLE people_count_hourly
    ADD INDEX idx_date_channel_hour (date, channel_name, hour);