import { useState, useMemo } from "react"
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
import { TrendingUp, TrendingDown, DollarSign, Zap, Target, Calendar } from "lucide-react"

// Types
type TimeRange = "this_month" | "last_month" | "last_6_months" | "this_year"
type ViewMode = "cost" | "change" | "usage"

interface ServiceDistribution {
    name: string
    value: number
    color: string
}

interface CostDriver {
    driver: string
    usage: string
    cost: number
    prevCost: number
    change: number
    changePercent: number
}

// Mock data for different time ranges
const trendDataByRange: Record<TimeRange, { period: string; cost: number }[]> = {
    this_month: [
        { period: "Week 1", cost: 12500 },
        { period: "Week 2", cost: 14200 },
        { period: "Week 3", cost: 11800 },
        { period: "Week 4", cost: 15600 },
    ],
    last_month: [
        { period: "Week 1", cost: 11200 },
        { period: "Week 2", cost: 13100 },
        { period: "Week 3", cost: 12400 },
        { period: "Week 4", cost: 14100 },
    ],
    this_year: [
        { period: "Jan", cost: 45000 },
        { period: "Feb", cost: 52000 },
        { period: "Mar", cost: 48500 },
        { period: "Apr", cost: 55200 },
        { period: "May", cost: 51000 },
        { period: "Jun", cost: 58000 },
        { period: "Jul", cost: 54200 },
        { period: "Aug", cost: 49800 },
        { period: "Sep", cost: 53500 },
        { period: "Oct", cost: 57200 },
        { period: "Nov", cost: 52800 },
        { period: "Dec", cost: 50000 },
    ],
    last_6_months: [
        { period: "Aug", cost: 49800 },
        { period: "Sep", cost: 53500 },
        { period: "Oct", cost: 57200 },
        { period: "Nov", cost: 52800 },
        { period: "Dec", cost: 50000 },
        { period: "Jan", cost: 54100 },
    ],
}

// Service distribution data
const serviceDistributionData: ServiceDistribution[] = [
    { name: "EC2", value: 18000, color: "#8b5cf6" },
    { name: "RDS", value: 12800, color: "#06b6d4" },
    { name: "S3", value: 7200, color: "#10b981" },
    { name: "Lambda", value: 8400, color: "#f59e0b" },
    { name: "Other", value: 3600, color: "#6b7280" },
]

// KPI data by time range
const kpiDataByRange: Record<TimeRange, {
    totalCost: number
    prevTotalCost: number
    topService: { name: string; cost: number }
    avgDailyCost: number
    projectedMonthEnd: number
}> = {
    this_month: {
        totalCost: 54100,
        prevTotalCost: 50800,
        topService: { name: "EC2", cost: 18000 },
        avgDailyCost: 1803,
        projectedMonthEnd: 55890,
    },
    last_month: {
        totalCost: 50800,
        prevTotalCost: 48200,
        topService: { name: "EC2", cost: 16500 },
        avgDailyCost: 1639,
        projectedMonthEnd: 0,
    },
    this_year: {
        totalCost: 627200,
        prevTotalCost: 582000,
        topService: { name: "EC2", cost: 216000 },
        avgDailyCost: 1718,
        projectedMonthEnd: 0,
    },
    last_6_months: {
        totalCost: 317400,
        prevTotalCost: 295800,
        topService: { name: "EC2", cost: 108000 },
        avgDailyCost: 1747,
        projectedMonthEnd: 0,
    },
}

