# Frontend-Backend Forecast Cost Integration Guide

## 🎯 **Overview**

บทความนี้อธิบายวิธีเชื่อมต่อ Frontend กับ Backend API เพื่อแสดงผลการคาดการณ์ต้นทุน (Forecast Cost) บนหน้า UI

## 📁 **Files Created/Modified**

### **Backend Changes**
- ✅ `backend/schemas.py` - เพิ่ม cost fields ใน `XGBoostMetricResult`
- ✅ `backend/forecasting/router.py` - API endpoints สำหรับ forecast พร้อมอยู่แล้ว
- ✅ `backend/models.py` - cost fields ถูกเพิ่มแล้ว
- ✅ `db/schema.sql` - database schema ถูกอัปเดตแล้ว

### **Frontend Changes**
- ✅ `frontend/src/lib/api.ts` - เพิ่ม forecast API endpoints
- ✅ `frontend/src/types/forecast.ts` - เพิ่ม types สำหรับ API responses
- ✅ `frontend/src/hooks/useForecastCost.ts` - Custom hook สำหรับ forecast API
- ✅ `frontend/src/components/forecast/ResourceSelector.tsx` - Component สำหรับเลือก resource
- ✅ `frontend/src/pages/ForecastCost.tsx` - อัปเดตเพื่อใช้ real API

## 🔄 **API Flow**

```
Frontend (React) → API Client → Backend (FastAPI) → Forecast Service → Database
```

### **1. API Endpoints**

#### **Get Available Metrics**
```typescript
GET /forecast/metrics
Response: {
  services: {
    "ec2": {
      metrics: ["cpu_utilization", "network_egress_gb", ...],
      resources: [
        { id: 45, name: "i-mock-web-01-9012", type: "t3.medium" },
        ...
      ]
    },
    "rds": { ... },
    "lambda": { ... },
    ...
  }
}
```

#### **Run Ensemble Forecast**
```typescript
POST /forecast/ensemble
Request: {
  resource_id: 45,
  service: "ec2",
  metric?: "cpu_utilization",  // optional - all metrics if not specified
  horizon: 30  // days
}

Response: {
  service: "ec2",
  resource_id: 45,
  results: [
    {
      metric: "cpu_utilization",
      method: "ensemble",
      forecast_dates: ["2026-03-19", "2026-03-20", ...],
      forecast_values: [5.2, 5.5, 5.8, ...],
      // Cost fields
      forecast_costs: [1.27, 1.28, 1.29, ...],
      total_forecast_cost: 38.50,
      avg_daily_cost: 1.28,
      cost_breakdown: {
        compute: [1.11, 1.11, ...],
        ebs: [0.16, 0.16, ...],
        network: [0.00, 0.01, ...],
        public_ip: [0.00, 0.00, ...]
      },
      cost_breakdown_totals: {
        compute: 33.30,
        ebs: 4.80,
        network: 0.30,
        public_ip: 0.10
      }
    }
  ]
}
```

### **2. Frontend Integration**

#### **API Client (`frontend/src/lib/api.ts`)**
```typescript
forecast: {
  getMetrics: () => request.get("/forecast/metrics"),
  runEnsemble: (data) => request.post("/forecast/ensemble", data),
  getRuns: () => request.get("/forecast/runs"),
  getRunById: (runId) => request.get(`/forecast/runs/${runId}`),
}
```

#### **Custom Hook (`frontend/src/hooks/useForecastCost.ts`)**
```typescript
const {
  isLoading,
  error,
  data: forecastData,
  getAvailableMetrics,
  runForecast,
  calculateCostSummary,
  transformForChart,
} = useForecastCost()
```

#### **Component Usage**
```typescript
// Get available resources
const metrics = await getAvailableMetrics()

// Run forecast for specific resource
const result = await runForecast({
  resource_id: 45,
  service: "ec2",
  horizon: 30
})

// Calculate cost summary
const costSummary = calculateCostSummary(result.results)

// Transform for chart display
const chartData = transformForChart(result.results)
```

## 🚀 **How to Use**

### **Step 1: Start Backend Server**
```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### **Step 2: Start Frontend Development**
```bash
cd frontend
npm run dev
```

### **Step 3: Access Forecast Cost Page**
```
http://localhost:5173/forecast-cost
```

### **Step 4: Use the Interface**

1. **Load Available Resources**
   - คลิก "Load Available Resources" ปุ่ม
   - ระบบจะดึงข้อมูล resources ทั้งหมดจาก backend

2. **Select Resource**
   - เลือก service (EC2, RDS, Lambda, S3, ALB)
   - เลือก resource ที่ต้องการ forecast
   - ระบบจะเรียกใช้ forecast API อัตโนมัติ

3. **View Results**
   - ดู forecast chart พร้อม cost information
   - ดู cost breakdown แยกตามประเภท
   - ดู summary cards พร้อม total forecast cost

## 📊 **Data Flow Example**

### **User Action: Select EC2 Instance**
```typescript
handleResourceSelect("ec2", 45)
```

### **API Call**
```http
POST /forecast/ensemble
{
  "resource_id": 45,
  "service": "ec2",
  "horizon": 30
}
```

### **Backend Processing**
1. **Load Historical Data** - ดึงข้อมูล 180 วันล่าสุด
2. **Run Ensemble Forecast** - ใช้ ETS + SARIMA + Ridge models
3. **Calculate Costs** - คำนวณต้นทุนจาก forecasted metrics
4. **Save Results** - เก็บผลลัพธ์ลง database
5. **Return Response** - ส่งข้อมูลกลับไป frontend

### **Frontend Display**
- **Chart**: แสดง forecast values และ daily costs
- **Summary**: Total 30-day cost: $38.50
- **Breakdown**: Compute $33.30, EBS $4.80, Network $0.30, Public IP $0.10

## 🛠️ **Configuration**

### **Environment Variables**
```bash
# Frontend (.env)
VITE_API_URL=http://localhost:8000

