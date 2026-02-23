from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from . import database, models
from .routers import auth, costs, monitoring, recommendations, system, sync

# Create DB tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="AI Cloud Cost Optimizer Backend")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(costs.router)
app.include_router(monitoring.router)
app.include_router(recommendations.router)
app.include_router(system.router)
app.include_router(sync.router)

@app.get("/")
def root():
    return {"message": "Cloud Cost Optimizer API is running"}
