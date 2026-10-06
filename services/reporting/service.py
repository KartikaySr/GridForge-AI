import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from edge.storage.repository import CapacityError, Rejected, Repository
from services.dispatch.permissions import Principal
from services.finance.engine import measure
from services.registry.contracts import Asset, SignalMapping
from services.reporting.contracts import (
    ProductionReport,
    ProductionWrite,
    ReportComparison,
    ReportComparisonRequest,
    ReportingSnapshot,
)


class ReportingService:
    """Immutable local evidence, never an equipment command or savings-ledger write."""

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def require(self, actor: Principal, permission: str, now: datetime) -> None:
        actor.require(permission, self.repo.org_id, self.repo.facility_id, now)

    def create(self, write: ProductionWrite, actor: Principal, now: datetime) -> ProductionReport:
        self.require(actor, "report.create", now)
        fingerprint = hashlib.sha256(write.model_dump_json().encode()).hexdigest()
        with self.repo.lock, self.repo.db:
            existing = self.repo.db.execute(
                "SELECT fingerprint,payload FROM production_reports WHERE request_id=?",
                (str(write.request_id),),
            ).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise Rejected("REPORT_REQUEST_CONFLICT")
                return ProductionReport.model_validate_json(existing[1])
            if write.ends_at > now - timedelta(seconds=5):
                raise Rejected("REPORT_WINDOW_NOT_CLOSED")
            if (
                self.repo.db.execute("SELECT COUNT(*) FROM production_reports").fetchone()[0]
                >= 10000
            ):
                raise CapacityError("REPORT_CAPACITY_REACHED")
            records = self.repo.registry.records()
            assets = {r.entity.id: r.entity for r in records if isinstance(r.entity, Asset)}
            mappings = {
                r.entity.asset_id: f"{r.entity.id}:{r.revision}"
                for r in records
                if isinstance(r.entity, SignalMapping) and r.entity.enabled
            }
            if any(a not in assets or a not in mappings for a in write.asset_ids):
                raise Rejected("REPORT_ASSET_OR_MAPPING_UNAVAILABLE")
            mapping = {a: mappings[a] for a in write.asset_ids}
            rows = self.repo.db.execute(
                "SELECT COUNT(*) FROM telemetry WHERE event_time>=? AND event_time<?",
                (write.starts_at.isoformat(), write.ends_at.isoformat()),
            ).fetchone()[0]
            if rows > 100000:
                raise CapacityError("REPORT_QUERY_BOUND_EXCEEDED")
            evidence, _ = measure(
                self.repo, write.starts_at, write.ends_at, write.asset_ids, mapping, Decimal(0), now
            )
            seconds = int((write.ends_at - write.starts_at).total_seconds())
            energy = evidence.actual_energy_kwh
            report = ProductionReport(
                id=uuid4(),
                org_id=self.repo.org_id,
                facility_id=self.repo.facility_id,
                created_at=now,
                actor=actor.actor,
                declaration=write,
                mapping_revisions=mapping,
                expected_seconds=seconds,
                valid_seconds=evidence.valid_slots,
                source_digest=evidence.source_digest,
                first_row=evidence.first_row,
                last_row=evidence.last_row,
                status="COMPLETE" if evidence.quality == "COMPLETE" else "INCOMPLETE",
                reason=evidence.reason,
                energy_kwh=energy,
                sec_kwh_per_good_tonne=energy / write.good_tonnes if energy is not None else None,
                reject_fraction=write.rejected_tonnes / (write.good_tonnes + write.rejected_tonnes),
                good_tonnes_per_hour=write.good_tonnes * Decimal(3600) / Decimal(seconds),
            )
            self.repo.db.execute(
                "INSERT INTO production_reports(id,request_id,fingerprint,payload) "
                "VALUES (?,?,?,?)",
                (str(report.id), str(write.request_id), fingerprint, report.model_dump_json()),
            )
            return report

    def snapshot(self, actor: Principal, before: int | None = None) -> ReportingSnapshot:
        self.require(actor, "report.read", datetime.now(UTC))
        with self.repo.lock:
            rows = self.repo.db.execute(
                "SELECT sequence,payload FROM production_reports WHERE sequence<? "
                "ORDER BY sequence DESC LIMIT 20",
                (before or 2**63 - 1,),
            ).fetchall()
            return ReportingSnapshot(
                reports=[ProductionReport.model_validate_json(r[1]) for r in rows],
                sequences=[r[0] for r in rows],
                next_before=rows[-1][0] if len(rows) == 20 else None,
            )

    def get(self, identifier: UUID) -> ProductionReport:
        row = self.repo.db.execute(
            "SELECT payload FROM production_reports WHERE id=?", (str(identifier),)
        ).fetchone()
        if not row:
            raise Rejected("REPORT_NOT_FOUND")
        return ProductionReport.model_validate_json(row[0])

    def compare(self, request: ReportComparisonRequest, actor: Principal) -> ReportComparison:
        self.require(actor, "report.read", datetime.now(UTC))
        with self.repo.lock:
            a, b = self.get(request.baseline_id), self.get(request.comparison_id)
        reasons = []
        if a.id == b.id or a.declaration.ends_at > b.declaration.starts_at:
            reasons.append("BASELINE_MUST_PRECEDE_COMPARISON_WITHOUT_OVERLAP")
        if a.status != "COMPLETE" or b.status != "COMPLETE":
            reasons.append("INCOMPLETE_ENERGY_EVIDENCE")
        if a.declaration.product != b.declaration.product:
            reasons.append("PRODUCT_MISMATCH")
        if a.mapping_revisions != b.mapping_revisions:
            reasons.append("ASSET_OR_MAPPING_BOUNDARY_MISMATCH")
        if a.expected_seconds != b.expected_seconds:
            reasons.append("DURATION_MISMATCH")
        if not a.sec_kwh_per_good_tonne:
            reasons.append("NONPOSITIVE_BASELINE_SEC")
        status: Literal["COMPARABLE", "NOT_COMPARABLE", "PRODUCTION_REGRESSION"] = (
            "NOT_COMPARABLE" if reasons else "COMPARABLE"
        )
        if not reasons:
            if b.good_tonnes_per_hour < a.good_tonnes_per_hour:
                reasons.append("DECLARED_THROUGHPUT_DECREASED")
            if b.reject_fraction > a.reject_fraction:
                reasons.append("DECLARED_REJECT_FRACTION_INCREASED")
            if reasons:
                status = "PRODUCTION_REGRESSION"
        change = None
        if status == "COMPARABLE":
            assert a.sec_kwh_per_good_tonne is not None and b.sec_kwh_per_good_tonne is not None
            change = (b.sec_kwh_per_good_tonne / a.sec_kwh_per_good_tonne - 1) * Decimal(100)
        return ReportComparison(
            baseline_id=a.id,
            comparison_id=b.id,
            status=status,
            reasons=reasons,
            sec_change_percent=change,
        )
