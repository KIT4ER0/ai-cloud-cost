# 📊 หลักการทำงานของ Forecast Cost Function (อย่างละเอียด)

## 🎯 **ภาพรวมการทำงาน**

Forecast Cost System ทำงานโดยการ **คาดการณ์การใช้งานในอนาคต** จากข้อมูลในอดีต แล้ว **คำนวณต้นทุน** จากการใช้งานที่คาดการณ์ได้โดยใช้ราคา AWS ปัจจุบัน

```
Historical Data → ML Forecast → Usage Prediction → Cost Calculation → Results
```

---

## 🏗️ **สถาปัตยกรรมระบบ**

### **1. Data Flow Architecture**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Historical    │    │   ML Forecast    │    │   Cost Calc     │
│   Metrics       │───▶│   Models         │───▶│   Engine        │
│   (180 days)    │    │   (ETS+SARIMA)   │    │   (AWS Pricing) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Database      │    │   Forecast       │    │   Cost Results  │
│   Storage       │    │   Results        │    │   (Daily costs) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### **2. Component Overview**
- **Forecast Service**: คาดการณ์ค่า metrics (CPU, Network, Storage, etc.)
- **Cost Integration**: ดึงข้อมูล resource และคำนวณต้นทุน
- **Pricing Engine**: คำนวณราคาตาม AWS pricing tables
- **Database Layer**: เก็บผลลัพธ์ทั้ง forecast และ costs

---

## 🔧 **Step-by-Step การทำงาน**

### **Phase 1: Data Collection & Preparation**

#### **1.1 Load Historical Metrics**
```python
# ดึงข้อมูล 180 วันล่าสุดจาก database
def load_metric_series(db, service, resource_id, metric_column):
    query = db.query(MetricModel).filter(
        MetricModel.resource_id == resource_id
    ).order_by(MetricModel.metric_date.desc()).limit(180)
    return df  # pandas DataFrame พร้อม dates + values
```

**Data Sources:**
- **EC2**: cpu_utilization, network_out, hours_running, ebs_snapshot_total_gb
- **RDS**: running_hours, free_storage_space, backup_retention_storage_gb, read_iops, write_iops
- **Lambda**: duration_avg, duration_p95, invocations, errors
- **S3**: bucket_size_bytes, number_of_objects
- **ALB**: request_count, processed_bytes, active_conn_count

#### **1.2 Data Quality Check**
```python
# ตรวจสอบว่ามีข้อมูลเพียงพอสำหรับ forecasting
if len(df) < MIN_ROWS_FOR_ENSEMBLE:  # 21 days minimum
    raise ValueError("Need at least 21 data points for forecasting")
```

---

### **Phase 2: ML Forecasting**

#### **2.1 Ensemble Model Approach**
ระบบใช้ **3 models ร่วมกัน** เพื่อความแม่นยำสูง:

```python
# น้ำหนักของแต่ละ model
ENSEMBLE_WEIGHTS = {
    "ets": 0.50,      # Exponential Smoothing - ตรวจจับ trend & seasonality
    "sarima": 0.30,   # Seasonal ARIMA - ตรวจจับ seasonal patterns  
    "ridge": 0.20,    # Linear Regression - ตรวจจับ linear trends
}
```

#### **2.2 Model Training Process**

**ETS Model (Holt-Winters):**
```python
# ตรวจจับ trend และ seasonality
model = ExponentialSmoothing(
    series,
    trend='add',           # Additive trend
    seasonal='add',        # Additive seasonality
    seasonal_periods=7    # Weekly seasonality
).fit()
forecast = model.forecast(horizon)
```

**SARIMA Model:**
```python
# Seasonal AutoRegressive Integrated Moving Average
model = SARIMAX(
    series,
    order=(1,1,1),           # (p,d,q) parameters
    seasonal_order=(1,1,1,7) # (P,D,Q,s) weekly seasonality
).fit()
forecast = model.forecast(horizon)
```

