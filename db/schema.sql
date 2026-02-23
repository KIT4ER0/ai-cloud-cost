<<<<<<< Updated upstream
BEGIN;
=======
-- =========================
-- Schema: cloudcost
-- Services: EC2, Lambda, RDS, S3
-- metrics & costs have their own IDs (PK)
-- No aws_accounts/aws_regions tables
-- No created_at/updated_at
-- No user_id in any table
-- =========================
>>>>>>> Stashed changes

-- =========================================
-- 0) SCHEMAS
-- =========================================
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;

<<<<<<< Updated upstream
-- =========================================
-- 1) RAW LAYER (แหล่งข้อมูลดิบ)
-- =========================================

-- 1.1 raw.costs : ค่าบริการรายวันจาก AWS Cost Explorer
CREATE TABLE IF NOT EXISTS raw.costs (
  usage_date     date         NOT NULL,
  account_id     varchar(20)  NOT NULL,
  region         varchar(50)  NOT NULL DEFAULT 'global',
  service        varchar(50)  NOT NULL,
  usage_type     varchar(100) NOT NULL,

  amount_usd     numeric(18,6) NOT NULL DEFAULT 0,
  currency_src   varchar(10)   NOT NULL DEFAULT 'USD',
  tags           jsonb         NOT NULL DEFAULT '{}'::jsonb,

  source_hash    text,
  ingested_at    timestamptz   NOT NULL DEFAULT now(),

  CONSTRAINT costs_pkey PRIMARY KEY (usage_date, account_id, region, service, usage_type)
);

-- ดัชนีช่วยคิวรีที่ใช้บ่อย
CREATE INDEX IF NOT EXISTS ix_costs_date_service   ON raw.costs (usage_date, service);
CREATE INDEX IF NOT EXISTS ix_costs_acct_region    ON raw.costs (account_id, region);
CREATE INDEX IF NOT EXISTS ix_costs_tags_gin       ON raw.costs USING GIN (tags);

COMMENT ON TABLE raw.costs IS 'Daily AWS costs by service/region. Source: Cost Explorer.';
COMMENT ON COLUMN raw.costs.tags IS 'Original CE tags (JSONB).';

-- 1.2 raw.metrics : เมตริกจาก CloudWatch (time series)
CREATE TABLE IF NOT EXISTS raw.metrics (
  metric_ts       timestamptz  NOT NULL,       -- เวลาจริงของจุดข้อมูล
  account_id      varchar(20)  NOT NULL,
  region          varchar(50)  NOT NULL DEFAULT 'us-east-1',
  resource_id     varchar(200) NOT NULL,       -- instance-id / arn / bucket
  service         varchar(50)  NOT NULL,       -- EC2/S3/RDS/Lambda/...
  namespace       varchar(100) NOT NULL,       -- AWS/EC2, AWS/S3, ...
  metric_name     varchar(100) NOT NULL,       -- CPUUtilization, BucketSizeBytes, ...
  stat            varchar(32)  NOT NULL,       -- Average, Sum, p95, Minimum, ...
  period_seconds  integer      NOT NULL,       -- 60/300/...
  metric_value    numeric(18,6) NOT NULL,
  unit            varchar(32)  NOT NULL,       -- Percent, Bytes, Bytes/Second, Milliseconds, Count...

  dimensions      jsonb         NOT NULL DEFAULT '{}'::jsonb,  -- Dimension dict
  source_hash     text,
  ingested_at     timestamptz   NOT NULL DEFAULT now(),

  CONSTRAINT metrics_pkey PRIMARY KEY (metric_ts, resource_id, metric_name, stat, period_seconds)
);

-- ดัชนีช่วยคิวรี
CREATE INDEX IF NOT EXISTS ix_metrics_service_name_ts  ON raw.metrics (service, metric_name, metric_ts);
CREATE INDEX IF NOT EXISTS ix_metrics_resource_ts      ON raw.metrics (resource_id, metric_ts);
CREATE INDEX IF NOT EXISTS ix_metrics_dimensions_gin   ON raw.metrics USING GIN (dimensions);

COMMENT ON TABLE raw.metrics IS 'CloudWatch metrics (time series) normalized.';
COMMENT ON COLUMN raw.metrics.dimensions IS 'Original CW dimensions (JSONB).';

-- =========================================
-- 2) CORE LAYER (Aggregation/Features)
-- =========================================

