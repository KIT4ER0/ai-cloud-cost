import { Card, CardContent } from '@/components/ui/card'
import { DollarSign, Calendar } from 'lucide-react'
import type { ForecastSummary } from '@/types/forecast'

interface ForecastSummaryCardsProps {
    summary: ForecastSummary
}

export function ForecastSummaryCards({ summary }: ForecastSummaryCardsProps) {
    const cards = [
        {
            title: 'Forecast Total',
            value: `$${summary.forecastTotal.toLocaleString()}`,
            subtitle: 'Next Month',
            icon: DollarSign,
            iconBg: 'bg-primary/10',
            iconColor: 'text-primary',
        },
        {
            title: 'Last Month Cost',
            value: `$${summary.lastMonthCost.toLocaleString()}`,
            subtitle: 'Last Month',
            icon: Calendar,
            iconBg: 'bg-blue-100',
            iconColor: 'text-blue-600',
        },
    ]

    return (
        <div className="grid gap-4 md:grid-cols-2">
            {cards.map((card, index) => (
                <Card key={index}>
                    <CardContent className="pt-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-muted-foreground">{card.title}</p>
                                <p className="text-2xl font-bold">
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
