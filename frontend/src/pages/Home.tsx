import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts"
import { DollarSign, TrendingUp, TrendingDown, ArrowRight, RefreshCw, Cpu, Loader2, AlertTriangle } from 'lucide-react'
import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { Button } from "@/components/ui/button"

export default function Home() {
    const [isSyncing, setIsSyncing] = useState(false);
    const [resourceSummary, setResourceSummary] = useState({ total_resources: 0, new_resources_this_month: 0 });
    const [costAnalysis, setCostAnalysis] = useState<any>(null);
    const [monthlyTrend, setMonthlyTrend] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [recommendations, setRecommendations] = useState<any[]>([]);

    useEffect(() => {
        const fetchData = async () => {
            setIsLoading(true);
            try {
                const [summaryData, costData, trendData, recData] = await Promise.all([
                    api.monitoring.getSummary(),
                    api.costs.getAnalysis("this_month"),
                    api.costs.getAnalysis("last_6_months"),
                    api.recommendations.list()
                ]);
                setResourceSummary(summaryData);
                setCostAnalysis(costData);
                setRecommendations(recData ?? []);
                
                // Process monthly trend data
                const processedTrend = trendData?.trend?.map((item: any) => ({
                    period: new Date(item.date).toLocaleDateString('en-US', { month: 'short' }),
                    cost: item.cost,
                    fullDate: item.date
                })) ?? [];
                setMonthlyTrend(processedTrend);
            } catch (error) {
                console.error("Failed to fetch dashboard data:", error);
            } finally {
                setIsLoading(false);
            }
        };
        fetchData();
    }, []);

    const handleSync = async () => {
        setIsSyncing(true);
        try {
            await Promise.all([
                api.sync.costs(),
                api.sync.metrics()
            ]);
            alert('Data sync has started in the background! Please check back in a few minutes after AWS finishes processing.');
        } catch (error: any) {
            alert(error.message || 'Failed to sync data');
        } finally {
            setIsSyncing(false);
        }
    };

    // Map label for rec_type
    const REC_LABELS: Record<string, { title: string; severity: 'High' | 'Medium' | 'Low' }> = {
        EC2_RIGHTSIZE_CPU_LOW: { title: 'Resize EC2 Instance', severity: 'High' },
        EC2_IDLE_STOPPED: { title: 'Terminate Idle EC2', severity: 'High' },
        EC2_EIP_UNASSOCIATED: { title: 'Release Unused Elastic IP', severity: 'Medium' },
        EC2_EBS_UNATTACHED: { title: 'Delete Unattached EBS Volume', severity: 'Medium' },
        EC2_EBS_SNAPSHOT_OLD: { title: 'Delete Old EBS Snapshot', severity: 'Low' },
        RDS_RIGHTSIZE_CPU_LOW: { title: 'Downsize RDS Instance', severity: 'High' },
        RDS_IDLE_STOP: { title: 'Stop Idle RDS Instance', severity: 'High' },
        RDS_HIGH_SNAPSHOT_COST: { title: 'Review RDS Snapshots', severity: 'Medium' },
        RDS_MEMORY_BOTTLENECK: { title: 'Upsize RDS Memory', severity: 'High' },
        LAMBDA_OPTIMIZE_DURATION: { title: 'Optimize Lambda Code', severity: 'High' },
        LAMBDA_HIGH_ERROR_WASTE: { title: 'Fix Lambda Errors', severity: 'High' },
        LAMBDA_UNUSED_CLEANUP: { title: 'Delete Unused Lambda', severity: 'Low' },
        DT_CROSS_AZ_WASTE: { title: 'Reduce Cross-AZ Traffic', severity: 'Medium' },
        DT_HIGH_INTERNET_EGRESS: { title: 'Add CDN / Caching Layer', severity: 'Medium' },
        ALB_IDLE_DELETE: { title: 'Delete Idle Load Balancer', severity: 'High' },
        ALB_HIGH_5XX_ERRORS: { title: 'Fix ALB 5XX Errors', severity: 'High' },
        CLB_MIGRATE_TO_ALB: { title: 'Migrate Classic LB → ALB', severity: 'Medium' },
        S3_LIFECYCLE_COLD: { title: 'Set S3 Lifecycle Policy', severity: 'Medium' },
        S3_EMPTY_BUCKET: { title: 'Delete Empty S3 Bucket', severity: 'Low' },
    }

    // Sort by High first, take top 3
    const severityOrder = { High: 0, Medium: 1, Low: 2 }
    const topRecommendations = [...recommendations]
        .sort((a, b) => {
            const sa = REC_LABELS[a.rec_type]?.severity ?? 'Low'
            const sb = REC_LABELS[b.rec_type]?.severity ?? 'Low'
            return (severityOrder[sa] ?? 2) - (severityOrder[sb] ?? 2)
        })
        .slice(0, 3)

    // Calculate dynamic values from real data if available
    const totalCost = costAnalysis?.summary?.totalCost ?? 0;
    const prevTotalCost = costAnalysis?.summary?.prevTotalCost ?? 0;
    const costChange = prevTotalCost > 0 ? ((totalCost - prevTotalCost) / prevTotalCost) * 100 : 0;
    const costChangeDirection = costChange >= 0 ? 'up' : 'down';
    const forecastCost = costAnalysis?.summary?.projectedMonthEnd ?? 0;

    // Map trend data for chart
    const costTrend = monthlyTrend.length > 0 ? monthlyTrend : [];

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(value)
    }

    if (isLoading) {
        return (
            <div className="flex h-[80vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">Loading dashboard...</span>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50/50 -m-8 p-8">
            <div className="space-y-8">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-3xl font-bold tracking-tight text-primary">Dashboard</h2>
                        <p className="text-muted-foreground">Overview of your cloud spend and health.</p>
                    </div>
                    <Button onClick={handleSync} disabled={isSyncing}>
                        <RefreshCw className={`mr-2 h-4 w-4 ${isSyncing ? 'animate-spin' : ''}`} />
                        {isSyncing ? 'Syncing...' : 'Sync AWS Data'}
                    </Button>
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
                            <div className="text-3xl font-bold">{formatCurrency(totalCost)}</div>
                            <div className="flex items-center gap-1 mt-1">
                                {costChangeDirection === 'up' ? (
                                    <TrendingUp className="h-4 w-4 text-red-500" />
                                ) : (
                                    <TrendingDown className="h-4 w-4 text-green-500" />
                                )}
                                <span className={`text-sm font-medium ${costChangeDirection === 'up' ? 'text-red-500' : 'text-green-500'}`}>
                                    {costChangeDirection === 'up' ? '+' : ''}{costChange.toFixed(1)}%
                                </span>
                                <span className="text-xs text-muted-foreground">from last month</span>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Card 2: Active Resources */}
                    <Card className="bg-white shadow-md hover:shadow-lg transition-shadow">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">Active Resources</CardTitle>
                            <Cpu className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{resourceSummary.total_resources}</div>
                            <div className="flex items-center gap-1 mt-1">
                                <TrendingUp className="h-4 w-4 text-blue-500" />
                                <span className="text-sm text-blue-500 font-medium">+{resourceSummary.new_resources_this_month}</span>
                                <span className="text-xs text-muted-foreground">new resources this month</span>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Card 3: Predicted Cost */}
                    <Card className="bg-white shadow-md hover:shadow-lg transition-shadow">
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">Predicted Cost</CardTitle>
                            <TrendingUp className="h-4 w-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-3xl font-bold">{formatCurrency(forecastCost)}</div>
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
                                <BarChart data={costTrend}>
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
                                <Link to="/recommend" className="text-sm text-primary hover:underline flex items-center gap-1">
                                    View all
                                    <ArrowRight className="h-3 w-3" />
                                </Link>
                            </div>
                            <p className="text-sm text-muted-foreground">
                                {recommendations.length > 0 ? (
                                    <span><span className="font-semibold text-orange-600">{recommendations.length}</span> issues found</span>
                                ) : (
                                    <span className="text-green-600 font-semibold">✓ All good!</span>
                                )}
                            </p>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            {topRecommendations.length === 0 ? (
                                <p className="text-sm text-muted-foreground text-center py-4">No recommendations yet.<br />Go to Recommend page to run analysis.</p>
                            ) : (
                                topRecommendations.map((rec) => {
                                    const label = REC_LABELS[rec.rec_type]
                                    const severity = label?.severity ?? 'Medium'
                                    return (
                                        <div key={rec.rec_id} className="flex items-start justify-between p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors">
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-1">
                                                    {severity === 'High' && <AlertTriangle className="h-3 w-3 text-red-500 flex-shrink-0" />}
                                                    <span className="font-medium text-sm truncate">{label?.title ?? rec.rec_type}</span>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    <Badge variant={severity === 'High' ? 'destructive' : 'secondary'} className="text-xs">{severity}</Badge>
                                                    <span className="text-xs text-muted-foreground truncate">{rec.resource_key}</span>
                                                </div>
                                            </div>
                                        </div>
                                    )
                                })
                            )}
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    )
}
