import logging
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.dialects.postgresql import insert
from .. import models

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Pricing Constants (ap-southeast-1 style)
# ──────────────────────────────────────────────

LB_PRICING = {
    "ALB": {"hourly": 0.0252, "lcu": 0.008},
    "NLB": {"hourly": 0.0225, "lcu": 0.006},
    "CLB": {"hourly": 0.028, "lcu": 0.0},
}

# ──────────────────────────────────────────────
# Mock LB Profiles
# ──────────────────────────────────────────────
MOCK_LOAD_BALANCERS = [
    {
        "lb_name": "alb-prod",
        "lb_type": "ALB",
        "state": "active",
        "usage_pattern": "business_hours",
        "lcu_weekday": (10.0, 25.0),
        "lcu_weekend": (1.0, 3.0),
    },
    {
        "lb_name": "alb-idle",
        "lb_type": "ALB",
        "state": "active",
        "usage_pattern": "24x7",
        "lcu_weekday": (0.0, 0.5),
        "lcu_weekend": (0.0, 0.2),
    },
    {
        "lb_name": "clb-legacy",
        "lb_type": "CLB",
        "state": "active",
        "usage_pattern": "24x7",
        "lcu_weekday": (0.0, 0.0),
        "lcu_weekend": (0.0, 0.0),
    },
    {
        "lb_name": "nlb-prod",
        "lb_type": "NLB",
        "state": "active",
        "usage_pattern": "24x7",
        "lcu_weekday": (8.0, 12.0),
        "lcu_weekend": (6.0, 10.0),
    },
]

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _simulate_lcu(lb: dict, date) -> float:
    """จำลอง LCU ตาม usage_pattern และวันในสัปดาห์"""
    is_weekend = date.weekday() >= 5
    low, high = lb["lcu_weekend"] if is_weekend else lb["lcu_weekday"]
    if low == high == 0.0:
        return 0.0
    return round(random.uniform(low, high), 4)

def _build_lb_cost_rows(alb_resource_id: int, lb: dict, days: int = 90) -> list[dict]:
    rows = []
    pricing = LB_PRICING.get(lb["lb_type"], LB_PRICING["ALB"])

    for days_ago in range(days):
        dt = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
        dt_iso = dt.isoformat()
        
        daily_total = 0.0

        # Hourly 
        hourly_cost = round(pricing["hourly"] * 24, 6)
        rows.append({
            "alb_resource_id": alb_resource_id,
            "usage_date": dt_iso,
            "usage_type": "hourly",
            "amount_usd": hourly_cost,
            "currency_src": "USD",
        })
        daily_total += hourly_cost

        # LCU
        if pricing["lcu"] > 0:
            lcu = _simulate_lcu(lb, dt)
            lcu_cost = round(pricing["lcu"] * lcu * 24, 6)
            rows.append({
                "alb_resource_id": alb_resource_id,
                "usage_date": dt_iso,
                "usage_type": "lcu",
                "amount_usd": lcu_cost,
                "currency_src": "USD",
            })
            daily_total += lcu_cost

        # TOTAL Row
        rows.append({
            "alb_resource_id": alb_resource_id,
            "usage_date": dt_iso,
            "usage_type": "total",
            "amount_usd": round(daily_total, 6),
            "currency_src": "USD",
        })

    return rows

# ──────────────────────────────────────────────
# Main Sync
# ──────────────────────────────────────────────

def mock_smart_sync_alb_metrics(db, account_id: str, region: str, profile_id: int):
    logger.info(f"Running MOCK ALB sync for account={account_id} region={region}")

    suffix = account_id[-4:] if account_id else "0000"

    for lb_tmpl in MOCK_LOAD_BALANCERS:
        lb_name = f"{lb_tmpl['lb_name']}-{suffix}"
        lb_type = lb_tmpl["lb_type"]
        
        # ARN construction
        if lb_type == "CLB":
            lb_arn = f"arn:aws:elasticloadbalancing:{region}:{account_id}:loadbalancer/{lb_name}"
        elif lb_type == "NLB":
            lb_arn = f"arn:aws:elasticloadbalancing:{region}:{account_id}:loadbalancer/net/{lb_name}/mock{suffix}"
        else:
            lb_arn = f"arn:aws:elasticloadbalancing:{region}:{account_id}:loadbalancer/app/{lb_name}/mock{suffix}"

        # ── 1. Upsert Load Balancer ──────────────────────────────────────────
        record = db.query(models.ALBResource).filter_by(
            account_id=account_id,
            region=region,
            alb_name=lb_name,
        ).first()

        if not record:
            record = models.ALBResource(
                profile_id=profile_id,
                account_id=account_id,
                region=region,
                alb_arn=lb_arn,
                alb_name=lb_name,
                alb_type=lb_type,
                state=lb_tmpl["state"],
                dns_name=f"{lb_name}.{region}.elb.amazonaws.com",
            )
            db.add(record)
            db.flush()
        else:
            record.state = lb_tmpl["state"]
            record.alb_arn = lb_arn
            db.flush()

        # ── 2. Upsert LB Costs (90 วัน) ─────────────────────────────────────
        cost_rows = _build_lb_cost_rows(record.alb_resource_id, lb_tmpl)
        if cost_rows:
            stmt = insert(models.ALBCost).values(cost_rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["alb_resource_id", "usage_date", "usage_type"],
                set_={"amount_usd": stmt.excluded.amount_usd},
            )
            db.execute(stmt)

        # ── 3. Mock Metrics ────────────────────────────────────────────────
        # (Optional but good for monitoring page)
        metric_rows = []
        for days_ago in range(90):
            dt = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
            is_weekend = dt.weekday() >= 5
            
            if lb_type == "ALB":
                req_base = 50000 if not is_weekend else 10000
                if lb_tmpl['lb_name'] == "alb-idle":
                    req_base = 100
                
                metric_rows.append({
                    "alb_resource_id": record.alb_resource_id,
                    "metric_date": dt,
                    "request_count": int(req_base * random.uniform(0.8, 1.2)),
                    "processed_bytes": int(req_base * random.uniform(1024, 10240)),  # 1-10 KB per request
                    "new_conn_count": int(req_base * random.uniform(0.01, 0.05)),   # 1-5% new connections
                    "response_time_p95": random.uniform(0.05, 0.15),
                    "http_5xx_count": random.randint(0, 5),
                    "active_conn_count": random.randint(10, 50),
                })
            elif lb_type == "NLB":
                metric_rows.append({
                    "alb_resource_id": record.alb_resource_id,
                    "metric_date": dt,
                    "request_count": int(200000 * random.uniform(0.9, 1.1)),
                    "processed_bytes": int(200000 * random.uniform(2048, 20480)),
                    "new_conn_count": random.randint(1000, 5000),
                    "active_conn_count": random.randint(100, 300),
                })

        if metric_rows:
            stmt_m = insert(models.ALBMetric).values(metric_rows)
            stmt_m = stmt_m.on_conflict_do_update(
                index_elements=["alb_resource_id", "metric_date"],
                set_={
                    "request_count": stmt_m.excluded.request_count,
                    "processed_bytes": stmt_m.excluded.processed_bytes,
                    "new_conn_count": stmt_m.excluded.new_conn_count,
                    "response_time_p95": stmt_m.excluded.response_time_p95,
                    "http_5xx_count": stmt_m.excluded.http_5xx_count,
                    "active_conn_count": stmt_m.excluded.active_conn_count,
                },
            )
            db.execute(stmt_m)

        logger.info(f"MOCK ALB sync done: {lb_name} ({lb_type})")

    db.commit()
    logger.info("All MOCK Load Balancers synced successfully")
