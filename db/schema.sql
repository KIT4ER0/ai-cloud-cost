-- =========================
-- Schema: cloudcost
-- Services: EC2, Lambda, RDS, S3, ALB
-- Auth: Supabase Auth (auth.users)
-- =========================

CREATE SCHEMA IF NOT EXISTS cloudcost;
SET search_path TO cloudcost;

-- =========================
-- User Profiles
-- =========================
CREATE TABLE IF NOT EXISTS user_profiles (
  profile_id          BIGSERIAL PRIMARY KEY,
  supabase_user_id    TEXT NOT NULL UNIQUE,
  email               TEXT,
  aws_role_arn        TEXT,
  aws_external_id     TEXT UNIQUE
);

-- =========================
-- 1) EC2
-- =========================
CREATE TABLE IF NOT EXISTS ec2_resources (
  ec2_resource_id BIGSERIAL PRIMARY KEY,
  profile_id      BIGINT NOT NULL REFERENCES user_profiles(profile_id),
  account_id      VARCHAR(12) NOT NULL,
  region          TEXT NOT NULL,
  instance_id     TEXT NOT NULL,
  instance_type   TEXT,
  state           TEXT,
  launch_time     TIMESTAMP,
  UNIQUE (account_id, region, instance_id)
);

CREATE TABLE IF NOT EXISTS ec2_metrics (
  ec2_metric_id       BIGSERIAL PRIMARY KEY,
  ec2_resource_id     BIGINT NOT NULL REFERENCES ec2_resources(ec2_resource_id) ON DELETE CASCADE,
  metric_date         DATE NOT NULL,
  cpu_utilization     DOUBLE PRECISION,
  network_in          BIGINT,
  network_out         BIGINT,
  hours_running       DOUBLE PRECISION,
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
CREATE INDEX IF NOT EXISTS idx_ec2_resources_profile     ON ec2_resources(profile_id);
CREATE INDEX IF NOT EXISTS idx_ec2_metrics_date          ON ec2_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_ec2_costs_date            ON ec2_costs(usage_date);

-- =========================
-- 2) Lambda
-- =========================
CREATE TABLE IF NOT EXISTS lambda_resources (
  lambda_resource_id BIGSERIAL PRIMARY KEY,
  profile_id         BIGINT NOT NULL REFERENCES user_profiles(profile_id),
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
  duration_p95           DOUBLE PRECISION,
  invocations            BIGINT,
  errors                 BIGINT,
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
CREATE INDEX IF NOT EXISTS idx_lambda_resources_profile     ON lambda_resources(profile_id);
CREATE INDEX IF NOT EXISTS idx_lambda_metrics_date          ON lambda_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_lambda_costs_date            ON lambda_costs(usage_date);

-- =========================
-- 3) RDS
-- =========================
CREATE TABLE IF NOT EXISTS rds_resources (
  rds_resource_id BIGSERIAL PRIMARY KEY,
  profile_id      BIGINT NOT NULL REFERENCES user_profiles(profile_id),
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
  cpu_utilization       DOUBLE PRECISION,
  database_connections  BIGINT,
  free_storage_space    BIGINT,
  data_transfer         BIGINT,
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
CREATE INDEX IF NOT EXISTS idx_rds_resources_profile     ON rds_resources(profile_id);
CREATE INDEX IF NOT EXISTS idx_rds_metrics_date          ON rds_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_rds_costs_date            ON rds_costs(usage_date);

-- =========================
-- 4) S3
-- =========================
CREATE TABLE IF NOT EXISTS s3_resources (
  s3_resource_id BIGSERIAL PRIMARY KEY,
  profile_id     BIGINT NOT NULL REFERENCES user_profiles(profile_id),
  account_id     VARCHAR(12) NOT NULL,
  region         TEXT NOT NULL,
  bucket_name    TEXT NOT NULL,
  storage_class  TEXT NOT NULL,
  bucket_arn     TEXT,
  is_versioning_enabled BOOLEAN DEFAULT FALSE,
  tags           JSONB,
  created_at     TIMESTAMPTZ DEFAULT NOW(),
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (account_id, region, bucket_name)
);

CREATE TABLE IF NOT EXISTS s3_metrics (
  s3_metric_id        BIGSERIAL PRIMARY KEY,
  s3_resource_id      BIGINT NOT NULL REFERENCES s3_resources(s3_resource_id) ON DELETE CASCADE,
  metric_date         DATE NOT NULL,
  bucket_size_bytes   BIGINT,
  number_of_objects   BIGINT,
  get_requests        BIGINT,
  put_requests        BIGINT,
  bytes_downloaded    BIGINT,
  bytes_uploaded      BIGINT,
  delete_requests     BIGINT,
  list_requests       BIGINT,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (s3_resource_id, metric_date)
);

CREATE TABLE IF NOT EXISTS s3_costs (
  s3_cost_id      BIGSERIAL PRIMARY KEY,
  s3_resource_id  BIGINT NOT NULL REFERENCES s3_resources(s3_resource_id) ON DELETE CASCADE,
  usage_date      DATE NOT NULL,
  usage_type      TEXT NOT NULL DEFAULT 'total',
  amount_usd      NUMERIC(14,6) NOT NULL DEFAULT 0,
  currency_src    TEXT NOT NULL DEFAULT 'USD',
  unit            TEXT,
  cost_type       TEXT DEFAULT 'unblended',
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (s3_resource_id, usage_date, usage_type)
);

