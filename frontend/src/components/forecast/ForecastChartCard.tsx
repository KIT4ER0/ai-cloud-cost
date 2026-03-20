import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
    Line,
    XAxis,
    YAxis,
    ResponsiveContainer,
    Legend,
    Area,
    ComposedChart,
} from 'recharts'
import { TrendingUp } from 'lucide-react'
import type { ForecastDataPoint } from '@/types/forecast'

interface ForecastChartCardProps {
    data: ForecastDataPoint[]
}

export function ForecastChartCard({ data }: ForecastChartCardProps) {

    const formatYAxis = (value: number) => `$${value.toFixed(0)}`

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
                        <Legend
                            wrapperStyle={{ paddingTop: 20 }}
                            iconType="circle"
                            formatter={(value) => {
                                const labels: Record<string, string> = {
                                    actual: 'History',
                                    baseline: 'Forecast',
                                    simulated: 'Optimized',
                                }
                                return <span className="text-xs font-medium text-slate-600">{labels[value] || value}</span>
                            }}
                        />

                        {/* Shaded Area for History */}

                        {/* Actual History - Solid line with area */}

                        {/* Actual History - Solid line with area */}
                        <Area
                            type="monotone"
                            dataKey="actual"
                            stroke="hsl(262, 80%, 50%)"
                            strokeWidth={3}
                            fill="url(#actualGradient)"
                            dot={{ fill: 'hsl(262, 80%, 50%)', strokeWidth: 0, r: 4 }}
                            activeDot={{ r: 6, strokeWidth: 0 }}
                            name="actual"
                        />

                        {/* Baseline Forecast - Dashed line */}
                        <Line
                            type="monotone"
                            dataKey="baseline"
                            stroke="#475569"
                            strokeWidth={2.5}
                            strokeDasharray="6 4"
                            dot={{ fill: '#475569', strokeWidth: 0, r: 3 }}
                            activeDot={{ r: 5, strokeWidth: 0 }}
                            name="baseline"
                        />


                    </ComposedChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    )
}
