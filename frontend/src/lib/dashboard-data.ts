// Dashboard Data Module
// Aggregates data from different modules for the Home Dashboard

import { RECOMMENDATIONS } from '@/types/recommendation'

// ============================================
// Cost Analysis Data (from CostAnalysis.tsx)
// ============================================

export interface CostKPI {
    totalCost: number
    prevTotalCost: number
    topService: { name: string; cost: number }
    avgDailyCost: number
    projectedMonthEnd: number
}

export interface CostTrendData {
    period: string
    cost: number
}

// Current month KPI data
export const currentMonthKPI: CostKPI = {
    totalCost: 54100,
    prevTotalCost: 50800,
    topService: { name: "EC2", cost: 18000 },
    avgDailyCost: 1803,
    projectedMonthEnd: 55890,
}

// Cost trend data for chart
export const monthlyCostTrend: CostTrendData[] = [
    { period: "Jan", cost: 45000 },
    { period: "Feb", cost: 52000 },
    { period: "Mar", cost: 48500 },
    { period: "Apr", cost: 55200 },
    { period: "May", cost: 51000 },
    { period: "Jun", cost: 54100 },
]

// ============================================
// Monitoring Data (from Monitoring.tsx)
// ============================================

export interface InstanceCounts {
    ec2: number
    lambda: number
    s3: number
    rds: number
    total: number
}

// Instance counts from monitoring
export const instanceCounts: InstanceCounts = {
    ec2: 4,      // From ec2Instances array
    lambda: 3,   // From lambdaFunctions array
    s3: 3,       // From s3Buckets array
    rds: 2,      // From rdsInstances array
    total: 12,
}

// ============================================
// Forecast Data
// ============================================

export interface ForecastData {
    endOfMonthCost: number
    nextMonthCost: number
    currency: 'USD' | 'THB'
}

// Calculate forecast for dashboard (simplified static version)
export function getDashboardForecast(): ForecastData {
    return {
        endOfMonthCost: currentMonthKPI.projectedMonthEnd,
        nextMonthCost: 53400, // From forecast mock data
        currency: 'USD'
    }
}

// ============================================
// Dashboard Summary
// ============================================

export interface DashboardSummary {
    // Cost metrics
    totalCost: number
    costChange: number
    costChangeDirection: 'up' | 'down'

    // Instance metrics
    activeInstances: number
    instanceChange: number

    // Forecast
    forecastCost: number

    // Recommendations
    totalPotentialSavings: number
    recommendationCount: number

    // Chart data
    costTrend: CostTrendData[]
}

export function getDashboardSummary(): DashboardSummary {
    const costChange = ((currentMonthKPI.totalCost - currentMonthKPI.prevTotalCost) / currentMonthKPI.prevTotalCost) * 100
    const forecast = getDashboardForecast()
    const potentialSavings = RECOMMENDATIONS.reduce((sum, rec) => sum + rec.savingsPerMonth, 0)

    return {
        totalCost: currentMonthKPI.totalCost,
        costChange: Math.abs(costChange),
        costChangeDirection: costChange >= 0 ? 'up' : 'down',

        activeInstances: instanceCounts.total,
        instanceChange: 3, // Mock: +3 new instances

        forecastCost: forecast.endOfMonthCost,

        totalPotentialSavings: potentialSavings,
        recommendationCount: RECOMMENDATIONS.length,

        costTrend: monthlyCostTrend
    }
}
