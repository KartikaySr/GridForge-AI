"""Quality-gated comparison to a declared pre-dispatch simulated forecast baseline."""

import hashlib
import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from services.finance.contracts import TariffVersion, WindowEvidence
from services.telemetry.contracts import StoredPoint

if TYPE_CHECKING:
    from edge.storage.repository import Repository


def slots(start: datetime, end: datetime) -> list[datetime]:
    # Whole UTC seconds inside a half-open window; no interpolation or unseen intervals.
    first = math.ceil(start.timestamp())
    return [datetime.fromtimestamp(t, UTC) for t in range(first, math.ceil(end.timestamp()))]


def rate_at(tariff: TariffVersion, at: datetime) -> Decimal | None:
    if not tariff.effective_from <= at < tariff.effective_until:
        return None
    matches = [b.rate_per_kwh for b in tariff.energy_bands if b.starts_at <= at < b.ends_at]
    return matches[0] if len(matches) == 1 else None


def measure(
    repo: "Repository",
    start: datetime,
    end: datetime,
    asset_ids: list[str],
    mapping_revisions: dict[str, str],
    baseline_kw: Decimal,
    observed_at: datetime,
) -> tuple[WindowEvidence, list[tuple[datetime, Decimal]]]:
    expected = slots(start, end)
    if not expected or not asset_ids:
        return WindowEvidence(
            starts_at=start,
            ends_at=end,
            expected_slots=len(expected),
            valid_slots=0,
            first_row=None,
            last_row=None,
            source_digest="",
            baseline_energy_kwh=None,
            actual_energy_kwh=None,
            quality="INCOMPLETE",
            reason="EMPTY_WINDOW_OR_ASSETS",
        ), []
    rows = repo.db.execute(
        "SELECT payload FROM telemetry WHERE event_time>=? AND event_time<? ORDER BY id",
        (start.isoformat(), end.isoformat()),
    )
    points = [StoredPoint.model_validate_json(r[0]) for r in rows]
    by_slot: dict[tuple[datetime, str], list[StoredPoint]] = {}
    for p in points:
        if (
            p.received_time > observed_at
            or p.received_time > p.event_time + timedelta(seconds=5)
            or not start <= p.event_time < end
        ):
            continue
        second = p.event_time.replace(microsecond=0)
        by_slot.setdefault((second, p.asset_id), []).append(p)
    actual: list[tuple[datetime, Decimal]] = []
    used: list[StoredPoint] = []
    for second in expected:
        collection = [by_slot.get((second, asset), []) for asset in asset_ids]
        if any(len(items) != 1 for items in collection):
            continue
        samples = [items[0] for items in collection]
        if any(
            p.quality != "GOOD"
            or p.flags
            or p.source != "SIMULATOR"
            or f"{p.mapping_id}:{p.mapping_revision}" != mapping_revisions.get(p.asset_id)
            or not second <= p.event_time < second + timedelta(seconds=1)
            for p in samples
        ):
            continue
        used.extend(samples)
        actual.append((second, sum((Decimal(str(p.value)) for p in samples), Decimal(0))))
    digest = hashlib.sha256(
        "\n".join(f"{p.row_id}:{p.idempotency_key}:{p.value}" for p in used).encode()
    ).hexdigest()
    complete = len(actual) == len(expected)
    evidence = WindowEvidence(
        starts_at=start,
        ends_at=end,
        expected_slots=len(expected),
        valid_slots=len(actual),
        first_row=min((p.row_id for p in used), default=None),
        last_row=max((p.row_id for p in used), default=None),
        source_digest=digest,
        baseline_energy_kwh=baseline_kw * Decimal(len(expected)) / Decimal(3600)
        if complete
        else None,
        actual_energy_kwh=sum((kw for _, kw in actual), Decimal(0)) / Decimal(3600)
        if complete
        else None,
        quality="COMPLETE" if complete else "INCOMPLETE",
        reason=None if complete else "MISSING_DUPLICATE_BAD_OR_LATE_SECONDS",
    )
    return evidence, actual
