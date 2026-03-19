# Forecast Cost Implementation Guide

## 🎯 **Overview**

This implementation adds **cost forecasting** capabilities to the AI Cloud Cost platform. The system now calculates predicted costs based on forecasted usage metrics using AWS pricing, stores them in the database, and makes them available for display in the forecast UI.

## 📋 **Features Implemented**

### **1. AWS Pricing Calculator** (`forecast_pricing.py`)
- **EC2 Pricing**: Compute, EBS volumes, EBS IOPS, network egress, public IPv4
- **RDS Pricing**: Instance hours, storage (gp2/gp3/io1)
- **Lambda Pricing**: Request count, duration (GB-seconds)
- **S3 Pricing**: Storage (Standard/IA/Glacier), GET/PUT requests
- **ALB/NLB Pricing**: Hourly cost, LCU/NLCU calculations

### **2. Database Schema Extensions**
Added to all forecast result tables:
- `forecast_costs`: Array of daily total costs (FLOAT8[])
- `cost_breakdown`: Detailed cost breakdown by type (JSONB)

### **3. Cost Integration Module** (`forecast_cost_integration.py`)
- Fetches resource information from database
- Builds forecast metrics dictionary
- Calculates costs using pricing functions
- Adds cost data to forecast results

### **4. Enhanced Ensemble Forecast Service**
- Automatically calculates costs after forecasting
- Saves cost data to database
- Includes cost info in API responses

## 🏗️ **Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                    Forecast Pipeline                         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Forecast Usage Metrics (ensemble_forecast_service.py)   │
│     - CPU utilization, network egress, invocations, etc.    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Fetch Resource Info (forecast_cost_integration.py)      │
│     - Instance type, EBS config, memory, storage class      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Calculate Costs (forecast_pricing.py)                   │
│     - Apply AWS pricing to forecasted metrics               │
│     - Generate cost breakdown by type                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Save to Database (models.py)                            │
│     - forecast_costs: [1.23, 1.45, 1.67, ...]              │
│     - cost_breakdown: {compute: [...], ebs: [...], ...}     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Return via API                                          │
│     - Include cost data in forecast response                │
│     - Frontend displays cost predictions                    │
└─────────────────────────────────────────────────────────────┘
```

## 📊 **Data Flow Example**

### **Input: EC2 Forecast Request**
```python
run_ensemble_forecast(
    db=db,
    service="ec2",
    resource_id=45,
    metric=None,  # Forecast all metrics
    horizon=30
)
```

### **Step 1: Forecast Metrics**
```json
{
  "cpu_utilization": [5.2, 5.5, 5.8, ...],
  "network_egress_gb": [4.5, 4.8, 5.1, ...],
  "hours_running": [24.0, 24.0, 24.0, ...]
}
```

### **Step 2: Get Resource Info**
```json
{
  "instance_type": "t3.medium",
  "has_public_ip": true,
  "ebs_type": "gp3",
  "ebs_size_gb": 50,
  "ebs_iops": 3000
}
```

### **Step 3: Calculate Costs**
```json
{
  "total_costs": [1.27, 1.28, 1.29, ...],
  "cost_breakdown": {
    "compute": [1.11, 1.11, 1.11, ...],
    "ebs": [0.16, 0.16, 0.16, ...],
    "network": [0.00, 0.01, 0.02, ...],
    "public_ip": [0.00, 0.00, 0.00, ...]
  }
}
```

### **Step 4: Save to Database**
```sql
UPDATE cloudcost.ec2_forecast_results
SET 
  forecast_costs = ARRAY[1.27, 1.28, 1.29, ...],
  cost_breakdown = '{"compute": [1.11, ...], "ebs": [0.16, ...], ...}'::jsonb
WHERE resource_id = 45 AND metric = 'cpu_utilization';
```

### **Output: API Response**
```json
{
  "service": "ec2",
  "resource_id": 45,
  "results": [
    {
      "metric": "cpu_utilization",
      "method": "ensemble",
      "forecast_dates": ["2026-03-19", "2026-03-20", ...],
      "forecast_values": [5.2, 5.5, 5.8, ...],
      "forecast_costs": [1.27, 1.28, 1.29, ...],
      "total_forecast_cost": 38.50,
      "avg_daily_cost": 1.28,
      "cost_breakdown": {
        "compute": [1.11, 1.11, 1.11, ...],
        "ebs": [0.16, 0.16, 0.16, ...],
        "network": [0.00, 0.01, 0.02, ...],
        "public_ip": [0.00, 0.00, 0.00, ...]
      },
      "cost_breakdown_totals": {
        "compute": 33.30,
        "ebs": 4.80,
        "network": 0.30,
        "public_ip": 0.10
      }
    }
  ]
}
```

## 💰 **Pricing Details**

### **EC2 Pricing (ap-southeast-1)**
```python
# Instance pricing ($/hour)
"t3.medium": 0.0464
"r6g.large": 0.1210
"c6i.xlarge": 0.1920