**Ridge Regression:**
```python
# Linear regression with regularization
# Features: trend, day_of_week, month
X = create_features(series)
model = Ridge(alpha=1.0)
model.fit(X, series)
forecast = model.predict(future_features)
```

#### **2.3 Ensemble Combination**
```python
# ผสมผลลลัพธ์จากทั้ง 3 models
ensemble_forecast = (
    0.50 * ets_forecast + 
    0.30 * sarima_forecast + 
    0.20 * ridge_forecast
)
```

---

### **Phase 3: Resource Information Gathering**

#### **3.1 Fetch Resource Configuration**
ระบบดึงข้อมูลการตั้งค่าของ resource เพื่อคำนวณต้นทุน:

**EC2 Resource Info:**
```python
def get_ec2_resource_info(db, resource_id):
    resource = db.query(EC2Resource).filter_by(ec2_resource_id=resource_id).first()
    ebs_volume = db.query(EC2EBSVolume).filter_by(ec2_resource_id=resource_id).first()
    
    return {
        "instance_type": resource.instance_type,           # t3.medium, m5.large, etc.
        "has_public_ip": resource.has_public_ip,           # Public IP cost
        "ebs_type": ebs_volume.volume_type,               # gp3, gp2, io1, etc.
        "ebs_size_gb": ebs_volume.size_gb,                 # Storage size
        "ebs_iops": ebs_volume.iops,                      # Performance IOPS
    }
```

**RDS Resource Info:**
```python
def get_rds_resource_info(db, resource_id):
    resource = db.query(RDSResource).filter_by(rds_resource_id=resource_id).first()
    return {
        "instance_class": resource.instance_class,        # db.t3.medium, etc.
        "storage_type": resource.storage_type,            # gp3, gp2, io1
        "allocated_gb": resource.allocated_gb,             # Storage allocation
        "engine": resource.engine,                        # MySQL, PostgreSQL, etc.
        "multi_az": resource.multi_az,                    # Multi-AZ cost
    }
```

#### **3.2 Resource Configuration Mapping**
แต่ละ service มี configuration ที่แตกต่างกัน:

| Service | Key Configs | Cost Impact |
|---------|-------------|-------------|
| **EC2** | instance_type, ebs_size, public_ip | Compute + Storage + Network |
| **RDS** | instance_class, storage_gb, multi_az | Compute + Storage + HA |
| **Lambda** | memory_size, duration, invocations | Compute + Requests |
| **S3** | storage_class, storage_gb, requests | Storage + Operations |
| **ALB** | lb_type, lcu_hours, data_processing | Load Balancer + Data |

---

### **Phase 4: Cost Calculation Engine**

#### **4.1 AWS Pricing Lookup**
ระบบมี pricing tables สำหรับแต่ละ AWS service:

```python
# EC2 Pricing Table (simplified)
EC2_PRICING = {
    "t3.medium": {"hourly": 0.0416, "vcpu": 2, "memory": 4},
    "m5.large": {"hourly": 0.096, "vcpu": 2, "memory": 8},
    "c5.2xlarge": {"hourly": 0.34, "vcpu": 8, "memory": 16},
}

# EBS Pricing Table
EBS_PRICING = {
    "gp3": {"gb_month": 0.08, "iops": 0.005, "throughput": 0.04},
    "gp2": {"gb_month": 0.10, "iops": 0.005, "throughput": 0.04},
    "io1": {"gb_month": 0.125, "iops": 0.065, "throughput": 0.04},
}
```

#### **4.2 Cost Calculation Logic**

