-- =========================
-- Schema: cloudcost
-- Services: EC2, Lambda, RDS, S3
-- metrics & costs have their own IDs (PK)
-- No aws_accounts/aws_regions tables
-- No created_at/updated_at
-- No user_id in any table
-- =========================

CREATE SCHEMA IF NOT EXISTS cloudcost;
SET search_path TO cloudcost;

-- =========================
-- Users
-- =========================
CREATE TABLE IF NOT EXISTS users (
  user_id        BIGSERIAL PRIMARY KEY,
  email          TEXT NOT NULL UNIQUE,
  password_hash  TEXT NOT NULL,
  aws_role_arn   TEXT,
  aws_external_id TEXT UNIQUE
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

-- =========================
-- 2) Lambda
-- =========================
CREATE TABLE IF NOT EXISTS lambda_resources (
  lambda_resource_id BIGSERIAL PRIMARY KEY,
  account_id         VARCHAR(12) NOT NULL,
  region             TEXT NOT NULL,
  function_name      TEXT NOT NULL,
  function_arn       TEXT,
  runtime            TEXT,
  memory_mb          INTEGER,
  timeout_sec        INTEGER,
  UNIQUE (account_id, region, function_name)
);

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

-- =========================
-- 3) RDS
-- =========================
CREATE TABLE IF NOT EXISTS rds_resources (
  rds_resource_id BIGSERIAL PRIMARY KEY,
  account_id      VARCHAR(12) NOT NULL,
  region          TEXT NOT NULL,
  db_identifier   TEXT NOT NULL,
  engine          TEXT,
  instance_class  TEXT,
  storage_type    TEXT,
  allocated_gb    INTEGER,
  UNIQUE (account_id, region, db_identifier)
);

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

-- =========================
-- 4) S3
-- =========================
CREATE TABLE IF NOT EXISTS s3_resources (
  s3_resource_id BIGSERIAL PRIMARY KEY,
  account_id     VARCHAR(12) NOT NULL,
  region         TEXT NOT NULL,
  bucket_name    TEXT NOT NULL,
  UNIQUE (account_id, region, bucket_name)
);

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
CREATE INDEX IF NOT EXISTS idx_recs_acct_reg ON recommendations(account_id, region);