# Backend (.env)
DATABASE_URL=postgresql://...
```

### **API Base URL**
```typescript
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
```

## 🔧 **Troubleshooting**

### **Common Issues**

#### **1. API Connection Error**
```
Error: Failed to fetch
```
**Solution**: ตรวจสอบว่า backend server กำลังทำงานอยู่ที่ port 8000

#### **2. No Resources Available**
```
No resources available
```
**Solution**: ตรวจสอบว่ามีข้อมูลใน database หรือ run sync metrics:
```bash
curl -X POST http://localhost:8000/sync/metrics
```

#### **3. Forecast Error**
```
Ensemble failed: Need at least 21 data points
```
**Solution**: ตรวจสอบว่า resource มีข้อมูลเพียงพอ (180 วัน)

#### **4. Cost Calculation Error**
```
Failed to calculate forecast costs
```
**Solution**: ตรวจสอบ resource configuration (instance type, EBS, etc.)

### **Debug Mode**
```typescript
// Enable debug logging
console.log('Forecast data:', forecastData)
console.log('Cost summary:', costSummary)
```

## 📈 **Performance Considerations**

### **API Response Time**
- **Forecast Calculation**: ~2-5 seconds (depending on data size)
- **Cost Calculation**: ~0.5 seconds
- **Database Query**: ~0.1 seconds

### **Optimization Tips**
1. **Cache Results**: เก็บ forecast results ไว้ 30 นาที
2. **Lazy Loading**: โหลด resource details เมื่อจำเป็น
3. **Batch Requests**: รวม multiple forecasts ใน request เดียว

## 🎨 **UI Components**

### **ResourceSelector**
- แสดง services ที่มีอยู่
- แสดง resources ในแต่ละ service
- สนับสนุนการเลือกและ run forecast

### **ForecastChartCard**
- แสดง forecast chart พร้อม cost line
- รองรับ zoom และ pan
- แสดง confidence intervals

### **ForecastSummaryCards**
- Total forecast cost
- Average daily cost
- Cost breakdown percentages
- Comparison with baseline

## 🔮 **Future Enhancements**

### **Planned Features**
1. **Multi-Resource Forecast** - Forecast หลาย resources พร้อมกัน
2. **Scenario Analysis** - What-if scenarios (instance changes, etc.)
3. **Budget Alerts** - แจ้งเตือนเมื่อ forecast เกิน budget
4. **Export Options** - Export forecast data เป็น CSV/PDF
5. **Historical Comparison** - เปรียบเทียบกับข้อมูลจริง

### **API Improvements**
1. **WebSocket Support** - Real-time forecast updates
2. **Batch Operations** - Forecast multiple resources in one call
3. **Streaming Results** - Progressive result loading
4. **Caching Layer** - Redis cache for frequent requests

## ✅ **Testing**

### **Manual Testing**
1. **Load Resources**: ทดสอบ load available metrics
2. **Run Forecast**: ทดสอบ run forecast สำหรับแต่ละ service
3. **Check Costs**: ตรวจสอบว่า cost calculation ถูกต้อง
4. **Error Handling**: ทดสอบ error scenarios

### **Automated Testing**
```typescript
// Example test case
test('should run EC2 forecast with costs', async () => {
  const result = await runForecast({
    resource_id: 45,
    service: 'ec2',
    horizon: 30
  })
  
  expect(result.results).toHaveLength(3) // cpu, network, hours
  expect(result.results[0].forecast_costs).toBeDefined()
  expect(result.results[0].total_forecast_cost).toBeGreaterThan(0)
})
```

## 📚 **Related Documentation**

- **Forecast Cost Implementation**: `FORECAST_COST_IMPLEMENTATION_GUIDE.md`
- **Enhanced Ensemble**: `ENHANCED_ENSEMBLE_IMPLEMENTATION_SUMMARY.md`
- **Backend API Docs**: `/docs` (Swagger UI at `http://localhost:8000/docs`)
- **Frontend Components**: `/frontend/src/components/forecast/`

---

**Integration Complete! 🎉**

Frontend ตอนนี้เชื่อมต่อกับ Backend API สำหรับ forecast cost calculation ได้สำเร็จแล้ว! ผู้ใช้สามารถเลือก resources และดูการคาดการณ์ต้นทุนแบบ real-time ได้ทันที
