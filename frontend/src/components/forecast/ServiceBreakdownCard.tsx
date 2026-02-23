import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from 'recharts'
import { PieChart } from 'lucide-react'
import type { ServiceBreakdown } from '@/types/forecast'

interface ServiceBreakdownCardProps {
    breakdown: ServiceBreakdown[]
}

export function ServiceBreakdownCard({ breakdown }: ServiceBreakdownCardProps) {
    // Prepare data for horizontal bar chart
    const chartData = breakdown.map(item => ({
        name: item.service,
        cost: item.cost,
        percentage: item.percentage,
        color: item.color,
    }))

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <PieChart className="h-4 w-4 text-primary" />
                    Current Baseline Breakdown
                </CardTitle>
                <p className="text-xs text-muted-foreground">Top 5 services by cost</p>
            </CardHeader>
            <CardContent>
                <ResponsiveContainer width="100%" height={180}>
                    <BarChart
                        data={chartData}
                        layout="vertical"
                        margin={{ top: 0, right: 40, bottom: 0, left: 50 }}
                    >
                        <XAxis
                            type="number"
                            tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                            tick={{ fontSize: 11 }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <YAxis
                            type="category"
                            dataKey="name"
                            tick={{ fontSize: 12 }}
                            axisLine={false}
                            tickLine={false}
                            width={45}
                        />
                        <Tooltip
                            formatter={(value) => {
                                const numValue = typeof value === 'number' ? value : 0
                                return [`$${numValue.toLocaleString()}`, 'Cost']
                            }}
                            contentStyle={{
                                backgroundColor: 'white',
                                border: '1px solid #e5e7eb',
                                borderRadius: '8px',
                                fontSize: '12px',
                            }}
                        />
                        <Bar dataKey="cost" radius={[0, 4, 4, 0]} barSize={20}>
                            {chartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>

                {/* Legend with percentages */}
                <div className="flex flex-wrap justify-center gap-3 mt-3 pt-3 border-t">
                    {breakdown.slice(0, 4).map((item) => (
                        <div key={item.service} className="flex items-center gap-1.5 text-xs">
                            <div
                                className="w-2.5 h-2.5 rounded-sm"
                                style={{ backgroundColor: item.color }}
                            />
                            <span className="text-muted-foreground">{item.service}</span>
                            <span className="font-medium">{item.percentage.toFixed(0)}%</span>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    )
}