**EC2 Cost Calculation:**
```python
def calculate_ec2_costs(forecast_values, resource_info):
    costs = []
    
    for i, hours_running in enumerate(forecast_values):
        daily_cost = 0
        
        # 1. Compute Cost
        instance_hourly_rate = EC2_PRICING[resource_info["instance_type"]]["hourly"]
        compute_cost = hours_running * instance_hourly_rate
        daily_cost += compute_cost
        
        # 2. EBS Storage Cost (daily)
        ebs_gb_month = EBS_PRICING[resource_info["ebs_type"]]["gb_month"]
        storage_cost = (ebs_gb_month / 30) * resource_info["ebs_size_gb"]
        daily_cost += storage_cost
        
        # 3. EBS IOPS Cost (if provisioned)
        if resource_info["ebs_iops"] > 3000:  # Free tier for gp3
            iops_cost = (EBS_PRICING[resource_info["ebs_type"]]["iops"] / 30) * (resource_info["ebs_iops"] - 3000)
            daily_cost += iops_cost
        
        # 4. Public IP Cost
        if resource_info["has_public_ip"]:
            daily_cost += 0.0045  # $0.0045 per hour
        
        # 5. Network Egress Cost
        network_gb = forecast_network_out[i]  # From forecast
        if network_gb > 100:  # 100GB free tier
            network_cost = (network_gb - 100) * 0.09  # $0.09 per GB
            daily_cost += network_cost
        
        costs.append(daily_cost)
    
    return costs
```

**RDS Cost Calculation:**
```python
def calculate_rds_costs(forecast_values, resource_info):
    costs = []
    
    for i, running_hours in enumerate(forecast_values):
        daily_cost = 0
        
        # 1. Instance Cost
        instance_hourly = RDS_PRICING[resource_info["instance_class"]]["hourly"]
        compute_cost = running_hours * instance_hourly
        daily_cost += compute_cost
        
        # 2. Storage Cost
        storage_gb_month = RDS_PRICING[resource_info["storage_type"]]["gb_month"]
        storage_cost = (storage_gb_month / 30) * resource_info["allocated_gb"]
        daily_cost += storage_cost
        
        # 3. Backup Storage Cost
        backup_gb = forecast_backup_storage[i]  # From forecast
        backup_cost = (0.095 / 30) * backup_gb  # $0.095 per GB-month
        daily_cost += backup_cost
        
        # 4. Multi-AZ Cost (if enabled)
        if resource_info.get("multi_az"):
            daily_cost *= 2  # Double cost for Multi-AZ
        
        costs.append(daily_cost)
    
    return costs
```

---

### **Phase 5: Cost Breakdown & Aggregation**

#### **5.1 Cost Categorization**
ระบบแบ่งต้นทุนออกเป็น categories ต่างๆ:

```python
def categorize_costs(service, resource_info, daily_costs):
    breakdown = {
        "compute": [],      # Instance/Lambda compute costs
        "storage": [],      # EBS/RDS/S3 storage costs
        "network": [],      # Data transfer costs
        "requests": [],     # API/operation costs
        "public_ip": [],    # Elastic IP costs
    }
    
    for day_cost in daily_costs:
        breakdown["compute"].append(day_cost.compute)
        breakdown["storage"].append(day_cost.storage)
        breakdown["network"].append(day_cost.network)
        # ... etc
    
    return breakdown
```

#### **5.2 Cost Aggregation**
```python
# คำนวณ aggregate metrics
total_forecast_cost = sum(forecast_costs)
avg_daily_cost = total_forecast_cost / len(forecast_costs)

# Cost breakdown totals
cost_breakdown_totals = {
    "compute": sum(breakdown["compute"]),
    "storage": sum(breakdown["storage"]),
    "network": sum(breakdown["network"]),
    "public_ip": sum(breakdown["public_ip"]),
}
```

---

### **Phase 6: Results Storage**

#### **6.1 Database Schema**
ผลลัพธ์ถูกเก็บใน database พร้อม cost fields:

