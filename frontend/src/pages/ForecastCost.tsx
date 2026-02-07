import { useState, useMemo, useCallback } from 'react'
import { ForecastSettingsBar } from '@/components/forecast/ForecastSettingsBar'
import { DataQualityCard } from '@/components/forecast/DataQualityCard'
import { ServiceBreakdownCard } from '@/components/forecast/ServiceBreakdownCard'
import { ForecastChartCard } from '@/components/forecast/ForecastChartCard'
import { ForecastSummaryCards } from '@/components/forecast/ForecastSummaryCards'
import { InsightsPanel } from '@/components/forecast/InsightsPanel'
import { EmptyState } from '@/components/forecast/EmptyState'
import type { ForecastSettings } from '@/types/forecast'
import { getDefaultSettings } from '@/types/forecast'
import {
    mockDataQuality,
    mockServiceBreakdown,
    generateForecastData,
    calculateForecastSummary,
    modelAssumptions,
} from '@/lib/forecast-data'

export default function ForecastCost() {
    // State for data connection (mock - always connected for demo)
    const [isDataConnected, setIsDataConnected] = useState(true)

    // State for simulation mode
    const [isSimulating, setIsSimulating] = useState(false)

    // Forecast settings
    const [settings, setSettings] = useState<ForecastSettings>(getDefaultSettings())

    // Generate chart data based on simulation state
    const chartData = useMemo(() => generateForecastData(isSimulating), [isSimulating])

    // Calculate summary based on simulation state
    const summary = useMemo(() => calculateForecastSummary(isSimulating), [isSimulating])

    // Handle settings change
    const handleSettingsChange = useCallback((newSettings: ForecastSettings) => {
        setSettings(newSettings)
    }, [])

    // Handle simulation toggle
    const handleSimulationToggle = useCallback((value: boolean) => {
        setIsSimulating(value)
    }, [])

    // Handle connect data action
    const handleConnectData = useCallback(() => {
        setIsDataConnected(true)
    }, [])

    // Empty state when no data is connected
    if (!isDataConnected) {
        return (
            <div className="space-y-6">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight text-primary">Cost Forecast</h2>
                    <p className="text-muted-foreground">
                        Predict future AWS costs based on historical data and optimization scenarios.
                    </p>
                </div>
                <EmptyState onConnectData={handleConnectData} />
            </div>
        )
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h2 className="text-3xl font-bold tracking-tight text-primary">Cost Forecast</h2>
                <p className="text-muted-foreground">
                    Predict future AWS costs based on historical data and optimization scenarios.
                </p>
            </div>

            {/* Section 1: Forecast Settings Bar */}
            <ForecastSettingsBar
                settings={settings}
                onSettingsChange={handleSettingsChange}
            />

            {/* Section 2: Data Source & Baseline (Middle) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <DataQualityCard dataQuality={mockDataQuality} />
                <ServiceBreakdownCard breakdown={mockServiceBreakdown} />
            </div>

            {/* Section 3: Forecast Results & Insights (Bottom) */}
            {/* Main Chart - Hero */}
            <ForecastChartCard
                data={chartData}
                isSimulating={isSimulating}
                onSimulationToggle={handleSimulationToggle}
            />

            {/* Summary Cards */}
            <ForecastSummaryCards summary={summary} isSimulating={isSimulating} />

            {/* Insights Panel */}
            <InsightsPanel assumptions={modelAssumptions} isSimulating={isSimulating} />
        </div>
    )
}
