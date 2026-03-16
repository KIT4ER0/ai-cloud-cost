import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import {
    LineChart,
    Line,
    PieChart,
    Pie,
    Cell,
    ResponsiveContainer,
    XAxis,
    YAxis,
    Tooltip,
    Legend,
} from "recharts"
import { TrendingUp, TrendingDown, DollarSign, Zap, Target, Calendar, Loader2, CloudOff } from "lucide-react"
import { api } from "@/lib/api"

// Types
type TimeRange = "this_month" | "last_month" | "last_6_months" | "this_year"
type ViewMode = "cost" | "change"

interface CostTrendItem {
    date: string
    cost: number
    projected: boolean
}

interface ServiceCostDistribution {
    name: string
    value: number
    color: string
}

interface ResourceCostItem {
    resource_id: string
    resource_name: string
    cost: number
    prevCost: number
    change: number
    changePercent: number
}

interface CostDriverItem {
    driver: string
    usage: string
    cost: number
    prevCost: number
    change: number
    changePercent: number
}

interface KPIItem {
    totalCost: number
    prevTotalCost: number
    topService: { name: string; cost: number }
    avgDailyCost: number
    projectedMonthEnd: number
}

interface CostAnalysisData {
    summary: KPIItem
    trend: CostTrendItem[]
    distribution: ServiceCostDistribution[]
    drivers: Record<string, CostDriverItem[]>
    resources: Record<string, ResourceCostItem[]>
}

// Time range presets
const timeRangePresets = [
    { value: "this_month", label: "This Month" },
    { value: "last_month", label: "Last Month" },
    { value: "last_6_months", label: "Last 6 Months" },
    { value: "this_year", label: "This Year" },
]

// Custom tooltip for pie chart
const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ name: string; value: number }> }) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-background border rounded-lg shadow-lg p-3">
                <p className="font-medium">{payload[0].name}</p>
                <p className="text-muted-foreground">${payload[0].value.toLocaleString()} USD</p>
            </div>
        )
    }
    return null
}

