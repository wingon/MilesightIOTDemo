USE milesight;

ALTER TABLE ug65
  ADD COLUMN IF NOT EXISTS gateway_model VARCHAR(16) NULL AFTER gateway_name;

CREATE INDEX IF NOT EXISTS idx_gateway_model ON ug65 (gateway_model);