-- 2.1 core.features : ฟีเจอร์รายวันต่อทรัพยากร (ผลจาก Aggregation)
CREATE TABLE IF NOT EXISTS core.features (
  feature_date                 date         NOT NULL,
  account_id                   varchar(20)  NOT NULL,
  region                       varchar(50)  NOT NULL,
  service                      varchar(50)  NOT NULL,
  resource_id                  varchar(200) NOT NULL,
  usage_type                   varchar(100) NOT NULL DEFAULT 'n/a',

  cpu_p95                      numeric(18,6),
  storage_gb                   numeric(18,6),
  network_gb                   numeric(18,6),
  lambda_duration_p95_ms       numeric(18,6),
  lambda_invocations           numeric(18,6),
  rds_cpu_p95                  numeric(18,6),
  rds_conn_avg                 numeric(18,6),
  rds_free_storage_gb_min      numeric(18,6),

  records_from                 date,
  ingested_at                  timestamptz  NOT NULL DEFAULT now(),

  CONSTRAINT features_pkey PRIMARY KEY (feature_date, account_id, region, service, resource_id, usage_type)
);

-- เผื่อกรณีตารางมีอยู่แล้วแต่คอลัมน์ยังไม่ครบ/ค่า default ยังไม่ตั้ง
ALTER TABLE core.features
  ALTER COLUMN usage_type SET DEFAULT 'n/a';
=======
-- =========================
-- Users
-- =========================
CREATE TABLE IF NOT EXISTS users (
  user_id        BIGSERIAL PRIMARY KEY,
  email          TEXT NOT NULL UNIQUE,
  password_hash  TEXT NOT NULL,
  display_name   TEXT,
  role           TEXT NOT NULL DEFAULT 'user',   -- user/admin
  is_active      BOOLEAN NOT NULL DEFAULT TRUE
);

-- =========================
-- Users
-- =========================
CREATE TABLE IF NOT EXISTS users (
  user_id        BIGSERIAL PRIMARY KEY,
  email          TEXT NOT NULL UNIQUE,
  password_hash  TEXT NOT NULL,
  display_name   TEXT,
  role           TEXT NOT NULL DEFAULT 'user',   -- user/admin
  is_active      BOOLEAN NOT NULL DEFAULT TRUE
);

-- =========================
-- 1) EC2
-- =========================
CREATE TABLE IF NOT EXISTS ec2_resources (
  ec2_resource_id BIGSERIAL PRIMARY KEY,
  account_id      VARCHAR(12) NOT NULL,
  region          TEXT NOT NULL,
  instance_id     TEXT NOT NULL,
  instance_type   TEXT,
  state           TEXT,
  UNIQUE (account_id, region, instance_id)
);

CREATE TABLE IF NOT EXISTS ec2_metrics (
  ec2_metric_id       BIGSERIAL PRIMARY KEY,
  ec2_resource_id     BIGINT NOT NULL REFERENCES ec2_resources(ec2_resource_id) ON DELETE CASCADE,
  metric_date         DATE NOT NULL,
  cpu_p95             DOUBLE PRECISION,
  network_out_gb_sum  DOUBLE PRECISION,
  UNIQUE (ec2_resource_id, metric_date)
);

CREATE TABLE IF NOT EXISTS ec2_costs (
  ec2_cost_id     BIGSERIAL PRIMARY KEY,
  ec2_resource_id BIGINT NOT NULL REFERENCES ec2_resources(ec2_resource_id) ON DELETE CASCADE,
  usage_date      DATE NOT NULL,
  usage_type      TEXT NOT NULL DEFAULT 'total',
  amount_usd      NUMERIC(14,6) NOT NULL DEFAULT 0,
  currency_src    TEXT NOT NULL DEFAULT 'USD',
  UNIQUE (ec2_resource_id, usage_date, usage_type)
);

CREATE INDEX IF NOT EXISTS idx_ec2_resources_acct_region ON ec2_resources(account_id, region);
CREATE INDEX IF NOT EXISTS idx_ec2_metrics_date          ON ec2_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_ec2_costs_date            ON ec2_costs(usage_date);
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes

-- ดัชนีช่วยคิวรี
CREATE INDEX IF NOT EXISTS ix_features_date_service ON core.features (feature_date, service);
CREATE INDEX IF NOT EXISTS ix_features_resource     ON core.features (service, resource_id);

COMMENT ON TABLE core.features IS 'Daily per-resource features derived from raw.metrics.';

-- 2.2 core.recommendations : ข้อเสนอแนะ/การกระทำ (rule/ML output)
CREATE TABLE IF NOT EXISTS core.recommendations (
  rec_date       date         NOT NULL,
  account_id     varchar(20)  NOT NULL,
  region         varchar(50)  NOT NULL,
  service        varchar(50)  NOT NULL,
  resource_id    varchar(200) NOT NULL,
  rec_type       text         NOT NULL,          -- e.g. rightsize-ec2, s3-lifecycle
  details        jsonb        NOT NULL DEFAULT '{}'::jsonb,
  est_saving_usd numeric(18,6),
  confidence     numeric(6,3),                   -- 0..1

  created_at     timestamptz  NOT NULL DEFAULT now(),

  CONSTRAINT recommendations_pkey PRIMARY KEY (rec_date, account_id, region, service, resource_id, rec_type)
);

