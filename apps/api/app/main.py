from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import load_settings
from app.schemas.domain import TelemetryPoint

settings = load_settings()

app = FastAPI(title="GridForge Core API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

assets: list[dict[str, str | int]] = [
    {
        "id": "CH-01",
        "name": "Chiller 01",
        "type": "Chiller",
        "line": "Utilities",
        "currentLoadKw": 920,
        "ratedLoadKw": 1200,
        "flexibilityKw": 260,
        "criticality": "medium",
        "status": "healthy",
    },
    {
        "id": "CP-02",
        "name": "Compressor 02",
        "type": "Compressor",
        "line": "Utilities",
        "currentLoadKw": 710,
        "ratedLoadKw": 900,
        "flexibilityKw": 220,
        "criticality": "medium",
        "status": "healthy",
    },
    {
        "id": "EX-04",
        "name": "Extruder 04",
        "type": "Extruder",
        "line": "Line 3",
        "currentLoadKw": 1180,
        "ratedLoadKw": 1400,
        "flexibilityKw": 80,
        "criticality": "high",
        "status": "warning",
    },
    {
        "id": "CR-01",
        "name": "Crusher 01",
        "type": "Crusher",
        "line": "Line 1",
        "currentLoadKw": 1350,
        "ratedLoadKw": 1600,
        "flexibilityKw": 0,
        "criticality": "high",
        "status": "healthy",
    },
    {
        "id": "PM-03",
        "name": "Pump 03",
        "type": "Pump",
        "line": "Utilities",
        "currentLoadKw": 390,
        "ratedLoadKw": 520,
        "flexibilityKw": 140,
        "criticality": "low",
        "status": "healthy",
    },
]
latest: dict[str, TelemetryPoint] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "gridforge-api",
        "mode": settings.mode,
        "check": "liveness",
    }


@app.get("/api/v1/dashboard/metrics")
def metrics() -> dict[str, float | str]:
    load = sum(v.active_power_kw for v in latest.values()) if latest else 8420
    forecast = max(load * 1.09, 9180 if not latest else 0)
    threshold = 9000
    risk = max(8, min(99, 50 + (forecast - threshold) / 8))
    return {
        "mode": settings.mode,
        "source": "simulation-scaffold",
        "currentLoadKw": round(load, 1),
        "predictedPeakKw": round(forecast, 1),
        "thresholdKw": threshold,
        "peakRiskPct": round(risk, 1),
        "todaySavingsInr": 12840,
        "activeAlerts": 3 if forecast > threshold else 1,
        "telemetryPerSecond": len(latest) or 5,
    }


@app.get("/api/v1/assets")
def get_assets() -> list[dict[str, str | int]]:
    return assets


@app.post("/api/v1/telemetry")
def ingest(point: TelemetryPoint) -> dict[str, bool | str]:
    latest[point.asset_id] = point
    return {"accepted": True, "assetId": point.asset_id}


@app.get("/api/v1/optimization/current")
def optimization() -> dict[str, str | float]:
    return {
        "mode": settings.mode,
        "source": "static-fixture",
        "id": "OPT-0001",
        "assetId": "CH-01",
        "action": "Throttle Chiller 01 to 70%",
        "reductionKw": 260,
        "durationMinutes": 15,
        "expectedSavingsInr": 3840,
        "productionImpactPct": 0.2,
        "status": "proposed",
    }
