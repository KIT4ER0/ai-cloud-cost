import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { AreaChart, Area, ResponsiveContainer, Tooltip } from "recharts"

const cpuData = [
    { time: "00:00", value: 20 },
    { time: "04:00", value: 40 },
    { time: "08:00", value: 30 },
    { time: "12:00", value: 70 },
    { time: "16:00", value: 50 },
    { time: "20:00", value: 60 },
    { time: "24:00", value: 45 },
]

const services = ["EC2", "Lambda", "S3", "RDS"]

export default function Monitoring() {
    const [selectedService, setSelectedService] = useState<string>("EC2")

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
                        onClick={() => setSelectedService(service)}
                        className="rounded-full px-6"
                    >
                        {service}
                    </Button>
                ))}
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                        <CardTitle className="text-sm font-medium">CPU Usage</CardTitle>
                        <Badge variant="default">Normal</Badge>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">45%</div>
                        <div className="h-[80px] mt-4">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={cpuData}>
                                    <Tooltip />
                                    <Area type="monotone" dataKey="value" stroke="var(--primary)" fill="var(--primary)" fillOpacity={0.2} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                        <CardTitle className="text-sm font-medium">Memory Usage</CardTitle>
                        <Badge variant="outline">Warning</Badge>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">82%</div>
                        <div className="h-[80px] mt-4 flex items-end">
                            <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
                                <div className="bg-orange-500 h-full w-[82%]"></div>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                        <CardTitle className="text-sm font-medium">Network In/Out</CardTitle>
                        <Badge variant="default">Healthy</Badge>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">1.2 GB/s</div>
                        <p className="text-xs text-muted-foreground">Peak: 2.1 GB/s</p>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
