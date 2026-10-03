from datetime import datetime

from pydantic import BaseModel, Field


class TelemetryPoint(BaseModel):
    timestamp: datetime
    asset_id: str
    voltage: float = Field(gt=0)
    current: float = Field(ge=0)
    active_power_kw: float = Field(ge=0)
    vibration: float = Field(ge=0)
