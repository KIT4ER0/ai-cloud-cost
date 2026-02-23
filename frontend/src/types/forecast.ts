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
    simulated?: number
    isProjected: boolean
}

// Forecast Summary
export interface ForecastSummary {
    forecastTotal: number
    avgMonthlyCost: number
    simulatedSavings: number
    changeFromBaseline: number
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
