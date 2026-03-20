import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
    TrendingDown, ArrowRight, RefreshCw, Loader2, FlaskConical,
    ChevronDown, ChevronRight, Info, Server, Database,
    Archive, Zap, Network, LoaderCircle
} from 'lucide-react'
import { api } from '@/lib/api'

// ---- Types ----
interface RecommendationItem {
    rec_id: number
    service: string
    resource_key: string
    rec_type: string
    details: Record<string, unknown>
    est_saving_usd: number | null
    confidence: number | null
    status: string
    region: string
    account_id: string
}

// ---- Label map ----
const REC_TYPE_LABELS: Record<string, {
    title: string
    description: (d: Record<string, unknown>) => string
    severity: 'High' | 'Medium' | 'Low'
}> = {
    EC2_RIGHTSIZE_CPU_LOW: { title: 'Resize EC2 Instance', description: (d) => `CPU p99 สูงสุดเพียง ${(d.max_cpu_p99 as number)?.toFixed(1)}% → ควรลดขนาดเครื่องลง`, severity: 'High' },
    EC2_IDLE_STOPPED: { title: 'Terminate Idle EC2', description: (d) => `เครื่องถูกปิดทิ้งไว้ ${d.running_hours_7d} ชม. ใน 7 วัน → กินค่า EBS เปล่าๆ`, severity: 'High' },
    EC2_EIP_UNASSOCIATED: { title: 'Release Unused Elastic IP', description: (d) => `IP ว่างงานมาแล้ว ${(d.idle_hours_7d as number)?.toFixed(0)} ชม. → คืน IP เพื่อลดค่า`, severity: 'Medium' },
    EC2_EBS_UNATTACHED: { title: 'Delete Unattached EBS Volume', description: () => `EBS Volume ไม่ได้ต่ออยู่กับเครื่องไหนเลย`, severity: 'Medium' },
    EC2_EBS_SNAPSHOT_OLD: { title: 'Delete Old EBS Snapshot', description: (d) => `Snapshot อายุ ${d.age_days} วัน → ลบเพื่อประหยัดค่า Storage`, severity: 'Low' },
    RDS_RIGHTSIZE_CPU_LOW: { title: 'Downsize RDS Instance', description: (d) => `CPU สูงสุด ${(d.max_cpu as number)?.toFixed(1)}% ใน 7 วัน → ลดสเปคเครื่อง DB`, severity: 'High' },
    RDS_IDLE_STOP: { title: 'Stop Idle RDS Instance', description: (d) => `มี Connection เพียง ${d.conns_7d} ครั้งใน 7 วัน → หยุดชั่วคราวเพื่อเซฟค่ารัน`, severity: 'High' },
    RDS_HIGH_SNAPSHOT_COST: { title: 'Review RDS Snapshots', description: (d) => `มี Snapshot สะสมถึง ${(d.snap_gb as number)?.toFixed(0)} GB → ลบ Snapshot เก่าทิ้ง`, severity: 'Medium' },
    RDS_MEMORY_BOTTLENECK: { title: 'Upsize RDS (Memory Bottleneck)', description: () => `RAM ล้นจนใช้ Swap Disk → ควรขยายสเปค หรือจูน Query`, severity: 'High' },
    S3_LIFECYCLE_COLD: { title: 'Set S3 Lifecycle Policy', description: (d) => `ไม่มีการเข้าถึงข้อมูลใน 30 วัน (Size: ${((d.max_size as number) / 1e9)?.toFixed(1)} GB) → ย้ายไป Glacier`, severity: 'Medium' },
    S3_ARCHIVE_PATTERN: { title: 'Direct S3 Writes to Glacier', description: (d) => `มีการ Upload ${d.puts_14d} ครั้งแต่ไม่เคยอ่านเลย → เขียนตรงไป Glacier ราคาถูกกว่า`, severity: 'Medium' },
    S3_HUGE_ABANDONED: { title: 'Review Inactive S3 Bucket', description: (d) => `Bucket ขนาด ${((d.max_size as number) / 1e9)?.toFixed(1)} GB ไม่มีกิจกรรม 30 วัน`, severity: 'Low' },
    S3_EMPTY_BUCKET: { title: 'Delete Empty S3 Bucket', description: () => `Bucket ว่างเปล่า ไม่มีไฟล์ใดๆ → ลบทิ้งให้เรียบร้อย`, severity: 'Low' },
    LAMBDA_OPTIMIZE_DURATION: { title: 'Optimize Lambda Code', description: (d) => `p95 duration ${(d.max_p95 as number)?.toFixed(0)} ms และถูกเรียก ${(d.invocations_14d as number)?.toFixed(0)} ครั้งใน 14 วัน → ปรับโค้ดลดค่ารัน`, severity: 'High' },
    LAMBDA_HIGH_ERROR_WASTE: { title: 'Fix Lambda Errors', description: (d) => `มี Error ${(d.errors_7d as number)?.toFixed(0)} ครั้งใน 7 วัน → เสียเงินค่ารันทั้งที่โค้ดพัง`, severity: 'High' },
    LAMBDA_UNUSED_CLEANUP: { title: 'Delete Unused Lambda Function', description: () => `ไม่มี Invocation ใดๆ ใน 30 วัน → ลบเพื่อจัดระเบียบ`, severity: 'Low' },
    DT_CROSS_AZ_WASTE: { title: 'Reduce Cross-AZ Traffic', description: (d) => `ข้อมูลวิ่งข้าม AZ รวม ${(d.cross_az_gb_30d as number)?.toFixed(1)} GB ใน 30 วัน → รวมทรัพยากรไว้ใน AZ เดียวกัน`, severity: 'Medium' },
    DT_HIGH_INTERNET_EGRESS: { title: 'Add CDN / Caching Layer', description: (d) => `ส่งข้อมูลออก Internet ${(d.egress_gb_30d as number)?.toFixed(0)} GB ใน 30 วัน → ใช้ CloudFront ลดค่า Bandwidth`, severity: 'Medium' },
    ALB_IDLE_DELETE: { title: 'Delete Idle Load Balancer', description: (d) => `Request เพียง ${d.req_count} ครั้งใน 7 วัน → ลบ ALB และประหยัดค่ารายชั่วโมง`, severity: 'High' },
    ALB_HIGH_5XX_ERRORS: { title: 'Fix ALB 5XX Errors', description: (d) => `มี HTTP 5XX รวม ${d.http_5xx} ครั้งใน 7 วัน → Target Group มีปัญหา รีบตรวจสอบ`, severity: 'High' },
    CLB_MIGRATE_TO_ALB: { title: 'Migrate Classic LB to ALB', description: () => `ใช้ Classic Load Balancer รุ่นเก่า → ย้ายมา ALB/NLB เพื่อประสิทธิภาพและราคาที่ดีขึ้น`, severity: 'Medium' },
}

