from datetime import datetime, timedelta
from math import sqrt
from statistics import fmean
from uuid import UUID

from services.forecasting.contracts import Evaluation, ForecastValue, InputEvidence, Prediction


def predict(
    identifier: UUID,
    org_id: UUID,
    facility_id: UUID,
    now: datetime,
    evidence: InputEvidence,
    live_reason: str | None,
    threshold: float | None,
    revision: int,
) -> Prediction:
    reason = live_reason or evidence.reason
    mean = fmean(b.value_kw for b in evidence.bins if b.value_kw is not None) if not reason else 0
    return Prediction(
        id=identifier,
        org_id=org_id,
        facility_id=facility_id,
        as_of=evidence.window_end,
        created_at=now,
        expires_at=evidence.window_end + timedelta(seconds=65),
        status="DEGRADED" if reason else "READY",
        reason=reason,
        evidence=evidence,
        threshold_kw=threshold,
        threshold_revision=revision,
        values=[]
        if reason
        else [
            ForecastValue(
                starts_at=evidence.window_end + timedelta(minutes=i),
                ends_at=evidence.window_end + timedelta(minutes=i + 1),
                value_kw=mean,
            )
            for i in range(30)
        ],
    )


def evaluate(prediction: Prediction, actual: InputEvidence, now: datetime) -> Evaluation:
    result = Evaluation(
        prediction_id=prediction.id,
        model_version=prediction.model_version,
        evaluated_at=now,
        status="UNKNOWN" if actual.reason else "EVALUATED",
        reason=actual.reason,
        actual_evidence=actual,
    )
    if actual.reason:
        return result
    values = [b.value_kw for b in actual.bins if b.value_kw is not None]
    if len(values) != 30 or len(prediction.values) != 30:
        raise ValueError("Evaluation requires a complete 30-minute horizon")
    errors = [p.value_kw - a for p, a in zip(prediction.values, values, strict=True)]
    percentages = [abs(e / a) * 100 for e, a in zip(errors, values, strict=True) if a > 0]
    result.mae_kw = fmean(abs(e) for e in errors)
    result.rmse_kw = sqrt(fmean(e * e for e in errors))
    result.mape_percent = fmean(percentages) if percentages else None
    result.mape_sample_count = len(percentages)
    if prediction.threshold_kw is not None:
        result.peak_predicted = (
            max(p.value_kw for p in prediction.values) >= prediction.threshold_kw
        )
        result.peak_actual = max(values) >= prediction.threshold_kw
    return result
