import { useState } from "react"
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

// Types for different services
interface EC2Instance {
    id: string
    name: string
    type: string
    zone: string
    elasticIp: string
    publicIp: string
}

interface LambdaFunction {
    id: string
    name: string
    runtime: string
    memory: string
    timeout: string
    lastModified: string
}

interface S3Bucket {
    id: string
    name: string
    region: string
    createdDate: string
    size: string
    objects: string
}

interface RDSInstance {
    id: string
    name: string
    engine: string
    instanceClass: string
    status: string
    endpoint: string
}

// Mock data for each service
const ec2Instances: EC2Instance[] = [
    { id: "i-0a1b2c3d4e5f6g7h8", name: "web-server-1", type: "t2.medium", zone: "us-east-1a", elasticIp: "52.23.45.67", publicIp: "44.204.44.231" },
    { id: "i-1b2c3d4e5f6g7h8i9", name: "api-server-1", type: "t2.large", zone: "us-east-1b", elasticIp: "-", publicIp: "44.205.55.123" },
    { id: "i-2c3d4e5f6g7h8i9j0", name: "db-server-1", type: "r5.xlarge", zone: "us-east-1a", elasticIp: "52.24.56.78", publicIp: "44.206.66.234" },
    { id: "i-3d4e5f6g7h8i9j0k1", name: "worker-1", type: "t3.medium", zone: "us-east-1c", elasticIp: "-", publicIp: "44.207.77.345" },
]

const lambdaFunctions: LambdaFunction[] = [
    { id: "fn-auth-handler", name: "auth-handler", runtime: "nodejs18.x", memory: "256 MB", timeout: "30s", lastModified: "2024-01-15" },
    { id: "fn-data-processor", name: "data-processor", runtime: "python3.11", memory: "512 MB", timeout: "60s", lastModified: "2024-01-20" },
    { id: "fn-notification", name: "notification-sender", runtime: "nodejs18.x", memory: "128 MB", timeout: "15s", lastModified: "2024-01-18" },
]

const s3Buckets: S3Bucket[] = [
    { id: "bucket-assets", name: "company-assets-prod", region: "us-east-1", createdDate: "2023-06-15", size: "125 GB", objects: "45,230" },
    { id: "bucket-logs", name: "application-logs", region: "us-east-1", createdDate: "2023-08-20", size: "890 GB", objects: "1,234,567" },
    { id: "bucket-backup", name: "db-backups", region: "us-west-2", createdDate: "2023-05-10", size: "2.5 TB", objects: "890" },
]

const rdsInstances: RDSInstance[] = [
    { id: "rds-prod-main", name: "prod-database", engine: "PostgreSQL 15.4", instanceClass: "db.r5.large", status: "available", endpoint: "prod-db.abc123.us-east-1.rds.amazonaws.com" },
    { id: "rds-staging", name: "staging-database", engine: "PostgreSQL 15.4", instanceClass: "db.t3.medium", status: "available", endpoint: "staging-db.abc123.us-east-1.rds.amazonaws.com" },
]

// Service-specific monitoring configurations
const serviceMonitoringConfig = {
    EC2: [
        { title: "CPU", subtitle: "utilizations (%)" },
        { title: "Network", subtitle: "in (bytes)" },
        { title: "Network", subtitle: "out (bytes)" },
        { title: "DiskRead", subtitle: "Bytes (bytes)" },
        { title: "DiskWrite", subtitle: "Bytes (bytes)" },
        { title: "StatusCheck", subtitle: "Failed (count)" },
    ],
    Lambda: [
        { title: "Invocations", subtitle: "count" },
        { title: "Duration", subtitle: "milliseconds" },
        { title: "Errors", subtitle: "count" },
        { title: "Throttles", subtitle: "count" },
        { title: "ConcurrentExecutions", subtitle: "count" },
        { title: "Memory", subtitle: "MB used" },
    ],
    S3: [
        { title: "BucketSizeBytes", subtitle: "bytes" },
        { title: "NumberOfObjects", subtitle: "count" },
        { title: "AllRequests", subtitle: "count" },
        { title: "GetRequests", subtitle: "count" },
        { title: "PutRequests", subtitle: "count" },
        { title: "BytesDownloaded", subtitle: "bytes" },
    ],
    RDS: [
        { title: "CPUUtilization", subtitle: "percent" },
        { title: "DatabaseConnections", subtitle: "count" },
        { title: "FreeableMemory", subtitle: "bytes" },
        { title: "ReadIOPS", subtitle: "count/sec" },
        { title: "WriteIOPS", subtitle: "count/sec" },
        { title: "FreeStorageSpace", subtitle: "bytes" },
    ],
}

// Generate random chart data for demo
const generateChartData = () => [
    { time: "12:15", value: Math.random() * 8 + 1 },
    { time: "12:30", value: Math.random() * 8 + 1 },
    { time: "12:45", value: Math.random() * 8 + 1 },
    { time: "13:00", value: Math.random() * 8 + 1 },
    { time: "13:15", value: Math.random() * 8 + 1 },
]

const services = ["EC2", "Lambda", "S3", "RDS"] as const
type ServiceType = typeof services[number]

interface MonitoringChartProps {
    title: string
    subtitle: string
    data: { time: string; value: number }[]
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
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data}>
                            <XAxis
                                dataKey="time"
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
                                type="linear"
                                dataKey="value"
                                stroke={color}
                                strokeWidth={2}
                                dot={{ fill: color, strokeWidth: 0, r: 3 }}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </CardContent>
        </Card>
    )
}

