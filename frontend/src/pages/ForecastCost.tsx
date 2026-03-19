import { useState, useMemo, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ServiceBreakdownCard } from '@/components/forecast/ServiceBreakdownCard'
import { ForecastChartCard } from '@/components/forecast/ForecastChartCard'
import { ForecastSummaryCards } from '@/components/forecast/ForecastSummaryCards'
import { useForecastCost } from '@/hooks/useForecastCost'
import { Loader2, Download } from 'lucide-react'

// Available services for multi-select
const AVAILABLE_SERVICES = [
    { key: 'ec2', label: 'EC2' },
    { key: 'rds', label: 'RDS' },
    { key: 's3', label: 'S3' },
    { key: 'lambda', label: 'Lambda' },
]

export default function ForecastCost() {
    const [selectedServices, setSelectedServices] = useState<string[]>(['ec2', 'rds'])
    const [baselinePeriod, setBaselinePeriod] = useState('3M')
    const [forecastPeriod, setForecastPeriod] = useState('1M')
    const [chartType, setChartType] = useState('line')
    const [isForecastRunning, setIsForecastRunning] = useState(false)

    const {
        resources,
        isLoading,
        error,
        data: forecastData,
        multiData,
        loadResources,
        runMultiForecast,
        calculateCostSummary,
        transformForChart,
        transformForMultiChart,
        exportToCSV,
        exportMultiToCSV,
        clearError,
    } = useForecastCost()

    // Load resources on component mount
    useEffect(() => {
        loadResources().catch(console.error)
    }, [loadResources])

    const busy = isLoading || isForecastRunning
    const hasForecastData = !!(forecastData?.results?.length)

    const toggleService = (serviceKey: string) => {
        setSelectedServices(prev =>
            prev.includes(serviceKey) 
                ? prev.filter(s => s !== serviceKey) 
                : [...prev, serviceKey]
        )
    }

    const handleRunForecast = async () => {
        if (selectedServices.length === 0 || !resources) return
        
        clearError()
        setIsForecastRunning(true)
        
        try {
            // Collect first resource from each selected service
            const resourceItems: Array<{ service: string; resource_id: number }> = []
            for (const svc of selectedServices) {
                const serviceData = resources[svc]
                if (serviceData?.resources?.length > 0) {
                    resourceItems.push({
                        service: svc,
                        resource_id: serviceData.resources[0].id,
                    })
                }
            }
            
            if (resourceItems.length === 0) {
                throw new Error('No resources available for selected services')
            }
            
            const horizon = forecastPeriod === '1M' ? 30 
                : forecastPeriod === '3M' ? 90 
                : forecastPeriod === '6M' ? 180 
                : 365
            
            await runMultiForecast({ resources: resourceItems, horizon })
        } catch (err) {
            console.error('Forecast failed:', err)
        } finally {
            setIsForecastRunning(false)
        }
    }

    const downloadFile = (content: string, filename: string, mime = 'text/csv') => {
        const blob = new Blob([content], { type: `${mime};charset=utf-8;` })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        a.click()
        URL.revokeObjectURL(url)
    }

    const handleExportCSV = () => {
        if (multiData) {
            const csv = exportMultiToCSV(multiData)
            if (csv) downloadFile(csv, 'forecast-multi-resource.csv')
        } else if (forecastData?.results) {
            const csv = exportToCSV(forecastData.results)
            if (csv) downloadFile(csv, 'forecast-results.csv')
        }
    }

    // Derived data
    const chartData = useMemo(() => {
        // Use multiData for multi-service forecast
        if (multiData && multiData.forecasts.length > 0) {
            return transformForMultiChart(multiData.forecasts)
        }
        
        // Fallback to single-service forecast
        if (hasForecastData) {
            return transformForChart(forecastData!.results)
        }
        
        // Only show mock data when no real data and not loading
        if (!busy) {
            const mockData = []
            const today = new Date()
            
            // Generate 6 months forecast data only (no historical)
            for (let i = 1; i <= 6; i++) {
                const date = new Date(today)
                date.setMonth(date.getMonth() + i)
                
                const baseValue = 2000 + Math.sin(i * 0.5) * 500
                const trend = i * 100
                const noise = Math.random() * 200 - 100
                const value = Math.max(1000, baseValue + trend + noise)
                
                mockData.push({
                    date: date.toISOString().split('T')[0],
                    label: date.toLocaleDateString('en-US', { month: 'short', year: '2-digit' }),
                    actual: undefined,
                    baseline: value,
                    simulated: undefined,
                    isProjected: true,
                })
            }
            return mockData
        }
        
        return []
    }, [hasForecastData, forecastData, transformForChart])

    const summary = useMemo(() => {
        // Use multiData for multi-service forecast summary
        if (multiData && multiData.forecasts.length > 0) {
            const totalForecastCost = multiData.forecasts
                .filter(f => !f.error && f.results.length > 0)
                .reduce((sum, f) => {
                    return sum + f.results.reduce((serviceSum, r) => serviceSum + (r.total_forecast_cost ?? 0), 0)
                }, 0)
            
            // DEBUG: Log summary calculation
            console.log('💳 DEBUG Summary Calculation:')
            console.log('   Number of forecasts:', multiData.forecasts.length)
            multiData.forecasts.forEach((f, idx) => {
                console.log(`   Forecast ${idx}: service=${f.service}, error=${!!f.error}`)
                if (!f.error && f.results.length > 0) {
                    const serviceTotal = f.results.reduce((serviceSum, r) => serviceSum + (r.total_forecast_cost ?? 0), 0)
                    console.log(`     Service total: ${serviceTotal}`)
                }
            })
            console.log('   Summary total:', totalForecastCost)
            
            const totalDays = 30 // Assuming 30-day forecast period
            const avgDailyCost = totalForecastCost / totalDays
            
            return {
                forecastTotal: totalForecastCost,
                avgMonthlyCost: avgDailyCost * 30,
                simulatedSavings: 0,
                changeFromBaseline: 0,
            }
        }
        
        // Fallback to single-service forecast
        if (hasForecastData) {
            const cs = calculateCostSummary(forecastData!.results)
            if (cs.hasCostData) {
                return {
                    forecastTotal: cs.totalForecastCost,
                    avgMonthlyCost: cs.avgDailyCost * 30,
                    simulatedSavings: 0,
                    changeFromBaseline: 0,
                }
            }
        }
        
        // Only show mock data when no real data and not loading
        if (!busy) {
            return {
                forecastTotal: 12400,
                avgMonthlyCost: 2800,
                simulatedSavings: 0,
                changeFromBaseline: 14.2,
            }
        }
        
        return null
    }, [hasForecastData, forecastData, multiData, calculateCostSummary, busy])

    const serviceBreakdown = useMemo(() => {
        const colors: Record<string, string> = {
            ec2: '#6366f1', rds: '#f59e0b', s3: '#10b981',
            lambda: '#8b5cf6', alb: '#ef4444',
        }
        const fallbackColors = ['#6366f1', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#ec4899']

        // Use multiData for per-service forecast breakdown
        if (multiData && multiData.forecasts.length > 0) {
            const items = multiData.forecasts
                .filter(f => !f.error && f.results.length > 0)
                .map(f => {
                    const totalCost = f.results.reduce((sum, r) => sum + (r.total_forecast_cost ?? 0), 0)
                    const mapes = f.results
                        .map(r => r.performance_metrics?.mape)
                        .filter((m): m is number => m != null)
                    const avgMape = mapes.length > 0 ? mapes.reduce((a, b) => a + b, 0) / mapes.length : null
                    return {
                        service: f.service.toUpperCase() as any,
                        resourceName: f.resource_name ?? `#${f.resource_id}`,
                        cost: totalCost,
                        percentage: 0,
                        color: colors[f.service] ?? fallbackColors[0],
                        metricsCount: f.results.length,
                        avgMape,
                    }
                })

            const grandTotal = items.reduce((s, i) => s + i.cost, 0)
            items.forEach(i => {
                i.percentage = grandTotal > 0 ? Math.round((i.cost / grandTotal) * 100) : 0
            })
            return items.length > 0 ? items : null
        }

        // Fallback: single-resource cost breakdown by type
        if (hasForecastData) {
            const cs = calculateCostSummary(forecastData!.results)
            if (cs.hasCostData && Object.keys(cs.costBreakdown).length) {
                const total = Object.values(cs.costBreakdown).reduce((s, v) => s + v, 0)
                return Object.entries(cs.costBreakdown).map(([name, cost], i) => ({
                    service: (name.charAt(0).toUpperCase() + name.slice(1)) as any,
                    cost,
                    percentage: total > 0 ? Math.round((cost / total) * 100) : 0,
                    color: fallbackColors[i % fallbackColors.length],
                }))
            }
        }

        if (!busy) {
            return [
                { service: 'EC2' as any, cost: 5200, percentage: 42, color: '#6366f1' },
                { service: 'RDS' as any, cost: 3100, percentage: 25, color: '#f59e0b' },
                { service: 'EKS' as any, cost: 4100, percentage: 33, color: '#10b981' },
            ]
        }

        return null
    }, [hasForecastData, forecastData, multiData, calculateCostSummary, busy])

    return (
        <div className="min-h-screen bg-gray-50 px-4 py-8">
            <div className="mx-auto max-w-6xl space-y-6">
                {/* Header */}
                <div>
                    <h1 className="text-2xl font-bold text-gray-800">Forecast Cost</h1>
                    <p className="mt-1 text-sm text-gray-400">Predict your future cloud spending</p>
                </div>

                {/* Service Selection Section */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Service Selection</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* Service Checkboxes */}
                        <div>
                            <p className="text-sm font-medium text-gray-700 mb-3">Select Services to Forecast</p>
                            <div className="grid grid-cols-3 gap-3">
                                {AVAILABLE_SERVICES.map(service => {
                                    const serviceData = resources?.[service.key]
                                    const resourceCount = serviceData?.resources?.length || 0
                                    const isAvailable = resourceCount > 0
                                    
                                    return (
                                        <div 
                                            key={service.key} 
                                            className={`flex items-center space-x-2 p-3 border rounded-lg hover:bg-gray-50 ${
                                                !isAvailable ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                                            }`}
                                        >
                                            <Checkbox
                                                id={service.key}
                                                checked={selectedServices.includes(service.key)}
                                                onCheckedChange={() => isAvailable && toggleService(service.key)}
                                                disabled={!isAvailable}
                                            />
                                            <label htmlFor={service.key} className={`cursor-pointer ${!isAvailable ? 'text-gray-400' : ''}`}>
                                                <span className="text-sm font-medium">{service.label}</span>
                                                <span className="text-xs text-gray-500 ml-1">({resourceCount})</span>
                                            </label>
                                        </div>
                                    )
                                })}
                            </div>
                            {resources && (
                                <p className="text-xs text-gray-500 mt-2">
                                    Services show available resource count. Only services with resources can be selected.
                                </p>
                            )}
                        </div>

                        {/* Selected Resources Display */}
                        {resources && selectedServices.length > 0 && (
                            <div>
                                <p className="text-sm font-medium text-gray-700 mb-2">Available Resources</p>
                                <div className="space-y-2 max-h-40 overflow-y-auto">
                                    {selectedServices.map(service => {
                                        const serviceData = resources[service]
                                        if (!serviceData || serviceData.resources.length === 0) return null
                                        
                                        return (
                                            <div key={service} className="text-xs p-2 bg-gray-50 rounded">
                                                <div className="font-medium text-gray-700">{service.toUpperCase()} Resources:</div>
                                                <div className="mt-1 space-y-1">
                                                    {serviceData.resources.slice(0, 3).map(resource => (
                                                        <div key={resource.id} className="text-gray-600">
                                                            • {resource.name || `${service.toUpperCase()} #${resource.id}`}
                                                            {resource.type && <span className="text-gray-400 ml-1">({resource.type})</span>}
                                                        </div>
                                                    ))}
                                                    {serviceData.resources.length > 3 && (
                                                        <div className="text-gray-400">... and {serviceData.resources.length - 3} more</div>
                                                    )}
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            </div>
                        )}

                        {/* Period Selection */}
                        <div className="flex items-center space-x-4">
                            <div className="flex items-center space-x-2">
                                <span className="text-sm font-medium text-gray-700">Period:</span>
                                <Select value={baselinePeriod} onValueChange={setBaselinePeriod}>
                                    <SelectTrigger className="w-32">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="1M">Last 1M</SelectItem>
                                        <SelectItem value="3M">Last 3M</SelectItem>
                                        <SelectItem value="6M">Last 6M</SelectItem>
                                        <SelectItem value="12M">Last 12M</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            
                            <div className="flex items-center space-x-2">
                                <span className="text-sm font-medium text-gray-700">Forecast:</span>
                                <Select value={forecastPeriod} onValueChange={setForecastPeriod}>
                                    <SelectTrigger className="w-32">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="1M">Next 1M</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        {/* Run Forecast Button */}
                        <div className="flex justify-center">
                            <Button
                                size="lg"
                                onClick={handleRunForecast}
                                disabled={selectedServices.length === 0 || busy}
                                className="px-8"
                            >
                                {busy ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Running Forecast...
                                    </>
                                ) : (
                                    'Run Forecast'
                                )}
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Error Display */}
                {error && (
                    <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-500">
                        {error}
                    </div>
                )}

                {/* Loading State */}
                {busy && (
                    <div className="space-y-4 animate-pulse">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {[1, 2, 3].map((i) => (
                                <div key={i} className="h-24 rounded-2xl bg-gray-200" />
                            ))}
                        </div>
                        <div className="h-80 rounded-2xl bg-gray-200" />
                        <div className="h-48 rounded-2xl bg-gray-200" />
                    </div>
                )}

                {/* Forecast Result Section */}
                {!busy && (
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Forecast Result</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            {/* Summary Cards */}
                            {summary && (
                                <div>
                                    <h3 className="text-sm font-medium text-gray-700 mb-3">Summary Cards</h3>
                                    <ForecastSummaryCards summary={summary} isSimulating={false} />
                                </div>
                            )}

                            {/* Chart Type Selection */}
                            <div className="flex items-center space-x-4">
                                <span className="text-sm font-medium text-gray-700">Chart Type:</span>
                                <div className="flex space-x-2">
                                    {['Line Chart'].map(type => (
                                        <Button
                                            key={type}
                                            variant={chartType === type.toLowerCase().split(' ')[0] ? 'default' : 'outline'}
                                            size="sm"
                                            onClick={() => setChartType(type.toLowerCase().split(' ')[0])}
                                        >
                                            {type}
                                        </Button>
                                    ))}
                                </div>
                            </div>

                            {/* Chart */}
                            <div>
                                <h3 className="text-sm font-medium text-gray-700 mb-3">Forecast Visualization</h3>
                                <ForecastChartCard
                                    data={chartData}
                                    isSimulating={false}
                                    onSimulationToggle={() => {}}
                                />
                            </div>

                            {/* Service Breakdown */}
                            {serviceBreakdown && (
                                <div>
                                    <h3 className="text-sm font-medium text-gray-700 mb-3">Per-Service Breakdown</h3>
                                    <ServiceBreakdownCard breakdown={serviceBreakdown} />
                                </div>
                            )}

                            {/* Multi-Resource Results */}
                            {multiData && multiData.forecasts.length > 1 && (
                                <div>
                                    <h3 className="text-sm font-medium text-gray-700 mb-3">Multi-Resource Results</h3>
                                    <div className="space-y-2">
                                        {multiData.forecasts.map((f, idx) => (
                                            <div key={idx} className={`flex items-center justify-between p-3 rounded-lg border ${
                                                f.error ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'
                                            }`}>
                                                <div>
                                                    <span className="text-sm font-medium">{f.service.toUpperCase()}</span>
                                                    <span className="text-xs text-gray-500 ml-2">
                                                        {f.resource_name || `#${f.resource_id}`}
                                                    </span>
                                                </div>
                                                <div className="text-xs">
                                                    {f.error ? (
                                                        <span className="text-red-600">Failed: {f.error}</span>
                                                    ) : (
                                                        <span className="text-green-700">
                                                            {f.results.length} metric(s) forecasted
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                        <p className="text-xs text-gray-500 pt-1">
                                            {multiData.successful}/{multiData.total_resources} resources forecasted successfully
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Export Buttons */}
                            <div className="flex justify-end space-x-2 pt-4 border-t">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleExportCSV}
                                    disabled={!hasForecastData && !multiData}
                                >
                                    <Download className="mr-2 h-4 w-4" />
                                    Export CSV
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Empty State */}
                {!busy && !hasForecastData && !error && (
                    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-white py-20 text-center">
                        <div className="h-12 w-12 bg-gray-200 rounded-full flex items-center justify-center mb-4">
                            <svg className="h-6 w-6 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                            </svg>
                        </div>
                        <p className="text-sm text-gray-400">
                            {resources ? (
                                <>
                                    Select services and click{' '}
                                    <span className="font-semibold text-blue-500">Run Forecast</span>{' '}
                                    to get started
                                </>
                            ) : (
                                <>
                                    Loading resources from backend...
                                </>
                            )}
                        </p>
                    </div>
                )}
            </div>
        </div>
    )
}