// Cost drivers data with change tracking
const costDriversData: Record<string, CostDriver[]> = {
    EC2: [
        { driver: "On-Demand Instances (m5.xlarge)", usage: "2,160 hours", cost: 1850, prevCost: 1650, change: 200, changePercent: 12.1 },
        { driver: "On-Demand Instances (t3.medium)", usage: "4,320 hours", cost: 720, prevCost: 680, change: 40, changePercent: 5.9 },
        { driver: "EBS Storage (gp3)", usage: "2,000 GB", cost: 640, prevCost: 580, change: 60, changePercent: 10.3 },
        { driver: "Data Transfer Out", usage: "500 GB", cost: 450, prevCost: 520, change: -70, changePercent: -13.5 },
        { driver: "Elastic IP Addresses", usage: "5 IPs", cost: 18, prevCost: 18, change: 0, changePercent: 0 },
    ],
    RDS: [
        { driver: "db.r5.large Instance", usage: "720 hours", cost: 1512, prevCost: 1320, change: 192, changePercent: 14.5 },
        { driver: "db.t3.medium Instance", usage: "720 hours", cost: 432, prevCost: 432, change: 0, changePercent: 0 },
        { driver: "Storage (gp2)", usage: "500 GB", cost: 115, prevCost: 100, change: 15, changePercent: 15.0 },
        { driver: "Backup Storage", usage: "200 GB", cost: 46, prevCost: 42, change: 4, changePercent: 9.5 },
        { driver: "I/O Requests", usage: "10M requests", cost: 95, prevCost: 85, change: 10, changePercent: 11.8 },
    ],
    S3: [
        { driver: "Standard Storage", usage: "5,000 GB", cost: 115, prevCost: 105, change: 10, changePercent: 9.5 },
        { driver: "Glacier Storage", usage: "10,000 GB", cost: 40, prevCost: 38, change: 2, changePercent: 5.3 },
        { driver: "PUT/COPY/POST Requests", usage: "5M requests", cost: 25, prevCost: 22, change: 3, changePercent: 13.6 },
        { driver: "GET Requests", usage: "50M requests", cost: 20, prevCost: 18, change: 2, changePercent: 11.1 },
        { driver: "Data Transfer", usage: "200 GB", cost: 18, prevCost: 20, change: -2, changePercent: -10.0 },
    ],
    Lambda: [
        { driver: "Compute (128MB)", usage: "50M invocations", cost: 520, prevCost: 450, change: 70, changePercent: 15.6 },
        { driver: "Compute (512MB)", usage: "20M invocations", cost: 832, prevCost: 780, change: 52, changePercent: 6.7 },
        { driver: "Compute (1024MB)", usage: "5M invocations", cost: 416, prevCost: 390, change: 26, changePercent: 6.7 },
        { driver: "Duration", usage: "2.5M GB-seconds", cost: 42, prevCost: 38, change: 4, changePercent: 10.5 },
        { driver: "Provisioned Concurrency", usage: "100 units", cost: 290, prevCost: 290, change: 0, changePercent: 0 },
    ],
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

    // Derived state
    const trendData = trendDataByRange[timeRange]
    const kpiData = kpiDataByRange[timeRange]
    const distributionData = serviceDistributionData
    const granularity = timeRange === "this_year" || timeRange === "last_6_months" ? "Monthly" : "Weekly"

    // Calculate delta percentage
    const deltaPercent = ((kpiData.totalCost - kpiData.prevTotalCost) / kpiData.prevTotalCost) * 100
    const deltaDirection = deltaPercent >= 0 ? "up" : "down"

    // Get sorted cost drivers (by change descending)
    const sortedCostDrivers = useMemo(() => {
        const result: Record<string, CostDriver[]> = {}
        for (const [service, drivers] of Object.entries(costDriversData)) {
            result[service] = [...drivers].sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
        }
        return result
    }, [])

    // Last updated timestamp
    const lastUpdated = new Date().toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
    })

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
                    value={`$${kpiData.totalCost.toLocaleString()}`}
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
                    subtitle={`$${Math.abs(kpiData.totalCost - kpiData.prevTotalCost).toLocaleString()} ${deltaDirection === "up" ? "increase" : "decrease"}`}
                    icon={deltaDirection === "up" ? TrendingUp : TrendingDown}
                />
                <KPICard
                    title="Top Service"
                    value={kpiData.topService.name}
                    subtitle={`$${kpiData.topService.cost.toLocaleString()} USD`}
                    icon={Zap}
                />
                <KPICard
                    title={timeRange === "this_month" ? "Projected Month-End" : "Avg Daily Cost"}
                    value={timeRange === "this_month"
                        ? `$${kpiData.projectedMonthEnd.toLocaleString()}`
                        : `$${kpiData.avgDailyCost.toLocaleString()}`
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
                        <LineChart data={trendData}>
                            <XAxis
                                dataKey="period"
                                tick={{ fontSize: 12 }}
                                axisLine={{ stroke: '#e5e7eb' }}
                            />
                            <YAxis
                                tick={{ fontSize: 12 }}
                                axisLine={{ stroke: '#e5e7eb' }}
                                tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                            />
                            <Tooltip
                                formatter={(value) => [`$${Number(value).toLocaleString()} USD`, "Cost"]}
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
                        <ResponsiveContainer width="100%" height={280}>
                            <PieChart>
                                <Pie
                                    data={distributionData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={50}
                                    outerRadius={90}
                                    paddingAngle={2}
                                    dataKey="value"
                                    label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                                    labelLine={true}
                                >
                                    {distributionData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Pie>
                                <Tooltip content={<CustomTooltip />} />
                            </PieChart>
                        </ResponsiveContainer>
                        <div className="flex justify-center gap-4 mt-4 flex-wrap">
                            {distributionData.map((item) => (
                                <div key={item.name} className="flex items-center gap-1.5 text-sm">
                                    <div
                                        className="w-3 h-3 rounded-full"
                                        style={{ backgroundColor: item.color }}
                                    />
                                    <span className="text-muted-foreground">{item.name}</span>
                                </div>
                            ))}
                        </div>
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
                            const sortedServices = [...distributionData].sort((a, b) => b.value - a.value).slice(0, 3);
                            const [first, second, third] = sortedServices;

                            return (
                                <div className="flex items-end justify-center gap-4 h-[280px] pt-8">
                                    {/* 2nd Place - Left */}
                                    {second && (
                                        <div className="flex flex-col items-center">
                                            <div className="text-center mb-2">
                                                <p className="font-semibold text-lg">{second.name}</p>
                                                <p className="text-muted-foreground text-sm">${second.value.toLocaleString()}</p>
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
                                                <span className="text-2xl">🌟</span>
                                                <p className="font-bold text-xl">{first.name}</p>
                                                <p className="text-primary font-semibold">${first.value.toLocaleString()}</p>
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
                                                <p className="text-muted-foreground text-sm">${third.value.toLocaleString()}</p>
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

            {/* Section 3: Enhanced Cost Drivers */}
            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                        <CardTitle>Cost Drivers</CardTitle>
                        <p className="text-sm text-muted-foreground">
                            Breakdown by service • Sorted by highest change
                        </p>
                    </div>
                    <div className="flex gap-1 bg-muted p-1 rounded-lg">
                        {(["usage", "cost", "change"] as ViewMode[]).map((mode) => (
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
                </CardHeader>
                <CardContent className="space-y-6">
                    {Object.entries(sortedCostDrivers).map(([service, drivers]) => (
                        <div key={service} className="space-y-2">
                            <div className="flex items-center gap-2">
                                <div
                                    className="w-3 h-3 rounded-full"
                                    style={{
                                        backgroundColor: serviceDistributionData.find(s => s.name === service)?.color || "#6b7280"
                                    }}
                                />
                                <h4 className="font-semibold text-lg">{service}</h4>
                            </div>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="w-[35%]">Cost Driver</TableHead>
                                        <TableHead className={viewMode === "usage" ? "bg-primary/5" : ""}>Usage</TableHead>
                                        <TableHead className={`text-right ${viewMode === "cost" ? "bg-primary/5" : ""}`}>Cost</TableHead>
                                        <TableHead className={`text-right ${viewMode === "change" ? "bg-primary/5" : ""}`}>Change vs Prev</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {drivers.map((driver, index) => (
                                        <TableRow key={index}>
                                            <TableCell className="font-medium">{driver.driver}</TableCell>
                                            <TableCell className={viewMode === "usage" ? "bg-primary/5 font-medium" : ""}>
                                                {driver.usage}
                                            </TableCell>
                                            <TableCell className={`text-right ${viewMode === "cost" ? "bg-primary/5 font-medium" : ""}`}>
                                                ${driver.cost.toLocaleString()}
                                            </TableCell>
                                            <TableCell className={`text-right ${viewMode === "change" ? "bg-primary/5" : ""}`}>
                                                <div className={`flex items-center justify-end gap-1 ${driver.change > 0 ? "text-red-500" : driver.change < 0 ? "text-green-500" : "text-muted-foreground"
                                                    }`}>
                                                    {driver.change > 0 && <TrendingUp className="h-3 w-3" />}
                                                    {driver.change < 0 && <TrendingDown className="h-3 w-3" />}
                                                    <span className="font-medium">
                                                        {driver.change > 0 ? "+" : ""}{driver.change !== 0 ? `$${Math.abs(driver.change)}` : "-"}
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
                    ))}
                </CardContent>
            </Card>
        </div>
    )
}
