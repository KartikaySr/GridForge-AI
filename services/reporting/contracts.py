from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator, model_validator

from edge.runtime.contracts import Contract


class ProductionWrite(Contract):
    request_id: UUID
    product: str = Field(min_length=1, max_length=100)
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    asset_ids: list[str] = Field(min_length=1, max_length=20)
    good_tonnes: Decimal = Field(gt=0, le=1000000, max_digits=16, decimal_places=6)
    rejected_tonnes: Decimal = Field(ge=0, le=1000000, max_digits=16, decimal_places=6)
    note: str = Field(min_length=1, max_length=500)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def utc_second(cls, value: datetime) -> datetime:
        if value.microsecond:
            raise ValueError("Whole-second boundaries required")
        return value.astimezone(UTC)

    @field_validator("product", "note")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A nonblank declaration is required")
        return value

    @field_validator("asset_ids")
    @classmethod
    def unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Duplicate assets")
        return sorted(value)

    @model_validator(mode="after")
    def window(self) -> "ProductionWrite":
        if not 1 <= (self.ends_at - self.starts_at).total_seconds() <= 3600:
            raise ValueError("Report intervals must be 1–3600 seconds")
        return self


class ProductionReport(Contract):
    schema_version: Literal["1"] = "1"
    mode: Literal["SIMULATION"] = "SIMULATION"
    id: UUID
    org_id: UUID
    facility_id: UUID
    created_at: AwareDatetime
    actor: str
    declaration: ProductionWrite
    method: Literal["complete-second-electricity-sec-v1"] = "complete-second-electricity-sec-v1"
    production_source: Literal["OPERATOR_DECLARED"] = "OPERATOR_DECLARED"
    sync_state: Literal["LOCAL_ONLY"] = "LOCAL_ONLY"
    mapping_revisions: dict[str, str]
    expected_seconds: int
    valid_seconds: int
    source_digest: str
    first_row: int | None
    last_row: int | None
    status: Literal["COMPLETE", "INCOMPLETE"]
    reason: str | None
    energy_kwh: Decimal | None
    sec_kwh_per_good_tonne: Decimal | None
    reject_fraction: Decimal
    good_tonnes_per_hour: Decimal


class ReportComparisonRequest(Contract):
    baseline_id: UUID
    comparison_id: UUID


class ReportComparison(Contract):
    mode: Literal["SIMULATION"] = "SIMULATION"
    baseline_id: UUID
    comparison_id: UUID
    status: Literal["COMPARABLE", "NOT_COMPARABLE", "PRODUCTION_REGRESSION"]
    reasons: list[str]
    sec_change_percent: Decimal | None
    interpretation: str = (
        "Descriptive comparison of synthetic electricity and operator-declared output; "
        "not causal proof, industrial savings or independent quality verification."
    )


class ReportingSnapshot(Contract):
    mode: Literal["SIMULATION"] = "SIMULATION"
    reports: list[ProductionReport]
    next_before: int | None
    sequences: list[int]


class ReportingQuery(Contract):
    before: int | None = Field(default=None, ge=1, le=9223372036854775807)
