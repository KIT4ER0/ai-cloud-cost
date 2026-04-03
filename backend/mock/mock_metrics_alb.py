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

        # ── 2. Upsert LB Costs (180 วัน) ─────────────────────────────────────
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
        for days_ago in range(180):
            dt = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
            is_weekend = dt.weekday() >= 5
            
            # More realistic ALB patterns
            if lb_type == "ALB":
                # Base request count with realistic ranges
                if lb_tmpl['lb_name'] == "alb-idle":
                    req_base = random.randint(50, 200)  # Idle ALB
                elif lb_tmpl['lb_name'] == "alb-web":
                    req_base = random.randint(2000, 8000)  # Web ALB
                else:
                    req_base = random.randint(1000, 5000)  # Standard ALB
                
                # Apply weekend patterns
                if is_weekend:
                    req_base = int(req_base * random.uniform(0.2, 0.4))  # Much less on weekends
                else:
                    req_base = int(req_base * random.uniform(0.8, 1.3))  # Daily variation
                
                metric_rows.append({
                    "alb_resource_id": record.alb_resource_id,
                    "metric_date": dt,
                    "request_count": req_base,
                    "processed_bytes": int(req_base * random.uniform(1024, 4096)),  # 1-4KB per request
                    "new_conn_count": int(req_base * random.uniform(0.01, 0.03)),   # 1-3% new connections
                    "response_time_p95": random.uniform(0.02, 0.08),  # More realistic response times
                    "http_5xx_count": random.randint(0, 2),  # Fewer errors
                    "active_conn_count": random.randint(5, 25),  # Moderate connection count
                })
            elif lb_type == "NLB":
                # NLB typically handles higher throughput with more consistent patterns
                base_requests = random.randint(50000, 150000)
                if is_weekend:
                    base_requests = int(base_requests * random.uniform(0.4, 0.6))  # Less on weekends
                else:
                    base_requests = int(base_requests * random.uniform(0.9, 1.1))  # Small daily variation
                
                metric_rows.append({
                    "alb_resource_id": record.alb_resource_id,
                    "metric_date": dt,
                    "request_count": base_requests,
                    "processed_bytes": int(base_requests * random.uniform(1024, 2048)),  # 1-2KB per request
                    "new_conn_count": random.randint(500, 2000),  # More realistic connection ranges
                    "active_conn_count": random.randint(50, 150),  # Moderate active connections
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
