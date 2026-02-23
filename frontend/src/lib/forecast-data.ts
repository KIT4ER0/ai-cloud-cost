import type { DataQuality, ServiceBreakdown, ForecastDataPoint, ForecastSummary } from '@/types/forecast'

// Service colors
export const SERVICE_COLORS: Record<string, string> = {
    EC2: '#8b5cf6',
    S3: '#10b981',
    RDS: '#06b6d4',
    Lambda: '#f59e0b',
    CloudFront: '#ec4899',
    DynamoDB: '#6366f1',
    ECS: '#14b8a6',
    EKS: '#3b82f6',
    ElastiCache: '#a855f7',
    Other: '#6b7280',
}

// Mock Data Quality
export const mockDataQuality: DataQuality = {
    lastUpdated: new Date('2026-02-07T08:30:00'),
    dataCoverage: 92,
    confidenceScore: 'high',
    dataPoints: 2760,
}

// Mock Service Breakdown (Top 5)
export const mockServiceBreakdown: ServiceBreakdown[] = [
    { service: 'EC2', cost: 18500, percentage: 36.1, color: SERVICE_COLORS.EC2 },
    { service: 'RDS', cost: 12200, percentage: 23.8, color: SERVICE_COLORS.RDS },
    { service: 'Lambda', cost: 8400, percentage: 16.4, color: SERVICE_COLORS.Lambda },
    { service: 'S3', cost: 7200, percentage: 14.0, color: SERVICE_COLORS.S3 },
    { service: 'Other', cost: 4980, percentage: 9.7, color: SERVICE_COLORS.Other },
]

// Generate historical + forecast data
export function generateForecastData(isSimulating: boolean): ForecastDataPoint[] {
    const data: ForecastDataPoint[] = []

    // Historical data (past 3 months)
    const historicalMonths = [
        { date: '2025-11', label: 'Nov 2025', actual: 48200 },
        { date: '2025-12', label: 'Dec 2025', actual: 51300 },
        { date: '2026-01', label: 'Jan 2026', actual: 51280 },
    ]

    historicalMonths.forEach(month => {
        data.push({
            date: month.date,
            label: month.label,
            actual: month.actual,
            baseline: undefined,
            simulated: undefined,
            isProjected: false,
        })
    })

    // Baseline forecast (next 3 months) - using moving average with slight growth
    const baselineProjections = [
        { date: '2026-02', label: 'Feb 2026', baseline: 52100 },
        { date: '2026-03', label: 'Mar 2026', baseline: 53400 },
        { date: '2026-04', label: 'Apr 2026', baseline: 54800 },
    ]

    // Simulated forecast (with optimization savings applied)
    const simulatedProjections = [
        { date: '2026-02', label: 'Feb 2026', simulated: 47800 },
        { date: '2026-03', label: 'Mar 2026', simulated: 48200 },
        { date: '2026-04', label: 'Apr 2026', simulated: 48900 },
    ]

    baselineProjections.forEach((proj, idx) => {
        data.push({
            date: proj.date,
            label: proj.label,
            actual: undefined,
            baseline: proj.baseline,
            simulated: isSimulating ? simulatedProjections[idx].simulated : undefined,
            isProjected: true,
        })
    })

    return data
}

// Calculate summary based on simulation state
export function calculateForecastSummary(isSimulating: boolean): ForecastSummary {
    const baselineTotal = 52100 + 53400 + 54800 // 160,300
    const simulatedTotal = 47800 + 48200 + 48900 // 144,900

    if (isSimulating) {
        return {
            forecastTotal: simulatedTotal,
            avgMonthlyCost: Math.round(simulatedTotal / 3),
            simulatedSavings: baselineTotal - simulatedTotal,
            changeFromBaseline: -((baselineTotal - simulatedTotal) / baselineTotal) * 100,
        }
    }

    return {
        forecastTotal: baselineTotal,
        avgMonthlyCost: Math.round(baselineTotal / 3),
        simulatedSavings: 0,
        changeFromBaseline: 0,
    }
}

// Model assumptions text
export const modelAssumptions = {
    model: '90-day Moving Average',
    assumptions: [
        'Based on historical spend patterns from the baseline period',
        'Excludes one-time purchases and tax adjustments',
        'Assumes consistent usage patterns with 3% monthly growth',
    ],
    simulationBasis: 'Applying recommended optimizations from cost recommendations',
}
