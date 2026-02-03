import { useState, useCallback } from 'react'
import { ForecastSettingsCard } from '@/components/forecast/ForecastSettingsCard'
import { ForecastResultsCard } from '@/components/forecast/ForecastResultsCard'
import type { ForecastSettings, ForecastResult, ForecastSummary } from '@/types/forecast'
import { getDefaultForecastSettings } from '@/lib/forecast-constants'
import { calculateForecast, generateForecastSummary } from '@/lib/forecast-calculations'
import { useSimulationStore } from '@/store/simulation-store'

export default function ForecastCost() {
    const [settings, setSettings] = useState<ForecastSettings>(getDefaultForecastSettings())
    const [results, setResults] = useState<ForecastResult[]>([])
    const [summary, setSummary] = useState<ForecastSummary | null>(null)
    const [isCalculating, setIsCalculating] = useState(false)

    // Get simulation data from global store
    const { simulatedItems } = useSimulationStore()
    const simulatedSavings = simulatedItems.reduce((sum, item) => sum + item.savingsPerMonth, 0)

    const handleCalculate = useCallback(() => {
        setIsCalculating(true)

        setTimeout(() => {
            const forecastResults = calculateForecast(settings)
            const forecastSummary = generateForecastSummary(forecastResults, settings)

            setResults(forecastResults)
            setSummary(forecastSummary)
            setIsCalculating(false)
        }, 300)
    }, [settings])

    const handleSettingsChange = useCallback((newSettings: ForecastSettings) => {
        setSettings(newSettings)
    }, [])

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-3xl font-bold tracking-tight text-primary">Cost Forecast</h2>
                <p className="text-muted-foreground">
                    Predict future AWS costs based on current usage and growth projections.
                </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <ForecastSettingsCard
                    settings={settings}
                    onSettingsChange={handleSettingsChange}
                    onCalculate={handleCalculate}
                    isCalculating={isCalculating}
                />

                <ForecastResultsCard
                    results={results}
                    summary={summary}
                    currency={settings.currency}
                    isLoading={isCalculating}
                    simulatedSavings={simulatedSavings}
                    simulatedItems={simulatedItems}
                />
            </div>
        </div>
    )
}