CREATE INDEX IF NOT EXISTS idx_s3_resources_acct_region ON s3_resources(account_id, region);
CREATE INDEX IF NOT EXISTS idx_s3_resources_profile     ON s3_resources(profile_id);
CREATE INDEX IF NOT EXISTS idx_s3_metrics_date          ON s3_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_s3_costs_date            ON s3_costs(usage_date);

-- =========================
-- 5) ALB (Application Load Balancer)
-- =========================
CREATE TABLE IF NOT EXISTS alb_resources (
  alb_resource_id BIGSERIAL PRIMARY KEY,
  profile_id      BIGINT NOT NULL REFERENCES user_profiles(profile_id),
  account_id      VARCHAR(12) NOT NULL,
  region          TEXT NOT NULL,
  lb_name         TEXT NOT NULL,
  lb_arn          TEXT,
  dns_name        TEXT,
  scheme          TEXT,
  UNIQUE (account_id, region, lb_name)
);

CREATE TABLE IF NOT EXISTS alb_metrics (
  alb_metric_id         BIGSERIAL PRIMARY KEY,
  alb_resource_id       BIGINT NOT NULL REFERENCES alb_resources(alb_resource_id) ON DELETE CASCADE,
  metric_date           DATE NOT NULL,
  request_count         BIGINT,
  response_time_p95     DOUBLE PRECISION,
  http_5xx_count        BIGINT,
  active_conn_count     BIGINT,
  UNIQUE (alb_resource_id, metric_date)
);

CREATE TABLE IF NOT EXISTS alb_costs (
  alb_cost_id      BIGSERIAL PRIMARY KEY,
  alb_resource_id  BIGINT NOT NULL REFERENCES alb_resources(alb_resource_id) ON DELETE CASCADE,
  usage_date       DATE NOT NULL,
  usage_type       TEXT NOT NULL DEFAULT 'total',
  amount_usd       NUMERIC(14,6) NOT NULL DEFAULT 0,
  currency_src     TEXT NOT NULL DEFAULT 'USD',
  UNIQUE (alb_resource_id, usage_date, usage_type)
);

CREATE INDEX IF NOT EXISTS idx_alb_resources_acct_region ON alb_resources(account_id, region);
CREATE INDEX IF NOT EXISTS idx_alb_resources_profile     ON alb_resources(profile_id);
CREATE INDEX IF NOT EXISTS idx_alb_metrics_date          ON alb_metrics(metric_date);
CREATE INDEX IF NOT EXISTS idx_alb_costs_date            ON alb_costs(usage_date);

-- =========================
-- Recommendations (Generic)
-- =========================
CREATE TABLE IF NOT EXISTS recommendations (
  rec_id          BIGSERIAL PRIMARY KEY,
  profile_id      BIGINT NOT NULL REFERENCES user_profiles(profile_id),
  rec_date        DATE NOT NULL,
  account_id      VARCHAR(12) NOT NULL,
  region          TEXT NOT NULL,
  service         TEXT NOT NULL,         -- EC2/Lambda/RDS/S3/ALB/DataTransfer
  resource_key    TEXT NOT NULL,         -- instance_id / function_name / db_identifier / bucket_name / lb_name
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
CREATE INDEX IF NOT EXISTS idx_recs_profile  ON recommendations(profile_id);

-- =========================
-- Forecast Runs (Baseline)
-- =========================
CREATE TABLE IF NOT EXISTS forecast_runs (
  run_id          BIGSERIAL PRIMARY KEY,
  profile_id      BIGINT NOT NULL REFERENCES user_profiles(profile_id),
  service         TEXT NOT NULL,           -- ec2 / rds / lambda / s3 / alb
  resource_id     BIGINT NOT NULL,         -- e.g. ec2_resource_id
  metric          TEXT NOT NULL,           -- e.g. cpu_utilization
  method          TEXT NOT NULL,           -- naive / moving_average / seasonal_naive
  params          JSONB NOT NULL DEFAULT '{}'::jsonb,  -- {"window": 7, "season_length": 7}
  horizon         INTEGER NOT NULL,
  train_size      INTEGER,                 -- จำนวน data points ที่ใช้ train
  mae             DOUBLE PRECISION,
  rmse            DOUBLE PRECISION,
  mape            DOUBLE PRECISION,
  created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_forecast_runs_profile  ON forecast_runs(profile_id);
CREATE INDEX IF NOT EXISTS idx_forecast_runs_service  ON forecast_runs(service, resource_id, metric);
CREATE INDEX IF NOT EXISTS idx_forecast_runs_created  ON forecast_runs(created_at);

-- =========================
-- Forecast Values
-- =========================
CREATE TABLE IF NOT EXISTS forecast_values (
  value_id        BIGSERIAL PRIMARY KEY,
  run_id          BIGINT NOT NULL REFERENCES forecast_runs(run_id) ON DELETE CASCADE,
  forecast_date   DATE NOT NULL,
  forecast_value  DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_forecast_values_run    ON forecast_values(run_id);
CREATE INDEX IF NOT EXISTS idx_forecast_values_date   ON forecast_values(forecast_date);
