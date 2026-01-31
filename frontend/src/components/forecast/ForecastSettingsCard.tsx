import { useState, useEffect, useCallback } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Checkbox } from '@/components/ui/checkbox'
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import {
    Calendar,
    DollarSign,
    Globe,
    TrendingUp,
    Calculator,
    ChevronDown,
    X
} from 'lucide-react'
import type { ForecastSettings, ForecastMode } from '@/types/forecast'
import {
    AWS_REGIONS,
    QUICK_SELECT_OPTIONS,
    getMonthOptions
} from '@/lib/forecast-constants'

interface ForecastSettingsCardProps {
    settings: ForecastSettings
    onSettingsChange: (settings: ForecastSettings) => void
    onCalculate: () => void
    isCalculating?: boolean
}

export function ForecastSettingsCard({
    settings,
    onSettingsChange,
    onCalculate,
    isCalculating = false
}: ForecastSettingsCardProps) {
    const [isRegionDropdownOpen, setIsRegionDropdownOpen] = useState(false)
    const monthOptions = getMonthOptions()

    const updateSetting = useCallback(<K extends keyof ForecastSettings>(
        key: K,
        value: ForecastSettings[K]
    ) => {
        onSettingsChange({ ...settings, [key]: value })
    }, [settings, onSettingsChange])

    const handleQuickSelect = useCallback((months: number) => {
        const startMonth = new Date()
        startMonth.setMonth(startMonth.getMonth() + 1)
        startMonth.setDate(1)

        const endMonth = new Date(startMonth)
        endMonth.setMonth(endMonth.getMonth() + months - 1)

        onSettingsChange({
            ...settings,
            startMonth,
            endMonth
        })
    }, [settings, onSettingsChange])

    const handleDateChange = useCallback((type: 'start' | 'end', value: string) => {
        const [year, month] = value.split('-').map(Number)
        const date = new Date(year, month - 1, 1)

        if (type === 'start') {
            updateSetting('startMonth', date)
        } else {
            updateSetting('endMonth', date)
        }
    }, [updateSetting])

    const handleRegionToggle = useCallback((regionId: string, checked: boolean) => {
        const currentRegions = settings.selectedRegions
        let newRegions: string[]

        if (checked) {
            newRegions = [...currentRegions, regionId]
        } else {
            newRegions = currentRegions.filter(id => id !== regionId)
        }

        updateSetting('selectedRegions', newRegions)
    }, [settings.selectedRegions, updateSetting])

    const removeRegion = useCallback((regionId: string) => {
        const newRegions = settings.selectedRegions.filter(id => id !== regionId)
        updateSetting('selectedRegions', newRegions)
    }, [settings.selectedRegions, updateSetting])

    const dateToValue = (date: Date) => {
        return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
    }

    useEffect(() => {
        if (settings.realTimeCalculation) {
            const timer = setTimeout(() => {
                onCalculate()
            }, 500)
            return () => clearTimeout(timer)
        }
    }, [settings, settings.realTimeCalculation, onCalculate])

    return (
        <Card className="h-fit">
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Calculator className="h-5 w-5 text-primary" />
                    Forecast Settings
                </CardTitle>
                <CardDescription>
                    Configure parameters for predicting future AWS costs
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                {/* Section 1: Forecast Horizon */}
                <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-medium">
                        <Calendar className="h-4 w-4 text-muted-foreground" />
                        Forecast Horizon
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="start-month">Start Month</Label>
                            <Select
                                value={dateToValue(settings.startMonth)}
                                onValueChange={(v) => handleDateChange('start', v)}
                            >
                                <SelectTrigger id="start-month">
                                    <SelectValue placeholder="Select month" />
                                </SelectTrigger>
                                <SelectContent>
                                    {monthOptions.map(option => (
                                        <SelectItem key={option.value} value={option.value}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="end-month">End Month</Label>
                            <Select
                                value={dateToValue(settings.endMonth)}
                                onValueChange={(v) => handleDateChange('end', v)}
                            >
                                <SelectTrigger id="end-month">
                                    <SelectValue placeholder="Select month" />
                                </SelectTrigger>
                                <SelectContent>
                                    {monthOptions.map(option => (
                                        <SelectItem key={option.value} value={option.value}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        {QUICK_SELECT_OPTIONS.map(option => (
                            <Button
                                key={option.value}
                                variant="outline"
                                size="sm"
                                onClick={() => handleQuickSelect(option.value)}
                                className="text-xs"
                            >
                                {option.label}
                            </Button>
                        ))}
                    </div>
                </div>

                <Separator />

                {/* Section 2: Currency & Exchange Rate */}
                <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-medium">
                        <DollarSign className="h-4 w-4 text-muted-foreground" />
                        Currency & Exchange Rate
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label>Currency</Label>
                            <div className="flex gap-1 bg-muted p-1 rounded-lg">
                                <Button
                                    variant={settings.currency === 'USD' ? 'default' : 'ghost'}
                                    size="sm"
                                    className="flex-1"
                                    onClick={() => updateSetting('currency', 'USD')}
                                >
                                    USD
                                </Button>
                                <Button
                                    variant={settings.currency === 'THB' ? 'default' : 'ghost'}
                                    size="sm"
                                    className="flex-1"
                                    onClick={() => updateSetting('currency', 'THB')}
                                >
                                    THB
                                </Button>
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="exchange-rate">Exchange Rate</Label>
                            <div className="relative">
                                <Input
                                    id="exchange-rate"
                                    type="number"
                                    step="0.1"
                                    min="0"
                                    value={settings.exchangeRate}
                                    onChange={(e) => updateSetting('exchangeRate', parseFloat(e.target.value) || 0)}
                                    disabled={settings.currency === 'USD'}
                                    className="pr-16"
                                />
                                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                                    THB/USD
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <Separator />

                {/* Section 3: Multi-Region Selection */}
                <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-medium">
                        <Globe className="h-4 w-4 text-muted-foreground" />
                        AWS Regions
                    </div>
                    <p className="text-xs text-muted-foreground">
                        Note: Pricing varies by region. Average modifier will be applied.
                    </p>

                    <div className="relative">
                        <Button
                            variant="outline"
                            className="w-full justify-between"
                            onClick={() => setIsRegionDropdownOpen(!isRegionDropdownOpen)}
                        >
                            <span>Select regions ({settings.selectedRegions.length} selected)</span>
                            <ChevronDown className={`h-4 w-4 transition-transform ${isRegionDropdownOpen ? 'rotate-180' : ''}`} />
                        </Button>

                        {isRegionDropdownOpen && (
                            <div className="absolute z-50 w-full mt-1 bg-popover border rounded-md shadow-lg max-h-60 overflow-y-auto">
                                <div className="p-2 space-y-1">
                                    {AWS_REGIONS.map(region => (
                                        <label
                                            key={region.id}
                                            className="flex items-center gap-2 p-2 hover:bg-accent rounded cursor-pointer"
                                        >
                                            <Checkbox
                                                checked={settings.selectedRegions.includes(region.id)}
                                                onCheckedChange={(checked) =>
                                                    handleRegionToggle(region.id, checked === true)
                                                }
                                            />
                                            <div className="flex-1">
                                                <div className="text-sm">{region.name}</div>
                                                <div className="text-xs text-muted-foreground">
                                                    Modifier: {region.pricingModifier.toFixed(2)}x
                                                </div>
                                            </div>
                                        </label>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

                    {settings.selectedRegions.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                            {settings.selectedRegions.map(regionId => {
                                const region = AWS_REGIONS.find(r => r.id === regionId)
                                return (
                                    <Badge key={regionId} variant="secondary" className="gap-1">
                                        {region?.code || regionId}
                                        <button
                                            onClick={() => removeRegion(regionId)}
                                            className="ml-1 hover:text-destructive"
                                        >
                                            <X className="h-3 w-3" />
                                        </button>
                                    </Badge>
                                )
                            })}
                        </div>
                    )}
                </div>

                <Separator />

                {/* Section 4: Forecasting Mode */}
                <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm font-medium">
                        <TrendingUp className="h-4 w-4 text-muted-foreground" />
                        Forecasting Mode
                    </div>

                    <RadioGroup
                        value={settings.forecastMode}
                        onValueChange={(v) => updateSetting('forecastMode', v as ForecastMode)}
                        className="space-y-3"
                    >
                        <div className="flex items-start gap-3">
                            <RadioGroupItem value="static" id="mode-static" className="mt-1" />
                            <div className="space-y-1">
                                <Label htmlFor="mode-static" className="font-medium cursor-pointer">
                                    Static
                                </Label>
                                <p className="text-xs text-muted-foreground">
                                    Maintains current usage/spending levels
                                </p>
                            </div>
                        </div>

                        <div className="flex items-start gap-3">
                            <RadioGroupItem value="percentage" id="mode-percentage" className="mt-1" />
                            <div className="flex-1 space-y-2">
                                <Label htmlFor="mode-percentage" className="font-medium cursor-pointer">
                                    Percentage Growth/Decline
                                </Label>
                                <p className="text-xs text-muted-foreground">
                                    Apply monthly percentage change
                                </p>
                                {settings.forecastMode === 'percentage' && (
                                    <div className="flex items-center gap-2 mt-2">
                                        <Input
                                            type="number"
                                            value={settings.percentageGrowth}
                                            onChange={(e) => updateSetting('percentageGrowth', parseFloat(e.target.value) || 0)}
                                            className="w-24"
                                        />
                                        <span className="text-sm text-muted-foreground">% per month</span>
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="flex items-start gap-3">
                            <RadioGroupItem value="driver-based" id="mode-driver" className="mt-1" />
                            <div className="flex-1 space-y-2">
                                <Label htmlFor="mode-driver" className="font-medium cursor-pointer">
                                    Driver-based Growth
                                </Label>
                                <p className="text-xs text-muted-foreground">
                                    Based on projected increase in traffic/requests
                                </p>
                                {settings.forecastMode === 'driver-based' && (
                                    <div className="flex items-center gap-2 mt-2">
                                        <Input
                                            type="number"
                                            value={settings.growthDriver}
                                            onChange={(e) => updateSetting('growthDriver', parseFloat(e.target.value) || 0)}
                                            className="w-24"
                                        />
                                        <span className="text-sm text-muted-foreground">% total growth</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </RadioGroup>
                </div>

                <Separator />

                {/* Section 5: Input Methodology */}
                <div className="space-y-4">
                    <Label className="text-sm font-medium">Input Methodology</Label>

                    <div className="flex gap-1 bg-muted p-1 rounded-lg">
                        <Button
                            variant={settings.inputMethodology === 'actual-cost' ? 'default' : 'ghost'}
                            size="sm"
                            className="flex-1"
                            onClick={() => updateSetting('inputMethodology', 'actual-cost')}
                        >
                            Actual Cost
                        </Button>
                        <Button
                            variant={settings.inputMethodology === 'total-usage' ? 'default' : 'ghost'}
                            size="sm"
                            className="flex-1"
                            onClick={() => updateSetting('inputMethodology', 'total-usage')}
                        >
                            Total Usage
                        </Button>
                    </div>

                    {settings.inputMethodology === 'actual-cost' ? (
                        <div className="space-y-2">
                            <Label htmlFor="latest-cost">Latest Month Total Cost (USD)</Label>
                            <div className="relative">
                                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">$</span>
                                <Input
                                    id="latest-cost"
                                    type="number"
                                    min="0"
                                    step="100"
                                    value={settings.latestMonthCost}
                                    onChange={(e) => updateSetting('latestMonthCost', parseFloat(e.target.value) || 0)}
                                    className="pl-7"
                                />
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="usage-units">Total Usage Units</Label>
                                <Input
                                    id="usage-units"
                                    type="number"
                                    min="0"
                                    value={settings.totalUsageUnits}
                                    onChange={(e) => updateSetting('totalUsageUnits', parseFloat(e.target.value) || 0)}
                                    placeholder="e.g., Instance Hours"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="cost-per-unit">Cost Per Unit (USD)</Label>
                                <div className="relative">
                                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">$</span>
                                    <Input
                                        id="cost-per-unit"
                                        type="number"
                                        min="0"
                                        step="0.0001"
                                        value={settings.costPerUnit}
                                        onChange={(e) => updateSetting('costPerUnit', parseFloat(e.target.value) || 0)}
                                        className="pl-7"
                                    />
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <Separator />

                {/* Options & Actions */}
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <Label htmlFor="realtime-toggle" className="cursor-pointer">
                                Real-time Calculation
                            </Label>
                            <p className="text-xs text-muted-foreground">
                                Update results as you change settings
                            </p>
                        </div>
                        <Switch
                            id="realtime-toggle"
                            checked={settings.realTimeCalculation}
                            onCheckedChange={(checked) => updateSetting('realTimeCalculation', checked)}
                        />
                    </div>

                    <Button
                        onClick={onCalculate}
                        className="w-full"
                        size="lg"
                        disabled={isCalculating}
                    >
                        {isCalculating ? (
                            <>
                                <span className="animate-spin mr-2">⏳</span>
                                Calculating...
                            </>
                        ) : (
                            <>
                                <Calculator className="mr-2 h-4 w-4" />
                                Calculate Forecast
                            </>
                        )}
                    </Button>
                </div>
            </CardContent>
        </Card>
    )
}

export default ForecastSettingsCard
