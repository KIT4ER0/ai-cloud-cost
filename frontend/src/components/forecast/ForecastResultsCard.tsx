import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import {
    LineChart,
    Line,
    BarChart,
    Bar,
    ResponsiveContainer,
    XAxis,
    YAxis,
    Tooltip,
    Legend,
    CartesianGrid,
} from 'recharts'
import { TrendingUp, TrendingDown, DollarSign, BarChart3, Target, Sparkles } from 'lucide-react'
import type { ForecastResult, ForecastSummary, Currency } from '@/types/forecast'
import type { SimulatedRecommendation } from '@/types/recommendation'
import { formatCurrency, formatCompactCurrency, convertCurrency } from '@/lib/forecast-calculations'

interface ForecastResultsCardProps {
    results: ForecastResult[]
    summary: ForecastSummary | null
    currency: Currency
    isLoading?: boolean
    simulatedSavings?: number
    simulatedItems?: SimulatedRecommendation[]
}

function SummaryStat({
    title,
    value,
    subtitle,
    icon: Icon,
    trend,
    highlight
}: {
    title: string
    value: string
    subtitle?: string
    icon: React.ElementType
    trend?: { direction: 'up' | 'down' | 'neutral'; value?: string }
    highlight?: boolean
}) {
    return (
        <div className={`p-4 rounded-lg ${highlight ? 'bg-green-500/10 border border-green-500/30' : 'bg-muted/50'}`}>
            <div className="flex items-center gap-2 mb-2">
                <Icon className={`h-4 w-4 ${highlight ? 'text-green-600' : 'text-muted-foreground'}`} />
                <span className={`text-sm ${highlight ? 'text-green-600 font-medium' : 'text-muted-foreground'}`}>{title}</span>
            </div>
            <div className={`text-2xl font-bold ${highlight ? 'text-green-600' : ''}`}>{value}</div>
            {subtitle && <div className="text-xs text-muted-foreground mt-1">{subtitle}</div>}
            {trend && (
                <div className={`flex items-center gap-1 mt-1 text-xs ${trend.direction === 'up' ? 'text-amber-500' :
                    trend.direction === 'down' ? 'text-green-500' :
                        'text-muted-foreground'
                    }`}>
                    {trend.direction === 'up' && <TrendingUp className="h-3 w-3" />}
                    {trend.direction === 'down' && <TrendingDown className="h-3 w-3" />}
                    {trend.value && <span>{trend.value}</span>}
                </div>
            )}
        </div>
    )
}

function CustomTooltip({
    active,
    payload,
    label,
    currency
}: {
    active?: boolean
    payload?: Array<{ value: number; name: string; color: string }>
    label?: string
    currency: Currency
}) {
    if (active && payload && payload.length) {
        return (
            <div className="bg-background border rounded-lg shadow-lg p-3">
                <p className="font-medium mb-2">{label}</p>
                {payload.map((entry, index) => (
                    <p key={index} className="text-sm" style={{ color: entry.color }}>
                        {entry.name}: {formatCurrency(entry.value, currency)}
                    </p>
                ))}
            </div>
        )
    }
    return null
}

