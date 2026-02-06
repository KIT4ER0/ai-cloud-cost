import { Link } from 'react-router-dom'
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Play, Check, X, TrendingDown, ArrowRight } from 'lucide-react'
import { RECOMMENDATIONS, type Recommendation } from '@/types/recommendation'
import { useSimulationStore } from '@/store/simulation-store'

export default function Recommend() {
    const {
        simulatedItems,
        toggleSimulation,
        removeSimulation,
        resetSimulation,
        isSimulated
    } = useSimulationStore()

    const totalSavings = simulatedItems.reduce((sum, item) => sum + item.savingsPerMonth, 0)
    const hasSimulations = simulatedItems.length > 0

    const handleSimulate = (rec: Recommendation) => {
        toggleSimulation({
            id: rec.id,
            title: rec.title,
            savingsPerMonth: rec.savingsPerMonth
        })
    }

    const handleIgnore = (rec: Recommendation) => {
        // If recommendation is simulated, remove it from simulation
        if (isSimulated(rec.id)) {
            removeSimulation(rec.id)
        }
        // In real app, would also mark as ignored in backend
    }

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-3xl font-bold tracking-tight text-primary">Recommendations</h2>
                <p className="text-muted-foreground">Actionable insights to optimize cost and performance.</p>
            </div>

            {/* Simulation Banner - Only visible when simulations are active */}
            {hasSimulations && (
                <Card className="border-primary/50 bg-primary/5 p-4">
                    <div className="flex items-center justify-between w-full">
                        <div className="flex items-center gap-3">
                            <div className="flex items-center gap-2">
                                <Play className="h-4 w-4 text-primary" />
                                <span className="font-semibold text-primary">Simulation Mode ON</span>
                            </div>
                            <span className="text-sm">
                                {simulatedItems.length} action{simulatedItems.length !== 1 ? 's' : ''} simulated · Estimated saving{' '}
                                <span className="font-semibold text-green-600">${totalSavings}/mo</span>
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={resetSimulation}
                                className="text-muted-foreground hover:text-foreground"
                            >
                                <X className="h-4 w-4 mr-1" />
                                Reset
                            </Button>
                            <Button asChild size="sm">
                                <Link to="/forecast-cost">
                                    View impact in Forecast
                                    <ArrowRight className="h-4 w-4 ml-1" />
                                </Link>
                            </Button>
                        </div>
                    </div>
                </Card>
            )}

            <div className="space-y-4">
                {RECOMMENDATIONS.map((rec) => {
                    const simulated = isSimulated(rec.id)

                    return (
                        <Card
                            key={rec.id}
                            className={`flex flex-col md:flex-row items-start md:items-center justify-between p-2 transition-colors ${simulated ? 'border-primary/50 bg-primary/5' : ''
                                }`}
                        >
                            <div className="flex-1 p-4">
                                <div className="flex items-center gap-2 mb-1">
                                    <h3 className="font-semibold text-lg">{rec.title}</h3>
                                    <Badge variant={rec.severity === 'High' ? 'destructive' : 'secondary'}>
                                        {rec.severity}
                                    </Badge>
                                    {simulated && (
                                        <Badge variant="outline" className="border-primary text-primary">
                                            <Check className="h-3 w-3 mr-1" />
                                            Simulated
                                        </Badge>
                                    )}
                                </div>
                                <p className="text-muted-foreground text-sm">{rec.description}</p>
                            </div>

                            <div className="p-4 flex flex-col items-end gap-2 min-w-[150px]">
                                <div className="flex items-center gap-1 text-green-600 font-bold mb-1">
                                    <TrendingDown className="h-4 w-4" />
                                    Save ${rec.savingsPerMonth}/mo
                                </div>
                                <div className="flex gap-2">
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => handleIgnore(rec)}
                                    >
                                        Ignore
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant={simulated ? 'secondary' : 'default'}
                                        onClick={() => handleSimulate(rec)}
                                    >
                                        {simulated ? (
                                            <>
                                                <Check className="h-4 w-4 mr-1" />
                                                Simulated
                                            </>
                                        ) : (
                                            <>
                                                <Play className="h-4 w-4 mr-1" />
                                                Simulate
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </div>
                        </Card>
                    )
                })}
            </div>
        </div>
    )
}