// Table components for each service
function EC2Table({ instances, selectedId, onRowClick }: { instances: EC2Instance[], selectedId: string | null, onRowClick: (id: string) => void }) {
    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead className="w-12"></TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Instance ID</TableHead>
                    <TableHead>Instance Type</TableHead>
                    <TableHead>Availability Zone</TableHead>
                    <TableHead>Elastic IP</TableHead>
                    <TableHead>Public IPv4</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {instances.map((instance) => (
                    <TableRow
                        key={instance.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => onRowClick(instance.id)}
                    >
                        <TableCell>
                            <Checkbox checked={selectedId === instance.id} onCheckedChange={() => onRowClick(instance.id)} />
                        </TableCell>
                        <TableCell>{instance.name}</TableCell>
                        <TableCell className="font-mono text-sm">{instance.id}</TableCell>
                        <TableCell>{instance.type}</TableCell>
                        <TableCell>
                            <Badge variant="outline" className="border-primary text-primary">{instance.zone}</Badge>
                        </TableCell>
                        <TableCell>{instance.elasticIp}</TableCell>
                        <TableCell>{instance.publicIp}</TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    )
}

function LambdaTable({ functions, selectedId, onRowClick }: { functions: LambdaFunction[], selectedId: string | null, onRowClick: (id: string) => void }) {
    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead className="w-12"></TableHead>
                    <TableHead>Function Name</TableHead>
                    <TableHead>Runtime</TableHead>
                    <TableHead>Memory</TableHead>
                    <TableHead>Timeout</TableHead>
                    <TableHead>Last Modified</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {functions.map((fn) => (
                    <TableRow
                        key={fn.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => onRowClick(fn.id)}
                    >
                        <TableCell>
                            <Checkbox checked={selectedId === fn.id} onCheckedChange={() => onRowClick(fn.id)} />
                        </TableCell>
                        <TableCell className="font-medium">{fn.name}</TableCell>
                        <TableCell>
                            <Badge variant="outline" className="border-primary text-primary">{fn.runtime}</Badge>
                        </TableCell>
                        <TableCell>{fn.memory}</TableCell>
                        <TableCell>{fn.timeout}</TableCell>
                        <TableCell>{fn.lastModified}</TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    )
}

function S3Table({ buckets, selectedId, onRowClick }: { buckets: S3Bucket[], selectedId: string | null, onRowClick: (id: string) => void }) {
    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead className="w-12"></TableHead>
                    <TableHead>Bucket Name</TableHead>
                    <TableHead>Region</TableHead>
                    <TableHead>Created Date</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>Objects</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {buckets.map((bucket) => (
                    <TableRow
                        key={bucket.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => onRowClick(bucket.id)}
                    >
                        <TableCell>
                            <Checkbox checked={selectedId === bucket.id} onCheckedChange={() => onRowClick(bucket.id)} />
                        </TableCell>
                        <TableCell className="font-medium">{bucket.name}</TableCell>
                        <TableCell>
                            <Badge variant="outline" className="border-primary text-primary">{bucket.region}</Badge>
                        </TableCell>
                        <TableCell>{bucket.createdDate}</TableCell>
                        <TableCell>{bucket.size}</TableCell>
                        <TableCell>{bucket.objects}</TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    )
}

function RDSTable({ instances, selectedId, onRowClick }: { instances: RDSInstance[], selectedId: string | null, onRowClick: (id: string) => void }) {
    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead className="w-12"></TableHead>
                    <TableHead>DB Name</TableHead>
                    <TableHead>Engine</TableHead>
                    <TableHead>Instance Class</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Endpoint</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {instances.map((instance) => (
                    <TableRow
                        key={instance.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => onRowClick(instance.id)}
                    >
                        <TableCell>
                            <Checkbox checked={selectedId === instance.id} onCheckedChange={() => onRowClick(instance.id)} />
                        </TableCell>
                        <TableCell className="font-medium">{instance.name}</TableCell>
                        <TableCell>{instance.engine}</TableCell>
                        <TableCell>{instance.instanceClass}</TableCell>
                        <TableCell>
                            <Badge variant="outline" className="border-green-500 text-green-600">{instance.status}</Badge>
                        </TableCell>
                        <TableCell className="font-mono text-xs max-w-[200px] truncate">{instance.endpoint}</TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    )
}

export default function Monitoring() {
    const [selectedService, setSelectedService] = useState<ServiceType>("EC2")
    const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null)

    const handleRowClick = (resourceId: string) => {
        setSelectedResourceId(resourceId === selectedResourceId ? null : resourceId)
    }

    const handleServiceChange = (service: ServiceType) => {
        setSelectedService(service)
        setSelectedResourceId(null)
    }

    // Get monitoring charts config for selected service
    const monitoringCharts = serviceMonitoringConfig[selectedService]

    // Render the appropriate table based on selected service
    const renderTable = () => {
        switch (selectedService) {
            case "EC2":
                return <EC2Table instances={ec2Instances} selectedId={selectedResourceId} onRowClick={handleRowClick} />
            case "Lambda":
                return <LambdaTable functions={lambdaFunctions} selectedId={selectedResourceId} onRowClick={handleRowClick} />
            case "S3":
                return <S3Table buckets={s3Buckets} selectedId={selectedResourceId} onRowClick={handleRowClick} />
            case "RDS":
                return <RDSTable instances={rdsInstances} selectedId={selectedResourceId} onRowClick={handleRowClick} />
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
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {monitoringCharts.map((chart, index) => (
                        <MonitoringChart
                            key={`${selectedService}-${index}`}
                            title={chart.title}
                            subtitle={chart.subtitle}
                            data={generateChartData()}
                        />
                    ))}
                </div>
            )}
        </div>
    )
}
