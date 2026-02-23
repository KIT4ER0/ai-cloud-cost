import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Info, CheckCircle2 } from 'lucide-react'

interface ModelAssumptions {
    model: string
    assumptions: string[]
    simulationBasis: string
}

interface InsightsPanelProps {
    assumptions: ModelAssumptions
    isSimulating: boolean
}

export function InsightsPanel({ assumptions, isSimulating }: InsightsPanelProps) {
    return (
        <Card className="bg-slate-50/50">
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-sm font-medium">
                    <Info className="h-4 w-4 text-muted-foreground" />
                    Model &amp; Assumptions
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
                <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Forecast Model:</span>
                    <span className="text-xs font-medium bg-white px-2 py-1 rounded border">
                        {assumptions.model}
                    </span>
                </div>

                <div className="space-y-1.5">
                    {assumptions.assumptions.map((assumption, index) => (
                        <div key={index} className="flex items-start gap-2">
                            <CheckCircle2 className="h-3.5 w-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                            <span className="text-xs text-muted-foreground">{assumption}</span>
                        </div>
                    ))}
                </div>

                {isSimulating && (
                    <div className="pt-2 mt-2 border-t border-dashed">
                        <p className="text-xs text-green-600 flex items-center gap-1.5">
                            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                            <span className="font-medium">Simulation:</span>
                            <span>{assumptions.simulationBasis}</span>
                        </p>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
