from datetime import datetime
from typing import Literal
from uuid import UUID

from edge.runtime.contracts import Contract


class ModelVersion(Contract):
    model_id: str = "facility-demand-baseline"
    version: str = "rolling-mean-v1"
    feature_version: str = "minute-coverage-v1"
    algorithm: str = "Mean of five complete 1-minute facility demand bins; flat 30-minute horizon"
    history_minutes: int = 5
    horizon_minutes: int = 30
    bin_seconds: int = 60
    minimum_seconds_per_asset_bin: int = 48
    expected_source_hz: int = 1
    status: Literal["BASELINE"] = "BASELINE"
    confidence: None = None
    training: str = "No fitted parameters; prospective chronological evaluation only"


class DemandBin(Contract):
    starts_at: datetime
    ends_at: datetime
    value_kw: float | None
    coverage: float


class InputEvidence(Contract):
    feature_version: str = "minute-coverage-v1"
    window_start: datetime
    window_end: datetime
    asset_ids: list[str]
    mapping_revisions: dict[str, str]
    registry_digest: str
    source_digest: str
    row_count: int
    first_row: int | None
    last_row: int | None
    bins: list[DemandBin]
    reason: str | None


class ForecastValue(Contract):
    starts_at: datetime
    ends_at: datetime
    value_kw: float


class Prediction(Contract):
    sequence: int = 0
    id: UUID
    org_id: UUID
    facility_id: UUID
    mode: Literal["SIMULATION"] = "SIMULATION"
    as_of: datetime
    created_at: datetime
    expires_at: datetime
    model_version: str = "rolling-mean-v1"
    status: Literal["READY", "DEGRADED"]
    reason: str | None
    target: str = "Per-minute mean facility active power over the next 30 minutes"
    unit: Literal["kW"] = "kW"
    horizon_minutes: Literal[30] = 30
    confidence: None = None
    threshold_kw: float | None
    threshold_revision: int
    evidence: InputEvidence
    values: list[ForecastValue]


class Evaluation(Contract):
    prediction_id: UUID
    model_version: str
    evaluated_at: datetime
    status: Literal["EVALUATED", "UNKNOWN"]
    reason: str | None
    actual_evidence: InputEvidence
    mae_kw: float | None = None
    rmse_kw: float | None = None
    mape_percent: float | None = None
    mape_sample_count: int = 0
    peak_predicted: bool | None = None
    peak_actual: bool | None = None


class EvaluationSummary(Contract):
    method: str = "Prospective rolling-origin evaluation; all 30 future minute bins required"
    evaluated_predictions: int
    unknown_predictions: int
    mae_kw: float | None
    rmse_kw: float | None
    mape_percent: float | None
    peak_precision: float | None
    peak_recall: float | None


class RiskRecord(Contract):
    id: UUID
    org_id: UUID
    facility_id: UUID
    state: Literal["OPEN", "RESOLVED", "SUPERSEDED"]
    severity: Literal["HIGH"] = "HIGH"
    probability: None = None
    opened_at: datetime
    updated_at: datetime
    first_prediction_id: UUID
    latest_prediction_id: UUID
    threshold_kw: float
    threshold_revision: int
    predicted_peak_kw: float
    window_start: datetime
    window_end: datetime
    reason: str


class IntelligenceEvent(Contract):
    sequence: int
    event_id: UUID
    event_type: Literal[
        "ForecastGenerated",
        "ForecastFailed",
        "ForecastEvaluated",
        "RiskDetected",
        "RiskUpdated",
        "RiskResolved",
        "RiskSuperseded",
    ]
    schema_version: Literal["1"] = "1"
    occurred_at: datetime
    producer: Literal["edge.intelligence"] = "edge.intelligence"
    org_id: UUID
    facility_id: UUID
    actor: Literal["simulation-inference-worker"] = "simulation-inference-worker"
    correlation_id: UUID
    causation_id: UUID
    idempotency_key: UUID
    payload: Prediction | Evaluation | RiskRecord


class IntelligenceSnapshot(Contract):
    schema_version: Literal["1"] = "1"
    mode: Literal["SIMULATION"] = "SIMULATION"
    observed_at: datetime
    org_id: UUID
    facility_id: UUID
    timezone: str
    status: Literal["READY", "DEGRADED", "UNKNOWN"]
    reason: str | None
    worker_error: str | None
    latest: Prediction | None
    models: list[ModelVersion]
    evaluation: EvaluationSummary
    risks: list[RiskRecord]
    risk_assessment: Literal["BREACH", "CLEAR", "UNKNOWN"]
    threshold_kw: float | None
    pending_events: int
    prediction_count: int
    prediction_capacity: int