```sql
-- Example for EC2 Forecast Results
CREATE TABLE ec2_forecast_results (
    forecast_result_id SERIAL PRIMARY KEY,
    resource_id INTEGER,
    metric VARCHAR(50),
    method VARCHAR(50),
    forecast_dates DATE[],
    forecast_values FLOAT[],
    
    -- Cost Fields
    forecast_costs FLOAT[],           -- Daily costs
    cost_breakdown JSONB,             -- Cost breakdown per day
    total_forecast_cost FLOAT,        -- Total cost
    avg_daily_cost FLOAT,             -- Average daily cost
    
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### **6.2 Save Results**
```python
def save_ensemble_forecast(db, service, resource_id, results):
    for metric_result in results:
        forecast_row = ForecastResultModel(
            resource_id=resource_id,
            metric=metric_result.metric,
            method="ensemble",
            forecast_dates=metric_result.forecast_dates,
            forecast_values=metric_result.forecast_values,
            
            # Cost data
            forecast_costs=metric_result.forecast_costs,
            cost_breakdown=metric_result.cost_breakdown,
            total_forecast_cost=metric_result.total_forecast_cost,
            avg_daily_cost=metric_result.avg_daily_cost,
        )
        db.add(forecast_row)
    
    db.commit()
```

---

## 📊 **Example Walkthrough**

### **Scenario: EC2 Instance Cost Forecast**

#### **Input Data:**
- **Resource**: EC2 t3.medium with 100GB gp3 EBS, Public IP
- **Historical Data**: 180 days of CPU, Network, Hours metrics
- **Forecast Horizon**: 30 days

#### **Step-by-Step Execution:**

**1. Load Historical Data**
```python
# Load 180 days of metrics
cpu_data = [45.2, 47.1, 43.8, ..., 50.1]  # CPU utilization %
network_data = [12.5, 15.2, 11.8, ..., 18.3]  # GB per day
hours_data = [24, 24, 23.5, ..., 24]  # Running hours per day
```

**2. Run Ensemble Forecast**
```python
# Forecast CPU utilization
cpu_forecast = ensemble_forecast(cpu_data, horizon=30)
# Result: [48.5, 49.2, 47.8, 51.1, ..., 52.3]  # 30 days forecast

# Forecast Network egress
network_forecast = ensemble_forecast(network_data, horizon=30)  
# Result: [16.2, 17.5, 15.9, ..., 19.8]  # GB per day

# Forecast running hours
hours_forecast = ensemble_forecast(hours_data, horizon=30)
# Result: [24, 24, 24, ..., 24]  # Always running
```

**3. Get Resource Configuration**
```python
resource_info = {
    "instance_type": "t3.medium",
    "has_public_ip": True,
    "ebs_type": "gp3", 
    "ebs_size_gb": 100,
    "ebs_iops": 3000,
}
```

**4. Calculate Daily Costs**
```python
# Day 1 Cost Calculation
hours_running = 24
network_gb = 16.2

compute_cost = 24 * 0.0416 = $0.9984      # t3.medium hourly rate
storage_cost = (0.08/30) * 100 = $0.267   # 100GB gp3
network_cost = (16.2 - 100) * 0.09 = $0    # Under 100GB free tier
public_ip_cost = 24 * 0.0045 = $0.108     # Public IP

daily_cost = 0.9984 + 0.267 + 0 + 0.108 = $1.373
```

**5. Generate Cost Breakdown**
```python
forecast_costs = [1.37, 1.42, 1.35, 1.51, ..., 1.48]  # 30 days
cost_breakdown = {
    "compute": [0.998, 0.998, ..., 0.998],     # $29.94 total
    "storage": [0.267, 0.267, ..., 0.267],     # $8.01 total  
    "network": [0, 0, ..., 0.45],              # $2.15 total
    "public_ip": [0.108, 0.108, ..., 0.108],   # $3.24 total
}

