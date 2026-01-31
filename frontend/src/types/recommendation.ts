// Recommendation Types

export type Severity = 'High' | 'Medium' | 'Low'

export interface Recommendation {
    id: string
    title: string
    description: string
    savingsPerMonth: number // numeric value in USD
    severity: Severity
}

export interface SimulatedRecommendation {
    id: string
    title: string
    savingsPerMonth: number
}

export interface SimulationState {
    simulatedItems: SimulatedRecommendation[]
    totalSavings: number
}

// Sample recommendations data
export const RECOMMENDATIONS: Recommendation[] = [
    {
        id: 'rec-1',
        title: 'Resize EC2 Instance',
        description: 'Instance i-0x83d2 is underutilized (5% CPU). Suggest moving to t3.small.',
        savingsPerMonth: 45,
        severity: 'High'
    },
    {
        id: 'rec-2',
        title: 'Delete Unused EBS Volume',
        description: "Volume vol-0x23a1 hasn't been attached for 30 days.",
        savingsPerMonth: 12,
        severity: 'Medium'
    },
    {
        id: 'rec-3',
        title: 'Purchase Reserved Instances',
        description: 'Consistent usage detected for db.m5.large. RI offers 30% discount.',
        savingsPerMonth: 120,
        severity: 'Low'
    }
]
