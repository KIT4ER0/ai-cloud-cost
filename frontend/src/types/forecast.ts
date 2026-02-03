// Forecast Settings Types

export type Currency = 'USD' | 'THB'

export type ForecastMode = 'static' | 'percentage' | 'driver-based'

export type InputMethodology = 'actual-cost' | 'total-usage'

export interface AWSRegion {
    id: string
    name: string
    code: string
    /** Pricing modifier relative to US East (1.0 = baseline) */
    pricingModifier: number
}

export interface ForecastSettings {
    // Forecast Horizon
    startMonth: Date
    endMonth: Date

    // Currency & Exchange Rate
    currency: Currency
    exchangeRate: number

    // Multi-Region Selection
    selectedRegions: string[]

    // Forecasting Mode
    forecastMode: ForecastMode
    percentageGrowth: number // For percentage mode (+/- %)
    growthDriver: number // For driver-based mode (% increase)

    // Input Methodology
    inputMethodology: InputMethodology
    latestMonthCost: number // For actual-cost method
    totalUsageUnits: number // For total-usage method
    costPerUnit: number // Cost per usage unit (e.g., cost per instance hour)

    // Options
    realTimeCalculation: boolean
}

export interface ForecastResult {
    month: Date
    monthLabel: string
    projectedCost: number
    projectedCostConverted: number // In selected currency
    cumulativeCost: number
    cumulativeCostConverted: number
    growthFromPrevious: number
}

export interface ForecastSummary {
    totalProjectedCost: number
    totalProjectedCostConverted: number
    averageMonthlyCost: number
    averageMonthlyCostConverted: number
    monthCount: number
    currency: Currency
    exchangeRate: number
}
