import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip, Legend } from "recharts"

const data = [
    { name: "EC2", cost: 4000 },
    { name: "RDS", cost: 3000 },
    { name: "S3", cost: 2000 },
    { name: "Lambda", cost: 2780 },
    { name: "Other", cost: 1890 },
]

export default function CostAnalysis() {
    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-3xl font-bold tracking-tight text-primary">Cost Analysis</h2>
                <p className="text-muted-foreground">Detailed breakdown of your cloud infrastructure costs.</p>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 items-end">
                <Button variant="outline">Last 7 Days</Button>
                <Button variant="default">Last 30 Days</Button>
                <Button variant="outline">Last Quarter</Button>
                <Button variant="outline">Year to Date</Button>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Cost by Service</CardTitle>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={400}>
                        <BarChart data={data} layout="vertical">
                            <XAxis type="number" hide />
                            <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 14 }} />
                            <Tooltip formatter={(value) => `$${value}`} />
                            <Legend />
                            <Bar dataKey="cost" fill="var(--primary)" barSize={40} radius={[0, 4, 4, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>
        </div>
    )
}
