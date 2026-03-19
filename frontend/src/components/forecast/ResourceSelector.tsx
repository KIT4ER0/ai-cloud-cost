import type { ServiceResources } from '@/hooks/useForecastCost'

const SERVICE_LABELS: Record<string, string> = {
    ec2: 'EC2 Instances',
    rds: 'RDS Databases',
    lambda: 'Lambda Functions',
    s3: 'S3 Buckets',
    alb: 'Load Balancers',
}

const SERVICE_COLORS: Record<string, string> = {
    ec2: 'text-orange-600 bg-orange-50 border-orange-200',
    rds: 'text-blue-600 bg-blue-50 border-blue-200',
    lambda: 'text-purple-600 bg-purple-50 border-purple-200',
    s3: 'text-green-600 bg-green-50 border-green-200',
    alb: 'text-pink-600 bg-pink-50 border-pink-200',
}

interface ResourceSelectorProps {
    resources: ServiceResources | null
    isLoading: boolean
    onLoadResources: () => void
    onResourceSelect: (service: string, resourceId: number) => void
    selectedResource?: { service: string; resourceId: number } | null
}

export function ResourceSelector({
    resources,
    isLoading,
    onLoadResources,
    onResourceSelect,
    selectedResource,
}: ResourceSelectorProps) {

    if (!resources) {
        return (
            <div className="bg-white dark:bg-gray-900 border rounded-lg p-6 flex flex-col items-center justify-center min-h-[200px]">
                <h3 className="text-lg font-semibold mb-2">Select Resource for Forecast</h3>
                <p className="text-sm text-muted-foreground mb-4 text-center">
                    Load your AWS resources to start forecasting costs.
                </p>
                <button
                    onClick={onLoadResources}
                    disabled={isLoading}
                    className="bg-primary text-primary-foreground px-5 py-2 rounded-md hover:opacity-90 disabled:opacity-50 font-medium"
                >
                    {isLoading ? 'Loading Resources...' : 'Load Resources'}
                </button>
            </div>
        )
    }

    const totalResources = Object.values(resources).reduce((sum, s) => sum + s.resources.length, 0)

    return (
        <div className="bg-white dark:bg-gray-900 border rounded-lg p-6 max-h-[500px] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Select Resource</h3>
                <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded-full">
                    {totalResources} resources
                </span>
            </div>
            
            <div className="space-y-3">
                {Object.entries(resources).map(([serviceName, serviceData]) => {
                    if (serviceData.resources.length === 0) return null
                    const colors = SERVICE_COLORS[serviceName] || 'text-gray-600 bg-gray-50 border-gray-200'

                    return (
                        <div key={serviceName} className={`border rounded-md p-3 ${colors.split(' ').slice(1).join(' ')}`}>
                            <h4 className={`font-medium text-sm mb-2 ${colors.split(' ')[0]}`}>
                                {SERVICE_LABELS[serviceName] || serviceName.toUpperCase()} ({serviceData.resources.length})
                            </h4>
                            <div className="space-y-1">
                                {serviceData.resources.map((resource) => {
                                    const isSelected = selectedResource?.service === serviceName && selectedResource?.resourceId === resource.id
                                    return (
                                        <button
                                            key={resource.id}
                                            onClick={() => onResourceSelect(serviceName, resource.id)}
                                            className={`w-full text-left px-3 py-2 rounded text-sm border transition-all ${
                                                isSelected
                                                    ? 'bg-primary/10 border-primary ring-1 ring-primary/30 font-medium'
                                                    : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700'
                                            }`}
                                        >
                                            <div className="font-medium truncate">
                                                {resource.name || `${serviceName}-${resource.id}`}
                                            </div>
                                            {resource.type && (
                                                <div className="text-xs text-muted-foreground">{resource.type}</div>
                                            )}
                                        </button>
                                    )
                                })}
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