<<<<<<< Updated upstream
CREATE INDEX IF NOT EXISTS ix_recs_date_service ON core.recommendations (rec_date, service);
CREATE INDEX IF NOT EXISTS ix_recs_details_gin  ON core.recommendations USING GIN (details);

COMMENT ON TABLE core.recommendations IS 'Optimization recommendations (rules/ML).';

-- =========================================
-- 3) MART LAYER (ตาราง/วิวเพื่อ Dashboard)
-- =========================================
=======
CREATE TABLE IF NOT EXISTS lambda_metrics (
  lambda_metric_id       BIGSERIAL PRIMARY KEY,
  lambda_resource_id     BIGINT NOT NULL REFERENCES lambda_resources(lambda_resource_id) ON DELETE CASCADE,
  metric_date            DATE NOT NULL,
  duration_p95_ms        DOUBLE PRECISION,
  invocations_sum        DOUBLE PRECISION,
  errors_sum             DOUBLE PRECISION,
  UNIQUE (lambda_resource_id, metric_date)
);

CREATE TABLE IF NOT EXISTS lambda_costs (
  lambda_cost_id      BIGSERIAL PRIMARY KEY,
  lambda_resource_id  BIGINT NOT NULL REFERENCES lambda_resources(lambda_resource_id) ON DELETE CASCADE,
  usage_date          DATE NOT NULL,
  usage_type          TEXT NOT NULL DEFAULT 'total',
  amount_usd          NUMERIC(14,6) NOT NULL DEFAULT 0,
  currency_src        TEXT NOT NULL DEFAULT 'USD',
  UNIQUE (lambda_resource_id, usage_date, usage_type)
);

CREATE INDEX IF NOT EXISTS idx_lambda_resources_acct_region ON lambda_resources(account_id, region);
CREATE INDEX IF NOT EXISTS idx_lambda_metrics_date          ON lambda_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_lambda_costs_date            ON lambda_costs(usage_date);
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes

-- 3.1 mart.daily_cost_features : cost + features รายวัน (พร้อมใช้ BI)
-- หมายเหตุ: CREATE MATERIALIZED VIEW IF NOT EXISTS จะไม่อัปเดตนิยามเดิมอัตโนมัติ
-- ถ้าต้องแก้ definition ใหม่ ให้ DROP แล้ว CREATE ใหม่
CREATE SCHEMA IF NOT EXISTS mart;

<<<<<<< Updated upstream
-- ลบของเดิมถ้ามี (เพื่ออัปเดตนิยาม)
DROP MATERIALIZED VIEW IF EXISTS mart.daily_cost_features;

-- 1) สร้าง Materialized View
CREATE MATERIALIZED VIEW mart.daily_cost_features AS
SELECT
  f.feature_date,
  f.account_id, f.region, f.service, f.resource_id,
  c.amount_usd,
  f.cpu_p95, f.network_gb, f.storage_gb,
  f.lambda_duration_p95_ms, f.lambda_invocations,
  f.rds_cpu_p95, f.rds_conn_avg, f.rds_free_storage_gb_min
FROM core.features f
LEFT JOIN (
  SELECT usage_date, account_id, region, service, SUM(amount_usd) AS amount_usd
  FROM raw.costs
  GROUP BY 1,2,3,4
) c
  ON (c.usage_date, c.account_id, c.region, c.service)
   = (f.feature_date, f.account_id, f.region, f.service)
WITH NO DATA;   -- สร้างก่อน ค่อย REFRESH เติมข้อมูล

-- 2) ดัชนีสำหรับอ่านเร็ว
CREATE INDEX IF NOT EXISTS ix_mart_dcf_date_svc_acct
  ON mart.daily_cost_features (feature_date, service, account_id);
CREATE INDEX IF NOT EXISTS ix_mart_dcf_resource
  ON mart.daily_cost_features (service, resource_id);
=======
CREATE TABLE IF NOT EXISTS rds_metrics (
  rds_metric_id         BIGSERIAL PRIMARY KEY,
  rds_resource_id       BIGINT NOT NULL REFERENCES rds_resources(rds_resource_id) ON DELETE CASCADE,
  metric_date           DATE NOT NULL,
  cpu_p95               DOUBLE PRECISION,
  db_conn_avg           DOUBLE PRECISION,
  free_storage_gb_min   DOUBLE PRECISION,
  UNIQUE (rds_resource_id, metric_date)
);