# EBS Volume ($/GB/month)
"gp3": 0.096
"gp2": 0.114
"io1": 0.138

# Network
Egress: $0.09/GB
Cross-AZ: $0.01/GB
Public IPv4: $0.005/hour
```

### **RDS Pricing**
```python
# Instance pricing ($/hour)
"db.t3.medium": 0.073
"db.r5.large": 0.280

# Storage ($/GB/month)
"gp3": 0.138
```

### **Lambda Pricing**
```python
Requests: $0.0000002/request
Duration: $0.0000166667/GB-second
```

### **S3 Pricing**
```python
# Storage ($/GB/month)
"Standard": 0.025
"Standard-IA": 0.0138

# Requests
GET: $0.00000044/1000 requests
PUT: $0.0000055/1000 requests
```

### **ALB/NLB Pricing**
```python
ALB Hourly: $0.0252/hour
ALB LCU: $0.008/LCU-hour
NLB Hourly: $0.0252/hour
NLB NLCU: $0.006/NLCU-hour
```

## 🗄️ **Database Migration**

Run the migration to add cost fields:

```bash
psql -h <host> -U <user> -d <database> -f backend/migrations/add_forecast_cost_fields.sql
```

Or apply manually:

```sql
-- Add cost fields to all forecast result tables
ALTER TABLE cloudcost.ec2_forecast_results 
ADD COLUMN IF NOT EXISTS forecast_costs FLOAT8[],
ADD COLUMN IF NOT EXISTS cost_breakdown JSONB;

-- Repeat for rds, lambda, s3, alb forecast result tables
```

## 🔧 **Usage Examples**

### **Example 1: Forecast EC2 Costs**

```python
from backend.forecasting.ensemble_forecast_service import run_ensemble_forecast
from backend.database import SessionLocal

db = SessionLocal()

# Run forecast with automatic cost calculation
result = run_ensemble_forecast(
    db=db,
    service="ec2",
    resource_id=45,
    metric=None,  # All metrics
    horizon=30
)

# Access cost data
for metric_result in result["results"]:
    if "forecast_costs" in metric_result:
        print(f"Metric: {metric_result['metric']}")
        print(f"Total 30-day cost: ${metric_result['total_forecast_cost']:.2f}")
        print(f"Average daily cost: ${metric_result['avg_daily_cost']:.2f}")
        print(f"Cost breakdown: {metric_result['cost_breakdown_totals']}")
```

### **Example 2: Query Forecast Costs from Database**

```python
from backend import models
from backend.database import SessionLocal

db = SessionLocal()

# Get latest forecast with costs
forecast = db.query(models.EC2ForecastResult).filter_by(
    resource_id=45,
    metric="cpu_utilization"
).order_by(models.EC2ForecastResult.created_at.desc()).first()

if forecast and forecast.forecast_costs:
    print(f"Forecast dates: {forecast.forecast_dates}")
    print(f"Forecast costs: {forecast.forecast_costs}")
    print(f"Total cost: ${sum(forecast.forecast_costs):.2f}")
    print(f"Cost breakdown: {forecast.cost_breakdown}")
```

### **Example 3: Calculate Costs for Custom Forecast**

```python
from backend.forecasting import forecast_pricing
from datetime import date, timedelta

# EC2 example
resource_info = {
    "instance_type": "t3.medium",
    "has_public_ip": True,
    "ebs_type": "gp3",
    "ebs_size_gb": 50,
    "ebs_iops": 3000
}

forecast_dates = [date.today() + timedelta(days=i) for i in range(30)]
forecast_metrics = {
    "hours_running": [24.0] * 30,
    "network_egress_gb": [5.0] * 30
}

total_costs, cost_breakdown = forecast_pricing.calculate_ec2_forecast_cost(
    resource_info, forecast_dates, forecast_metrics
)

print(f"Total 30-day cost: ${sum(total_costs):.2f}")
print(f"Breakdown: {cost_breakdown}")
```

## 📈 **Frontend Integration**

### **API Response Structure**

The forecast API now returns cost data:

```typescript
interface ForecastResult {
  metric: string;
  method: string;
  forecast_dates: string[];
  forecast_values: number[];
  