// ---- Service icon & color map ----
const SERVICE_META: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
    EC2:     { icon: Server,       color: 'text-indigo-500',  bg: 'bg-indigo-50 dark:bg-indigo-950/30' },
    EBS:     { icon: Archive,      color: 'text-blue-500',    bg: 'bg-blue-50 dark:bg-blue-950/30' },
    EC2_EIP: { icon: Network,      color: 'text-teal-500',    bg: 'bg-teal-50 dark:bg-teal-950/30' },
    EC2_DT:  { icon: Network,      color: 'text-orange-500',  bg: 'bg-orange-50 dark:bg-orange-950/30' },
    EBS_SNAPSHOT: { icon: Archive, color: 'text-blue-400',    bg: 'bg-blue-50 dark:bg-blue-950/30' },
    RDS:     { icon: Database,     color: 'text-yellow-500',  bg: 'bg-yellow-50 dark:bg-yellow-950/30' },
    S3:      { icon: Archive,      color: 'text-green-500',   bg: 'bg-green-50 dark:bg-green-950/30' },
    Lambda:  { icon: Zap,          color: 'text-purple-500',  bg: 'bg-purple-50 dark:bg-purple-950/30' },
    ALB:     { icon: LoaderCircle, color: 'text-red-500',     bg: 'bg-red-50 dark:bg-red-950/30' },
}

