// Forecast Types for Data-Driven Dashboard

export type Currency = 'USD' | 'THB'

export type BaselinePeriod = '3M' | '6M' | '12M'
export type ForecastHorizon = '1M' | '3M' | '6M' | '12M'
export type Granularity = 'monthly' | 'weekly'
export type ConfidenceLevel = 'high' | 'medium' | 'low'

// AWS Services for filtering
export const AWS_SERVICES = [
    'EC2', 'S3', 'RDS', 'Lambda', 'CloudFront', 'DynamoDB', 'ECS', 'EKS', 'ElastiCache', 'Other'
] as const

export type AWSService = typeof AWS_SERVICES[number]

// AWS Regions for filtering
export const AWS_REGIONS = [
    { id: 'us-east-1', name: 'US East (N. Virginia)' },
    { id: 'us-west-2', name: 'US West (Oregon)' },
    { id: 'eu-west-1', name: 'Europe (Ireland)' },
    { id: 'ap-southeast-1', name: 'Asia Pacific (Singapore)' },
    { id: 'ap-northeast-1', name: 'Asia Pacific (Tokyo)' },
] as const

export type AWSRegion = typeof AWS_REGIONS[number]['id']

// Forecast Settings (Scope Selection)
export interface ForecastSettings {
    baselinePeriod: BaselinePeriod
    forecastHorizon: ForecastHorizon
    granularity: Granularity
    selectedServices: AWSService[]
    selectedRegions: AWSRegion[]
}

// Data Quality Information
export interface DataQuality {
    lastUpdated: Date
    dataCoverage: number // days
    confidenceScore: ConfidenceLevel
    dataPoints: number
}

// Service Cost Breakdown
export interface ServiceBreakdown {
    service: AWSService
    cost: number
    percentage: number
    color: string
}

// Forecast Data Point (for chart)
export interface ForecastDataPoint {
    date: string
    label: string
    actual?: number
    baseline?: number
    lower?: number
    upper?: number
    simulated?: number
    isProjected: boolean
}

// Forecast Summary
export interface ForecastSummary {
    forecastTotal: number
    lastMonthCost: number
    simulatedSavings: number
    changeFromBaseline: number
}

// API Response Types
export interface ForecastMetricResult {
    metric: string
    method: string
    forecast_dates: string[]
    forecast_values: number[]
    backtest_dates?: string[]
    backtest_actuals?: number[]
    backtest_preds?: number[]
    fallback?: boolean
    performance_metrics?: {
        mae?: number
        rmse?: number
        mape?: number
    }
    // Cost fields
    forecast_costs?: number[]
    total_forecast_cost?: number
    avg_daily_cost?: number
    cost_breakdown?: {
        [costType: string]: number[]
    }
    cost_breakdown_totals?: {
        [costType: string]: number
    }
    history_costs?: number[]
    history_dates?: string[]
    created_at?: string
}

export interface EnsembleForecastResponse {
    service: string
    resource_id: number
    results: ForecastMetricResult[]
}

export interface ForecastMetricsResponse {
    services: {
        [serviceName: string]: {
            metrics: string[]
            resources: Array<{
                id: number
                name?: string
                type?: string
            }>
        }
    }
}

export interface ForecastRun {
    run_id: number
    service: string
    resource_id: number
    metric?: string
    method: string
    horizon: number
    train_size?: number
    mae?: number
    rmse?: number
    mape?: number
    created_at: string
    params?: any
}

// Enhanced forecast types with cost data
export interface CostBreakdown {
    compute?: number[]
    storage?: number[]
    network?: number[]
    requests?: number[]
    duration?: number[]
    ebs?: number[]
    public_ip?: number[]
    hourly?: number[]
    lcu?: number[]
    [key: string]: number[] | undefined
}

export interface ForecastDataPointWithCost extends ForecastDataPoint {
    cost?: number
    costBreakdown?: CostBreakdown
}

// Multi-resource forecast types
export interface MultiEnsembleForecastResult {
    service: string
    resource_id: number
    resource_name?: string
    results: ForecastMetricResult[]
    error?: string
}

export interface MultiEnsembleForecastResponse {
    total_resources: number
    successful: number
    failed: number
    forecasts: MultiEnsembleForecastResult[]
    last_month_cost?: number
}

// Default settings
export function getDefaultSettings(): ForecastSettings {
    return {
        baselinePeriod: '3M',
        forecastHorizon: '3M',
        granularity: 'monthly',
        selectedServices: ['EC2', 'S3', 'RDS', 'Lambda'],
        selectedRegions: ['us-east-1'],
    }
}
