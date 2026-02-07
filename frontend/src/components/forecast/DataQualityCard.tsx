import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Database, Clock, Shield, BarChart3 } from 'lucide-react'
import type { DataQuality, ConfidenceLevel } from '@/types/forecast'

interface DataQualityCardProps {
    dataQuality: DataQuality
}

const confidenceBadgeStyles: Record<ConfidenceLevel, { variant: 'default' | 'secondary' | 'outline' | 'destructive'; className: string }> = {
    high: { variant: 'default', className: 'bg-green-100 text-green-700 hover:bg-green-100' },
    medium: { variant: 'secondary', className: 'bg-amber-100 text-amber-700 hover:bg-amber-100' },
    low: { variant: 'outline', className: 'bg-red-100 text-red-700 hover:bg-red-100' },
}

export function DataQualityCard({ dataQuality }: DataQualityCardProps) {
    const formatLastUpdated = (date: Date) => {
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        })
    }

    const badgeStyle = confidenceBadgeStyles[dataQuality.confidenceScore]

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Database className="h-4 w-4 text-primary" />
                    Data Quality
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Last Updated */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Clock className="h-4 w-4" />
                        Last Updated
                    </div>
                    <span className="text-sm font-medium">{formatLastUpdated(dataQuality.lastUpdated)}</span>
                </div>

                {/* Data Coverage */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <BarChart3 className="h-4 w-4" />
                        Data Coverage
                    </div>
                    <span className="text-sm font-medium">{dataQuality.dataCoverage} days</span>
                </div>

                {/* Confidence Score */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Shield className="h-4 w-4" />
                        Confidence Score
                    </div>
                    <Badge variant={badgeStyle.variant} className={badgeStyle.className}>
                        {dataQuality.confidenceScore.charAt(0).toUpperCase() + dataQuality.confidenceScore.slice(1)}
                    </Badge>
                </div>

                {/* Data Points */}
                <div className="pt-2 border-t">
                    <p className="text-xs text-muted-foreground text-center">
                        Based on {dataQuality.dataPoints.toLocaleString()} data points
                    </p>
                </div>
            </CardContent>
        </Card>
    )
}