// KPI Card component
function KPICard({
    title,
    value,
    subtitle,
    icon: Icon,
    trend
}: {
    title: string
    value: string
    subtitle?: string
    icon: React.ElementType
    trend?: { direction: "up" | "down"; value: string }
}) {
    return (
        <Card>
            <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                    <div>
                        <p className="text-sm font-medium text-muted-foreground">{title}</p>
                        <p className="text-2xl font-bold">{value}</p>
                        {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
                        {trend && (
                            <div className={`flex items-center gap-1 mt-1 text-sm ${trend.direction === "up" ? "text-red-500" : "text-green-500"
                                }`}>
                                {trend.direction === "up" ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
                                <span>{trend.value}</span>
                            </div>
                        )}
                    </div>
                    <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                        <Icon className="h-6 w-6 text-primary" />
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

export default function CostAnalysis() {
    const [timeRange, setTimeRange] = useState<TimeRange>("this_month")
    const [viewMode, setViewMode] = useState<ViewMode>("cost")
    const [displayTab, setDisplayTab] = useState<"drivers" | "resources">("drivers")
    const [data, setData] = useState<CostAnalysisData | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true)
            try {
                const result = await api.costs.getAnalysis(timeRange)
                setData(result)
            } catch (error) {
                console.error("Failed to fetch cost analysis:", error)
            } finally {
                setLoading(false)
            }
        }
        fetchData()
    }, [timeRange])

    if (loading || !data) {
        return (
            <div className="flex h-[80vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">Loading cost analysis...</span>
            </div>
        )
    }

    const { summary, trend, distribution, drivers } = data
    const granularity = timeRange === "this_year" || timeRange === "last_6_months" ? "Monthly" : "Daily"

    // Calculate delta percentage
    const deltaPercent = summary.prevTotalCost > 0
        ? ((summary.totalCost - summary.prevTotalCost) / summary.prevTotalCost) * 100
        : 0
    const deltaDirection = deltaPercent >= 0 ? "up" : "down"

    // Last updated timestamp
    const lastUpdated = new Date().toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    })

    // Check for empty data
    const isDataEmpty = summary.totalCost === 0 && distribution.length === 0

    return (
        <div className="space-y-6">
            {/* Header with Title and Global Controls */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight text-primary">Cost Analysis</h2>
                    <p className="text-muted-foreground">Detailed breakdown of your cloud infrastructure costs.</p>
                </div>
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                    <div className="text-xs text-muted-foreground">
                        Last Updated: {lastUpdated}
                    </div>
                    <Select value={timeRange} onValueChange={(v) => setTimeRange(v as TimeRange)}>
                        <SelectTrigger className="w-[160px]">
                            <Calendar className="h-4 w-4 mr-2" />
                            <SelectValue placeholder="Time Range" />
                        </SelectTrigger>
                        <SelectContent>
                            {timeRangePresets.map((preset) => (
                                <SelectItem key={preset.value} value={preset.value}>
                                    {preset.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {isDataEmpty ? (
                <Card className="h-[60vh] flex flex-col items-center justify-center text-center p-8">
                    <div className="bg-muted p-4 rounded-full mb-4">
                        <CloudOff className="h-10 w-10 text-muted-foreground" />
                    </div>
                    <h3 className="text-lg font-semibold">No Cost Data Available</h3>
                    <p className="text-muted-foreground max-w-sm mt-2">
                        There is no cost data for the selected time range.
                        Connect your AWS accounts or wait for data ingestion.
                    </p>
                </Card>
            ) : (
                <>
                    {/* Granularity Indicator */}
                    <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                            Viewing: {granularity} Data
                        </Badge>
                        <Badge variant="secondary" className="text-xs">
                            Currency: USD
                        </Badge>
                    </div>

                    {/* KPI Summary Cards */}
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                        <KPICard
                            title="Total Cost"
                            value={`$${summary.totalCost.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                            subtitle="USD"
                            icon={DollarSign}
                            trend={{
                                direction: deltaDirection,
                                value: `${deltaPercent >= 0 ? "+" : ""}${deltaPercent.toFixed(1)}% vs prev`
                            }}
                        />
                        <KPICard
                            title="Change vs Previous"
                            value={`${deltaPercent >= 0 ? "+" : ""}${deltaPercent.toFixed(1)}%`}
                            subtitle={`$${Math.abs(summary.totalCost - summary.prevTotalCost).toLocaleString(undefined, { maximumFractionDigits: 0 })} ${deltaDirection === "up" ? "increase" : "decrease"}`}
                            icon={deltaDirection === "up" ? TrendingUp : TrendingDown}
                        />
                        <KPICard
                            title="Top Service"
                            value={summary.topService.name}
                            subtitle={`$${summary.topService.cost.toLocaleString(undefined, { maximumFractionDigits: 0 })} USD`}
                            icon={Zap}
                        />
                        <KPICard
                            title={timeRange === "this_month" ? "Projected Month-End" : "Avg Daily Cost"}
                            value={timeRange === "this_month"
                                ? `$${summary.projectedMonthEnd.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                                : `$${summary.avgDailyCost.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                            }
                            subtitle={timeRange === "this_month" ? "Estimated" : "Per day"}
                            icon={Target}
                        />
                    </div>

                    {/* Section 1: Total Cost Trend */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Total Cost Trend ({granularity})</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <ResponsiveContainer width="100%" height={300}>
                                <LineChart data={trend}>
                                    <XAxis
                                        dataKey="date"
                                        tick={{ fontSize: 10 }}
                                        axisLine={{ stroke: '#e5e7eb' }}
                                        tickFormatter={(val) => {
                                            const d = new Date(val);
                                            return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
                                        }}
                                    />
                                    <YAxis
                                        tick={{ fontSize: 12 }}
                                        axisLine={{ stroke: '#e5e7eb' }}
                                        tickFormatter={(value) => `$${value}`}
                                    />
                                    <Tooltip
                                        formatter={(value) => [`$${Number(value).toLocaleString()} USD`, "Cost"]}
                                        labelFormatter={(label) => new Date(label).toLocaleDateString()}
                                    />
                                    <Legend />
                                    <Line
                                        type="monotone"
                                        dataKey="cost"
                                        stroke="hsl(var(--primary))"
                                        strokeWidth={2}
                                        dot={{ fill: "hsl(var(--primary))", strokeWidth: 0, r: 4 }}
                                        name="Total Cost"
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>

                    {/* Section 2: Service Highlights (Side-by-Side Layout) */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Left Column: Distribution Pie Chart */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Service Cost Distribution</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {distribution.length > 0 ? (
                                    <>
                                        <ResponsiveContainer width="100%" height={280}>
                                            <PieChart>
                                                <Pie
                                                    data={distribution}
                                                    cx="50%"
                                                    cy="50%"
                                                    innerRadius={50}
                                                    outerRadius={90}
                                                    paddingAngle={2}
                                                    minAngle={5}
                                                    dataKey="value"
                                                    label={({ percent }) => `${((percent ?? 0) * 100).toFixed(0)}%`}
                                                    labelLine={true}
                                                >
                                                    {distribution.map((entry, index) => (
                                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                                    ))}
                                                </Pie>
                                                <Tooltip content={<CustomTooltip />} />
                                            </PieChart>
                                        </ResponsiveContainer>
                                        <div className="flex justify-center gap-4 mt-4 flex-wrap">
                                            {distribution.map((item) => (
                                                <div key={item.name} className="flex items-center gap-1.5 text-sm">
                                                    <div
                                                        className="w-3 h-3 rounded-full"
                                                        style={{ backgroundColor: item.color }}
                                                    />
                                                    <span className="text-muted-foreground">{item.name}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </>
                                ) : (
                                    <div className="h-[280px] flex items-center justify-center text-muted-foreground">
                                        No cost distribution data available
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Right Column: Top 3 Leaders Podium */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Top 3 Most Expensive Services</CardTitle>
                                <p className="text-sm text-muted-foreground">Ranked by total cost</p>
                            </CardHeader>
                            <CardContent>
                                {(() => {
                                    const sortedServices = [...distribution].sort((a, b) => b.value - a.value).slice(0, 3);
                                    if (sortedServices.length === 0) {
                                        return <div className="h-[280px] flex items-center justify-center text-muted-foreground">No data available</div>
                                    }
                                    const [first, second, third] = sortedServices;

                                    return (
                                        <div className="flex items-end justify-center gap-4 h-[280px] pt-8">
                                            {/* 2nd Place - Left */}
                                            {second && (
                                                <div className="flex flex-col items-center">
                                                    <div className="text-center mb-2">
                                                        <p className="font-semibold text-lg">{second.name}</p>
                                                        <p className="text-muted-foreground text-sm">${second.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
                                                    </div>
                                                    <div
                                                        className="w-24 rounded-t-lg flex items-center justify-center text-white font-bold text-2xl"
                                                        style={{
                                                            backgroundColor: second.color,
                                                            height: '120px'
                                                        }}
                                                    >
                                                        2
                                                    </div>
                                                </div>
                                            )}

                                            {/* 1st Place - Center (Tallest) */}
                                            {first && (
                                                <div className="flex flex-col items-center">
                                                    <div className="text-center mb-2">
                                                        <p className="font-bold text-xl">{first.name}</p>
                                                        <p className="text-primary font-semibold">${first.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
                                                    </div>
                                                    <div
                                                        className="w-28 rounded-t-lg flex items-center justify-center text-white font-bold text-3xl"
                                                        style={{
                                                            backgroundColor: first.color,
                                                            height: '160px'
                                                        }}
                                                    >
                                                        1
                                                    </div>
                                                </div>
                                            )}

                                            {/* 3rd Place - Right */}
                                            {third && (
                                                <div className="flex flex-col items-center">
                                                    <div className="text-center mb-2">
                                                        <p className="font-semibold text-lg">{third.name}</p>
                                                        <p className="text-muted-foreground text-sm">${third.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
                                                    </div>
                                                    <div
                                                        className="w-24 rounded-t-lg flex items-center justify-center text-white font-bold text-2xl"
                                                        style={{
                                                            backgroundColor: third.color,
                                                            height: '90px'
                                                        }}
                                                    >
                                                        3
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })()}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Section 3: Enhanced Cost Drivers / Resources */}
                    <Card>
                        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                            <div className="space-y-1">
                                <CardTitle>{displayTab === "drivers" ? "Cost Drivers" : "Resources Cost"}</CardTitle>
                                <p className="text-sm text-muted-foreground">
                                    {displayTab === "drivers" 
                                        ? "Breakdown by usage type • Sorted by highest change" 
                                        : "Breakdown by individual resource • Sorted by cost"}
                                </p>
                            </div>
                            <div className="flex flex-wrap items-center gap-3">
                                {/* Tab Switcher */}
                                <div className="flex gap-1 bg-muted p-1 rounded-lg">
                                    <Button
                                        variant={displayTab === "drivers" ? "default" : "ghost"}
                                        size="sm"
                                        onClick={() => setDisplayTab("drivers")}
                                    >
                                        Drivers
                                    </Button>
                                    <Button
                                        variant={displayTab === "resources" ? "default" : "ghost"}
                                        size="sm"
                                        onClick={() => setDisplayTab("resources")}
                                    >
                                        Resources
                                    </Button>
                                </div>
                                
                                <div className="h-8 w-[1px] bg-border hidden sm:block" />

                                <div className="flex gap-1 bg-muted p-1 rounded-lg">
                                    {(["cost", "change"] as ViewMode[]).map((mode) => (
                                        <Button
                                            key={mode}
                                            variant={viewMode === mode ? "default" : "ghost"}
                                            size="sm"
                                            onClick={() => setViewMode(mode)}
                                            className="capitalize"
                                        >
                                            {mode}
                                        </Button>
                                    ))}
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-8">
                            {displayTab === "drivers" ? (
                                // Original Drivers View
                                Object.entries(drivers).length > 0 ? Object.entries(drivers).map(([service, serviceDrivers]) => (
                                <div key={service} className="space-y-2">
                                    <div className="flex items-center gap-2">
                                        <div
                                            className="w-3 h-3 rounded-full"
                                            style={{
                                                backgroundColor: distribution.find(s => s.name === service)?.color || "#6b7280"
                                            }}
                                        />
                                        <h4 className="font-semibold text-lg">{service}</h4>
                                    </div>
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead className="w-[35%]">Cost Driver</TableHead>
                                                <TableHead className={`text-right ${viewMode === "cost" ? "bg-primary/5" : ""}`}>Cost</TableHead>
                                                <TableHead className={`text-right ${viewMode === "change" ? "bg-primary/5" : ""}`}>Change vs Prev</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {serviceDrivers.map((driver, index) => (
                                                <TableRow key={index}>
                                                    <TableCell className="font-medium">{driver.driver}</TableCell>
                                                    <TableCell className={`text-right ${viewMode === "cost" ? "bg-primary/5 font-medium" : ""}`}>
                                                        ${driver.cost.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                                                    </TableCell>
                                                    <TableCell className={`text-right ${viewMode === "change" ? "bg-primary/5" : ""}`}>
                                                        <div className={`flex items-center justify-end gap-1 ${driver.change > 0 ? "text-red-500" : driver.change < 0 ? "text-green-500" : "text-muted-foreground"
                                                            }`}>
                                                            {driver.change > 0 && <TrendingUp className="h-3 w-3" />}
                                                            {driver.change < 0 && <TrendingDown className="h-3 w-3" />}
                                                            <span className="font-medium">
                                                                {driver.change > 0 ? "+" : ""}{driver.change !== 0 ? `$${Math.abs(driver.change).toLocaleString(undefined, { maximumFractionDigits: 2 })}` : "-"}
                                                            </span>
                                                            {driver.change !== 0 && (
                                                                <span className="text-xs">
                                                                    ({driver.changePercent > 0 ? "+" : ""}{driver.changePercent.toFixed(1)}%)
                                                                </span>
                                                            )}
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </div>
                                )) : (
                                    <div className="text-center py-12 text-muted-foreground">No cost drivers found for this period</div>
                                )
                            ) : (
                                // New Resources View
                                Object.entries(data.resources).length > 0 ? Object.entries(data.resources).map(([service, resources]) => (
                                    <div key={service} className="space-y-3">
                                        <div className="flex items-center gap-2">
                                            <div
                                                className="w-3 h-3 rounded-full"
                                                style={{
                                                    backgroundColor: distribution.find(s => s.name === service)?.color || "#6b7280"
                                                }}
                                            />
                                            <h4 className="font-semibold text-lg">{service} Resources</h4>
                                        </div>
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead className="w-[45%]">Resource ID</TableHead>
                                                    <TableHead className={`text-right ${viewMode === "cost" ? "bg-primary/5" : ""}`}>Cost</TableHead>
                                                    <TableHead className={`text-right ${viewMode === "change" ? "bg-primary/5" : ""}`}>Change vs Prev</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {resources.map((res, index) => (
                                                    <TableRow key={index} className="hover:bg-muted/50 transition-colors">
                                                        <TableCell className="font-medium font-mono text-xs max-w-[200px] truncate" title={res.resource_id}>
                                                            {res.resource_id}
                                                        </TableCell>
                                                        <TableCell className={`text-right ${viewMode === "cost" ? "bg-primary/5 font-medium" : ""}`}>
                                                            ${res.cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                                        </TableCell>
                                                        <TableCell className={`text-right ${viewMode === "change" ? "bg-primary/5" : ""}`}>
                                                            <div className={`flex items-center justify-end gap-1 ${res.change > 0 ? "text-red-500" : res.change < 0 ? "text-green-500" : "text-muted-foreground"
                                                                }`}>
                                                                {res.change > 0 && <TrendingUp className="h-3 w-3" />}
                                                                {res.change < 0 && <TrendingDown className="h-3 w-3" />}
                                                                <span className="font-medium text-xs">
                                                                    {res.change > 0 ? "+" : ""}{res.change !== 0 ? `$${Math.abs(res.change).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "-"}
                                                                </span>
                                                                {res.change !== 0 && (
                                                                    <span className="text-[10px] opacity-70">
                                                                        ({res.changePercent > 0 ? "+" : ""}{res.changePercent.toFixed(1)}%)
                                                                    </span>
                                                                )}
                                                            </div>
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </div>
                                )) : (
                                    <div className="text-center py-12 text-muted-foreground">No resource-level cost data found</div>
                                )
                            )}
                        </CardContent>
                    </Card>
                </>
            )}
        </div>
    )
}
