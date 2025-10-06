
-- =======================================================================
-- AI Cloud Cost Optimization - Database Schema (PostgreSQL)  [LEAN VERSION]
-- Change: raw.costs no longer stores `operation` (GroupBy limit in CE API
--         and not required for current project scope)
-- =======================================================================

-- =========================
-- RAW SCHEMA (INGEST LAYER)
-- =========================
CREATE SCHEMA IF NOT EXISTS raw;

-- 1) Daily costs from AWS Cost Explorer (lean: SERVICE + USAGE_TYPE)
CREATE TABLE IF NOT EXISTS raw.costs (
  usage_date    DATE        NOT NULL,
  account_id    TEXT        NOT NULL,
  region        TEXT,
  service       TEXT        NOT NULL,              -- EC2/S3/RDS/Lambda/DataTransfer
  usage_type    TEXT,
  amount_usd    NUMERIC(18,6) NOT NULL DEFAULT 0,  -- normalized currency
  currency_src  TEXT        NOT NULL DEFAULT 'USD',
  tags          JSONB,                              -- cost allocation tags (optional)
  source_hash   TEXT,                               -- hash of source row (optional)
  ingested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (usage_date, account_id, region, service, usage_type)
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS ix_raw_costs_date_svc
  ON raw.costs (usage_date, service);
CREATE INDEX IF NOT EXISTS ix_raw_costs_acct_date
  ON raw.costs (account_id, usage_date);

-- 2) CloudWatch metrics (unchanged)
CREATE TABLE IF NOT EXISTS raw.metrics (
  metric_ts      TIMESTAMPTZ NOT NULL,             -- UTC
  account_id     TEXT        NOT NULL,
  region         TEXT,
  resource_id    TEXT        NOT NULL,             -- i-xxx / bucket / arn:...
  service        TEXT        NOT NULL,             -- EC2/S3/RDS/Lambda/...
  namespace      TEXT        NOT NULL,             -- AWS/EC2, AWS/S3, ...
  metric_name    TEXT        NOT NULL,             -- CPUUtilization, BucketSizeBytes, ...
  stat           TEXT        NOT NULL,             -- Average, Sum, Maximum, p95, ...
  period_seconds INT         NOT NULL,             -- 60/300/86400 ...
  metric_value   NUMERIC(18,6) NOT NULL,           -- value as-is from CloudWatch
  unit           TEXT,                             -- Percent / Bytes / Count / Milliseconds / Bytes/Second
  dimensions     JSONB,                            -- {"BucketName":"...", "StorageType":"..."}
  source_hash    TEXT,
  ingested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (metric_ts, resource_id, metric_name, stat, period_seconds)
) PARTITION BY RANGE (metric_ts);

-- Example monthly partition (Oct 2025). Create new partitions monthly.
CREATE TABLE IF NOT EXISTS raw.metrics_2025_10
  PARTITION OF raw.metrics
  FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');

CREATE INDEX IF NOT EXISTS ix_raw_metrics_res_metric_ts
  ON raw.metrics (resource_id, metric_name, metric_ts);

-- 3) Optional: resource metadata (unchanged)
CREATE TABLE IF NOT EXISTS raw.resources (
  resource_id   TEXT PRIMARY KEY,                  -- i-xxx / bucket / db-arn / lambda-arn
  service       TEXT        NOT NULL,
  account_id    TEXT        NOT NULL,
  region        TEXT,
  name          TEXT,                               -- Tag:Name if available
  tags          JSONB,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================
-- CORE SCHEMA (PROCESS LAYER)
-- ============================
CREATE SCHEMA IF NOT EXISTS core;

CREATE TABLE IF NOT EXISTS core.features (
  feature_date      DATE        NOT NULL,
  account_id        TEXT        NOT NULL,
  region            TEXT,
  service           TEXT        NOT NULL,          -- EC2/S3/RDS/Lambda/DataTransfer
  resource_id       TEXT,
  usage_type        TEXT,
  cost_usd          NUMERIC(18,6) DEFAULT 0,
  cpu_p95           NUMERIC(6,2),
  net_out_gb        NUMERIC(18,6),
  s3_storage_gb     NUMERIC(18,6),
  rds_iops_p95      NUMERIC(18,2),
  lambda_dur_p95_ms NUMERIC(18,2),
  lambda_invocations NUMERIC(18,2),
  records_from      DATE        NOT NULL DEFAULT CURRENT_DATE,
  ingested_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (feature_date, account_id, region, service, resource_id, usage_type)
);

CREATE INDEX IF NOT EXISTS ix_core_feat_date_svc
  ON core.features (feature_date, service);

CREATE TABLE IF NOT EXISTS core.forecasts (
  forecast_date   DATE        NOT NULL,
  target_date     DATE        NOT NULL,
  account_id      TEXT        NOT NULL,
  region          TEXT,
  service         TEXT        NOT NULL,
  usage_type      TEXT,
  cost_pred_usd   NUMERIC(18,6) NOT NULL,
  lower_usd       NUMERIC(18,6),
  upper_usd       NUMERIC(18,6),
  model_name      TEXT        NOT NULL,
  model_version   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (forecast_date, target_date, account_id, region, service, usage_type)
);

CREATE INDEX IF NOT EXISTS ix_core_fc_target
  ON core.forecasts (target_date, service);

CREATE TABLE IF NOT EXISTS core.recommendations (
  rec_id             BIGSERIAL PRIMARY KEY,
  rec_date           DATE        NOT NULL DEFAULT CURRENT_DATE,
  account_id         TEXT        NOT NULL,
  region             TEXT,
  target             TEXT        NOT NULL,
  rule_code          TEXT        NOT NULL,
  severity           TEXT        NOT NULL,
  estimate_save_usd  NUMERIC(18,2) NOT NULL,
  rationale          TEXT,
  status             TEXT        NOT NULL DEFAULT 'open',
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (rec_date, account_id, region, target, rule_code)
);

CREATE INDEX IF NOT EXISTS ix_core_rec_status
  ON core.recommendations (status, severity, rec_date);

-- ============================
-- MART SCHEMA (REPORT LAYER)
-- ============================
CREATE SCHEMA IF NOT EXISTS mart;

CREATE MATERIALIZED VIEW IF NOT EXISTS mart.daily_cost_by_service AS
SELECT
  usage_date,
  account_id,
  region,
  service,
  SUM(amount_usd) AS cost_usd
FROM raw.costs
GROUP BY 1,2,3,4;

CREATE INDEX IF NOT EXISTS ix_mart_cost_date_svc
  ON mart.daily_cost_by_service (usage_date, service);

-- =======================================================================
-- End of LEAN schema
-- =======================================================================
