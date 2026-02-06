import type { AWSRegion, ForecastSettings } from '@/types/forecast'

// AWS Regions with pricing modifiers
export const AWS_REGIONS: AWSRegion[] = [
    { id: 'us-east-1', name: 'US East (N. Virginia)', code: 'us-east-1', pricingModifier: 1.0 },
    { id: 'us-east-2', name: 'US East (Ohio)', code: 'us-east-2', pricingModifier: 1.0 },
    { id: 'us-west-1', name: 'US West (N. California)', code: 'us-west-1', pricingModifier: 1.05 },
    { id: 'us-west-2', name: 'US West (Oregon)', code: 'us-west-2', pricingModifier: 1.0 },
    { id: 'ap-southeast-1', name: 'Asia Pacific (Singapore)', code: 'ap-southeast-1', pricingModifier: 1.1 },
    { id: 'ap-southeast-2', name: 'Asia Pacific (Sydney)', code: 'ap-southeast-2', pricingModifier: 1.12 },
    { id: 'ap-northeast-1', name: 'Asia Pacific (Tokyo)', code: 'ap-northeast-1', pricingModifier: 1.15 },
    { id: 'ap-northeast-2', name: 'Asia Pacific (Seoul)', code: 'ap-northeast-2', pricingModifier: 1.08 },
    { id: 'ap-south-1', name: 'Asia Pacific (Mumbai)', code: 'ap-south-1', pricingModifier: 1.05 },
    { id: 'eu-west-1', name: 'Europe (Ireland)', code: 'eu-west-1', pricingModifier: 1.08 },
    { id: 'eu-west-2', name: 'Europe (London)', code: 'eu-west-2', pricingModifier: 1.1 },
    { id: 'eu-central-1', name: 'Europe (Frankfurt)', code: 'eu-central-1', pricingModifier: 1.1 },
    { id: 'sa-east-1', name: 'South America (São Paulo)', code: 'sa-east-1', pricingModifier: 1.25 },
]

// Quick-select horizon options (in months)
export const QUICK_SELECT_OPTIONS = [
    { value: 1, label: '1 month' },
    { value: 3, label: '3 months' },
    { value: 6, label: '6 months' },
    { value: 12, label: '12 months' },
]

// Default exchange rate (USD to THB)
export const DEFAULT_EXCHANGE_RATE = 35.5

// Default cost per usage unit (for demo purposes)
export const DEFAULT_COST_PER_UNIT = 0.0464 // Example: EC2 t3.micro hourly rate

// Month names for display
export const MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
]

export const MONTH_NAMES_SHORT = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
]

// Generate month options for dropdowns
export function getMonthOptions() {
    const currentYear = new Date().getFullYear()
    const options: { value: string; label: string; date: Date }[] = []

    for (let year = currentYear; year <= currentYear + 2; year++) {
        for (let month = 0; month < 12; month++) {
            const date = new Date(year, month, 1)
            options.push({
                value: `${year}-${String(month + 1).padStart(2, '0')}`,
                label: `${MONTH_NAMES_SHORT[month]} ${year}`,
                date
            })
        }
    }

    return options
}

// Get default forecast settings
export function getDefaultForecastSettings(): ForecastSettings {
    const now = new Date()
    const startMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1) // Next month
    const endMonth = new Date(now.getFullYear(), now.getMonth() + 4, 1) // 3 months later

    return {
        startMonth,
        endMonth,
        currency: 'USD',
        exchangeRate: DEFAULT_EXCHANGE_RATE,
        selectedRegions: ['us-east-1'],
        forecastMode: 'static',
        percentageGrowth: 5,
        growthDriver: 10,
        inputMethodology: 'actual-cost',
        latestMonthCost: 10000,
        totalUsageUnits: 10000,
        costPerUnit: DEFAULT_COST_PER_UNIT,
        realTimeCalculation: false
    }
}
