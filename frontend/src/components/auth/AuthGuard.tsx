import { ReactNode, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/useAuthStore";
import { Loader2 } from "lucide-react";

interface AuthGuardProps {
    children: ReactNode;
    requireAuth?: boolean;
}

export function AuthGuard({ children, requireAuth = true }: AuthGuardProps) {
    const { isAuthenticated, initialize } = useAuthStore();
    const [isInitializing, setIsInitializing] = useState(true);
    const location = useLocation();

    useEffect(() => {
        const init = async () => {
            await initialize();
            setIsInitializing(false);
        };
        init();
    }, [initialize]);

    if (isInitializing) {
        return (
            <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 gap-4">
                <Loader2 className="h-10 w-10 text-blue-600 animate-spin" />
                <p className="text-slate-600 font-medium">Verifying your session...</p>
            </div>
        );
    }

    if (requireAuth && !isAuthenticated) {
        // Redirect to signin but save the location they were trying to access
        return <Navigate to="/signin" state={{ from: location }} replace />;
    }

    if (!requireAuth && isAuthenticated) {
        // If user is already logged in and tries to access signin/onboarding, redirect to home
        return <Navigate to="/home" replace />;
    }

    return <>{children}</>;
}
