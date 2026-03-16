import { Link, useLocation, useNavigate } from "react-router-dom"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
    LayoutDashboard,
    BarChart3,
    LineChart,
    Activity,
    Lightbulb,
    LogOut,
    User
} from "lucide-react"
import { useAuthStore } from "@/store/useAuthStore"

interface SidebarProps {
    className?: string
}

export function Sidebar({ className }: SidebarProps) {
    const location = useLocation()
    const navigate = useNavigate()
    const logout = useAuthStore((state) => state.logout)

    const links = [
        { name: "Dashboard", href: "/home", icon: LayoutDashboard },
        { name: "Cost Analysis", href: "/cost-analysis", icon: BarChart3 },
        { name: "Monitoring", href: "/monitoring", icon: Activity },
        { name: "Forecast Cost", href: "/forecast-cost", icon: LineChart },
        { name: "Recommendations", href: "/recommend", icon: Lightbulb },
        { name: "User Profile", href: "/profile", icon: User },
    ]

    const handleSignOut = async () => {
        try {
            await logout();
            navigate('/signin');
        } catch (error) {
            console.error("Sign out failed:", error);
            // Fallback redirect even if logout fails
            window.location.href = '/signin';
        }
    };

    return (
        <div className={cn("pb-12 w-64 border-r bg-background min-h-screen", className)}>
            <div className="space-y-4 py-4">
                <div className="px-3 py-2">
                    <h2 className="mb-2 px-4 text-xl font-bold tracking-tight text-primary">
                        AI Cloud Cost
                    </h2>
                    <div className="space-y-1">
                        {links.map((link) => (
                            <Button
                                key={link.href}
                                variant={location.pathname === link.href ? "secondary" : "ghost"}
                                className={cn(
                                    "w-full justify-start",
                                    location.pathname === link.href && "text-primary font-semibold"
                                )}
                                asChild
                            >
                                <Link to={link.href}>
                                    <link.icon className="mr-2 h-4 w-4" />
                                    {link.name}
                                </Link>
                            </Button>
                        ))}
                    </div>
                </div>
                <div className="px-3 py-2 mt-auto">
                    <Button
                        variant="ghost"
                        className="w-full justify-start text-red-500 hover:text-red-600 hover:bg-red-50"
                        onClick={handleSignOut}
                    >
                        <LogOut className="mr-2 h-4 w-4" />
                        Sign Out
                    </Button>
                </div>
            </div>
        </div>
    )
}
