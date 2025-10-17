
-- =====================================================================
-- One-shot migration for raw.costs (LEAN schema without `operation`)
-- - Deduplicate by (usage_date, account_id, region, service, usage_type)
-- - Normalize NULLs for region/usage_type -> 'unknown'
-- - Enforce NOT NULL
-- - Create PRIMARY KEY (usage_date, account_id, region, service, usage_type)
-- - Recreate helpful indexes
-- Safe to run multiple times.
-- =====================================================================

BEGIN;



-- 1) Normalize NULLs to 'unknown' first
UPDATE raw.costs SET region = 'unknown'     WHERE region IS NULL;
UPDATE raw.costs SET usage_type = 'unknown' WHERE usage_type IS NULL;

-- 2) Deduplicate rows, keep the newest by ingested_at
WITH ranked AS (
  SELECT ctid,
         ROW_NUMBER() OVER (
           PARTITION BY usage_date, account_id, region, service, usage_type
           ORDER BY ingested_at DESC NULLS LAST
         ) AS rn
  FROM raw.costs
)
DELETE FROM raw.costs c
USING ranked r
WHERE c.ctid = r.ctid
  AND r.rn > 1;

-- 3) Enforce NOT NULL on PK columns
ALTER TABLE raw.costs
  ALTER COLUMN usage_date SET NOT NULL,
  ALTER COLUMN account_id SET NOT NULL,
  ALTER COLUMN region SET NOT NULL,
  ALTER COLUMN service SET NOT NULL,
  ALTER COLUMN usage_type SET NOT NULL;

-- 4) Drop old PK (if any) and create the new PK
ALTER TABLE raw.costs DROP CONSTRAINT IF EXISTS raw_costs_pkey;
ALTER TABLE raw.costs DROP CONSTRAINT IF EXISTS costs_pkey;

ALTER TABLE raw.costs
  ADD CONSTRAINT raw_costs_pkey
  PRIMARY KEY (usage_date, account_id, region, service, usage_type);

-- 5) Helpful indexes
CREATE INDEX IF NOT EXISTS ix_raw_costs_date_svc  ON raw.costs (usage_date, service);
CREATE INDEX IF NOT EXISTS ix_raw_costs_acct_date ON raw.costs (account_id, usage_date);

COMMIT;

-- =====================================================================
-- End
-- =====================================================================
