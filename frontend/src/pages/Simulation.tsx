import { useState, useEffect, useMemo } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
    FlaskConical,
    TrendingDown,
    CheckSquare,
    Square,
    Loader2,
    RefreshCw,
    DollarSign,
    Zap,
    AlertTriangle,
} from 'lucide-react'
import { api } from '@/lib/api'

// ─── Types ───────────────────────────────────────────────────────────────────

interface SimPreviewItem {
    rec_id: number
    service: string
    resource_key: string
    rec_type: string
    est_saving_usd: number
    confidence: number
}

interface SimPreviewResponse {
    total_savings_usd: number
    items: SimPreviewItem[]
    by_service: Record<string, number>
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const SERVICE_COLORS: Record<string, string> = {
    EC2: '#6366f1',
    RDS: '#f59e0b',
    S3: '#10b981',
    Lambda: '#8b5cf6',
    ALB: '#ef4444',
    EBS: '#3b82f6',
    EC2_EIP: '#14b8a6',
    EC2_DT: '#f97316',
}

const REC_TYPE_LABELS: Record<string, { title: string; description: (item: SimPreviewItem) => string }> = {
    EC2_RIGHTSIZE_CPU_LOW: { title: 'Resize EC2 Instance', description: () => 'CPU ต่ำกว่า threshold → ลดขนาดเครื่อง' },
    EC2_IDLE_STOPPED: { title: 'Terminate Idle EC2', description: () => 'เครื่องถูกปิดทิ้งไว้ → กินค่า EBS เปล่าๆ' },
    EC2_EIP_UNASSOCIATED: { title: 'Release Unused Elastic IP', description: () => 'IP ว่างงาน → คืน IP เพื่อลดค่า' },
    EC2_EBS_UNATTACHED: { title: 'Delete Unattached EBS Volume', description: () => 'EBS Volume ไม่ได้ต่ออยู่กับเครื่องไหนเลย' },
    EC2_EBS_SNAPSHOT_OLD: { title: 'Delete Old EBS Snapshot', description: () => 'Snapshot เก่า → ลบเพื่อประหยัดค่า Storage' },
    RDS_RIGHTSIZE_CPU_LOW: { title: 'Downsize RDS Instance', description: () => 'CPU ต่ำ 7 วัน → ลดสเปคเครื่อง DB' },
    RDS_IDLE_STOP: { title: 'Stop Idle RDS Instance', description: () => 'Connection น้อยมาก → หยุดชั่วคราว' },
    RDS_HIGH_SNAPSHOT_COST: { title: 'Review RDS Snapshots', description: () => 'Snapshot สะสมเยอะ → ลบ Snapshot เก่า' },
    RDS_MEMORY_BOTTLENECK: { title: 'Upsize RDS (Memory Issue)', description: () => 'RAM ล้นจนใช้ Swap Disk' },
    S3_LIFECYCLE_COLD: { title: 'Set S3 Lifecycle Policy', description: () => 'ไม่มีการเข้าถึง 30 วัน → ย้ายไป Glacier' },
    S3_ARCHIVE_PATTERN: { title: 'Direct S3 Writes to Glacier', description: () => 'Upload แต่ไม่เคยอ่าน → เขียนตรงไป Glacier' },
    S3_HUGE_ABANDONED: { title: 'Review Inactive S3 Bucket', description: () => 'Bucket ใหญ่ไม่มีกิจกรรม 30 วัน' },
    S3_EMPTY_BUCKET: { title: 'Delete Empty S3 Bucket', description: () => 'Bucket ว่างเปล่า → ลบทิ้ง' },
    LAMBDA_OPTIMIZE_DURATION: { title: 'Optimize Lambda Code', description: () => 'Duration นาน + ถูกเรียกบ่อย → ปรับโค้ด' },
    LAMBDA_HIGH_ERROR_WASTE: { title: 'Fix Lambda Errors', description: () => 'Error เยอะ → เสียเงินค่ารันทั้งที่โค้ดพัง' },
    LAMBDA_UNUSED_CLEANUP: { title: 'Delete Unused Lambda', description: () => 'ไม่มี Invocation 30 วัน → ลบ' },
    DT_CROSS_AZ_WASTE: { title: 'Reduce Cross-AZ Traffic', description: () => 'ข้อมูลวิ่งข้าม AZ → รวม resource ไว้ใน AZ เดียวกัน' },
    DT_HIGH_INTERNET_EGRESS: { title: 'Add CDN / Caching Layer', description: () => 'ส่งข้อมูลออก Internet เยอะ → ใช้ CloudFront' },
    ALB_IDLE_DELETE: { title: 'Delete Idle Load Balancer', description: () => 'Request น้อยมาก 7 วัน → ลบ ALB' },
    ALB_HIGH_5XX_ERRORS: { title: 'Fix ALB 5XX Errors', description: () => 'HTTP 5XX เยอะ → Target Group มีปัญหา' },
    CLB_MIGRATE_TO_ALB: { title: 'Migrate Classic LB to ALB', description: () => 'ใช้ Classic LB รุ่นเก่า → ย้ายมา ALB/NLB' },
}

// Simple bar chart component
function SavingsBar({ label, value, maxValue, color }: { label: string; value: number; maxValue: number; color: string }) {
    const pct = maxValue > 0 ? (value / maxValue) * 100 : 0
    return (
        <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground w-20 shrink-0 text-right">{label}</span>
            <div className="flex-1 rounded-full bg-muted h-3 overflow-hidden">
                <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${pct}%`, backgroundColor: color }}
                />
            </div>
            <span className="text-sm font-semibold w-16 text-right">${value.toFixed(0)}/mo</span>
        </div>
    )
}

// Donut chart (SVG)
function DonutChart({ data }: { data: Array<{ label: string; value: number; color: string }> }) {
    const total = data.reduce((s, d) => s + d.value, 0)
    if (total === 0) return null

    let offset = 0
    const R = 50
    const circumference = 2 * Math.PI * R
    const segments = data.map((d) => {
        const pct = d.value / total
        const seg = { ...d, pct, offset }
        offset += pct
        return seg
    })

    return (
        <div className="flex items-center gap-6 flex-wrap">
            <svg viewBox="0 0 120 120" className="w-28 h-28 shrink-0 -rotate-90">
                <circle cx={60} cy={60} r={R} fill="none" stroke="#1f2937" strokeWidth={18} />
                {segments.map((seg, i) => (
                    <circle
                        key={i}
                        cx={60}
                        cy={60}
                        r={R}
                        fill="none"
                        stroke={seg.color}
                        strokeWidth={18}
                        strokeDasharray={`${seg.pct * circumference} ${circumference}`}
                        strokeDashoffset={-seg.offset * circumference}
                        className="transition-all duration-500"
                    />
                ))}
            </svg>
            <div className="flex flex-col gap-1.5">
                {segments.map((seg, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                        <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: seg.color }} />
                        <span className="text-muted-foreground">{seg.label}</span>
                        <span className="font-semibold ml-1">${seg.value.toFixed(0)}</span>
                    </div>
                ))}
            </div>
        </div>
    )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function Simulation() {
    const [data, setData] = useState<SimPreviewResponse | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [selected, setSelected] = useState<Set<number>>(new Set())

    const fetchData = async () => {
        setLoading(true)
        setError(null)
        try {
            const res = await api.simulation.preview()
            setData(res)
            // default: select all
            setSelected(new Set(res.items.map((i: SimPreviewItem) => i.rec_id)))
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to load simulation data')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => { fetchData() }, [])

    // ── Derived state ───────────────────────────────────────────────────────
    const allSelected = data ? selected.size === data.items.length : false

    const selectedSavings = useMemo(() => {
        if (!data) return 0
        return data.items
            .filter(i => selected.has(i.rec_id))
            .reduce((s, i) => s + i.est_saving_usd, 0)
    }, [data, selected])

    const selectedByService = useMemo(() => {
        if (!data) return {}
        const byService: Record<string, number> = {}
        data.items.filter(i => selected.has(i.rec_id)).forEach(i => {
            byService[i.service] = (byService[i.service] ?? 0) + i.est_saving_usd
        })
        return byService
    }, [data, selected])

    // group items by service
    const groupedItems = useMemo(() => {
        if (!data) return {}
        const groups: Record<string, SimPreviewItem[]> = {}
        data.items.forEach(i => {
            if (!groups[i.service]) groups[i.service] = []
            groups[i.service].push(i)
        })
        return groups
    }, [data])

    const maxServiceSaving = Math.max(...Object.values(selectedByService), 1)

    const donutData = Object.entries(selectedByService)
        .filter(([, v]) => v > 0)
        .map(([label, value]) => ({
            label,
            value,
            color: SERVICE_COLORS[label] ?? '#6366f1',
        }))

    // ── Handlers ────────────────────────────────────────────────────────────
    const toggleAll = () => {
        if (!data) return
        if (allSelected) setSelected(new Set())
        else setSelected(new Set(data.items.map(i => i.rec_id)))
    }

    const toggleItem = (id: number) => {
        setSelected(prev => {
            const next = new Set(prev)
            next.has(id) ? next.delete(id) : next.add(id)
            return next
        })
    }

    const toggleService = (service: string) => {
        if (!data) return
        const ids = data.items.filter(i => i.service === service).map(i => i.rec_id)
        const allIn = ids.every(id => selected.has(id))
        setSelected(prev => {
            const next = new Set(prev)
            if (allIn) ids.forEach(id => next.delete(id))
            else ids.forEach(id => next.add(id))
            return next
        })
    }

    // ── Render ──────────────────────────────────────────────────────────────
    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight text-primary flex items-center gap-2">
                        <FlaskConical className="h-7 w-7" />
                        Cost Simulation
                    </h2>
                    <p className="text-muted-foreground mt-1">
                        Select the recommendations you want to apply and see your projected cost savings in real time.
                    </p>
                </div>
                <Button onClick={fetchData} disabled={loading} variant="outline" size="sm">
                    {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                    Refresh
                </Button>
            </div>

            {loading ? (
                <div className="flex items-center justify-center py-24 text-muted-foreground">
                    <Loader2 className="h-6 w-6 animate-spin mr-2" />
                    Loading simulation data...
                </div>
            ) : error ? (
                <Card className="p-8 text-center">
                    <AlertTriangle className="h-8 w-8 text-destructive mx-auto mb-3" />
                    <p className="text-destructive font-medium">{error}</p>
                    <p className="text-sm text-muted-foreground mt-1">
                        Try clicking "Refresh Analysis" on the Recommendations page first to generate analysis data.
                    </p>
                </Card>
            ) : !data || data.items.length === 0 ? (
                <Card className="p-12 text-center text-muted-foreground">
                    <FlaskConical className="h-10 w-10 mx-auto mb-3 opacity-30" />
                    <p className="font-semibold text-lg mb-1">No Recommendations Found</p>
                    <p className="text-sm">Go to the Recommendations page and click "Refresh Analysis" to generate data.</p>
                </Card>
            ) : (
                <>
                    {/* ── Summary Banner ─────────────────────────────────── */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <Card className="p-5 border-primary/40 bg-primary/5 col-span-1 md:col-span-1">
                            <div className="flex items-center gap-3 mb-1">
                                <div className="p-2 rounded-lg bg-primary/15">
                                    <DollarSign className="h-5 w-5 text-primary" />
                                </div>
                                <span className="text-sm text-muted-foreground font-medium">Projected Monthly Savings</span>
                            </div>
                            <div className="text-4xl font-bold text-primary mt-2">
                                ${selectedSavings.toFixed(2)}
                            </div>
                            <div className="text-xs text-muted-foreground mt-1">
                                ≈ ${(selectedSavings * 12).toFixed(0)} / year
                            </div>
                        </Card>

                        <Card className="p-5 col-span-1">
                            <div className="flex items-center gap-3 mb-1">
                                <div className="p-2 rounded-lg bg-green-500/15">
                                    <Zap className="h-5 w-5 text-green-500" />
                                </div>
                                <span className="text-sm text-muted-foreground font-medium">Actions Selected</span>
                            </div>
                            <div className="text-4xl font-bold text-green-500 mt-2">
                                {selected.size}
                            </div>
                            <div className="text-xs text-muted-foreground mt-1">
                                out of {data.items.length} total actions
                            </div>
                        </Card>

                        <Card className="p-5 col-span-1">
                            <div className="flex items-center gap-3 mb-3">
                                <TrendingDown className="h-5 w-5 text-emerald-500" />
                                <span className="text-sm text-muted-foreground font-medium">Top Savings by Service</span>
                            </div>
                            <div className="space-y-2">
                                {Object.entries(selectedByService)
                                    .sort(([, a], [, b]) => b - a)
                                    .slice(0, 3)
                                    .map(([svc, val]) => (
                                        <div key={svc} className="flex justify-between text-sm">
                                            <span className="text-muted-foreground">{svc}</span>
                                            <span className="font-semibold">${val.toFixed(0)}/mo</span>
                                        </div>
                                    ))}
                            </div>
                        </Card>
                    </div>

                    {/* ── Charts Row ─────────────────────────────────────── */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Bar chart */}
                        <Card className="p-5">
                            <h3 className="font-semibold mb-4">Savings Breakdown by Service</h3>
                            <div className="space-y-3">
                                {Object.entries(selectedByService)
                                    .sort(([, a], [, b]) => b - a)
                                    .map(([svc, val]) => (
                                        <SavingsBar
                                            key={svc}
                                            label={svc}
                                            value={val}
                                            maxValue={maxServiceSaving}
                                            color={SERVICE_COLORS[svc] ?? '#6366f1'}
                                        />
                                    ))}
                                {Object.keys(selectedByService).length === 0 && (
                                    <p className="text-sm text-muted-foreground text-center py-4">
                                        Select at least one action to see the breakdown.
                                    </p>
                                )}
                            </div>
                        </Card>

                        {/* Donut chart */}
                        <Card className="p-5">
                            <h3 className="font-semibold mb-4">Proportion of Savings</h3>
                            {donutData.length > 0 ? (
                                <DonutChart data={donutData} />
                            ) : (
                                <p className="text-sm text-muted-foreground text-center py-8">
                                    Select an action to see the savings proportion.
                                </p>
                            )}
                        </Card>
                    </div>

                    {/* ── Recommendation List ────────────────────────────── */}
                    <Card className="p-5">
                        {/* Toolbar */}
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="font-semibold text-lg">Select Recommendations to Simulate</h3>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={toggleAll}
                                className="gap-2"
                            >
                                {allSelected ? <CheckSquare className="h-4 w-4 text-primary" /> : <Square className="h-4 w-4" />}
                                {allSelected ? 'Deselect All' : 'Select All'}
                            </Button>
                        </div>

                        {/* Groups */}
                        <div className="space-y-6">
                            {Object.entries(groupedItems).map(([service, items]) => {
                                const allSvcSelected = items.every(i => selected.has(i.rec_id))
                                const svcSaving = items
                                    .filter(i => selected.has(i.rec_id))
                                    .reduce((s, i) => s + i.est_saving_usd, 0)

                                return (
                                    <div key={service}>
                                        {/* Service header */}
                                        <button
                                            onClick={() => toggleService(service)}
                                            className="flex items-center gap-2 mb-2 w-full text-left group"
                                        >
                                            {allSvcSelected
                                                ? <CheckSquare className="h-4 w-4 text-primary shrink-0" />
                                                : <Square className="h-4 w-4 text-muted-foreground shrink-0" />
                                            }
                                            <span
                                                className="text-sm font-bold px-2 py-0.5 rounded-full"
                                                style={{
                                                    backgroundColor: `${SERVICE_COLORS[service] ?? '#6366f1'}25`,
                                                    color: SERVICE_COLORS[service] ?? '#6366f1',
                                                }}
                                            >
                                                {service}
                                            </span>
                                            <span className="text-xs text-muted-foreground">
                                                {items.length} action{items.length !== 1 ? 's' : ''}
                                            </span>
                                            {svcSaving > 0 && (
                                                <span className="ml-auto text-xs font-semibold text-green-600">
                                                    saves ${svcSaving.toFixed(0)}/mo
                                                </span>
                                            )}
                                        </button>

                                        {/* Recommendation rows */}
                                        <div className="space-y-2 pl-6">
                                            {items.map(item => {
                                                const isSelected = selected.has(item.rec_id)
                                                const label = REC_TYPE_LABELS[item.rec_type]

                                                return (
                                                    <button
                                                        key={item.rec_id}
                                                        onClick={() => toggleItem(item.rec_id)}
                                                        className={`w-full text-left rounded-lg border px-4 py-3 flex items-center gap-3 transition-colors ${isSelected
                                                            ? 'border-primary/50 bg-primary/5'
                                                            : 'border-border bg-background hover:bg-muted/50'
                                                            }`}
                                                    >
                                                        {isSelected
                                                            ? <CheckSquare className="h-4 w-4 text-primary shrink-0" />
                                                            : <Square className="h-4 w-4 text-muted-foreground shrink-0" />
                                                        }
                                                        <div className="flex-1 min-w-0">
                                                            <div className="flex items-center gap-2 flex-wrap">
                                                                <span className="font-medium text-sm">
                                                                    {label?.title ?? item.rec_type}
                                                                </span>
                                                                <Badge variant="outline" className="text-xs">
                                                                    {(item.confidence * 100).toFixed(0)}% confidence
                                                                </Badge>
                                                            </div>
                                                            <p className="text-xs text-muted-foreground mt-0.5 truncate">
                                                                {label?.description(item) ?? item.resource_key}
                                                            </p>
                                                            <code className="text-xs text-muted-foreground bg-muted px-1 rounded mt-0.5 inline-block truncate max-w-[260px]">
                                                                {item.resource_key}
                                                            </code>
                                                        </div>
                                                        {item.est_saving_usd > 0 && (
                                                            <div className="shrink-0 text-right">
                                                                <div className="flex items-center gap-1 text-green-600 font-bold text-sm">
                                                                    <TrendingDown className="h-3.5 w-3.5" />
                                                                    ${item.est_saving_usd.toFixed(0)}/mo
                                                                </div>
                                                            </div>
                                                        )}
                                                    </button>
                                                )
                                            })}
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    </Card>
                </>
            )}
        </div>
    )
}
