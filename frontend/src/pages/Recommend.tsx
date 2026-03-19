import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Play, Check, X, TrendingDown, ArrowRight, RefreshCw, Loader2 } from 'lucide-react'
import { useSimulationStore } from '@/store/simulation-store'
import { api } from '@/lib/api'

// ---- Types จาก Backend Schema ----
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

// แปลง rec_type ให้เป็นชื่อที่อ่านง่าย
const REC_TYPE_LABELS: Record<string, { title: string; description: (d: Record<string, unknown>) => string; severity: 'High' | 'Medium' | 'Low' }> = {
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

const getSeverityFromConfidence = (confidence: number | null): 'High' | 'Medium' | 'Low' => {
    if (!confidence) return 'Low'
    if (confidence >= 0.9) return 'High'
    if (confidence >= 0.75) return 'Medium'
    return 'Low'
}

export default function Recommend() {
    const { simulatedItems, toggleSimulation, removeSimulation, resetSimulation, isSimulated } = useSimulationStore()
    const [recommendations, setRecommendations] = useState<RecommendationItem[]>([])
    const [loading, setLoading] = useState(true)
    const [generating, setGenerating] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const totalSavings = simulatedItems.reduce((sum, item) => sum + item.savingsPerMonth, 0)
    const hasSimulations = simulatedItems.length > 0

    const fetchRecommendations = async () => {
        setLoading(true)
        setError(null)
        try {
            const data = await api.recommendations.list()
            setRecommendations(data)
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'ดึงข้อมูลไม่สำเร็จ')
        } finally {
            setLoading(false)
        }
    }

    const handleGenerate = async () => {
        setGenerating(true)
        setError(null)
        // Debug: ตรวจสอบ token ก่อนส่ง request
        const token = localStorage.getItem('token')
        console.log('[Recommend] Token exists:', !!token, '| Length:', token?.length)
        try {
            await api.recommendations.generate()
            // รอให้ backend รันเสร็จแล้ว fetch ทันทีแบบไม่ต้องดีเลย์ 
            await fetchRecommendations()
        } catch (e: unknown) {
            console.error('[Recommend] Generate error:', e)
            setError(e instanceof Error ? e.message : 'Generate ไม่สำเร็จ')
        } finally {
            setGenerating(false)
        }
    }

    useEffect(() => {
        fetchRecommendations()
    }, [])

    const handleSimulate = (rec: RecommendationItem) => {
        const label = REC_TYPE_LABELS[rec.rec_type]
        toggleSimulation({
            id: String(rec.rec_id),
            title: label?.title ?? rec.rec_type,
            savingsPerMonth: rec.est_saving_usd ?? 0
        })
    }

    const handleIgnore = (rec: RecommendationItem) => {
        if (isSimulated(String(rec.rec_id))) {
            removeSimulation(String(rec.rec_id))
        }
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight text-primary">Recommendations</h2>
                    <p className="text-muted-foreground">Actionable insights to optimize cost and performance.</p>
                </div>
                <Button onClick={handleGenerate} disabled={generating} variant="outline" size="sm">
                    {generating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                    {generating ? 'Analyzing...' : 'Refresh Analysis'}
                </Button>
            </div>

            {/* Simulation Banner */}
            {hasSimulations && (
                <Card className="border-primary/50 bg-primary/5 p-4">
                    <div className="flex items-center justify-between w-full">
                        <div className="flex items-center gap-3">
                            <div className="flex items-center gap-2">
                                <Play className="h-4 w-4 text-primary" />
                                <span className="font-semibold text-primary">Simulation Mode ON</span>
                            </div>
                            <span className="text-sm">
                                {simulatedItems.length} action{simulatedItems.length !== 1 ? 's' : ''} simulated · Estimated saving{' '}
                                <span className="font-semibold text-green-600">${totalSavings}/mo</span>
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Button variant="ghost" size="sm" onClick={resetSimulation} className="text-muted-foreground hover:text-foreground">
                                <X className="h-4 w-4 mr-1" />Reset
                            </Button>
                            <Button asChild size="sm">
                                <Link to="/forecast-cost">
                                    View impact in Forecast
                                    <ArrowRight className="h-4 w-4 ml-1" />
                                </Link>
                            </Button>
                        </div>
                    </div>
                </Card>
            )}

            {/* Recommendation List */}
            <div className="space-y-4">
                {loading ? (
                    <div className="flex items-center justify-center py-16 text-muted-foreground">
                        <Loader2 className="h-6 w-6 animate-spin mr-2" />
                        Loading recommendations...
                    </div>
                ) : error ? (
                    <Card className="p-6 text-center text-destructive">{error}</Card>
                ) : recommendations.length === 0 ? (
                    <Card className="p-10 text-center text-muted-foreground">
                        <p className="font-semibold text-lg mb-1">No recommendations found</p>
                        <p className="text-sm">กด "Refresh Analysis" เพื่อให้ระบบวิเคราะห์ข้อมูลล่าสุดจาก Cloud ของคุณอีกครั้ง</p>
                    </Card>
                ) : (
                    recommendations.map((rec) => {
                        const simulated = isSimulated(String(rec.rec_id))
                        const label = REC_TYPE_LABELS[rec.rec_type]
                        const severity = label?.severity ?? getSeverityFromConfidence(rec.confidence)
                        const title = label?.title ?? rec.rec_type
                        const description = label ? label.description(rec.details) : `Resource: ${rec.resource_key}`

                        return (
                            <Card key={rec.rec_id} className={`flex flex-col md:flex-row items-start md:items-center justify-between p-2 transition-colors ${simulated ? 'border-primary/50 bg-primary/5' : ''}`}>
                                <div className="flex-1 p-4">
                                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                                        <h3 className="font-semibold text-lg">{title}</h3>
                                        <Badge variant={severity === 'High' ? 'destructive' : 'secondary'}>{severity}</Badge>
                                        <Badge variant="outline" className="text-xs text-muted-foreground">{rec.service}</Badge>
                                        <Badge variant="outline" className="text-xs text-muted-foreground">{rec.region}</Badge>
                                        {simulated && (
                                            <Badge variant="outline" className="border-primary text-primary">
                                                <Check className="h-3 w-3 mr-1" />Simulated
                                            </Badge>
                                        )}
                                    </div>
                                    <p className="text-muted-foreground text-sm">{description}</p>
                                    <p className="text-xs text-muted-foreground mt-1">Resource: <code className="bg-muted px-1 rounded">{rec.resource_key}</code></p>
                                </div>

                                <div className="p-4 flex flex-col items-end gap-2 min-w-[150px]">
                                    {rec.est_saving_usd ? (
                                        <div className="flex items-center gap-1 text-green-600 font-bold mb-1">
                                            <TrendingDown className="h-4 w-4" />
                                            Save ${rec.est_saving_usd.toFixed(0)}/mo
                                        </div>
                                    ) : (
                                        <div className="text-xs text-muted-foreground mb-1">
                                            Confidence {((rec.confidence ?? 0) * 100).toFixed(0)}%
                                        </div>
                                    )}
                                    <div className="flex gap-2">
                                        <Button size="sm" variant="outline" onClick={() => handleIgnore(rec)}>Ignore</Button>
                                        <Button size="sm" variant={simulated ? 'secondary' : 'default'} onClick={() => handleSimulate(rec)}>
                                            {simulated ? <><Check className="h-4 w-4 mr-1" />Simulated</> : <><Play className="h-4 w-4 mr-1" />Simulate</>}
                                        </Button>
                                    </div>
                                </div>
                            </Card>
                        )
                    })
                )}
            </div>
        </div>
    )
}
