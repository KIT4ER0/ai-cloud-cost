import { createBrowserRouter, Navigate } from "react-router-dom"
import MainLayout from "@/layouts/MainLayout"
import Home from "@/pages/Home"
import CostAnalysis from "@/pages/CostAnalysis"
import ForecastCost from "@/pages/ForecastCost"
import Monitoring from "@/pages/Monitoring"
import Recommend from "@/pages/Recommend"
import Simulation from "@/pages/Simulation"
import Onboarding from "@/pages/Onboarding"
import SignIn from "@/pages/SignIn"
import Profile from "@/pages/Profile"
import { AuthGuard } from "@/components/auth/AuthGuard"

export const router = createBrowserRouter([
    {
        path: "/",
        element: (
            <AuthGuard>
                <MainLayout />
            </AuthGuard>
        ),
        children: [
            {
                path: "/",
                element: <Navigate to="/home" replace />,
            },
            {
                path: "home",
                element: <Home />,
            },
            {
                path: "cost-analysis",
                element: <CostAnalysis />,
            },
            {
                path: "forecast-cost",
                element: <ForecastCost />,
            },
            {
                path: "monitoring",
                element: <Monitoring />,
            },
            {
                path: "recommend",
                element: <Recommend />,
            },
            {
                path: "simulation",
                element: <Simulation />,
            },
            {
                path: "profile",
                element: <Profile />,
            },
        ],
    },
    {
        path: "/onboarding",
        element: (
            <AuthGuard requireAuth={false}>
                <Onboarding />
            </AuthGuard>
        ),
    },
    {
        path: "/signin",
        element: (
            <AuthGuard requireAuth={false}>
                <SignIn />
            </AuthGuard>
        ),
    },
]);
