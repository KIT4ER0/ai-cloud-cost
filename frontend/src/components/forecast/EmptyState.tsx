import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Database, Cloud, ArrowRight } from 'lucide-react'

interface EmptyStateProps {
    onConnectData: () => void
}

export function EmptyState({ onConnectData }: EmptyStateProps) {
    return (
        <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                {/* Icon stack */}
                <div className="relative mb-6">
                    <div className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center">
                        <Cloud className="h-10 w-10 text-slate-400" />
                    </div>
                    <div className="absolute -bottom-1 -right-1 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center border-2 border-white">
                        <Database className="h-4 w-4 text-primary" />
                    </div>
                </div>

                {/* Title and description */}
                <h3 className="text-xl font-semibold text-foreground mb-2">
                    No Data Connected
                </h3>
                <p className="text-muted-foreground max-w-md mb-6">
                    Connect your AWS Cost Explorer data to generate accurate forecasts based on your
                    historical spending patterns.
                </p>

                {/* Benefits list */}
                <div className="flex flex-wrap justify-center gap-4 mb-8 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                        ML-powered predictions
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                        What-if simulations
                    </div>
                    <div className="flex items-center gap-1.5">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                        Service-level breakdowns
                    </div>
                </div>

                {/* CTA Button */}
                <Button onClick={onConnectData} size="lg" className="gap-2">
                    Connect Data Source
                    <ArrowRight className="h-4 w-4" />
                </Button>

                <p className="text-xs text-muted-foreground mt-4">
                    Requires AWS Cost Explorer API access
                </p>
            </CardContent>
        </Card>
    )
}
