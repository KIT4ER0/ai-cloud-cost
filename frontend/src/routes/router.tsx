import { createBrowserRouter, Navigate } from "react-router-dom"
import MainLayout from "@/layouts/MainLayout"
import Home from "@/pages/Home"
import CostAnalysis from "@/pages/CostAnalysis"
import ForecastCost from "@/pages/ForecastCost"
import Monitoring from "@/pages/Monitoring"
import Recommend from "@/pages/Recommend"

export const router = createBrowserRouter([
    {
        path: "/",
        element: <MainLayout />,
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
        ],
    },
])
