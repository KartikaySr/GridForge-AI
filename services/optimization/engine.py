"""Deterministic continuous curtailment allocator. No command or physical adapter dependency."""

from datetime import datetime

from services.optimization.contracts import (
    CandidateEvaluation,
    ConstraintResult,
    OptimizationPolicy,
)
from services.registry.contracts import Asset, RegistryRecord, SignalMapping
from services.telemetry.contracts import StoredPoint


def gate(code: str, passed: bool, detail: str) -> ConstraintResult:
    return ConstraintResult(code=code, kind="HARD", passed=passed, detail=detail)


def evaluate(
    asset: Asset,
    records: list[RegistryRecord],
    point: StoredPoint | None,
    policy: OptimizationPolicy,
    now: datetime,
    end: datetime,
) -> CandidateEvaluation:
    entities = {r.entity.id: r.entity for r in records}
    mappings = [
        r
        for r in records
        if isinstance(r.entity, SignalMapping)
        and r.entity.asset_id == asset.id
        and r.entity.enabled
    ]
    mapping = mappings[0] if len(mappings) == 1 else None
    device = (
        entities.get(mapping.entity.device_id)
        if mapping and isinstance(mapping.entity, SignalMapping)
        else None
    )
    current = point.value if point else None
    available = max(0.0, min(asset.max_reduction_kw, (current or 0) - asset.min_load_kw))
    checks = [
        gate(
            "ENABLED",
            asset.enabled and bool(entities.get(asset.line_id) and entities[asset.line_id].enabled),
            "Asset and parent line enabled",
        ),
        gate("NONCRITICAL", asset.criticality == "NORMAL", "Critical assets are excluded"),
        gate(
            "SIMULATED_CAPABILITY",
            asset.flexible and "simulated_load_adjustment" in asset.capabilities,
            "Explicit simulated flexibility required; no physical commissioning implied",
        ),
        gate(
            "MAPPING_DEVICE",
            mapping is not None and device is not None and device.enabled,
            "Exactly one enabled mapping and enabled simulator device required",
        ),
        gate(
            "LIVE_QUALITY",
            point is not None
            and point.quality == "GOOD"
            and not point.flags
            and 0 <= (now - point.event_time).total_seconds() <= 5
            and 0 <= (now - point.received_time).total_seconds() <= 5,
            "Fresh good telemetry required within five seconds",
        ),
        gate(
            "MAPPING_REVISION",
            point is not None
            and mapping is not None
            and point.mapping_id == mapping.entity.id
            and point.mapping_revision == mapping.revision,
            "Telemetry must match current mapping revision",
        ),
        gate(
            "LOAD_BOUNDS",
            current is not None
            and asset.min_load_kw <= current <= asset.max_load_kw
            and current - available >= asset.min_load_kw,
            "Current and proposed loads must remain inside configured bounds",
        ),
        gate(
            "MAINTENANCE",
            not any(m.starts_at < end and m.ends_at > now for m in asset.maintenance),
            "Entire action window must avoid maintenance",
        ),
        gate(
            "RUNTIME_DOWNTIME_EVIDENCE",
            asset.min_run_seconds == 0 and asset.min_off_seconds == 0,
            "Nonzero runtime/downtime requirements are blocked until verified "
            "operating-state history exists",
        ),
        gate(
            "COMMAND_BOUND",
            0 < available <= asset.max_reduction_kw,
            "Positive reduction bounded by asset flexibility; no shifting or restart action",
        ),
    ]
    penalty = policy.asset_penalties.get(asset.id, 1)
    checks.append(
        ConstraintResult(
            code="PREFERENCE_COST",
            kind="SOFT",
            passed=True,
            detail=f"Relative penalty {penalty} per kW; lower is preferred",
        )
    )
    return CandidateEvaluation(
        asset_id=asset.id,
        name=asset.name,
        current_kw=current,
        available_kw=available,
        penalty=penalty,
        eligible=all(c.passed for c in checks if c.kind == "HARD"),
        constraints=checks,
    )


def allocate(candidates: list[CandidateEvaluation], target: float, cap: float) -> bool:
    """Optimal for this restricted continuous, separable linear penalty problem."""
    eligible = sorted((c for c in candidates if c.eligible), key=lambda c: (c.penalty, c.asset_id))
    if target > cap or sum(c.available_kw for c in eligible) < target:
        return False
    remaining = target
    for candidate in eligible:
        selected = min(candidate.available_kw, remaining)
        candidate.selected_kw = selected
        remaining = max(0.0, remaining - selected)
    return remaining <= 1e-9
