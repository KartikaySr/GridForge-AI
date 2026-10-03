"""Pure, deterministic event-time features. No filling missing asset demand with zero."""

import hashlib
from datetime import UTC, datetime, timedelta
from statistics import fmean

from services.forecasting.contracts import DemandBin, InputEvidence
from services.telemetry.contracts import StoredPoint


def minute(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(second=0, microsecond=0)


def features(
    points: list[StoredPoint],
    start: datetime,
    minutes: int,
    available_at: datetime,
    assets: list[str],
    mappings: dict[str, str],
    registry_digest: str,
) -> InputEvidence:
    end = start + timedelta(minutes=minutes)
    # A sample must have existed at the prediction origin. A later backfill cannot enter training.
    eligible = sorted(
        (
            p
            for p in points
            if start <= p.event_time < end
            and p.event_time <= available_at
            and p.received_time <= available_at
            and p.asset_id in assets
        ),
        key=lambda p: p.row_id,
    )
    slots: dict[tuple[int, str, int], StoredPoint] = {}
    invalid: set[tuple[int, str, int]] = set()
    for p in eligible:
        index = int((p.event_time - start).total_seconds()) // 60
        key = (index, p.asset_id, p.event_time.second)
        if (
            p.quality != "GOOD"
            or p.flags
            or mappings.get(p.asset_id) != f"{p.mapping_id}:{p.mapping_revision}"
        ):
            invalid.add(key)
        else:
            slots[key] = p
    buckets: dict[tuple[int, str], list[float]] = {}
    for key, point in slots.items():
        if key not in invalid:
            buckets.setdefault((key[0], key[1]), []).append(point.value)
    bins = []
    for index in range(minutes):
        by_asset = [buckets.get((index, asset), []) for asset in assets]
        coverage = min((len(values) / 60 for values in by_asset), default=0)
        value = sum(fmean(values) for values in by_asset) if coverage >= 0.8 else None
        bins.append(
            DemandBin(
                starts_at=start + timedelta(minutes=index),
                ends_at=start + timedelta(minutes=index + 1),
                value_kw=value,
                coverage=coverage,
            )
        )
    digest = hashlib.sha256()
    for point in eligible:
        digest.update(point.model_dump_json().encode())
        digest.update(b"\n")
    return InputEvidence(
        window_start=start,
        window_end=end,
        asset_ids=assets,
        mapping_revisions=mappings,
        registry_digest=registry_digest,
        source_digest=digest.hexdigest(),
        row_count=len(eligible),
        first_row=eligible[0].row_id if eligible else None,
        last_row=eligible[-1].row_id if eligible else None,
        bins=bins,
        reason="INSUFFICIENT_GOOD_MINUTE_COVERAGE"
        if any(b.value_kw is None for b in bins)
        else None,
    )
