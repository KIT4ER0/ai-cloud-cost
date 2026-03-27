import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from 'recharts'
import { TrendingUp } from 'lucide-react'
import type { ServiceBreakdown } from '@/types/forecast'

interface ExtendedBreakdown extends ServiceBreakdown {
    resourceName?: string
    metricsCount?: number
    avgMape?: number | null
    isFallback?: boolean
    method?: string
}

interface ServiceBreakdownCardProps {
    breakdown: ExtendedBreakdown[]
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload }: any) {
    if (!active || !payload?.[0]) return null
    const d = payload[0].payload as ExtendedBreakdown & { name: string }
    return (
        <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs space-y-1">
            <p className="font-semibold text-sm">{d.name}</p>
            {d.resourceName && (
                <p className="text-gray-500">{d.resourceName}</p>
            )}
            <div className="pt-1 mt-1 border-t border-gray-100 space-y-1">
                <p>Method: <span className={`font-medium ${d.isFallback ? 'text-amber-600' : 'text-primary'}`}>
                    {d.method === 'ensemble' ? 'Ensemble' : 'Fallback'}
                </span></p>
                <p>Forecast Cost: <span className="font-medium">${d.cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></p>
                <p>Share: <span className="font-medium">{d.percentage}%</span></p>
                {d.avgMape != null && !d.isFallback && (
                    <p>Avg MAPE: <span className={`font-medium ${
                        d.avgMape < 35 ? 'text-green-600' :
                        d.avgMape < 45 ? 'text-lime-600' :
                        d.avgMape < 55 ? 'text-yellow-600' :
                        d.avgMape < 65 ? 'text-orange-500' :
                        'text-red-600'
                    }`}>
                        {d.avgMape.toFixed(1)}%
                    </span></p>
                )}
            </div>
        </div>
    )
}

export function ServiceBreakdownCard({ breakdown }: ServiceBreakdownCardProps) {
    const hasForecastInfo = breakdown.some(b => b.metricsCount != null)
    const grandTotal = breakdown.reduce((s, b) => s + b.cost, 0)

    const chartData = breakdown.map(item => ({
        ...item,
        name: item.service,
    }))

    const barHeight = Math.max(breakdown.length * 40, 120)

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <TrendingUp className="h-4 w-4 text-primary" />
                    {hasForecastInfo ? 'Forecast Cost by Service' : 'Cost Breakdown'}
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                    {hasForecastInfo
                        ? `Total forecast: $${grandTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                        : 'Top services by cost'}
                </p>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={barHeight}>
                    <BarChart
                        data={chartData}
                        layout="vertical"
                        margin={{ top: 0, right: 50, bottom: 0, left: 55 }}
                    >
                        <XAxis
                            type="number"
                            tickFormatter={(value) =>
                                value >= 1000 ? `$${(value / 1000).toFixed(1)}k` : `$${value.toFixed(0)}`
                            }
                            tick={{ fontSize: 11 }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <YAxis
                            type="category"
                            dataKey="name"
                            tick={{ fontSize: 12, fontWeight: 500 }}
                            axisLine={false}
                            tickLine={false}
                            width={50}
                        />
                        <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0,0,0,0.04)' }} />
                        <Bar dataKey="cost" radius={[0, 6, 6, 0]} barSize={24}>
                            {chartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>

                {/* Legend */}
                <div className="flex flex-wrap justify-center gap-4 mt-3 pt-3 border-t">
                    {breakdown.map((item) => (
                        <div key={item.service} className="flex flex-col gap-1 items-center">
                            <div className="flex items-center gap-1.5 text-xs">
                                <div
                                    className="w-2.5 h-2.5 rounded-full"
                                    style={{ backgroundColor: item.color }}
                                />
                                <span className="text-muted-foreground">{item.service}</span>
                                <span className="font-semibold">{item.percentage}%</span>
                            </div>
                            <div className="flex gap-1">
                                <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${
                                    item.isFallback ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'
                                }`}>
                                    {item.method === 'ensemble' ? 'Ensemble' : 'Fallback'}
                                </span>
                                {item.avgMape != null && !item.isFallback && (
                                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                                        item.avgMape < 35 ? 'bg-green-100 text-green-700' :
                                        item.avgMape < 45 ? 'bg-lime-100 text-lime-700' :
                                        item.avgMape < 55 ? 'bg-yellow-100 text-yellow-700' :
                                        item.avgMape < 65 ? 'bg-orange-100 text-orange-700' :
                                        'bg-red-100 text-red-700'
                                    }`}>
                                        MAPE {item.avgMape.toFixed(0)}%
                                    </span>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    )
}
