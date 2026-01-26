import { Outlet } from "react-router-dom"
import { Sidebar } from "@/components/Sidebar"

export default function MainLayout() {
    return (
        <div className="flex min-h-screen bg-background text-foreground">
            <Sidebar className="hidden lg:block w-64 fixed inset-y-0" />
            <div className="flex-1 lg:pl-64">
                {/* Mobile Header could go here */}
                <main className="p-8">
                    <Outlet />
                </main>
            </div>
        </div>
    )
}
