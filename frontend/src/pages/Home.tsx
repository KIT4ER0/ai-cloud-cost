import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts"
import { DollarSign, Server, TrendingUp, TrendingDown, ArrowRight } from 'lucide-react'
import { RECOMMENDATIONS } from '@/types/recommendation'
import { getDashboardSummary } from '@/lib/dashboard-data'

export default function Home() {
    // Get real-time data from shared data module
    const dashboard = getDashboardSummary()

    // Take top 3 recommendations for the summary
    const topRecommendations = RECOMMENDATIONS.slice(0, 3)

    // Format currency
    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(value)
    }

    return (
        <div className="min-h-screen bg-gray-50/50 -m-8 p-8">
            <div className="space-y-8">
                {/* Header */}
                <div>
                    <h2 className="text-3xl font-bold tracking-tight text-primary">Dashboard</h2>
                    <p className="text-muted-foreground">Overview of your cloud spend and health.</p>
                </div>

                {/* Top Row: 3 Summary Cards */}
                <div className="grid gap-4 grid-cols-1 md:grid-cols-3">
                    {/* Card 1: Total Cost */}
                    <Card className="bg-white shadow-md hover:shadow-lg transition-shadow">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">Total Cost</CardTitle>
                            <DollarSign className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{formatCurrency(dashboard.totalCost)}</div>
                            <div className="flex items-center gap-1 mt-1">
                                {dashboard.costChangeDirection === 'up' ? (
                                    <TrendingUp className="h-4 w-4 text-red-500" />
                                ) : (
                                    <TrendingDown className="h-4 w-4 text-green-500" />
                                )}
                                <span className={`text-sm font-medium ${dashboard.costChangeDirection === 'up' ? 'text-red-500' : 'text-green-500'}`}>
                                    {dashboard.costChangeDirection === 'up' ? '+' : '-'}{dashboard.costChange.toFixed(1)}%
                                </span>
                                <span className="text-xs text-muted-foreground">from last month</span>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Card 2: Active Instances */}
                    <Card className="bg-white shadow-md hover:shadow-lg transition-shadow">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">Active Instances</CardTitle>
                            <Server className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{dashboard.activeInstances}</div>
                            <div className="flex items-center gap-1 mt-1">
                                <TrendingUp className="h-4 w-4 text-blue-500" />
                                <span className="text-sm text-blue-500 font-medium">+{dashboard.instanceChange}</span>
                                <span className="text-xs text-muted-foreground">new instances</span>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Card 3: Forecast Cost */}
                    <Card className="bg-white shadow-md hover:shadow-lg transition-shadow">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">Forecast Cost</CardTitle>
                            <TrendingUp className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{formatCurrency(dashboard.forecastCost)}</div>
                            <p className="text-xs text-muted-foreground mt-1">Predicted end of month</p>
                        </CardContent>
                    </Card>
                </div>

                {/* Second Row: Two Column Layout (70/30) */}
                <div className="grid gap-4 grid-cols-1 lg:grid-cols-10">
                    {/* Left Column: Overview Cost (70%) */}
                    <Card className="lg:col-span-7 bg-white shadow-md">
                        <CardHeader>
                            <CardTitle>Cost Overview</CardTitle>
                        </CardHeader>
                        <CardContent className="pl-2">
                            <ResponsiveContainer width="100%" height={350}>
                                <BarChart data={dashboard.costTrend}>
                                    <XAxis
                                        dataKey="period"
                                        stroke="#888888"
                                        fontSize={12}
                                        tickLine={false}
                                        axisLine={false}
                                    />
                                    <YAxis
                                        stroke="#888888"
                                        fontSize={12}
                                        tickLine={false}
                                        axisLine={false}
                                        tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                                    />
                                    <Tooltip
                                        contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
                                        labelStyle={{ color: '#000' }}
                                        formatter={(value) => [`${formatCurrency(Number(value))}`, 'Cost']}
                                    />
                                    <Bar dataKey="cost" fill="currentColor" radius={[4, 4, 0, 0]} className="fill-primary" />
                                </BarChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>

                    {/* Right Column: Recommendations Summary (30%) */}
                    <Card className="lg:col-span-3 bg-white shadow-md">
                        <CardHeader className="pb-3">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-lg">Recommendations</CardTitle>
                                <Link
                                    to="/recommend"
                                    className="text-sm text-primary hover:underline flex items-center gap-1"
                                >
                                    View all
                                    <ArrowRight className="h-3 w-3" />
                                </Link>
                            </div>
                            <p className="text-sm text-muted-foreground">
                                Potential savings: <span className="font-semibold text-green-600">${dashboard.totalPotentialSavings}/mo</span>
                            </p>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {topRecommendations.map((rec) => (
                                <div
                                    key={rec.id}
                                    className="flex items-start justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                                >
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="font-medium text-sm truncate">{rec.title}</span>
                                            <Badge
                                                variant={rec.severity === 'High' ? 'destructive' : 'secondary'}
                                                className="text-xs"
                                            >
                                                {rec.severity}
                                            </Badge>
                                        </div>
                                        <div className="flex items-center gap-1 text-green-600 text-sm">
                                            <TrendingDown className="h-3 w-3" />
                                            <span className="font-medium">${rec.savingsPerMonth}/mo</span>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    )
}
