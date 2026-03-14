from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import ssl

# Load env early
load_dotenv()
load_dotenv("backend/.env")

# Bypass SSL verification for development (fixes JWKS fetch on macOS)
ssl._create_default_https_context = ssl._create_unverified_context

from . import database, models
from .routers import auth, costs, monitoring, recommendations, system, aws, sync
from .forecasting.router import router as forecast_router

from sqlalchemy import text

# Create schema and DB tables
with database.engine.begin() as conn:
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS cloudcost;"))
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="AI Cloud Cost Optimizer Backend")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(aws.router)
app.include_router(costs.router)
app.include_router(monitoring.router)
app.include_router(recommendations.router)
app.include_router(system.router)
app.include_router(sync.router)
app.include_router(forecast_router)

@app.get("/")
def root():
    return {"message": "Cloud Cost Optimizer API is running"}
