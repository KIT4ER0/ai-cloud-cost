from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from datetime import datetime, timedelta, date
from typing import List, Dict, Any
import calendar

from .. import database, models, auth, schemas

router = APIRouter(
    prefix="/api/costs",
    tags=["Costs"],
    dependencies=[Depends(auth.get_current_user)]
)

def get_date_range(time_range: str):
    today = datetime.utcnow().date()
    if time_range == "this_month":
        start_date = today.replace(day=1)
        end_date = today
        prev_start = (start_date - timedelta(days=1)).replace(day=1)
        prev_end = start_date - timedelta(days=1)
    elif time_range == "last_month":
        # First day of this month - 1 day = last day of last month
        last_month_end = today.replace(day=1) - timedelta(days=1)
        start_date = last_month_end.replace(day=1)
        end_date = last_month_end
        # Previous to last month
        prev_month_end = start_date - timedelta(days=1)
        prev_start = prev_month_end.replace(day=1)
        prev_end = prev_month_end
    elif time_range == "last_6_months":
        start_date = today - timedelta(days=180)
        end_date = today
        prev_start = start_date - timedelta(days=180)
        prev_end = start_date - timedelta(days=1)
    elif time_range == "this_year":
        start_date = today.replace(month=1, day=1)
        end_date = today
        prev_start = start_date.replace(year=start_date.year - 1)
        prev_end = end_date.replace(year=end_date.year - 1)
    else:
        # Default to this month
        start_date = today.replace(day=1)
        end_date = today
        prev_start = (start_date - timedelta(days=1)).replace(day=1)
        prev_end = start_date - timedelta(days=1)
    
    return start_date, end_date, prev_start, prev_end

@router.get("/analysis", response_model=schemas.CostAnalysisData)
def get_cost_analysis(
    time_range: str = Query("this_month", enum=["this_month", "last_month", "last_6_months", "this_year"]),
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    start_date, end_date, prev_start, prev_end = get_date_range(time_range)

    # Helper to query cost tables, filtered by profile_id through resource JOIN
    def query_service_costs(cost_model, resource_model, fk_col, start, end):
        return db.query(
            cost_model.usage_date,
            func.sum(cost_model.amount_usd).label("cost")
        ).join(
            resource_model, fk_col == getattr(resource_model, resource_model.__tablename__[:-1] + "_id")
        ).filter(
            resource_model.profile_id == current_user.profile_id,
            cost_model.usage_date >= start,
            cost_model.usage_date <= end
        ).group_by(cost_model.usage_date).all()

    # Query all services (cost_model, resource_model, fk_column)
    services_map = {
        "EC2": (models.EC2Cost, models.EC2Resource, models.EC2Cost.ec2_resource_id),
        "Lambda": (models.LambdaCost, models.LambdaResource, models.LambdaCost.lambda_resource_id),
        "RDS": (models.RDSCost, models.RDSResource, models.RDSCost.rds_resource_id),
        "S3": (models.S3Cost, models.S3Resource, models.S3Cost.s3_resource_id),
    }

    # Data structures for aggregation
    daily_costs: Dict[str, float] = {}
    service_totals: Dict[str, float] = {s: 0.0 for s in services_map.keys()}
    
    total_cost = 0.0
    
    # 1. Current Period Data
    for service_name, (cost_model, resource_model, fk_col) in services_map.items():
        rows = query_service_costs(cost_model, resource_model, fk_col, start_date, end_date)
        for r in rows:
            d_str = str(r.usage_date)
            val = float(r.cost or 0)
            daily_costs[d_str] = daily_costs.get(d_str, 0.0) + val
            service_totals[service_name] += val
            total_cost += val

    # 2. Previous Period Data (for KPI comparison)
    prev_total_cost = 0.0
    for service_name, (cost_model, resource_model, fk_col) in services_map.items():
        val = db.query(func.sum(cost_model.amount_usd)).join(
            resource_model, fk_col == getattr(resource_model, resource_model.__tablename__[:-1] + "_id")
        ).filter(
            resource_model.profile_id == current_user.profile_id,
            cost_model.usage_date >= prev_start,
            cost_model.usage_date <= prev_end
        ).scalar() or 0.0
        prev_total_cost += float(val)

    # 3. KPI Calculations
    # Top Service
    top_service_name = max(service_totals, key=service_totals.get)
    top_service_val = service_totals[top_service_name]

    # Forecast / Projection (simple linear based on daily avg)
    days_elapsed = (end_date - start_date).days + 1
    avg_daily = total_cost / max(days_elapsed, 1)
    
    projected = 0.0
    if time_range == "this_month":
        # Project to end of month
        last_day = calendar.monthrange(start_date.year, start_date.month)[1]
        days_in_month = last_day
        projected = avg_daily * days_in_month
    
    summary = schemas.KPIItem(
        totalCost=total_cost,
        prevTotalCost=prev_total_cost,
        topService={"name": top_service_name, "cost": top_service_val},
        avgDailyCost=avg_daily,
        projectedMonthEnd=projected
    )

    # 4. Trends (Chart Data)
    # Fill missing dates with 0
    trend_data = []
    curr = start_date
    while curr <= end_date:
        d_str = str(curr)
        trend_data.append(schemas.CostTrendItem(
            date=d_str,
            cost=daily_costs.get(d_str, 0.0)
        ))
        curr += timedelta(days=1)
    
    # 5. Distribution (Pie Chart)
    # Define colors
    colors = {
        "EC2": "#8b5cf6",
        "RDS": "#06b6d4",
        "S3": "#10b981",
        "Lambda": "#f59e0b"
    }
    distribution = [
        schemas.ServiceCostDistribution(
            name=k,
            value=v,
            color=colors.get(k, "#94a3b8")
        ) for k, v in service_totals.items() if v > 0
    ]
    # Sort by value desc
    distribution.sort(key=lambda x: x.value, reverse=True)

    # 6. Cost Drivers (Breakdown by usage_type)
    drivers_data = {}
    for service_name, (cost_model, resource_model, fk_col) in services_map.items():
        # Get top usage types by cost
        rows = db.query(
            cost_model.usage_type,
            func.sum(cost_model.amount_usd).label("cost")
        ).join(
            resource_model, fk_col == getattr(resource_model, resource_model.__tablename__[:-1] + "_id")
        ).filter(
            resource_model.profile_id == current_user.profile_id,
            cost_model.usage_date >= start_date,
            cost_model.usage_date <= end_date
        ).group_by(cost_model.usage_type).order_by(desc("cost")).limit(5).all()

        service_drivers = []
        for r in rows:
            # Get previous cost for this specific usage type
            prev_val = db.query(func.sum(cost_model.amount_usd)).join(
                resource_model, fk_col == getattr(resource_model, resource_model.__tablename__[:-1] + "_id")
            ).filter(
                resource_model.profile_id == current_user.profile_id,
                cost_model.usage_date >= prev_start,
                cost_model.usage_date <= prev_end,
                cost_model.usage_type == r.usage_type
            ).scalar() or 0.0
            
            cost = float(r.cost or 0)
            prev_cost = float(prev_val)
            change = cost - prev_cost
            pct = 0.0
            if prev_cost > 0:
                pct = (change / prev_cost) * 100
            
            service_drivers.append(schemas.CostDriverItem(
                driver=r.usage_type,
                usage="N/A", # We calculate cost, usage units not normalized
                cost=cost,
                prevCost=prev_cost,
                change=change,
                changePercent=pct
            ))
        drivers_data[service_name] = service_drivers

    return schemas.CostAnalysisData(
        summary=summary,
        trend=trend_data,
        distribution=distribution,
        drivers=drivers_data
    )