const SERVICE_ORDER = ['EC2', 'RDS', 'S3', 'Lambda', 'ALB', 'EBS', 'EC2_EIP', 'EC2_DT', 'EBS_SNAPSHOT']

const getSeverityFromConfidence = (confidence: number | null): 'High' | 'Medium' | 'Low' => {
    if (!confidence) return 'Low'
    if (confidence >= 0.9) return 'High'
    if (confidence >= 0.75) return 'Medium'
    return 'Low'
}

// ---- Detail panel ----
function DetailPanel({ rec }: { rec: RecommendationItem }) {
    const entries = Object.entries(rec.details).filter(([, v]) => v !== null && v !== undefined)
    return (
        <div className="mt-3 pt-3 border-t border-border space-y-3 text-sm">
            {/* Metrics from details */}
            {entries.length > 0 && (
                <div>
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Metrics</p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                        {entries.map(([k, v]) => (
                            <div key={k} className="bg-muted/60 rounded-lg px-3 py-2">
                                <p className="text-xs text-muted-foreground capitalize">{k.replace(/_/g, ' ')}</p>
                                <p className="font-semibold mt-0.5">
                                    {typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(v)}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Resource info */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div>
                    <p className="text-muted-foreground">Account ID</p>
                    <code className="font-mono text-xs">{rec.account_id}</code>
                </div>
                <div>
                    <p className="text-muted-foreground">Region</p>
                    <p className="font-medium">{rec.region}</p>
                </div>
                <div>
                    <p className="text-muted-foreground">Resource</p>
                    <code className="font-mono text-xs break-all">{rec.resource_key}</code>
                </div>
                <div>
                    <p className="text-muted-foreground">Confidence</p>
                    <p className="font-medium">{((rec.confidence ?? 0) * 100).toFixed(0)}%</p>
                </div>
            </div>
        </div>
    )
}

// ---- Recommendation card ----
function RecCard({ rec }: { rec: RecommendationItem }) {
    const [expanded, setExpanded] = useState(false)
    const label = REC_TYPE_LABELS[rec.rec_type]
    const severity = label?.severity ?? getSeverityFromConfidence(rec.confidence)
    const title = label?.title ?? rec.rec_type
    const description = label ? label.description(rec.details) : `Resource: ${rec.resource_key}`

    return (
        <Card
            className={`transition-all cursor-pointer ${expanded ? 'border-primary/40 shadow-sm' : 'hover:border-muted-foreground/30'}`}
            onClick={() => setExpanded(e => !e)}
        >
            <div className="p-4">
                {/* Top row */}
                <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                            <h3 className="font-semibold">{title}</h3>
                            <Badge variant={severity === 'High' ? 'destructive' : 'secondary'} className="text-xs">{severity}</Badge>
                            <Badge variant="outline" className="text-xs text-muted-foreground">{rec.region}</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">{description}</p>
                        <code className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded mt-1 inline-block max-w-full truncate">
                            {rec.resource_key}
                        </code>
                    </div>

                    {/* Right side */}
                    <div className="flex flex-col items-end gap-2 shrink-0">
                        {rec.est_saving_usd ? (
                            <div className="flex items-center gap-1 text-green-600 font-bold text-sm whitespace-nowrap">
                                <TrendingDown className="h-4 w-4" />
                                Save ${rec.est_saving_usd.toFixed(0)}/mo
                            </div>
                        ) : (
                            <span className="text-xs text-muted-foreground">
                                {((rec.confidence ?? 0) * 100).toFixed(0)}% confidence
                            </span>
                        )}
                        {expanded
                            ? <ChevronDown className="h-4 w-4 text-muted-foreground" />
                            : <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        }
                    </div>
                </div>

                {/* Expandable detail */}
                {expanded && <DetailPanel rec={rec} />}
            </div>
        </Card>
    )
}

// ---- Service group ----
function ServiceGroup({ service, items }: { service: string; items: RecommendationItem[] }) {
    const [collapsed, setCollapsed] = useState(false)
    const meta = SERVICE_META[service] ?? { icon: Info, color: 'text-muted-foreground', bg: 'bg-muted/30' }
    const Icon = meta.icon
    const totalSaving = items.reduce((s, r) => s + (r.est_saving_usd ?? 0), 0)

    return (
        <div className="space-y-2">
            {/* Group header */}
            <button
                onClick={() => setCollapsed(c => !c)}
                className="flex items-center gap-3 w-full text-left group"
            >
                <div className={`p-1.5 rounded-lg ${meta.bg}`}>
                    <Icon className={`h-4 w-4 ${meta.color}`} />
                </div>
                <span className="font-semibold text-base">{service}</span>
                <span className="text-sm text-muted-foreground">
                    {items.length} recommendation{items.length !== 1 ? 's' : ''}
                </span>
                {totalSaving > 0 && (
                    <span className="ml-auto text-sm font-semibold text-green-600">
                        ${totalSaving.toFixed(0)}/mo potential savings
                    </span>
                )}
                {collapsed
                    ? <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    : <ChevronDown className="h-4 w-4 text-muted-foreground" />
                }
            </button>

            {/* Cards */}
            {!collapsed && (
                <div className="space-y-2 pl-4 border-l-2 border-border ml-4">
                    {items.map(rec => <RecCard key={rec.rec_id} rec={rec} />)}
                </div>
            )}
        </div>
    )
}

// ---- Main Page ----
export default function Recommend() {
    const [recommendations, setRecommendations] = useState<RecommendationItem[]>([])
    const [loading, setLoading] = useState(true)
    const [generating, setGenerating] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchRecommendations = async () => {
        setLoading(true)
        setError(null)
        try {
            const data = await api.recommendations.list()
            setRecommendations(data)
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to load recommendations')
        } finally {
            setLoading(false)
        }
    }

    const handleGenerate = async () => {
        setGenerating(true)
        setError(null)
        try {
            await api.recommendations.generate()
            await fetchRecommendations()
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Analysis failed')
        } finally {
            setGenerating(false)
        }
    }

    useEffect(() => { fetchRecommendations() }, [])

    // Group by service, sorted by predefined order
    const grouped = useMemo(() => {
        const map: Record<string, RecommendationItem[]> = {}
        recommendations.forEach(r => {
            if (!map[r.service]) map[r.service] = []
            map[r.service].push(r)
        })
        // Sort: known services first, then alphabetical for the rest
        const sorted = Object.keys(map).sort((a, b) => {
            const ai = SERVICE_ORDER.indexOf(a)
            const bi = SERVICE_ORDER.indexOf(b)
            if (ai === -1 && bi === -1) return a.localeCompare(b)
            if (ai === -1) return 1
            if (bi === -1) return -1
            return ai - bi
        })
        return sorted.map(svc => ({ service: svc, items: map[svc] }))
    }, [recommendations])

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight text-primary">Recommendations</h2>
                    <p className="text-muted-foreground">Actionable insights to optimize cost and performance.</p>
                </div>
                <div className="flex items-center gap-2">
                    <Button asChild variant="outline" size="sm">
                        <Link to="/simulation">
                            <FlaskConical className="h-4 w-4 mr-2" />
                            View Simulation
                            <ArrowRight className="h-4 w-4 ml-1" />
                        </Link>
                    </Button>
                    <Button onClick={handleGenerate} disabled={generating} variant="outline" size="sm">
                        {generating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                        {generating ? 'Analyzing...' : 'Refresh Analysis'}
                    </Button>
                </div>
            </div>

            {/* Content */}
            {loading ? (
                <div className="flex items-center justify-center py-20 text-muted-foreground">
                    <Loader2 className="h-6 w-6 animate-spin mr-2" />
                    Loading recommendations...
                </div>
            ) : error ? (
                <Card className="p-6 text-center text-destructive">{error}</Card>
            ) : recommendations.length === 0 ? (
                <Card className="p-10 text-center text-muted-foreground">
                    <p className="font-semibold text-lg mb-1">No recommendations found</p>
                    <p className="text-sm">Click "Refresh Analysis" to analyze your latest cloud data.</p>
                </Card>
            ) : (
                <div className="space-y-8">
                    {grouped.map(({ service, items }) => (
                        <ServiceGroup key={service} service={service} items={items} />
                    ))}
                </div>
            )}
        </div>
    )
}
