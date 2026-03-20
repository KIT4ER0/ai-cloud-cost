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
        baseline_days?: number
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
        baseline_days?: number
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
        
        const totalHistoryCost = primaryResult.history_costs?.reduce((s, c) => s + c, 0) ?? 0
        
        const costBreakdown: Record<string, number> = {}
        // Since breakdown totals are resource-level but attached to every metric result, 
        // we only process them for the primary metric of each resource in this context.
        // Actually, for a single resource forecast, we just take the first one.
        const firstWithBreakdown = resultsWithCosts[0]
        if (firstWithBreakdown.cost_breakdown_totals) {
            Object.entries(firstWithBreakdown.cost_breakdown_totals).forEach(([type, amount]) => {
                costBreakdown[type] = amount
            })
        }

        return { 
            totalForecastCost: totalCost, 
            avgDailyCost, 
            lastMonthCost: totalHistoryCost,
            costBreakdown, 
            hasCostData: true 
        }
    }, [])

    // Transform multi-service forecast data for chart display
    const transformForMultiChart = useCallback((multiForecasts: MultiEnsembleForecastResult[]) => {
        if (!multiForecasts || multiForecasts.length === 0) return []

        const chartData: any[] = []
        // Get all historical dates and aggregate their costs
        const historyDataMap: Record<string, number> = {}
        const historyDatesSet = new Set<string>()

        multiForecasts.forEach(forecast => {
            if (!forecast.error && forecast.results.length > 0) {
                // Assume all results for the same resource have the same history_dates
                const result = forecast.results[0]
                if (result.history_dates && result.history_costs) {
                    result.history_dates.forEach((date, dateIdx) => {
                        historyDatesSet.add(date)
                        const cost = result.history_costs?.[dateIdx] || 0
                        historyDataMap[date] = (historyDataMap[date] || 0) + cost
                    })
                }
            }
        })

        // Add historical data points (sorted by date)
        const sortedHistoryDates = Array.from(historyDatesSet).sort()
        sortedHistoryDates.forEach(date => {
            const cost = historyDataMap[date]
            chartData.push({
                date,
                label: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                actual: cost,
                baseline: undefined,
                simulated: undefined,
                cost: cost,
                isProjected: false,
            })
        })

        // Get all forecast dates from the first successful forecast
        const firstSuccessful = multiForecasts.find(f => !f.error && f.results.length > 0)
        if (!firstSuccessful) return chartData
        
        const forecastDates = firstSuccessful.results[0]?.forecast_dates || []
        
        // Add forecast data for each day
        let chartGrandTotal = 0
        forecastDates.forEach((date: string, dateIndex: number) => {
            let totalForecastCost = 0
            
            // Sum costs from all services/resources for this date
            multiForecasts.forEach(forecast => {
                if (!forecast.error && forecast.results.length > 0) {
                    // Every metric result for a resource has the SAME resource-level daily costs.
                    // We only take it from the first result per resource.
                    const firstResult = forecast.results[0]
                    const dayCost = firstResult.forecast_costs?.[dateIndex] || 0
                    totalForecastCost += dayCost
                }
            })
            
            chartGrandTotal += totalForecastCost
            
            chartData.push({
                date,
                label: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                actual: undefined,
                baseline: totalForecastCost, // Total forecast cost across all services
                lower: totalForecastCost * 0.9,
                upper: totalForecastCost * 1.1,
                simulated: undefined,
                cost: totalForecastCost,
                isProjected: true,
            })
        })
        
        // DEBUG: Log chart totals
        return chartData
    }, [])

    // Transform forecast data for chart display
    const transformForChart = useCallback((results: ForecastMetricResult[]) => {
        if (!results || results.length === 0) return []

        // Find a result that has cost data, or use the first one
        const primaryResult = results.find(r => r.forecast_costs && r.forecast_costs.length > 0) || results[0]
        
        const chartData: any[] = []
        
        // Include historical data
        if (primaryResult.history_dates && primaryResult.history_costs) {
            primaryResult.history_dates.forEach((date, index) => {
                chartData.push({
                    date,
                    label: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                    actual: primaryResult.history_costs?.[index],
                    baseline: undefined,
                    simulated: undefined,
                    cost: primaryResult.history_costs?.[index],
                    isProjected: false,
                })
            })
        }
        
        // Add forecast data
        primaryResult.forecast_dates.forEach((date, index) => {
            const baseline = primaryResult.forecast_costs?.[index] || primaryResult.forecast_values[index];
            chartData.push({
                date,
                label: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                actual: undefined,
                baseline: baseline,
                lower: baseline * 0.9,
                upper: baseline * 1.1,
                simulated: undefined,
                cost: baseline,
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
