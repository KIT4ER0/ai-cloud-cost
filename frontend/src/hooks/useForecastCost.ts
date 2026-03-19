import { useState, useCallback } from 'react'
import { api } from '@/lib/api'
import type { 
    EnsembleForecastResponse, 
    ForecastMetricResult,
    MultiEnsembleForecastResponse,
    MultiEnsembleForecastResult
} from '@/types/forecast'

export interface ResourceInfo {
    id: number
    name: string | null
    type: string | null
}

export interface ServiceResources {
    [service: string]: {
        metrics: string[]
        resources: ResourceInfo[]
    }
}

export function useForecastCost() {
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [data, setData] = useState<EnsembleForecastResponse | null>(null)
    const [multiData, setMultiData] = useState<MultiEnsembleForecastResponse | null>(null)
    const [resources, setResources] = useState<ServiceResources | null>(null)

    // Load all resources per service from backend DB
    const loadResources = useCallback(async () => {
        try {
            setIsLoading(true)
            setError(null)
            const response = await api.forecast.getResources()
            setResources(response as ServiceResources)
            return response as ServiceResources
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Failed to load resources'
            setError(errorMessage)
            throw err
        } finally {
            setIsLoading(false)
        }
    }, [])

    // Get saved forecast results (with costs) from DB
    const loadSavedResults = useCallback(async (service: string, resourceId: number) => {
        try {
            setIsLoading(true)
            setError(null)
            const response = await api.forecast.getResults(service, resourceId)
            setData(response as EnsembleForecastResponse)
            return response as EnsembleForecastResponse
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'No saved results found'
            setError(errorMessage)
            throw err
        } finally {
            setIsLoading(false)
        }
    }, [])

    // Run new ensemble forecast (calls ML pipeline + cost calculation)
    const runForecast = useCallback(async (params: {
        resource_id: number
        service: string
        metric?: string
        horizon?: number
    }) => {
        try {
            setIsLoading(true)
            setError(null)
            const response = await api.forecast.runEnsemble(params)
            setData(response as EnsembleForecastResponse)
            return response as EnsembleForecastResponse
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Failed to run forecast'
            setError(errorMessage)
            throw err
        } finally {
            setIsLoading(false)
        }
    }, [])

    // Run ensemble forecast for multiple resources at once
    const runMultiForecast = useCallback(async (params: {
        resources: Array<{ service: string; resource_id: number }>
        horizon?: number
    }) => {
        try {
            setIsLoading(true)
            setError(null)
            const response = await api.forecast.runMultiEnsemble(params)
            const typed = response as MultiEnsembleForecastResponse
            setMultiData(typed)

            // Also set single-resource `data` from the first successful forecast
            // so existing chart/summary components keep working
            const first = typed.forecasts.find(f => f.results.length > 0)
            if (first) {
                setData({
                    service: first.service,
                    resource_id: first.resource_id,
                    results: first.results,
                })
            }
            return typed
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Failed to run multi-resource forecast'
            setError(errorMessage)
            throw err
        } finally {
            setIsLoading(false)
        }
    }, [])

    // Export forecast results to CSV string
    const exportToCSV = useCallback((results: ForecastMetricResult[]): string => {
        if (!results || results.length === 0) return ''

        const lines: string[] = []
        lines.push('metric,date,forecast_value,cost')

        results.forEach(result => {
            result.forecast_dates.forEach((date, i) => {
                const value = result.forecast_values[i] ?? ''
                const cost = result.forecast_costs?.[i] ?? ''
                lines.push(`${result.metric},${date},${value},${cost}`)
            })
        })

        return lines.join('\n')
    }, [])

    // Export multi-resource forecast to CSV string
    const exportMultiToCSV = useCallback((multiResponse: MultiEnsembleForecastResponse): string => {
        if (!multiResponse?.forecasts?.length) return ''

        const lines: string[] = []
        lines.push('service,resource_id,resource_name,metric,date,forecast_value,cost')

        multiResponse.forecasts.forEach(forecast => {
            if (forecast.error) return
            forecast.results.forEach(result => {
                result.forecast_dates.forEach((date, i) => {
                    const value = result.forecast_values[i] ?? ''
                    const cost = result.forecast_costs?.[i] ?? ''
                    lines.push(
                        `${forecast.service},${forecast.resource_id},` +
                        `${forecast.resource_name ?? ''},${result.metric},` +
                        `${date},${value},${cost}`
                    )
                })
            })
        })

        return lines.join('\n')
    }, [])

    // Calculate cost summary from forecast results
    const calculateCostSummary = useCallback((results: ForecastMetricResult[]) => {
        const resultsWithCosts = results.filter(r => r.forecast_costs && r.forecast_costs.length > 0)
        
        if (resultsWithCosts.length === 0) {
            return {
                totalForecastCost: 0,
                avgDailyCost: 0,
                costBreakdown: {} as Record<string, number>,
                hasCostData: false
            }
        }

        const primaryResult = resultsWithCosts[0]
        const totalCost = primaryResult.total_forecast_cost ?? 
            primaryResult.forecast_costs?.reduce((s, c) => s + c, 0) ?? 0
        const avgDailyCost = primaryResult.avg_daily_cost ?? 
            (totalCost / (primaryResult.forecast_costs?.length || 1))
        
        const costBreakdown: Record<string, number> = {}
        resultsWithCosts.forEach(result => {
            if (result.cost_breakdown_totals) {
                Object.entries(result.cost_breakdown_totals).forEach(([type, amount]) => {
                    costBreakdown[type] = (costBreakdown[type] || 0) + amount
                })
            }
        })

        return { totalForecastCost: totalCost, avgDailyCost, costBreakdown, hasCostData: true }
    }, [])

    // Transform multi-service forecast data for chart display
    const transformForMultiChart = useCallback((multiForecasts: MultiEnsembleForecastResult[]) => {
        if (!multiForecasts || multiForecasts.length === 0) return []

        // Generate forecast data for all services (no historical data)
        const chartData: any[] = []
        
        // Get all forecast dates from the first successful forecast
        const firstSuccessful = multiForecasts.find(f => !f.error && f.results.length > 0)
        if (!firstSuccessful) return []
        
        const forecastDates = firstSuccessful.results[0]?.forecast_dates || []
        
        // DEBUG: Log forecast data structure
        console.log('🔍 DEBUG transformForMultiChart:')
        console.log('   Number of forecasts:', multiForecasts.length)
        console.log('   Forecast dates:', forecastDates.length)
        multiForecasts.forEach((f, idx) => {
            console.log(`   Forecast ${idx}: service=${f.service}, error=${!!f.error}, results=${f.results.length}`)
            if (!f.error && f.results.length > 0) {
                f.results.forEach((r, rIdx) => {
                    console.log(`     Result ${rIdx}: metric=${r.metric}, total_forecast_cost=${r.total_forecast_cost}, forecast_costs=${r.forecast_costs?.length}`)
                })
            }
        })
        
        // Add forecast data for each day
        let chartGrandTotal = 0
        forecastDates.forEach((date: string, dateIndex: number) => {
            let totalForecastCost = 0
            
            // Sum costs from all services for this date
            multiForecasts.forEach(forecast => {
                if (!forecast.error && forecast.results.length > 0) {
                    forecast.results.forEach((result: any) => {
                        const dayCost = result.forecast_costs?.[dateIndex] || 0
                        totalForecastCost += dayCost
                    })
                }
            })
            
            chartGrandTotal += totalForecastCost
            
            chartData.push({
                date,
                label: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                actual: undefined,
                baseline: totalForecastCost, // Total forecast cost across all services
                simulated: undefined,
                cost: totalForecastCost,
                isProjected: true,
            })
        })
        
        // DEBUG: Log chart totals
        console.log('📊 CHART Totals:')
        console.log('   Chart grand total:', chartGrandTotal)
        console.log('   Chart daily averages:', chartGrandTotal / forecastDates.length)
        
        return chartData
    }, [])

    // Transform forecast data for chart display
    const transformForChart = useCallback((results: ForecastMetricResult[]) => {
        if (!results || results.length === 0) return []

        // Find a result that has cost data, or use the first one
        const primaryResult = results.find(r => r.forecast_costs && r.forecast_costs.length > 0) || results[0]
        
        // Generate forecast data only (no historical data)
        const chartData: any[] = []
        
        // Add forecast data
        primaryResult.forecast_dates.forEach((date, index) => {
            chartData.push({
                date,
                label: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                actual: undefined,
                baseline: primaryResult.forecast_costs?.[index] || primaryResult.forecast_values[index],
                simulated: undefined,
                cost: primaryResult.forecast_costs?.[index],
                isProjected: true,
            })
        })
        
        return chartData
    }, [])

    return {
        isLoading,
        error,
        data,
        multiData,
        resources,
        loadResources,
        loadSavedResults,
        runForecast,
        runMultiForecast,
        calculateCostSummary,
        transformForChart,
        transformForMultiChart,
        exportToCSV,
        exportMultiToCSV,
        clearError: () => setError(null),
        clearData: () => { setData(null); setMultiData(null) },
    }
}