total_cost = sum(forecast_costs) = $43.34
avg_daily = total_cost / 30 = $1.44
```

**6. Save Results**
```python
save_ensemble_forecast(db, "ec2", 45, {
    "metric": "cpu_utilization",
    "forecast_dates": ["2026-03-19", "2026-03-20", ...],
    "forecast_values": [48.5, 49.2, ...],
    "forecast_costs": [1.37, 1.42, ...],
    "cost_breakdown": cost_breakdown,
    "total_forecast_cost": 43.34,
    "avg_daily_cost": 1.44,
})
```

---

## 🎯 **Key Features & Benefits**

### **1. ML-Driven Accuracy**
- **Ensemble Models**: 3 models ร่วมกันเพื่อความแม่นยำสูง
- **Seasonality Detection**: ตรวจจับรูปแบบรายสัปดาห์/รายเดือน
- **Trend Analysis**: ตรวจจับทิศทางการเปลี่ยนแปลงของการใช้งาน

### **2. Comprehensive Cost Coverage**
- **All AWS Services**: EC2, RDS, Lambda, S3, ALB
- **Cost Components**: Compute, Storage, Network, Requests, IP
- **Pricing Accuracy**: ใช้ AWS pricing tables ปัจจุบัน

### **3. Real-Time Integration**
- **Database Storage**: บันทึกผลลัพธ์สำหรับ historical comparison
- **API Integration**: Frontend ดึงข้อมูลผ่าน REST API
- **Cost Breakdown**: แยกต้นทุนตามประเภทให้ละเอียด

### **4. Production Ready**
- **Error Handling**: Fallback mechanisms และ validation
- **Performance**: Efficient database queries และ caching
- **Scalability**: รองรับ multiple resources และ concurrent forecasts

---

## 🔍 **Technical Deep Dive**

### **Ensemble Model Mathematics**

**ETS (Exponential Smoothing):**
```
ŷ_t = α * y_t + (1-α) * (ŷ_{t-1} + b_{t-1})
b_t = β * (ŷ_t - ŷ_{t-1}) + (1-β) * b_{t-1}
s_t = γ * (y_t - ŷ_t) + (1-γ) * s_{t-L}
```

**SARIMA:**
```
(1 - φ₁B - φ₂B²)(1 - Φ₁B^L)(1 - B)(1 - B^L)y_t = 
(1 + θ₁B + θ₂B²)(1 + Θ₁B^L)ε_t
```

**Ridge Regression:**
```
min ||y - Xβ||² + λ||β||²
```

### **Cost Calculation Formulas**

**EC2 Daily Cost:**
```
Cost = (Hours * InstanceRate) + 
       (StorageGB * StorageRate/30) + 
       (IOPS * IOPRate/30) + 
       (PublicIP * 0.0045) + 
       (NetworkGB-100) * 0.09
```

**Lambda Daily Cost:**
```
Cost = Requests * RequestRate + 
       (Duration/1000ms) * GB-sec * ComputeRate
```

---

## 📈 **Performance & Accuracy**

### **Model Accuracy Metrics**
- **MAPE (Mean Absolute Percentage Error)**: 10-25% โดยเฉลี่ย
- **RMSE (Root Mean Square Error)**: ขึ้นอยู่กับ metric volatility
- **Confidence Intervals**: 95% CI สำหรับ forecast ranges

### **Cost Accuracy**
- **Pricing Updates**: Monthly AWS pricing updates
- **Regional Variations**: Support for different AWS regions
- **Currency**: USD base with conversion support

---

## 🚀 **Future Enhancements**

### **Planned Features**
1. **Multi-Resource Forecasting**: คาดการณ์หลาย resources พร้อมกัน
2. **Scenario Analysis**: What-if analysis (instance changes, scaling)
3. **Budget Integration**: Alert เมื่อ forecast เกิน budget
4. **Optimization Recommendations**: AI-driven cost optimization tips
5. **Historical Comparison**: เปรียบเทียบ forecast vs actual costs

### **Technical Improvements**
1. **Advanced ML Models**: LSTM, Prophet, Deep Learning
2. **Real-Time Pricing**: Integration with AWS Pricing API
3. **Multi-Region Support**: Different pricing per region
4. **Cost Anomaly Detection**: ML-based anomaly detection
5. **Export Capabilities**: CSV, PDF, API integrations

---

นี่คือรายละเอียดการทำงานของ forecast cost system ทั้งหมดครับ ระบบถูกออกแบบมาให้มีความแม่นยำสูง ครอบคลุมทุกด้าน และพร้อมใช้งานจริงใน production environment! 🎯
