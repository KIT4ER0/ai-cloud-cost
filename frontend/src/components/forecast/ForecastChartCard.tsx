import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
    Line,
    XAxis,
    YAxis,
    ResponsiveContainer,
    Tooltip,
    Legend,
    ReferenceLine,
    Area,
    ComposedChart,
} from 'recharts'
import { TrendingUp, Zap } from 'lucide-react'
import type { ForecastDataPoint } from '@/types/forecast'

interface ForecastChartCardProps {
    data: ForecastDataPoint[]
    isSimulating: boolean
    onSimulationToggle: (value: boolean) => void
}

export function ForecastChartCard({ data, isSimulating, onSimulationToggle }: ForecastChartCardProps) {
    // Find the transition point between actual and projected
    const lastActualIndex = data.findIndex(d => d.isProjected) - 1
    const transitionDate = lastActualIndex >= 0 ? data[lastActualIndex].date : null

    const formatYAxis = (value: number) => `$${(value / 1000).toFixed(0)}k`

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-4">
                <div>
                    <CardTitle className="flex items-center gap-2">
                        <TrendingUp className="h-5 w-5 text-primary" />
                        Cost Forecast
                    </CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                        Historical trend with projected costs
                    </p>
                </div>
                <div className="flex items-center gap-4">
                    <Badge variant="outline" className="text-xs">
                        {transitionDate ? `Projection starts: Feb 2026` : ''}
                    </Badge>
                    <div className="flex items-center gap-2 bg-slate-50 px-3 py-2 rounded-lg border">
                        <Zap className={`h-4 w-4 ${isSimulating ? 'text-green-500' : 'text-muted-foreground'}`} />
                        <Label htmlFor="simulation-mode" className="text-sm font-medium cursor-pointer">
                            Simulation Mode
                        </Label>
                        <Switch
                            id="simulation-mode"
                            checked={isSimulating}
                            onCheckedChange={onSimulationToggle}
                        />
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={350}>
                    <ComposedChart 
                        data={data} 
                        margin={{ top: 20, right: 30, bottom: 20, left: 20 }}
                    >
                        <defs>
                            <linearGradient id="actualGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="hsl(270, 91%, 29%)" stopOpacity={0.15} />
                                <stop offset="95%" stopColor="hsl(270, 91%, 29%)" stopOpacity={0} />
                            </linearGradient>
                            <linearGradient id="simulatedGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                            </linearGradient>
                        </defs>

                        <XAxis
                            dataKey="label"
                            tick={{ fontSize: 12 }}
                            axisLine={{ stroke: '#e5e7eb' }}
                            tickLine={false}
                        />
                        <YAxis
                            tickFormatter={formatYAxis}
                            tick={{ fontSize: 12 }}
                            axisLine={{ stroke: '#e5e7eb' }}
                            tickLine={false}
                            domain={['auto', 'auto']}
                        />
                        <Tooltip
                            formatter={(value, name) => {
                                if (value === undefined || typeof value !== 'number') return [String(value ?? 'N/A'), String(name)]
                                const labels: Record<string, string> = {
                                    actual: 'Actual',
                                    baseline: 'Baseline Forecast',
                                    simulated: 'After Optimization',
                                }
                                return [`$${value.toLocaleString()}`, labels[String(name)] || String(name)]
                            }}
                            contentStyle={{
                                backgroundColor: 'white',
                                border: '1px solid #e5e7eb',
                                borderRadius: '8px',
                                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                            }}
                            labelStyle={{ fontWeight: 600 }}
                        />
                        <Legend
                            wrapperStyle={{ paddingTop: 20 }}
                            iconType="line"
                            formatter={(value) => {
                                const labels: Record<string, string> = {
                                    actual: 'Actual History',
                                    baseline: 'Baseline Forecast',
                                    simulated: 'After Optimization',
                                }
                                return <span className="text-sm">{labels[value] || value}</span>
                            }}
                        />

                        {/* Projection zone marker */}
                        {transitionDate && (
                            <ReferenceLine
                                x="Jan 2026"
                                stroke="#94a3b8"
                                strokeDasharray="4 4"
                                label={{
                                    value: 'Projection',
                                    position: 'top',
                                    fill: '#94a3b8',
                                    fontSize: 11,
                                }}
                            />
                        )}

                        {/* Actual History - Solid line with area */}
                        <Area
                            type="monotone"
                            dataKey="actual"
                            stroke="hsl(270, 91%, 29%)"
                            strokeWidth={2.5}
                            fill="url(#actualGradient)"
                            dot={{ fill: 'hsl(270, 91%, 29%)', strokeWidth: 0, r: 4 }}
                            activeDot={{ r: 6.5 }}
                            connectNulls={false}
                            name="actual"
                        />

                        {/* Baseline Forecast - Dashed line */}
                        <Line
                            type="monotone"
                            dataKey="baseline"
                            stroke="#64748b"
                            strokeWidth={2}
                            strokeDasharray="6 4"
                            dot={{ fill: '#64748b', strokeWidth: 0, r: 3.5 }}
                            activeDot={{ r: 5.5 }}
                            connectNulls={false}
                            name="baseline"
                        />

                        {/* Simulated Forecast - Green line (only when simulating) */}
                        {isSimulating && (
                            <Area
                                type="monotone"
                                dataKey="simulated"
                                stroke="#10b981"
                                strokeWidth={2.5}
                                fill="url(#simulatedGradient)"
                                dot={{ fill: '#10b981', strokeWidth: 0, r: 4 }}
                                activeDot={{ r: 6.5 }}
                                connectNulls={false}
                                name="simulated"
                            />
                        )}
                    </ComposedChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    )
}
