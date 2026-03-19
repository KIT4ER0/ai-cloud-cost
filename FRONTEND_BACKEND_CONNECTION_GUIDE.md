# Frontend-Backend Connection Guide

## 🚀 Quick Start

### 1. Environment Setup

Create a `.env.local` file in the frontend directory:

```bash
# Frontend/.env.local
VITE_API_URL=http://localhost:8000
```

### 2. Start Backend Server

```bash
# Navigate to backend directory
cd backend

# Start FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Start Frontend Development Server

```bash
# Navigate to frontend directory  
cd frontend

# Start Vite dev server
npm run dev
```

### 4. Access the Application

Open your browser and navigate to: `http://localhost:5173`

## 📊 API Endpoints Used by Forecast Cost Page

### Resource Management
- `GET /forecast/resources` - Load available AWS resources per service
- `GET /forecast/results/{service}/{resource_id}` - Get saved forecast results

### Forecast Execution  
- `POST /forecast/ensemble` - Run ensemble forecast with cost calculation

## 🔧 How the Connection Works

### 1. Resource Loading (On Page Mount)
```typescript
// Automatically loads when ForecastCost page mounts
useEffect(() => {
    loadResources().catch(console.error)
}, [loadResources])
```

### 2. Service Selection
- Frontend displays available services with resource counts
- Only services with available resources can be selected
- UI shows resource details for selected services

### 3. Forecast Execution
```typescript
// When user clicks "Run Forecast"
const handleRunForecast = async () => {
    const service = selectedServices[0]  // First selected service
    const serviceData = resources[service]
    const firstResource = serviceData.resources[0]  // First available resource
    
    await runForecast({
        resource_id: firstResource.id,
        service: service,
        horizon: forecastHorizonDays
    })
}
```

### 4. Data Flow
```
Frontend → API Request → Backend ML Pipeline → Cost Calculation → Database → Frontend
```

## 🎯 Features Now Connected

### ✅ Working Features
1. **Resource Discovery**: Load real AWS resources from database
2. **Service Selection**: Multi-select with resource counts
3. **Forecast Execution**: Run ML ensemble forecasts
4. **Cost Calculation**: Automatic cost integration
5. **Real-time Updates**: Loading states and error handling
6. **Data Visualization**: Charts with real forecast data

### 🔄 Data States
- **Loading**: Shows skeleton animations
- **Empty**: Displays helpful messages
- **Error**: Shows API error messages
- **Success**: Displays forecast results with costs

## 🐛 Troubleshooting

### Common Issues

#### 1. "Failed to load resources"
- **Cause**: Backend server not running or API URL incorrect
- **Fix**: Ensure backend is running on `http://localhost:8000`

#### 2. "No resources found for EC2"
- **Cause**: Database has no resources for current user
- **Fix**: Sync data from AWS or add test resources

#### 3. "Forecast failed"  
- **Cause**: ML pipeline error or insufficient historical data
- **Fix**: Check backend logs and ensure resource has metrics data

#### 4. CORS Errors
- **Cause**: Frontend and backend on different ports
- **Fix**: Backend should have CORS enabled for localhost

### Debug Steps

1. **Check Backend Health**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check API Endpoints**
   ```bash
   # Test resources endpoint
   curl -H "Authorization: Bearer <token>" \
        http://localhost:8000/forecast/resources
   ```

3. **Check Frontend Network Tab**
   - Open browser dev tools
   - Go to Network tab
   - Look for failed requests to `/forecast/*`

4. **Check Backend Logs**
   - Look for error messages in backend console
   - Check database connection status

## 📝 Environment Variables

### Required Variables
```bash
VITE_API_URL=http://localhost:8000  # Backend API URL
```

### Optional Variables  
```bash
VITE_API_URL=https://api.yourdomain.com  # Production API
```

## 🔐 Authentication

The API uses JWT tokens for authentication:
- Token stored in `localStorage`
- Automatically included in API requests
- Token validation on each request

## 📈 Production Deployment

### Environment Setup
```bash
# Production environment
VITE_API_URL=https://your-api-domain.com
```

### Build Process
```bash
# Build for production
npm run build

# Preview build
npm run preview
```

### API Configuration
- Ensure CORS is configured for production domain
- Use HTTPS for API endpoints
- Set up proper authentication

## 🎉 Success Checklist

- [ ] Backend server running on port 8000
- [ ] Frontend dev server running on port 5173  
- [ ] `.env.local` configured with API URL
- [ ] Resources loading in service selection
- [ ] Forecast execution working
- [ ] Cost data displaying in results
- [ ] Charts showing real forecast data
- [ ] Export buttons (UI ready)
- [ ] Error handling working

## 📚 Next Steps

1. **Multi-Resource Forecasting**: Extend to forecast multiple resources
2. **Export Functionality**: Implement CSV/PDF export
3. **Chart Types**: Add bar and stacked area charts
4. **Real-time Updates**: WebSocket for live forecast updates
5. **Advanced Filters**: Date ranges, metric selection
6. **Cost Optimization**: ML-powered recommendations
