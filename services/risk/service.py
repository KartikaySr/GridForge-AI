from uuid import uuid4

from services.forecasting.contracts import Prediction, RiskRecord


def transition(active: RiskRecord | None, prediction: Prediction) -> list[RiskRecord]:
    changes = []
    if active and (active.threshold_revision != prediction.threshold_revision):
        changes.append(
            active.model_copy(
                update={
                    "state": "SUPERSEDED",
                    "updated_at": prediction.created_at,
                    "latest_prediction_id": prediction.id,
                    "reason": "Facility threshold configuration changed",
                }
            )
        )
        active = None
    # Missing data never resolves a previously detected breach.
    if prediction.status != "READY" or prediction.threshold_kw is None:
        return changes
    peak = max(p.value_kw for p in prediction.values)
    if peak >= prediction.threshold_kw:
        changes.append(
            RiskRecord(
                id=active.id if active else uuid4(),
                org_id=prediction.org_id,
                facility_id=prediction.facility_id,
                state="OPEN",
                opened_at=active.opened_at if active else prediction.created_at,
                updated_at=prediction.created_at,
                first_prediction_id=active.first_prediction_id if active else prediction.id,
                latest_prediction_id=prediction.id,
                threshold_kw=prediction.threshold_kw,
                threshold_revision=prediction.threshold_revision,
                predicted_peak_kw=peak,
                window_start=prediction.values[0].starts_at,
                window_end=prediction.values[-1].ends_at,
                reason="Baseline forecast meets or exceeds the simulation demand threshold",
            )
        )
    elif active:
        changes.append(
            active.model_copy(
                update={
                    "state": "RESOLVED",
                    "updated_at": prediction.created_at,
                    "latest_prediction_id": prediction.id,
                    "reason": "A complete fresh forecast is below the same configured threshold",
                }
            )
        )
    return changes
