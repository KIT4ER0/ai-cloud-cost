import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, Legend } from "recharts"

const data = [
    { month: "Jan", actual: 4000, forecast: 4000 },
    { month: "Feb", actual: 3000, forecast: 3200 },
    { month: "Mar", actual: 2000, forecast: 2500 },
    { month: "Apr", actual: 2780, forecast: 2800 },
    { month: "May", actual: 1890, forecast: 2000 },
    { month: "Jun", actual: 2390, forecast: 2400 },
    { month: "Jul", forecast: 3000 },
    { month: "Aug", forecast: 3400 },
    { month: "Sep", forecast: 3600 },
]

export default function ForecastCost() {
    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-3xl font-bold tracking-tight text-primary">Cost Forecast</h2>
                <p className="text-muted-foreground">AI-powered predictions for future spending.</p>
            </div>

            <div className="flex gap-4">
                <Card className="w-full md:w-1/3">
                    <CardHeader>
                        <CardTitle>Projected Spend</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold text-primary">$15,400</div>
                        <p className="text-sm text-muted-foreground">Next Month Estimate</p>
                    </CardContent>
                </Card>
                <Card className="w-full md:w-1/3">
                    <CardHeader>
                        <CardTitle>Confidence Level</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-3xl font-bold text-green-600">94%</div>
                        <p className="text-sm text-muted-foreground">Based on historical data</p>
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle>6-Month Forecast</CardTitle>
                    <Button size="sm" variant="outline">Run "What-if" Scenario</Button>
                </CardHeader>
                <CardContent>
                    <ResponsiveContainer width="100%" height={400}>
                        <LineChart data={data}>
                            <XAxis dataKey="month" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(value) => `$${value}`} />
                            <Tooltip />
                            <Legend />
                            <Line type="monotone" dataKey="actual" stroke="#888888" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 8 }} />
                            <Line type="monotone" dataKey="forecast" stroke="var(--primary)" strokeWidth={2} strokeDasharray="5 5" dot={{ r: 4 }} />
                        </LineChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>
        </div>
    )
}
