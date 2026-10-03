"""Local persistence orchestration; bounded, scoped and transactionally audited."""

import hashlib
from datetime import UTC, datetime, timedelta
from math import sqrt
from statistics import fmean
from typing import TYPE_CHECKING
from uuid import UUID, uuid4, uuid5

from services.forecasting.baseline import evaluate, predict
from services.forecasting.contracts import (
    Evaluation,
    EvaluationSummary,
    IntelligenceEvent,
    IntelligenceSnapshot,
    ModelVersion,
    Prediction,
    RiskRecord,
)
from services.forecasting.features import features, minute
from services.registry.contracts import Asset, Facility, SignalMapping
from services.risk.service import transition
from services.telemetry.contracts import StoredPoint

if TYPE_CHECKING:
    from edge.storage.repository import Repository


class ForecastService:
    capacity = 1440
    event_capacity = 10000

    def __init__(self, repo: "Repository") -> None:
        self.repo = repo
        self.worker_error: str | None = None
        model = ModelVersion()
        with repo.lock, repo.db:
            repo.db.execute(
                "INSERT OR IGNORE INTO model_versions VALUES (?,?)",
                (model.version, model.model_dump_json()),
            )
            saved = repo.db.execute(
                "SELECT body FROM model_versions WHERE version=?", (model.version,)
            ).fetchone()[0]
            if ModelVersion.model_validate_json(saved) != model:
                raise ValueError("Immutable model version conflict")

    def context(self) -> tuple[Facility, int, list[str], dict[str, str], str]:
        records = self.repo.registry.records()
        facility_record = next(r for r in records if isinstance(r.entity, Facility))
        assert isinstance(facility_record.entity, Facility)
        assets = sorted(
            r.entity.id
            for r in records
            if isinstance(r.entity, Asset)
            and r.entity.enabled
            and "telemetry" in r.entity.capabilities
        )
        mappings = {
            r.entity.asset_id: f"{r.entity.id}:{r.revision}"
            for r in records
            if isinstance(r.entity, SignalMapping) and r.entity.enabled
        }
        digest = hashlib.sha256(
            "\n".join(r.model_dump_json() for r in records).encode()
        ).hexdigest()
        return facility_record.entity, facility_record.revision, assets, mappings, digest

    def live_reason(self, now: datetime, disconnected: bool = False) -> str | None:
        _, _, assets, mappings, _ = self.context()
        if disconnected:
            return "TELEMETRY_UNAVAILABLE"
        if not assets:
            return "NO_TELEMETRY_ASSETS"
        points = {p.asset_id: p for p in self.repo.state()[1]}
        for asset in assets:
            p = points.get(asset)
            if p is None or asset not in mappings:
                return "MISSING_ASSET_OR_MAPPING"
            if not 0 <= (now - p.event_time).total_seconds() <= 5:
                return "STALE_OR_FUTURE_TELEMETRY"
            if p.quality != "GOOD" or p.flags:
                return "BAD_TELEMETRY_QUALITY"
            if mappings[asset] != f"{p.mapping_id}:{p.mapping_revision}":
                return "MAPPING_CHANGED"
        return None

    def points(self, start: datetime, end: datetime) -> list[StoredPoint]:
        return [
            StoredPoint.model_validate_json(r[0])
            for r in self.repo.db.execute(
                "SELECT payload FROM telemetry WHERE event_time>=? AND event_time<? ORDER BY id",
                (start.isoformat(), end.isoformat()),
            )
        ]

    def emit(
        self,
        payload: Prediction | Evaluation | RiskRecord,
        event_type: str,
        correlation: UUID,
        now: datetime,
    ) -> None:
        count = self.repo.db.execute("SELECT COUNT(*) FROM intelligence_outbox").fetchone()[0]
        if count >= self.event_capacity:
            raise ValueError("INTELLIGENCE_EVENT_CAPACITY")
        event_id = uuid4()
        event = IntelligenceEvent.model_validate(
            dict(
                sequence=count + 1,
                event_id=event_id,
                event_type=event_type,
                occurred_at=now,
                org_id=self.repo.org_id,
                facility_id=self.repo.facility_id,
                correlation_id=correlation,
                causation_id=correlation,
                idempotency_key=event_id,
                payload=payload,
            )
        )
        self.repo.db.execute(
            "INSERT INTO intelligence_outbox(event_id,body) VALUES (?,?)",
            (str(event_id), event.model_dump_json()),
        )

    def run(self, now: datetime | None = None, disconnected: bool = False) -> Prediction:
        now = now or datetime.now(UTC)
        origin = minute(now)
        with self.repo.lock, self.repo.db:
            facility, revision, assets, mappings, digest = self.context()
            live = self.live_reason(now, disconnected)
            # One immutable result per minute/config/live-quality state, also after restart.
            key = f"rolling-mean-v1:{origin.isoformat()}:{digest}:{live}"
            row = self.repo.db.execute(
                "SELECT body FROM predictions WHERE run_key=?", (key,)
            ).fetchone()
            if row:
                return Prediction.model_validate_json(row[0])
            count = self.repo.db.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
            if count >= self.capacity:
                raise ValueError("PREDICTION_CAPACITY")
            start = origin - timedelta(minutes=5)
            evidence = features(
                self.points(start, origin), start, 5, origin, assets, mappings, digest
            )
            result = predict(
                uuid5(self.repo.facility_id, key),
                self.repo.org_id,
                self.repo.facility_id,
                now,
                evidence,
                live,
                facility.simulation_demand_threshold_kw,
                revision,
            )
            result.sequence = count + 1
            self.repo.db.execute(
                "INSERT INTO predictions(id,run_key,org_id,facility_id,as_of,body) "
                "VALUES (?,?,?,?,?,?)",
                (
                    str(result.id),
                    key,
                    str(self.repo.org_id),
                    str(self.repo.facility_id),
                    origin.isoformat(),
                    result.model_dump_json(),
                ),
            )
            self.emit(
                result,
                "ForecastGenerated" if result.status == "READY" else "ForecastFailed",
                result.id,
                now,
            )
            active_row = self.repo.db.execute(
                "SELECT body FROM risks WHERE state='OPEN' AND org_id=? AND facility_id=?",
                (str(self.repo.org_id), str(self.repo.facility_id)),
            ).fetchone()
            active = RiskRecord.model_validate_json(active_row[0]) if active_row else None
            for risk in transition(active, result):
                event = {"RESOLVED": "RiskResolved", "SUPERSEDED": "RiskSuperseded"}.get(
                    risk.state, "RiskUpdated" if active and active.id == risk.id else "RiskDetected"
                )
                self.repo.db.execute(
                    "INSERT INTO risks VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                    "state=excluded.state,body=excluded.body",
                    (
                        str(risk.id),
                        str(risk.org_id),
                        str(risk.facility_id),
                        risk.state,
                        risk.model_dump_json(),
                    ),
                )
                self.emit(risk, event, result.id, now)
            return result

    def evaluate_due(self, now: datetime | None = None) -> Evaluation | None:
        now = now or datetime.now(UTC)
        with self.repo.lock, self.repo.db:
            # One chronological origin per worker cycle bounds catch-up work.
            row = self.repo.db.execute(
                "SELECT p.body FROM predictions p LEFT JOIN forecast_evaluations e "
                "ON e.prediction_id=p.id "
                "WHERE e.prediction_id IS NULL AND json_extract(p.body,'$.status')='READY' "
                "AND p.as_of<=? AND p.org_id=? AND p.facility_id=? ORDER BY p.sequence LIMIT 1",
                (
                    (now - timedelta(minutes=30, seconds=5)).isoformat(),
                    str(self.repo.org_id),
                    str(self.repo.facility_id),
                ),
            ).fetchone()
            if not row:
                return None
            prediction = Prediction.model_validate_json(row[0])
            end = prediction.as_of + timedelta(minutes=30)
            actual = features(
                self.points(prediction.as_of, end),
                prediction.as_of,
                30,
                end + timedelta(seconds=5),
                prediction.evidence.asset_ids,
                prediction.evidence.mapping_revisions,
                prediction.evidence.registry_digest,
            )
            result = evaluate(prediction, actual, now)
            self.repo.db.execute(
                "INSERT INTO forecast_evaluations VALUES (?,?)",
                (str(prediction.id), result.model_dump_json()),
            )
            self.emit(result, "ForecastEvaluated", prediction.id, now)
            return result

    def tick(self, disconnected: bool = False) -> None:
        self.worker_error = None
        try:
            self.run(disconnected=disconnected)
        except Exception:
            self.worker_error = "INFERENCE_OR_STORAGE_FAILED"
        try:
            # Even when new predictions reach capacity, finish scoring existing origins.
            self.evaluate_due()
        except Exception:
            # Never expose DB details or interrupt telemetry. Keep immutable evidence for diagnosis.
            self.worker_error = "INFERENCE_OR_STORAGE_FAILED"

    def summary(self) -> EvaluationSummary:
        results = [
            Evaluation.model_validate_json(r[0])
            for r in self.repo.db.execute("SELECT body FROM forecast_evaluations")
        ]
        valid = [r for r in results if r.status == "EVALUATED"]
        mae = [r.mae_kw for r in valid if r.mae_kw is not None]
        mse = [r.rmse_kw**2 for r in valid if r.rmse_kw is not None]
        percentage_count = sum(r.mape_sample_count for r in valid)
        tp = sum(r.peak_predicted is True and r.peak_actual is True for r in valid)
        predicted = sum(r.peak_predicted is True for r in valid)
        actual = sum(r.peak_actual is True for r in valid)
        return EvaluationSummary(
            evaluated_predictions=len(valid),
            unknown_predictions=len(results) - len(valid),
            mae_kw=fmean(mae) if mae else None,
            rmse_kw=sqrt(fmean(mse)) if mse else None,
            mape_percent=sum((r.mape_percent or 0) * r.mape_sample_count for r in valid)
            / percentage_count
            if percentage_count
            else None,
            peak_precision=tp / predicted if predicted else None,
            peak_recall=tp / actual if actual else None,
        )

    def snapshot(
        self, disconnected: bool = False, now: datetime | None = None
    ) -> IntelligenceSnapshot:
        now = now or datetime.now(UTC)
        with self.repo.lock:
            facility, _, _, _, digest = self.context()
            latest_list = self.history(limit=1)
            latest = latest_list[0] if latest_list else None
            reason = self.worker_error or self.live_reason(now, disconnected)
            if latest is None:
                reason = reason or "AWAITING_FIRST_RUN"
            elif latest.expires_at < now or latest.as_of > now:
                reason = reason or "FORECAST_EXPIRED"
            elif latest.evidence.registry_digest != digest:
                reason = reason or "CONFIGURATION_CHANGED"
            else:
                reason = reason or latest.reason
            threshold = facility.simulation_demand_threshold_kw
            assessment = "UNKNOWN"
            if latest and not reason and threshold is not None:
                assessment = (
                    "BREACH" if max(p.value_kw for p in latest.values) >= threshold else "CLEAR"
                )
            return IntelligenceSnapshot.model_validate(
                dict(
                    observed_at=now,
                    org_id=self.repo.org_id,
                    facility_id=self.repo.facility_id,
                    timezone=facility.timezone,
                    status="DEGRADED" if reason else "READY",
                    reason=reason,
                    worker_error=self.worker_error,
                    latest=latest,
                    models=[
                        ModelVersion.model_validate_json(r[0])
                        for r in self.repo.db.execute("SELECT body FROM model_versions")
                    ],
                    evaluation=self.summary(),
                    risks=self.risks(),
                    risk_assessment=assessment,
                    threshold_kw=threshold,
                    pending_events=self.repo.db.execute(
                        "SELECT COUNT(*) FROM intelligence_outbox WHERE acknowledged=0"
                    ).fetchone()[0],
                    prediction_count=self.repo.db.execute(
                        "SELECT COUNT(*) FROM predictions"
                    ).fetchone()[0],
                    prediction_capacity=self.capacity,
                )
            )

    def history(self, before: int | None = None, limit: int = 20) -> list[Prediction]:
        with self.repo.lock:
            return [
                Prediction.model_validate_json(r[0])
                for r in self.repo.db.execute(
                    "SELECT body FROM predictions WHERE (? IS NULL OR sequence<?) "
                    "AND org_id=? AND facility_id=? "
                    "ORDER BY sequence DESC LIMIT ?",
                    (before, before, str(self.repo.org_id), str(self.repo.facility_id), limit),
                )
            ]

    def risks(self) -> list[RiskRecord]:
        return [
            RiskRecord.model_validate_json(r[0])
            for r in self.repo.db.execute(
                "SELECT body FROM risks WHERE org_id=? AND facility_id=? "
                "ORDER BY (state='OPEN') DESC,json_extract(body,'$.updated_at') DESC LIMIT 20",
                (str(self.repo.org_id), str(self.repo.facility_id)),
            )
        ]

    def events(self, after: int = 0) -> list[IntelligenceEvent]:
        with self.repo.lock:
            return [
                IntelligenceEvent.model_validate_json(r[0])
                for r in self.repo.db.execute(
                    "SELECT body FROM intelligence_outbox WHERE sequence>? "
                    "ORDER BY sequence LIMIT 20",
                    (after,),
                )
            ]
