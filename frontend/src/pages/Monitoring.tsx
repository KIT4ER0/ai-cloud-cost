import { useState, useEffect, useCallback } from "react"
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

// Service-specific monitoring chart configs
const serviceMonitoringConfig = {
    EC2: [
        { title: "CPU P95", subtitle: "utilization (%)", dataKey: "cpu_p95" },
        { title: "Network Out", subtitle: "GB sum", dataKey: "network_out_gb_sum" },
    ],
    Lambda: [
        { title: "Duration P95", subtitle: "milliseconds", dataKey: "duration_p95_ms" },
        { title: "Invocations", subtitle: "count", dataKey: "invocations_sum" },
        { title: "Errors", subtitle: "count", dataKey: "errors_sum" },
    ],
    S3: [
        { title: "Storage", subtitle: "GB avg", dataKey: "storage_gb_avg" },
        { title: "Objects", subtitle: "count", dataKey: "number_of_objects" },
    ],
    RDS: [
        { title: "CPU P95", subtitle: "percent", dataKey: "cpu_p95" },
        { title: "DB Connections", subtitle: "avg", dataKey: "db_conn_avg" },
        { title: "Free Storage", subtitle: "GB min", dataKey: "free_storage_gb_min" },
    ],
}

// Resource ID field names per service
const resourceIdField: Record<ServiceType, string> = {
    EC2: "ec2_resource_id",
    Lambda: "lambda_resource_id",
    S3: "s3_resource_id",
    RDS: "rds_resource_id",
}

const services = ["EC2", "Lambda", "S3", "RDS"] as const
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

function EC2Table({ resources, selectedId, onRowClick }: { resources: any[], selectedId: number | null, onRowClick: (id: number) => void }) {
    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead className="w-12"></TableHead>
                    <TableHead>Instance ID</TableHead>
                    <TableHead>Instance Type</TableHead>
                    <TableHead>State</TableHead>
                    <TableHead>Region</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {resources.map((r) => (
                    <TableRow key={r.ec2_resource_id} className="cursor-pointer hover:bg-muted/50" onClick={() => onRowClick(r.ec2_resource_id)}>
                        <TableCell><Checkbox checked={selectedId === r.ec2_resource_id} onCheckedChange={() => onRowClick(r.ec2_resource_id)} /></TableCell>
                        <TableCell className="font-mono text-sm">{r.instance_id}</TableCell>
                        <TableCell>{r.instance_type || "-"}</TableCell>
                        <TableCell>
                            <Badge variant="outline" className={r.state === "running" ? "border-green-500 text-green-600" : "border-slate-400 text-slate-500"}>{r.state || "unknown"}</Badge>
                        </TableCell>
                        <TableCell><Badge variant="outline" className="border-primary text-primary">{r.region}</Badge></TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
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

export default function Monitoring() {
    const [selectedService, setSelectedService] = useState<ServiceType>("EC2")
    const [selectedResourceId, setSelectedResourceId] = useState<number | null>(null)
    const [resources, setResources] = useState<any[]>([])
    const [metrics, setMetrics] = useState<any[]>([])
    const [loadingResources, setLoadingResources] = useState(false)
    const [loadingMetrics, setLoadingMetrics] = useState(false)

    // Fetch resources when service changes
    const fetchResources = useCallback(async (service: ServiceType) => {
        setLoadingResources(true)
        try {
            const data = await api.monitoring.getResources(service)
            setResources(data)
        } catch (err) {
            console.error("Failed to load resources:", err)
            setResources([])
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
    }

    const monitoringCharts = serviceMonitoringConfig[selectedService]

    const renderTable = () => {
        if (loadingResources) {
            return (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    <span className="ml-2 text-muted-foreground">Loading resources...</span>
                </div>
            )
        }
        if (resources.length === 0) {
            return (
                <div className="flex items-center justify-center py-12 text-muted-foreground">
                    No {selectedService} resources found in the database.
                </div>
            )
        }
        switch (selectedService) {
            case "EC2":
                return <EC2Table resources={resources} selectedId={selectedResourceId} onRowClick={handleRowClick} />
            case "Lambda":
                return <LambdaTable resources={resources} selectedId={selectedResourceId} onRowClick={handleRowClick} />
            case "S3":
                return <S3Table resources={resources} selectedId={selectedResourceId} onRowClick={handleRowClick} />
            case "RDS":
                return <RDSTable resources={resources} selectedId={selectedResourceId} onRowClick={handleRowClick} />
            default:
                return null
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
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                        {monitoringCharts.map((chart, index) => {
                            const chartData = metrics.map((m) => ({
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
                )
            )}
        </div>
    )
}
