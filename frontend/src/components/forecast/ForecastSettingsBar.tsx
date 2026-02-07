import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Calendar, Map, Server, Filter } from 'lucide-react'
import type { ForecastSettings, BaselinePeriod, ForecastHorizon, Granularity, AWSService, AWSRegion } from '@/types/forecast'
import { AWS_SERVICES, AWS_REGIONS } from '@/types/forecast'

interface ForecastSettingsBarProps {
    settings: ForecastSettings
    onSettingsChange: (settings: ForecastSettings) => void
}

export function ForecastSettingsBar({ settings, onSettingsChange }: ForecastSettingsBarProps) {
    const handleBaselineChange = (period: BaselinePeriod) => {
        onSettingsChange({ ...settings, baselinePeriod: period })
    }

    const handleHorizonChange = (horizon: ForecastHorizon) => {
        onSettingsChange({ ...settings, forecastHorizon: horizon })
    }

    const handleGranularityChange = (granularity: Granularity) => {
        onSettingsChange({ ...settings, granularity: granularity })
    }

    const handleServiceToggle = (service: AWSService) => {
        const newServices = settings.selectedServices.includes(service)
            ? settings.selectedServices.filter(s => s !== service)
            : [...settings.selectedServices, service]
        onSettingsChange({ ...settings, selectedServices: newServices })
    }

    const handleRegionChange = (region: AWSRegion) => {
        onSettingsChange({ ...settings, selectedRegions: [region] })
    }

    return (
        <Card className="bg-slate-50/50">
            <CardContent className="py-4">
                <div className="flex flex-wrap items-center gap-6">
                    {/* Baseline Period */}
                    <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium text-muted-foreground">Baseline:</span>
                        <div className="flex gap-1 bg-white rounded-lg p-1 border">
                            {(['3M', '6M', '12M'] as BaselinePeriod[]).map((period) => (
                                <Button
                                    key={period}
                                    variant={settings.baselinePeriod === period ? 'default' : 'ghost'}
                                    size="sm"
                                    className="h-7 px-3 text-xs"
                                    onClick={() => handleBaselineChange(period)}
                                >
                                    {period}
                                </Button>
                            ))}
                        </div>
                    </div>

                    {/* Forecast Horizon */}
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-muted-foreground">Horizon:</span>
                        <Select value={settings.forecastHorizon} onValueChange={handleHorizonChange}>
                            <SelectTrigger className="w-24 h-8 bg-white">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="1M">1 Month</SelectItem>
                                <SelectItem value="3M">3 Months</SelectItem>
                                <SelectItem value="6M">6 Months</SelectItem>
                                <SelectItem value="12M">12 Months</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Granularity */}
                    <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-muted-foreground">View:</span>
                        <div className="flex gap-1 bg-white rounded-lg p-1 border">
                            {([{ value: 'monthly', label: 'Monthly' }, { value: 'weekly', label: 'Weekly' }] as const).map(({ value, label }) => (
                                <Button
                                    key={value}
                                    variant={settings.granularity === value ? 'default' : 'ghost'}
                                    size="sm"
                                    className="h-7 px-3 text-xs"
                                    onClick={() => handleGranularityChange(value)}
                                >
                                    {label}
                                </Button>
                            ))}
                        </div>
                    </div>

                    {/* Services Multi-select */}
                    <div className="flex items-center gap-2">
                        <Server className="h-4 w-4 text-muted-foreground" />
                        <Select>
                            <SelectTrigger className="w-32 h-8 bg-white">
                                <Filter className="h-3 w-3 mr-1" />
                                <span className="text-xs">
                                    {settings.selectedServices.length === AWS_SERVICES.length
                                        ? 'All Services'
                                        : `${settings.selectedServices.length} Services`}
                                </span>
                            </SelectTrigger>
                            <SelectContent>
                                <div className="p-2 space-y-2">
                                    {AWS_SERVICES.map((service) => (
                                        <div key={service} className="flex items-center gap-2">
                                            <Checkbox
                                                id={`service-${service}`}
                                                checked={settings.selectedServices.includes(service)}
                                                onCheckedChange={() => handleServiceToggle(service)}
                                            />
                                            <label htmlFor={`service-${service}`} className="text-sm cursor-pointer">
                                                {service}
                                            </label>
                                        </div>
                                    ))}
                                </div>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Region */}
                    <div className="flex items-center gap-2">
                        <Map className="h-4 w-4 text-muted-foreground" />
                        <Select value={settings.selectedRegions[0]} onValueChange={handleRegionChange}>
                            <SelectTrigger className="w-44 h-8 bg-white">
                                <SelectValue placeholder="Select Region" />
                            </SelectTrigger>
                            <SelectContent>
                                {AWS_REGIONS.map((region) => (
                                    <SelectItem key={region.id} value={region.id}>
                                        {region.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}
