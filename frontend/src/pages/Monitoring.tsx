import { useState, useEffect, useCallback, useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts"
import { Loader2 } from "lucide-react"
import { api } from "@/lib/api"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"

// Service-specific monitoring chart configs
const serviceMonitoringConfig = {
    EC2: [
        { title: "CPU Avg", subtitle: "% (Avg)", dataKey: "cpu_utilization" },
        { title: "CPU Max", subtitle: "% (Max)", dataKey: "cpu_max" },
        { title: "CPU P99", subtitle: "% (P99)", dataKey: "cpu_p99" },
        { title: "Hours Running", subtitle: "hours (daily)", dataKey: "hours_running" },
        { title: "Network In", subtitle: "bytes", dataKey: "network_in" },
        { title: "Network Out", subtitle: "bytes", dataKey: "network_out" },
    ],
    Lambda: [
        { title: "Duration P95", subtitle: "milliseconds", dataKey: "duration_p95" },
        { title: "Invocations", subtitle: "count (sum)", dataKey: "invocations" },
        { title: "Errors", subtitle: "count (sum)", dataKey: "errors" },
    ],
    S3: [
        { title: "Bucket Size", subtitle: "bytes", dataKey: "bucket_size_bytes" },
        { title: "Objects", subtitle: "count", dataKey: "number_of_objects" },
    ],
    RDS: [
        { title: "CPU Utilization", subtitle: "%", dataKey: "cpu_utilization" },
        { title: "Database Connections", subtitle: "count", dataKey: "database_connections" },
        { title: "Free Storage Space", subtitle: "bytes", dataKey: "free_storage_space" },
        { title: "Read IOPS", subtitle: "count/s", dataKey: "read_iops" },
        { title: "Write IOPS", subtitle: "count/s", dataKey: "write_iops" },
    ],
    ALB: [
        { title: "Request Count", subtitle: "count (sum)", dataKey: "request_count" },
        { title: "Response Time", subtitle: "seconds (avg)", dataKey: "response_time_avg" },
        { title: "HTTP 5xx", subtitle: "count (sum)", dataKey: "http_5xx_count" },
        { title: "Active Connections", subtitle: "count (sum)", dataKey: "active_conn_count" },
    ],
}

const services = ["EC2", "Lambda", "S3", "RDS", "ALB"] as const
type ServiceType = typeof services[number]

interface MonitoringChartProps {
    title: string
    subtitle: string
    data: { date: string; value: number | null }[]
    color?: string
}

function MonitoringChart({ title, subtitle, data, color = "hsl(var(--primary))" }: MonitoringChartProps) {
    return (
        <Card>
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-primary">{title}</CardTitle>
                <p className="text-xs text-muted-foreground">{subtitle}</p>
            </CardHeader>
            <CardContent>
                <div className="h-[120px]">
                    {data.length === 0 ? (
                        <div className="h-full flex items-center justify-center text-sm text-muted-foreground">No metric data</div>
                    ) : (
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={data}>
                                <XAxis
                                    dataKey="date"
                                    tick={{ fontSize: 10 }}
                                    axisLine={{ stroke: '#e5e7eb' }}
                                    tickLine={{ stroke: '#e5e7eb' }}
                                />
                                <YAxis
                                    tick={{ fontSize: 10 }}
                                    axisLine={{ stroke: '#e5e7eb' }}
                                    tickLine={{ stroke: '#e5e7eb' }}
                                    domain={[0, 'auto']}
                                />
                                <Tooltip />
                                <Line
                                    type="monotone"
                                    dataKey="value"
                                    stroke={color}
                                    strokeWidth={2}
                                    dot={{ fill: color, strokeWidth: 0, r: 3 }}
                                    connectNulls
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    )}
                </div>
            </CardContent>
        </Card>
    )
}

// ---- Per-service table components ----

function EC2Table({ resources, eips, selectedId, onRowClick }: { resources: any[], eips: any[], selectedId: number | null, onRowClick: (id: number) => void }) {
    return (
        <div className="space-y-6">
            <div className="space-y-2">
                <h3 className="px-4 text-lg font-semibold">EC2 Instances</h3>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-12"></TableHead>
                            <TableHead>Instance ID</TableHead>
                            <TableHead>Instance Type</TableHead>
                            <TableHead>State</TableHead>
                            <TableHead>Public IP</TableHead>
                            <TableHead>Region</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {resources.map((r) => {
                            return (
                                <TableRow key={r.ec2_resource_id} className="cursor-pointer hover:bg-muted/50" onClick={() => onRowClick(r.ec2_resource_id)}>
                                    <TableCell><Checkbox checked={selectedId === r.ec2_resource_id} onCheckedChange={() => onRowClick(r.ec2_resource_id)} /></TableCell>
                                    <TableCell className="font-mono text-sm">{r.instance_id}</TableCell>
                                    <TableCell>{r.instance_type || "-"}</TableCell>
                                    <TableCell>
                                        <Badge variant="outline" className={r.state === "running" ? "border-green-500 text-green-600" : "border-slate-400 text-slate-500"}>{r.state || "unknown"}</Badge>
                                    </TableCell>
                                    <TableCell className="font-mono text-xs">{r.public_ip || "-"}</TableCell>
                                    <TableCell><Badge variant="outline" className="border-primary text-primary">{r.region}</Badge></TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </div>

            <div className="space-y-2 pt-4 border-t">
                <h3 className="px-4 text-lg font-semibold flex items-center gap-2">
                    Elastic IPs
                    <Badge variant="secondary" className="font-normal">
                        {eips.filter(e => e.is_idle).length} Idle
                    </Badge>
                </h3>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Public IP</TableHead>
                            <TableHead>Allocation ID</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Daily Cost ($)</TableHead>
                            <TableHead>Associated Resource</TableHead>
                            <TableHead>Region</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {eips.map((eip) => {
                            const associatedInstance = resources.find(r => r.ec2_resource_id === eip.ec2_resource_id);
                            return (
                                <TableRow key={eip.eip_id}>
                                    <TableCell className="font-mono font-medium">{eip.public_ip}</TableCell>
                                    <TableCell className="font-mono text-xs text-muted-foreground">{eip.allocation_id}</TableCell>
                                    <TableCell>
                                        <Badge variant={eip.is_idle ? "destructive" : "outline"} className={!eip.is_idle ? "border-green-500 text-green-600" : ""}>
                                            {eip.is_idle ? "Idle" : "In Use"}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="font-medium text-destructive">
                                        {eip.current_cost_usd > 0 ? `$${eip.current_cost_usd.toFixed(3)}` : "-"}
                                    </TableCell>
                                    <TableCell>
                                        {associatedInstance ? (
                                            <span className="text-sm font-mono">{associatedInstance.instance_id}</span>
                                        ) : (
                                            <span className="text-sm text-muted-foreground">-</span>
                                        )}
                                    </TableCell>
                                    <TableCell><Badge variant="outline" className="border-primary text-primary">{eip.region}</Badge></TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </div>
        </div>
    )
}

function LambdaTable({ resources, selectedId, onRowClick }: { resources: any[], selectedId: number | null, onRowClick: (id: number) => void }) {
    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead className="w-12"></TableHead>
                    <TableHead>Function Name</TableHead>
                    <TableHead>Runtime</TableHead>
                    <TableHead>Memory</TableHead>
                    <TableHead>Timeout</TableHead>
                    <TableHead>Region</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {resources.map((r) => (
                    <TableRow key={r.lambda_resource_id} className="cursor-pointer hover:bg-muted/50" onClick={() => onRowClick(r.lambda_resource_id)}>
                        <TableCell><Checkbox checked={selectedId === r.lambda_resource_id} onCheckedChange={() => onRowClick(r.lambda_resource_id)} /></TableCell>
                        <TableCell className="font-medium">{r.function_name}</TableCell>
                        <TableCell><Badge variant="outline" className="border-primary text-primary">{r.runtime || "-"}</Badge></TableCell>
                        <TableCell>{r.memory_mb ? `${r.memory_mb} MB` : "-"}</TableCell>
                        <TableCell>{r.timeout_sec ? `${r.timeout_sec}s` : "-"}</TableCell>
                        <TableCell><Badge variant="outline" className="border-primary text-primary">{r.region}</Badge></TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    )
}

function S3Table({ resources, selectedId, onRowClick }: { resources: any[], selectedId: number | null, onRowClick: (id: number) => void }) {
    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead className="w-12"></TableHead>
                    <TableHead>Bucket Name</TableHead>
                    <TableHead>Region</TableHead>
                    <TableHead>Account ID</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {resources.map((r) => (
                    <TableRow key={r.s3_resource_id} className="cursor-pointer hover:bg-muted/50" onClick={() => onRowClick(r.s3_resource_id)}>
                        <TableCell><Checkbox checked={selectedId === r.s3_resource_id} onCheckedChange={() => onRowClick(r.s3_resource_id)} /></TableCell>
                        <TableCell className="font-medium">{r.bucket_name}</TableCell>
                        <TableCell><Badge variant="outline" className="border-primary text-primary">{r.region}</Badge></TableCell>
                        <TableCell className="font-mono text-sm">{r.account_id}</TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    )
}

function RDSTable({ resources, selectedId, onRowClick }: { resources: any[], selectedId: number | null, onRowClick: (id: number) => void }) {
    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead className="w-12"></TableHead>
                    <TableHead>DB Identifier</TableHead>
                    <TableHead>Engine</TableHead>
                    <TableHead>Instance Class</TableHead>
                    <TableHead>Storage</TableHead>
                    <TableHead>Region</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {resources.map((r) => (
                    <TableRow key={r.rds_resource_id} className="cursor-pointer hover:bg-muted/50" onClick={() => onRowClick(r.rds_resource_id)}>
                        <TableCell><Checkbox checked={selectedId === r.rds_resource_id} onCheckedChange={() => onRowClick(r.rds_resource_id)} /></TableCell>
                        <TableCell className="font-medium">{r.db_identifier}</TableCell>
                        <TableCell>{r.engine || "-"}</TableCell>
                        <TableCell>{r.instance_class || "-"}</TableCell>
                        <TableCell>{r.allocated_gb ? `${r.allocated_gb} GB` : "-"}</TableCell>
                        <TableCell><Badge variant="outline" className="border-primary text-primary">{r.region}</Badge></TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    )
}

function ALBTable({ resources, selectedId, onRowClick }: { resources: any[], selectedId: number | null, onRowClick: (id: number) => void }) {
    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead className="w-12"></TableHead>
                    <TableHead>Load Balancer</TableHead>
                    <TableHead>ALB Type</TableHead>
                    <TableHead>State</TableHead>
                    <TableHead>Region</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {resources.map((r) => (
                    <TableRow key={r.alb_resource_id} className="cursor-pointer hover:bg-muted/50" onClick={() => onRowClick(r.alb_resource_id)}>
                        <TableCell><Checkbox checked={selectedId === r.alb_resource_id} onCheckedChange={() => onRowClick(r.alb_resource_id)} /></TableCell>
                        <TableCell className="font-medium">{r.alb_name}</TableCell>
                        <TableCell className="font-mono text-sm truncate max-w-[200px]" title={r.alb_type || ""}>{r.alb_type || "-"}</TableCell>
                        <TableCell>{r.state || "-"}</TableCell>
                        <TableCell><Badge variant="outline" className="border-primary text-primary">{r.region}</Badge></TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    )
}

export default function Monitoring() {
    const [selectedService, setSelectedService] = useState<ServiceType>("EC2")
    const [selectedResourceId, setSelectedResourceId] = useState<number | null>(null)
    const [resources, setResources] = useState<any[]>([])
    const [metrics, setMetrics] = useState<any[]>([])
    const [selectedYear, setSelectedYear] = useState<string | null>(null)
    const [selectedMonthNum, setSelectedMonthNum] = useState<string | null>(null)
    const [loadingResources, setLoadingResources] = useState(false)
    const [loadingMetrics, setLoadingMetrics] = useState(false)
    const [eips, setEips] = useState<any[]>([])

    // Fetch resources and EIPs when service changes
    const fetchResources = useCallback(async (service: ServiceType) => {
        setLoadingResources(true)
        try {
            const data = await api.monitoring.getResources(service)
            setResources(data)

            if (service === "EC2") {
                const eipData = await api.monitoring.getEIPs()
                setEips(eipData)
            } else {
                setEips([])
            }
        } catch (err) {
            console.error("Failed to load resources:", err)
            setResources([])
            setEips([])
        } finally {
            setLoadingResources(false)
        }
    }, [])

    // Fetch metrics when a resource is selected
    const fetchMetrics = useCallback(async (service: ServiceType, resourceId: number) => {
        setLoadingMetrics(true)
        try {
            const data = await api.monitoring.getMetrics(service, resourceId)
            setMetrics(data)
        } catch (err) {
            console.error("Failed to load metrics:", err)
            setMetrics([])
        } finally {
            setLoadingMetrics(false)
        }
    }, [])

    useEffect(() => {
        fetchResources(selectedService)
    }, [selectedService, fetchResources])

    useEffect(() => {
        if (selectedResourceId !== null) {
            fetchMetrics(selectedService, selectedResourceId)
        } else {
            setMetrics([])
        }
    }, [selectedResourceId, selectedService, fetchMetrics])

    const handleRowClick = (resourceId: number) => {
        setSelectedResourceId(resourceId === selectedResourceId ? null : resourceId)
    }

    const handleServiceChange = (service: ServiceType) => {
        setSelectedService(service)
        setSelectedResourceId(null)
        setMetrics([])
        setSelectedYear(null)
        setSelectedMonthNum(null)
    }

    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    const allMonths = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]

    // Compute year range: earliest data year .. current year + 2
    const availableYears = useMemo(() => {
        const currentYear = new Date().getFullYear()
        let minYear = currentYear
        metrics.forEach((m) => {
            const y = parseInt(m.metric_date?.substring(0, 4))
            if (y && y < minYear) minYear = y
        })
        const years: string[] = []
        for (let y = minYear; y <= currentYear + 2; y++) {
            years.push(String(y))
        }
        return years
    }, [metrics])

    // Auto-select latest year+month when metrics load
    useEffect(() => {
        if (metrics.length === 0) return
        if (!selectedYear || !selectedMonthNum) {
            const dates = metrics.map((m) => m.metric_date).filter(Boolean).sort()
            if (dates.length > 0) {
                const latest = dates[dates.length - 1]
                setSelectedYear(latest.substring(0, 4))
                setSelectedMonthNum(latest.substring(5, 7))
            }
        }
    }, [metrics, selectedYear, selectedMonthNum])

    // Reset when resource changes
    useEffect(() => {
        setSelectedYear(null)
        setSelectedMonthNum(null)
    }, [selectedResourceId])

    // Build the YYYY-MM key for filtering
    const selectedYM = selectedYear && selectedMonthNum ? `${selectedYear}-${selectedMonthNum}` : null

    // Filter metrics by selected month
    const filteredMetrics = useMemo(() => {
        if (!selectedYM) return metrics
        return metrics.filter((m) => m.metric_date?.startsWith(selectedYM))
    }, [metrics, selectedYM])

    const monitoringCharts = serviceMonitoringConfig[selectedService]

    const renderTable = () => {
        if (loadingResources) {
            return (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">กำลังโหลดรายการทรัพยากร...</span>
                </div>
            )
        }

        if (resources.length === 0 && (selectedService !== "EC2" || eips.length === 0)) {
            return (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <p>ไม่พบรายการทรัพยากรสำหรับบริการนี้</p>
                </div>
            )
        }

        switch (selectedService) {
            case "EC2": return <EC2Table resources={resources} eips={eips} selectedId={selectedResourceId} onRowClick={handleRowClick} />
            case "Lambda": return <LambdaTable resources={resources} selectedId={selectedResourceId} onRowClick={handleRowClick} />
            case "S3": return <S3Table resources={resources} selectedId={selectedResourceId} onRowClick={handleRowClick} />
            case "RDS": return <RDSTable resources={resources} selectedId={selectedResourceId} onRowClick={handleRowClick} />
            case "ALB": return <ALBTable resources={resources} selectedId={selectedResourceId} onRowClick={handleRowClick} />
            default: return null
        }
    }

    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-3xl font-bold tracking-tight text-primary">Monitoring</h2>
            </div>

            {/* Service Selection Buttons */}
            <div className="flex gap-2">
                {services.map((service) => (
                    <Button
                        key={service}
                        variant={selectedService === service ? "default" : "outline"}
                        onClick={() => handleServiceChange(service)}
                        className="rounded-full px-6"
                    >
                        {service}
                    </Button>
                ))}
            </div>

            {/* Resource Table */}
            <Card>
                {renderTable()}
            </Card>

            {/* Monitoring Charts - Only show when a resource is selected */}
            {selectedResourceId && (
                loadingMetrics ? (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                        <span className="ml-2 text-muted-foreground">Loading metrics...</span>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {/* Month Picker */}
                        {availableYears.length > 0 && (
                            <div className="flex items-center justify-end gap-2">
                                <Select
                                    value={selectedMonthNum || undefined}
                                    onValueChange={(value) => setSelectedMonthNum(value)}
                                >
                                    <SelectTrigger className="h-8 w-[100px] text-xs">
                                        <SelectValue placeholder="เดือน" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {allMonths.map((m) => (
                                            <SelectItem key={m} value={m}>
                                                {monthNames[parseInt(m) - 1]}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <Select
                                    value={selectedYear || undefined}
                                    onValueChange={(value) => setSelectedYear(value)}
                                >
                                    <SelectTrigger className="h-8 w-[80px] text-xs">
                                        <SelectValue placeholder="ปี" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {availableYears.map((y) => (
                                            <SelectItem key={y} value={y}>
                                                {y}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}

                        {/* Charts */}
                        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                            {monitoringCharts.map((chart, index) => {
                                const chartData = filteredMetrics.map((m) => ({
                                    date: m.metric_date,
                                    value: m[chart.dataKey] ?? null,
                                }))
                                return (
                                    <MonitoringChart
                                        key={`${selectedService}-${index}`}
                                        title={chart.title}
                                        subtitle={chart.subtitle}
                                        data={chartData}
                                    />
                                )
                            })}
                        </div>
                    </div>
                )
            )}
        </div>
    )
}