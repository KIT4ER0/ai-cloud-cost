import type { ForecastSettings, ForecastResult, ForecastSummary } from '@/types/forecast'
import { AWS_REGIONS, MONTH_NAMES_SHORT } from './forecast-constants'

/**
 * Get the number of months between two dates
 */
export function getMonthsBetween(startDate: Date, endDate: Date): number {
    const start = new Date(startDate.getFullYear(), startDate.getMonth(), 1)
    const end = new Date(endDate.getFullYear(), endDate.getMonth(), 1)

    const months = (end.getFullYear() - start.getFullYear()) * 12
        + (end.getMonth() - start.getMonth())

    return Math.max(0, months) + 1 // Include both start and end months
}

/**
 * Convert USD to the selected currency
 */
export function convertCurrency(
    amountUSD: number,
    currency: 'USD' | 'THB',
    exchangeRate: number
): number {
    if (currency === 'USD') {
        return amountUSD
    }
    return amountUSD * exchangeRate
}

/**
 * Calculate average pricing modifier based on selected regions
 */
export function getAveragePricingModifier(selectedRegions: string[]): number {
    if (selectedRegions.length === 0) return 1.0

    const modifiers = selectedRegions.map(regionId => {
        const region = AWS_REGIONS.find(r => r.id === regionId)
        return region?.pricingModifier ?? 1.0
    })

    return modifiers.reduce((sum, mod) => sum + mod, 0) / modifiers.length
}

/**
 * Get base cost from settings based on input methodology
 */
export function getBaseCost(settings: ForecastSettings): number {
    if (settings.inputMethodology === 'actual-cost') {
        return settings.latestMonthCost
    }
    // Convert usage units to cost
    return settings.totalUsageUnits * settings.costPerUnit
}

/**
 * Calculate monthly forecasted costs based on settings
 */
export function calculateForecast(settings: ForecastSettings): ForecastResult[] {
    const results: ForecastResult[] = []
    const monthCount = getMonthsBetween(settings.startMonth, settings.endMonth)
    const baseCost = getBaseCost(settings)
    const pricingModifier = getAveragePricingModifier(settings.selectedRegions)

    let cumulativeCost = 0
    let previousCost = baseCost * pricingModifier

    for (let i = 0; i < monthCount; i++) {
        const currentMonth = new Date(
            settings.startMonth.getFullYear(),
            settings.startMonth.getMonth() + i,
            1
        )

        let projectedCost: number

        switch (settings.forecastMode) {
            case 'static':
                // Maintain constant cost
                projectedCost = baseCost * pricingModifier
                break

            case 'percentage':
                // Apply compounding monthly growth/decline
                if (i === 0) {
                    projectedCost = baseCost * pricingModifier
                } else {
                    const growthFactor = 1 + (settings.percentageGrowth / 100)
                    projectedCost = previousCost * growthFactor
                }
                break

            case 'driver-based':
                // Scale cost proportionally with growth driver
                if (i === 0) {
                    projectedCost = baseCost * pricingModifier
                } else {
                    const monthlyGrowthRate = settings.growthDriver / 100 / monthCount
                    const growthFactor = 1 + monthlyGrowthRate * (i + 1)
                    projectedCost = baseCost * pricingModifier * growthFactor
                }
                break

            default:
                projectedCost = baseCost * pricingModifier
        }

        const growthFromPrevious = i === 0 ? 0 : ((projectedCost - previousCost) / previousCost) * 100
        cumulativeCost += projectedCost

        const monthLabel = `${MONTH_NAMES_SHORT[currentMonth.getMonth()]} ${currentMonth.getFullYear()}`

        results.push({
            month: currentMonth,
            monthLabel,
            projectedCost,
            projectedCostConverted: convertCurrency(projectedCost, settings.currency, settings.exchangeRate),
            cumulativeCost,
            cumulativeCostConverted: convertCurrency(cumulativeCost, settings.currency, settings.exchangeRate),
            growthFromPrevious
        })

        previousCost = projectedCost
    }

    return results
}

/**
 * Generate forecast summary from results
 */
export function generateForecastSummary(
    results: ForecastResult[],
    settings: ForecastSettings
): ForecastSummary {
    if (results.length === 0) {
        return {
            totalProjectedCost: 0,
            totalProjectedCostConverted: 0,
            averageMonthlyCost: 0,
            averageMonthlyCostConverted: 0,
            monthCount: 0,
            currency: settings.currency,
            exchangeRate: settings.exchangeRate
        }
    }

    const lastResult = results[results.length - 1]
    const totalProjectedCost = lastResult.cumulativeCost
    const averageMonthlyCost = totalProjectedCost / results.length

    return {
        totalProjectedCost,
        totalProjectedCostConverted: convertCurrency(totalProjectedCost, settings.currency, settings.exchangeRate),
        averageMonthlyCost,
        averageMonthlyCostConverted: convertCurrency(averageMonthlyCost, settings.currency, settings.exchangeRate),
        monthCount: results.length,
        currency: settings.currency,
        exchangeRate: settings.exchangeRate
    }
}

/**
 * Format currency value for display
 */
export function formatCurrency(value: number, currency: 'USD' | 'THB'): string {
    const symbol = currency === 'USD' ? '$' : '฿'
    const formattedValue = value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    })
    return `${symbol}${formattedValue}`
}

/**
 * Format compact currency value (e.g., $10.5K, $1.2M)
 */
export function formatCompactCurrency(value: number, currency: 'USD' | 'THB'): string {
    const symbol = currency === 'USD' ? '$' : '฿'

    if (value >= 1000000) {
        return `${symbol}${(value / 1000000).toFixed(1)}M`
    }
    if (value >= 1000) {
        return `${symbol}${(value / 1000).toFixed(1)}K`
    }
    return `${symbol}${value.toFixed(2)}`
}