CREATE TABLE IF NOT EXISTS rds_costs (
  rds_cost_id      BIGSERIAL PRIMARY KEY,
  rds_resource_id  BIGINT NOT NULL REFERENCES rds_resources(rds_resource_id) ON DELETE CASCADE,
  usage_date       DATE NOT NULL,
  usage_type       TEXT NOT NULL DEFAULT 'total',
  amount_usd       NUMERIC(14,6) NOT NULL DEFAULT 0,
  currency_src     TEXT NOT NULL DEFAULT 'USD',
  UNIQUE (rds_resource_id, usage_date, usage_type)
);

CREATE INDEX IF NOT EXISTS idx_rds_resources_acct_region ON rds_resources(account_id, region);
CREATE INDEX IF NOT EXISTS idx_rds_metrics_date          ON rds_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_rds_costs_date            ON rds_costs(usage_date);
<<<<<<< Updated upstream
>>>>>>> Stashed changes
=======
>>>>>>> Stashed changes

-- 3) ดัชนียูนีค (เพื่อใช้ REFRESH CONCURRENTLY ได้)
CREATE UNIQUE INDEX IF NOT EXISTS ux_mart_dcf_unique
  ON mart.daily_cost_features (feature_date, account_id, region, service, resource_id);

<<<<<<< Updated upstream

COMMENT ON MATERIALIZED VIEW mart.daily_cost_features IS 'Daily join of cost and per-resource features for BI.';

COMMIT;

-- =========================================
-- 4) REFRESH MATERIALIZED VIEW (เรียกใช้หลังรัน ETL แล้ว)
-- =========================================
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mart.daily_cost_features;
=======
CREATE TABLE IF NOT EXISTS s3_metrics (
  s3_metric_id        BIGSERIAL PRIMARY KEY,
  s3_resource_id      BIGINT NOT NULL REFERENCES s3_resources(s3_resource_id) ON DELETE CASCADE,
  metric_date         DATE NOT NULL,
  storage_gb_avg      DOUBLE PRECISION,
  number_of_objects   DOUBLE PRECISION,
  UNIQUE (s3_resource_id, metric_date)
);

CREATE TABLE IF NOT EXISTS s3_costs (
  s3_cost_id      BIGSERIAL PRIMARY KEY,
  s3_resource_id  BIGINT NOT NULL REFERENCES s3_resources(s3_resource_id) ON DELETE CASCADE,
  usage_date      DATE NOT NULL,
  usage_type      TEXT NOT NULL DEFAULT 'total',
  amount_usd      NUMERIC(14,6) NOT NULL DEFAULT 0,
  currency_src    TEXT NOT NULL DEFAULT 'USD',
  UNIQUE (s3_resource_id, usage_date, usage_type)
);

CREATE INDEX IF NOT EXISTS idx_s3_resources_acct_region ON s3_resources(account_id, region);
CREATE INDEX IF NOT EXISTS idx_s3_metrics_date          ON s3_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_s3_costs_date            ON s3_costs(usage_date);

-- =========================
-- Recommendations (Generic)
-- =========================
CREATE TABLE IF NOT EXISTS recommendations (
  rec_id          BIGSERIAL PRIMARY KEY,
  rec_date        DATE NOT NULL,
  account_id      VARCHAR(12) NOT NULL,
  region          TEXT NOT NULL,
  service         TEXT NOT NULL,         -- EC2/Lambda/RDS/S3/DataTransfer
  resource_key    TEXT NOT NULL,         -- instance_id / function_name / db_identifier / bucket_name / etc.
  rec_type        TEXT NOT NULL,         -- เช่น EC2_RIGHTSIZE_P95_LOW
  details         JSONB NOT NULL DEFAULT '{}'::jsonb,
  est_saving_usd  NUMERIC(14,6),
  confidence      DOUBLE PRECISION,
  status          TEXT NOT NULL DEFAULT 'open', -- open/accepted/rejected/done
  UNIQUE (rec_date, account_id, region, service, resource_key, rec_type)
);

CREATE INDEX IF NOT EXISTS idx_recs_date     ON recommendations(rec_date);
CREATE INDEX IF NOT EXISTS idx_recs_service  ON recommendations(service);
CREATE INDEX IF NOT EXISTS idx_recs_status   ON recommendations(status);
<<<<<<< Updated upstream
CREATE INDEX IF NOT EXISTS idx_recs_acct_reg ON recommendations(account_id, region);
>>>>>>> Stashed changes
=======
CREATE INDEX IF NOT EXISTS idx_recs_acct_reg ON recommendations(account_id, region);
>>>>>>> Stashed changes
