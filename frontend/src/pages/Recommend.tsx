import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

export default function Recommend() {
    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-3xl font-bold tracking-tight text-primary">Recommendations</h2>
                <p className="text-muted-foreground">Actionable insights to optimize cost and performance.</p>
            </div>

            <div className="space-y-4">
                {[
                    { title: "Resize EC2 Instance", desc: "Instance i-0x83d2 is underutilized (5% CPU). Suggest moving to t3.small.", savings: "$45/mo", severity: "High" },
                    { title: "Delete Unused EBS Volume", desc: "Volume vol-0x23a1 hasn't been attached for 30 days.", savings: "$12/mo", severity: "Medium" },
                    { title: "Purchase Reserved Instances", desc: "Consistent usage detected for db.m5.large. RI offers 30% discount.", savings: "$120/mo", severity: "Low" },
                ].map((rec, i) => (
                    <Card key={i} className="flex flex-col md:flex-row items-start md:items-center justify-between p-2">
                        <div className="flex-1 p-4">
                            <div className="flex items-center gap-2 mb-1">
                                <h3 className="font-semibold text-lg">{rec.title}</h3>
                                <Badge variant={rec.severity === 'High' ? 'destructive' : 'secondary'}>{rec.severity}</Badge>
                            </div>
                            <p className="text-muted-foreground text-sm">{rec.desc}</p>
                        </div>

                        <div className="p-4 flex flex-col items-end gap-2 min-w-[150px]">
                            <div className="text-green-600 font-bold mb-1">Save {rec.savings}</div>
                            <div className="flex gap-2">
                                <Button size="sm" variant="outline">Ignore</Button>
                                <Button size="sm">Apply</Button>
                            </div>
                        </div>
                    </Card>
                ))}
            </div>
        </div>
    )
}
