BEGIN;

-- =========================================
-- 0) SCHEMAS
-- =========================================
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;

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

CREATE INDEX IF NOT EXISTS ix_recs_date_service ON core.recommendations (rec_date, service);
CREATE INDEX IF NOT EXISTS ix_recs_details_gin  ON core.recommendations USING GIN (details);

COMMENT ON TABLE core.recommendations IS 'Optimization recommendations (rules/ML).';

-- =========================================
-- 3) MART LAYER (ตาราง/วิวเพื่อ Dashboard)
-- =========================================

-- 3.1 mart.daily_cost_features : cost + features รายวัน (พร้อมใช้ BI)
-- หมายเหตุ: CREATE MATERIALIZED VIEW IF NOT EXISTS จะไม่อัปเดตนิยามเดิมอัตโนมัติ
-- ถ้าต้องแก้ definition ใหม่ ให้ DROP แล้ว CREATE ใหม่
CREATE SCHEMA IF NOT EXISTS mart;

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

-- 3) ดัชนียูนีค (เพื่อใช้ REFRESH CONCURRENTLY ได้)
CREATE UNIQUE INDEX IF NOT EXISTS ux_mart_dcf_unique
  ON mart.daily_cost_features (feature_date, account_id, region, service, resource_id);


COMMENT ON MATERIALIZED VIEW mart.daily_cost_features IS 'Daily join of cost and per-resource features for BI.';

COMMIT;

-- =========================================
-- 4) REFRESH MATERIALIZED VIEW (เรียกใช้หลังรัน ETL แล้ว)
-- =========================================
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mart.daily_cost_features;
