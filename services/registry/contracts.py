from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, Field, TypeAdapter, field_validator, model_validator

from edge.runtime.contracts import Contract

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")]
Positive = Annotated[float, Field(ge=0, le=1000000, allow_inf_nan=False)]


class Entity(Contract):
    id: Identifier
    org_id: UUID
    facility_id: UUID
    name: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")
    enabled: bool = True


class Organization(Entity):
    kind: Literal["organization"] = "organization"


class Facility(Entity):
    kind: Literal["facility"] = "facility"
    timezone: str = "UTC"
    simulation_demand_threshold_kw: float | None = Field(
        default=None, gt=0, le=100000000, allow_inf_nan=False
    )

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown IANA timezone") from None
        return value


class ProductionLine(Entity):
    kind: Literal["line"] = "line"


class Maintenance(Contract):
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    reason: str = Field(min_length=1, max_length=200)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("Maintenance end must follow start")
        return self


class Asset(Entity):
    kind: Literal["asset"] = "asset"
    line_id: Identifier
    rated_kw: Positive
    criticality: Literal["NORMAL", "CRITICAL"] = "NORMAL"
    capabilities: list[Literal["telemetry", "simulated_load_adjustment"]] = Field(
        default=["telemetry"], max_length=2
    )
    flexible: bool = False
    max_reduction_kw: Positive = 0
    min_load_kw: Positive = 0
    max_load_kw: Positive
    min_run_seconds: int = Field(default=0, ge=0, le=86400)
    min_off_seconds: int = Field(default=0, ge=0, le=86400)
    maintenance: list[Maintenance] = Field(default=[], max_length=20)

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if not self.min_load_kw <= self.rated_kw <= self.max_load_kw:
            raise ValueError("Load bounds must contain the rated load")
        if self.max_reduction_kw > self.rated_kw - self.min_load_kw:
            raise ValueError("Reduction exceeds configured range")
        if self.flexible and (
            self.criticality == "CRITICAL" or "simulated_load_adjustment" not in self.capabilities
        ):
            raise ValueError("Flexible assets require noncritical simulated capability")
        if not self.flexible and self.max_reduction_kw != 0:
            raise ValueError("Nonflexible assets cannot declare reduction")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ValueError("Duplicate capabilities")
        return self

    def flexibility_available(self, now: datetime) -> bool:
        return (
            self.enabled
            and self.flexible
            and not any(m.starts_at <= now < m.ends_at for m in self.maintenance)
        )


class Device(Entity):
    kind: Literal["device"] = "device"
    protocol: Literal["SIMULATOR"] = "SIMULATOR"
    writable: Literal[False] = False


class Metric(Entity):
    kind: Literal["metric"] = "metric"
    metric: Literal["active_power"] = "active_power"
    canonical_unit: Literal["kW"] = "kW"


class SignalMapping(Entity):
    kind: Literal["mapping"] = "mapping"
    asset_id: Identifier
    device_id: Identifier
    signal_id: Identifier
    metric_id: Literal["active_power"] = "active_power"
    input_unit: Literal["W", "kW"] = "W"
    scale: float = Field(default=0.001, gt=0, le=1000, allow_inf_nan=False)
    offset: float = Field(default=0, ge=-1000000, le=1000000, allow_inf_nan=False)
    writable: Literal[False] = False


RegistryEntity = Annotated[
    Organization | Facility | ProductionLine | Asset | Device | Metric | SignalMapping,
    Field(discriminator="kind"),
]
ENTITY: TypeAdapter[RegistryEntity] = TypeAdapter(RegistryEntity)


class RegistryRecord(Contract):
    revision: int
    entity: RegistryEntity


class RegistryWrite(Contract):
    expected_revision: int = Field(ge=0)
    request_id: UUID
    entity: RegistryEntity


class ConfigurationEvent(Contract):
    sequence: int
    event_id: UUID
    event_type: Literal["ConfigurationChanged"] = "ConfigurationChanged"
    schema_version: Literal["1"] = "1"
    occurred_at: AwareDatetime
    producer: Literal["edge.registry"] = "edge.registry"
    org_id: UUID
    facility_id: UUID
    correlation_id: UUID
    causation_id: UUID
    actor: Literal["local-simulation-session"] = "local-simulation-session"
    idempotency_key: UUID
    payload: RegistryRecord


class ConnectorHealth(Contract):
    device_id: str
    state: Literal["CONNECTED", "DISCONNECTED", "DISABLED", "DEGRADED"]
    protocol: Literal["SIMULATOR"] = "SIMULATOR"
    writable: Literal[False] = False
    mapping_count: int
    last_received_at: datetime | None
    detail: str


class RegistrySnapshot(Contract):
    schema_version: Literal["1"] = "1"
    mode: Literal["SIMULATION"] = "SIMULATION"
    org_id: UUID
    facility_id: UUID
    records: list[RegistryRecord]
    connectors: list[ConnectorHealth]
    flexibility_available: list[str]
    pending_configuration_events: int
