import { Card, CardContent } from '@/components/ui/card'
import { DollarSign, Calendar, TrendingDown, Sparkles } from 'lucide-react'
import type { ForecastSummary } from '@/types/forecast'

interface ForecastSummaryCardsProps {
    summary: ForecastSummary
    isSimulating: boolean
}

export function ForecastSummaryCards({ summary, isSimulating }: ForecastSummaryCardsProps) {
    const cards = [
        {
            title: 'Forecast Total',
            value: `$${summary.forecastTotal.toLocaleString()}`,
            subtitle: 'Next 3 months',
            icon: DollarSign,
            iconBg: 'bg-primary/10',
            iconColor: 'text-primary',
        },
        {
            title: 'Avg Monthly Cost',
            value: `$${summary.avgMonthlyCost.toLocaleString()}`,
            subtitle: 'Projected average',
            icon: Calendar,
            iconBg: 'bg-blue-100',
            iconColor: 'text-blue-600',
        },
    ]

    // Add simulated savings card only when simulating
    if (isSimulating && summary.simulatedSavings > 0) {
        cards.push({
            title: 'Simulated Savings',
            value: `$${summary.simulatedSavings.toLocaleString()}`,
            subtitle: `${Math.abs(summary.changeFromBaseline).toFixed(1)}% reduction`,
            icon: isSimulating ? Sparkles : TrendingDown,
            iconBg: 'bg-green-100',
            iconColor: 'text-green-600',
        })
    }

    return (
        <div className={`grid gap-4 ${isSimulating ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
            {cards.map((card, index) => (
                <Card key={index} className={isSimulating && index === 2 ? 'border-green-200 bg-green-50/30' : ''}>
                    <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-muted-foreground">{card.title}</p>
                                <p className={`text-2xl font-bold ${isSimulating && index === 2 ? 'text-green-600' : ''}`}>
                                    {card.value}
                                </p>
                                <p className="text-xs text-muted-foreground mt-1">{card.subtitle}</p>
                            </div>
                            <div className={`h-12 w-12 rounded-full ${card.iconBg} flex items-center justify-center`}>
                                <card.icon className={`h-6 w-6 ${card.iconColor}`} />
                            </div>
                        </div>
                    </CardContent>
                </Card>
            ))}
        </div>
    )
}