export function ForecastResultsCard({
    results,
    summary,
    currency,
    isLoading: _isLoading = false,
    simulatedSavings = 0,
    simulatedItems = []
}: ForecastResultsCardProps) {
    const hasSimulation = simulatedSavings > 0

    // Convert simulated savings to selected currency
    const simulatedSavingsConverted = currency === 'THB' && summary
        ? convertCurrency(simulatedSavings, currency, summary.exchangeRate)
        : simulatedSavings

    if (!summary || results.length === 0) {
        return (
            <Card className="h-fit">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <BarChart3 className="h-5 w-5 text-primary" />
                        Forecast Results
                    </CardTitle>
                    <CardDescription>
                        Configure settings and click Calculate to see projections
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-col items-center justify-center h-64 text-center text-muted-foreground">
                        <BarChart3 className="h-16 w-16 mb-4 opacity-20" />
                        <p>No forecast data yet</p>
                        <p className="text-sm">Adjust settings and calculate to view projections</p>
                    </div>
                </CardContent>
            </Card>
        )
    }

    // Prepare chart data with simulation comparison
    const chartData = results.map(r => {
        const afterSimulation = Math.max(0, r.projectedCostConverted - simulatedSavingsConverted)
        return {
            month: r.monthLabel,
            baseline: r.projectedCostConverted,
            afterSimulation: hasSimulation ? afterSimulation : undefined,
            cumulative: r.cumulativeCostConverted,
            cumulativeAfter: hasSimulation
                ? Math.max(0, r.cumulativeCostConverted - (simulatedSavingsConverted * (results.indexOf(r) + 1)))
                : undefined
        }
    })

    const firstCost = results[0]?.projectedCostConverted || 0
    const lastCost = results[results.length - 1]?.projectedCostConverted || 0
    const totalTrend = firstCost > 0 ? ((lastCost - firstCost) / firstCost) * 100 : 0

    // Calculate totals for comparison
    const totalBaseline = summary.totalProjectedCostConverted
    const totalAfterSimulation = hasSimulation
        ? Math.max(0, totalBaseline - (simulatedSavingsConverted * results.length))
        : totalBaseline
    const totalSavings = totalBaseline - totalAfterSimulation

    return (
        <Card className="h-fit">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <BarChart3 className="h-5 w-5 text-primary" />
                            Forecast Results
                            {hasSimulation && (
                                <Badge variant="outline" className="ml-2 border-green-500 text-green-600">
                                    <Sparkles className="h-3 w-3 mr-1" />
                                    Simulation Active
                                </Badge>
                            )}
                        </CardTitle>
                        <CardDescription>
                            {summary.monthCount} month projection • {currency}
                        </CardDescription>
                    </div>
                    <Badge variant="outline" className="text-xs">
                        Rate: 1 USD = {summary.exchangeRate} THB
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="space-y-6">
                {/* Simulation Summary */}
                {hasSimulation && (
                    <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/30">
                        <div className="flex items-center gap-2 mb-2">
                            <Sparkles className="h-4 w-4 text-green-600" />
                            <span className="font-semibold text-green-600">Simulation Impact</span>
                        </div>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <span className="text-muted-foreground">Actions Simulated: </span>
                                <span className="font-medium">{simulatedItems.length}</span>
                            </div>
                            <div>
                                <span className="text-muted-foreground">Monthly Savings: </span>
                                <span className="font-medium text-green-600">
                                    {formatCurrency(simulatedSavingsConverted, currency)}
                                </span>
                            </div>
                            <div>
                                <span className="text-muted-foreground">Current Forecast: </span>
                                <span className="font-medium">{formatCompactCurrency(totalBaseline, currency)}</span>
                            </div>
                            <div>
                                <span className="text-muted-foreground">After Simulation: </span>
                                <span className="font-medium text-green-600">
                                    {formatCompactCurrency(totalAfterSimulation, currency)}
                                </span>
                            </div>
                        </div>
                        <div className="mt-3 pt-3 border-t border-green-500/30">
                            <span className="text-muted-foreground">Total Projected Savings: </span>
                            <span className="font-bold text-green-600 text-lg">
                                {formatCurrency(totalSavings, currency)}
                            </span>
                        </div>
                    </div>
                )}

                <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                    <SummaryStat
                        title="Total Projected Cost"
                        value={formatCompactCurrency(summary.totalProjectedCostConverted, currency)}
                        subtitle={hasSimulation ? "Before simulation" : `${summary.monthCount} months`}
                        icon={DollarSign}
                    />
                    {hasSimulation ? (
                        <SummaryStat
                            title="After Simulation"
                            value={formatCompactCurrency(totalAfterSimulation, currency)}
                            subtitle={`Save ${formatCompactCurrency(totalSavings, currency)}`}
                            icon={Sparkles}
                            highlight
                        />
                    ) : (
                        <SummaryStat
                            title="Avg Monthly Cost"
                            value={formatCompactCurrency(summary.averageMonthlyCostConverted, currency)}
                            subtitle="Per month"
                            icon={Target}
                        />
                    )}
                    <SummaryStat
                        title="Growth Trend"
                        value={`${totalTrend >= 0 ? '+' : ''}${totalTrend.toFixed(1)}%`}
                        subtitle="First to last month"
                        icon={totalTrend >= 0 ? TrendingUp : TrendingDown}
                        trend={{
                            direction: totalTrend > 0 ? 'up' : totalTrend < 0 ? 'down' : 'neutral'
                        }}
                    />
                </div>

                <div>
                    <div className="flex items-center gap-2 mb-3">
                        <h4 className="text-sm font-medium">Cost Projection</h4>
                        {hasSimulation && (
                            <Badge variant="outline" className="text-xs border-green-500 text-green-600">
                                Before vs After
                            </Badge>
                        )}
                    </div>
                    <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                            <XAxis
                                dataKey="month"
                                tick={{ fontSize: 11 }}
                                axisLine={{ stroke: '#e5e7eb' }}
                            />
                            <YAxis
                                tick={{ fontSize: 11 }}
                                axisLine={{ stroke: '#e5e7eb' }}
                                tickFormatter={(value) => formatCompactCurrency(value, currency)}
                            />
                            <Tooltip content={<CustomTooltip currency={currency} />} />
                            <Legend />
                            <Line
                                type="monotone"
                                dataKey="baseline"
                                stroke="hsl(var(--primary))"
                                strokeWidth={2}
                                dot={{ fill: "hsl(var(--primary))", strokeWidth: 0, r: 4 }}
                                name={hasSimulation ? "Baseline (Current)" : "Monthly Cost"}
                            />
                            {hasSimulation && (
                                <Line
                                    type="monotone"
                                    dataKey="afterSimulation"
                                    stroke="hsl(142, 76%, 36%)"
                                    strokeWidth={2}
                                    strokeDasharray="5 5"
                                    dot={{ fill: "hsl(142, 76%, 36%)", strokeWidth: 0, r: 4 }}
                                    name="After Simulation"
                                />
                            )}
                        </LineChart>
                    </ResponsiveContainer>
                </div>

                <div>
                    <h4 className="text-sm font-medium mb-3">Cumulative Cost</h4>
                    <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                            <XAxis
                                dataKey="month"
                                tick={{ fontSize: 11 }}
                                axisLine={{ stroke: '#e5e7eb' }}
                            />
                            <YAxis
                                tick={{ fontSize: 11 }}
                                axisLine={{ stroke: '#e5e7eb' }}
                                tickFormatter={(value) => formatCompactCurrency(value, currency)}
                            />
                            <Tooltip content={<CustomTooltip currency={currency} />} />
                            <Legend />
                            <Bar
                                dataKey="cumulative"
                                fill="hsl(var(--primary))"
                                radius={[4, 4, 0, 0]}
                                name={hasSimulation ? "Baseline" : "Cumulative Total"}
                            />
                            {hasSimulation && (
                                <Bar
                                    dataKey="cumulativeAfter"
                                    fill="hsl(142, 76%, 36%)"
                                    radius={[4, 4, 0, 0]}
                                    name="After Simulation"
                                />
                            )}
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                <div>
                    <h4 className="text-sm font-medium mb-3">Monthly Breakdown</h4>
                    <div className="border rounded-lg overflow-hidden">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Month</TableHead>
                                    <TableHead className="text-right">
                                        {hasSimulation ? 'Baseline' : 'Projected Cost'}
                                    </TableHead>
                                    {hasSimulation && (
                                        <TableHead className="text-right text-green-600">After Simulation</TableHead>
                                    )}
                                    <TableHead className="text-right">Cumulative</TableHead>
                                    <TableHead className="text-right">Change</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {results.map((result, index) => {
                                    const afterSimCost = Math.max(0, result.projectedCostConverted - simulatedSavingsConverted)
                                    return (
                                        <TableRow key={index}>
                                            <TableCell className="font-medium">
                                                {result.monthLabel}
                                            </TableCell>
                                            <TableCell className="text-right">
                                                {formatCurrency(result.projectedCostConverted, currency)}
                                            </TableCell>
                                            {hasSimulation && (
                                                <TableCell className="text-right text-green-600 font-medium">
                                                    {formatCurrency(afterSimCost, currency)}
                                                </TableCell>
                                            )}
                                            <TableCell className="text-right text-muted-foreground">
                                                {formatCurrency(result.cumulativeCostConverted, currency)}
                                            </TableCell>
                                            <TableCell className="text-right">
                                                {index === 0 ? (
                                                    <span className="text-muted-foreground">—</span>
                                                ) : (
                                                    <span className={
                                                        result.growthFromPrevious > 0 ? 'text-amber-500' :
                                                            result.growthFromPrevious < 0 ? 'text-green-500' :
                                                                'text-muted-foreground'
                                                    }>
                                                        {result.growthFromPrevious > 0 ? '+' : ''}
                                                        {result.growthFromPrevious.toFixed(1)}%
                                                    </span>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    )
                                })}
                            </TableBody>
                        </Table>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

export default ForecastResultsCard