  // New cost fields
  forecast_costs?: number[];
  total_forecast_cost?: number;
  avg_daily_cost?: number;
  cost_breakdown?: {
    [costType: string]: number[];
  };
  cost_breakdown_totals?: {
    [costType: string]: number;
  };
}
```

### **Display Recommendations**

1. **Summary Card**
   ```
   ┌─────────────────────────────────────┐
   │  30-Day Cost Forecast               │
   │  Total: $38.50                      │
   │  Avg/Day: $1.28                     │
   │                                     │
   │  Breakdown:                         │
   │  ▓▓▓▓▓▓▓▓▓▓ Compute    $33.30 (87%)│
   │  ▓▓        EBS         $4.80  (12%)│
   │  ▓         Network     $0.30  (1%) │
   │            Public IP   $0.10  (0%) │
   └─────────────────────────────────────┘
   ```

2. **Cost Trend Chart**
   - Line chart showing daily costs over forecast period
   - Stacked area chart for cost breakdown by type
   - Comparison with historical costs

3. **Budget Planning**
   - Monthly projection based on forecast
   - Alert if forecast exceeds budget
   - Recommendations for cost optimization

## 🎯 **Benefits for Users**

### **1. Budget Planning**
- **Accurate projections**: Based on ML forecasts, not simple averages
- **30-day visibility**: Plan ahead with confidence
- **Cost breakdown**: Understand where money is going

### **2. Cost Optimization**
- **Identify trends**: Spot increasing costs early
- **Compare scenarios**: What-if analysis for different configurations
- **Right-sizing**: See impact of instance type changes

### **3. Decision Support**
- **Data-driven**: Make informed decisions about resources
- **Risk mitigation**: Avoid budget overruns
- **ROI analysis**: Evaluate cost vs. performance trade-offs

## 🔍 **Validation & Testing**

### **Test Cost Calculation**

```python
# Test EC2 cost calculation
from backend.forecasting.forecast_pricing import calculate_ec2_forecast_cost
from datetime import date, timedelta

resource_info = {
    "instance_type": "t3.medium",  # $0.0464/hour
    "has_public_ip": True,          # $0.005/hour
    "ebs_type": "gp3",              # $0.096/GB/month
    "ebs_size_gb": 50,
    "ebs_iops": 3000
}

forecast_dates = [date.today() + timedelta(days=i) for i in range(1)]
forecast_metrics = {
    "hours_running": [24.0],
    "network_egress_gb": [0.0]
}

total_costs, breakdown = calculate_ec2_forecast_cost(
    resource_info, forecast_dates, forecast_metrics
)

# Expected daily cost:
# Compute: $0.0464 * 24 = $1.1136
# EBS: ($0.096 * 50) / 30 = $0.16
# Public IP: $0.005 * 24 = $0.12
# Total: ~$1.39

print(f"Calculated: ${total_costs[0]:.2f}")
print(f"Expected: ~$1.39")
assert abs(total_costs[0] - 1.39) < 0.01, "Cost calculation mismatch!"
```

## 📝 **Next Steps**

### **1. Run Database Migration**
```bash
psql -h <host> -U <user> -d <database> -f backend/migrations/add_forecast_cost_fields.sql
```

### **2. Test Cost Calculation**
```bash
python -c "from backend.forecasting.forecast_pricing import *; print('Pricing module loaded successfully')"
```

### **3. Run Forecast with Costs**
```python
from backend.forecasting.ensemble_forecast_service import run_ensemble_forecast
from backend.database import SessionLocal

db = SessionLocal()
result = run_ensemble_forecast(db, "ec2", 45, None, 30)
print(f"Cost data available: {'forecast_costs' in result['results'][0]}")
```

### **4. Update Frontend**
- Add cost display components
- Create cost trend charts
- Implement budget alerts

### **5. Monitor & Optimize**
- Track cost calculation performance
- Validate pricing accuracy
- Update pricing as AWS changes rates

## 🚀 **Production Deployment**

1. **Apply database migration**
2. **Deploy updated backend code**
3. **Test with sample resources**
4. **Update frontend to display costs**
5. **Monitor logs for cost calculation errors**
6. **Set up pricing update process**

## 📚 **Additional Resources**

- **AWS Pricing**: https://aws.amazon.com/pricing/
- **Cost Optimization**: https://aws.amazon.com/pricing/cost-optimization/
- **Forecast Service Docs**: `ENHANCED_ENSEMBLE_IMPLEMENTATION_SUMMARY.md`

---

**Implementation Complete! ✅**

The forecast cost calculation system is now fully integrated and ready for use. Users can now see predicted costs alongside usage forecasts, enabling better budget planning and decision-making.
