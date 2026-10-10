from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

from backend.agri.api import router as agri_router
from backend.agri.workspace import router as workspace_router
from backend.agri.review_api import router as review_router

load_dotenv()

app = FastAPI(
    title="NEXYRA API",
    description="Agricultural market intelligence with evaluated forecasts",
    version="1.0.0"
)

# Local development origins only. The review API additionally checks the
# connecting client address and loopback Host on every read and write.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agri_router, prefix="/api")
app.include_router(workspace_router, prefix="/api")
app.include_router(review_router, prefix="/api")

@app.get("/api/health")
def health_check():
    try:
        from backend.app.models.database import engine
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
        database_status = "reachable"
    except Exception:
        database_status = "unavailable"
    return {"status": "ok" if database_status == "reachable" else "degraded",
            "service": "NEXYRA Agricultural API", "version": "1.0.0",
            "database": database_status, "review_api": "loopback_only"}

@app.get("/")
def root():
    return {
        "product": "NEXYRA",
        "phase": "AgriSense MVP",
        "purpose": "Agricultural Market Intelligence",
        "status": "Operational",
        "endpoints": ["/api/health", "/api/agri/markets", "/api/agri/models", "/api/agri/market/{series_id}", "/api/agri/forecast/{series_id}"]
    }
