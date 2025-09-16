CREATE TABLE IF NOT EXISTS raw_costs (
  id BIGSERIAL PRIMARY KEY,
  usage_date DATE NOT NULL,
  service TEXT NOT NULL,
  usage_type TEXT,
  amount NUMERIC(18,6),
  currency TEXT DEFAULT 'USD',
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE (usage_date, service, usage_type)
);

CREATE TABLE IF NOT EXISTS raw_metrics (
  id BIGSERIAL PRIMARY KEY,
  metric_date TIMESTAMP NOT NULL,
  resource_id TEXT NOT NULL,
  service TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  metric_value NUMERIC(18,6),
  created_at TIMESTAMP DEFAULT NOW()
);
