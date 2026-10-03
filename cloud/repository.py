import hashlib
import hmac
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from services.sync.codec import PRODUCERS, STREAMS, digest
from services.sync.contracts import (
    CloudStreamCursor,
    CloudSyncState,
    Stream,
    SyncAck,
    SyncBatch,
    SyncEntry,
)


class CloudRejected(ValueError):
    def __init__(self, code: str, stream: str = "", sequence: int = 0) -> None:
        super().__init__(code)
        self.code = code
        self.stream = stream
        self.sequence = sequence


class CloudRepository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def migrate(self) -> None:
        with psycopg.connect(self.dsn) as conn:
            for name in ("0002_sync.sql", "0003_ai_sync.sql"):
                conn.execute((Path(__file__).parents[1] / "database/migrations" / name).read_text())

    def enroll(self, edge_id: UUID, org_id: UUID, facility_id: UUID, token: str) -> None:
        """Administrator-only local provisioning API; never exposed as an HTTP route."""
        if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
            raise ValueError("Edge token must be 256-bit lowercase hexadecimal")
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "INSERT INTO sync_edges(edge_id,org_id,facility_id,token_sha256) "
                "VALUES (%s,%s,%s,%s)",
                (edge_id, org_id, facility_id, token_hash),
            )
            for stream in STREAMS:
                conn.execute(
                    "INSERT INTO sync_stream_cursors(edge_id,stream) VALUES (%s,%s)",
                    (edge_id, stream),
                )

    def authenticate(self, edge_id: UUID, token: str) -> tuple[UUID, UUID]:
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(
                "SELECT org_id,facility_id,token_sha256,enabled FROM sync_edges WHERE edge_id=%s",
                (edge_id,),
            ).fetchone()
        candidate = hashlib.sha256(token.encode()).hexdigest()
        if not row or not row[3] or not hmac.compare_digest(row[2], candidate):
            raise CloudRejected("EDGE_AUTH_DENIED")
        return row[0], row[1]

    def state(self, edge_id: UUID, token: str) -> CloudSyncState:
        org_id, facility_id = self.authenticate(edge_id, token)
        with psycopg.connect(self.dsn) as conn:
            rows = conn.execute(
                "SELECT stream,acknowledged_sequence FROM sync_stream_cursors "
                "WHERE edge_id=%s ORDER BY stream",
                (edge_id,),
            ).fetchall()
        return CloudSyncState(
            edge_id=edge_id,
            org_id=org_id,
            facility_id=facility_id,
            observed_at=datetime.now(UTC),
            cursors=[
                CloudStreamCursor(stream=row[0], acknowledged_sequence=row[1]) for row in rows
            ],
        )

    @staticmethod
    def scope_matches(value: Any, org_id: UUID, facility_id: UUID) -> bool:
        if isinstance(value, dict):
            if "org_id" in value and value["org_id"] != str(org_id):
                return False
            if "facility_id" in value and value["facility_id"] != str(facility_id):
                return False
            if "mode" in value and value["mode"] != "SIMULATION":
                return False
            return all(
                CloudRepository.scope_matches(item, org_id, facility_id) for item in value.values()
            )
        if isinstance(value, list):
            return all(CloudRepository.scope_matches(item, org_id, facility_id) for item in value)
        return True

    @staticmethod
    def validate_entry(entry: SyncEntry, stream: Stream, org_id: UUID, facility_id: UUID) -> None:
        body = entry.body
        if (
            str(body.get("event_id")) != str(entry.event_id)
            or body.get("org_id") != str(org_id)
            or body.get("facility_id") != str(facility_id)
            or body.get("schema_version") != "1"
            or body.get("producer") != PRODUCERS[stream]
            or not isinstance(body.get("event_type"), str)
            or not isinstance(body.get("occurred_at"), str)
            or ("sequence" in body and body["sequence"] != entry.sequence)
            or digest(body) != entry.digest
            or not CloudRepository.scope_matches(body, org_id, facility_id)
        ):
            raise CloudRejected("EVENT_CONTRACT_OR_SCOPE_CONFLICT", stream, entry.sequence)

    def apply(self, batch: SyncBatch, token: str) -> SyncAck:
        org_id, facility_id = self.authenticate(batch.edge_id, token)
        accepted = replayed = 0
        try:
            with psycopg.connect(self.dsn) as conn:
                row = conn.execute(
                    "SELECT acknowledged_sequence FROM sync_stream_cursors "
                    "WHERE edge_id=%s AND stream=%s FOR UPDATE",
                    (batch.edge_id, batch.stream),
                ).fetchone()
                if not row:
                    raise CloudRejected("UNKNOWN_STREAM", batch.stream)
                cursor = int(row[0])
                for entry in batch.entries:
                    self.validate_entry(entry, batch.stream, org_id, facility_id)
                    if entry.sequence <= cursor:
                        existing = conn.execute(
                            "SELECT event_id,digest FROM sync_events "
                            "WHERE edge_id=%s AND stream=%s AND sequence=%s",
                            (batch.edge_id, batch.stream, entry.sequence),
                        ).fetchone()
                        if not existing or existing != (entry.event_id, entry.digest):
                            raise CloudRejected("REPLAY_CONFLICT", batch.stream, entry.sequence)
                        replayed += 1
                        continue
                    if entry.sequence != cursor + 1:
                        raise CloudRejected("SEQUENCE_GAP", batch.stream, entry.sequence)
                    try:
                        conn.execute(
                            "INSERT INTO sync_events(edge_id,stream,sequence,event_id,org_id,"
                            "facility_id,event_type,schema_version,digest,body) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                batch.edge_id,
                                batch.stream,
                                entry.sequence,
                                entry.event_id,
                                org_id,
                                facility_id,
                                entry.body["event_type"],
                                "1",
                                entry.digest,
                                Jsonb(entry.body),
                            ),
                        )
                    except psycopg.errors.UniqueViolation:
                        raise CloudRejected(
                            "EVENT_ID_CONFLICT", batch.stream, entry.sequence
                        ) from None
                    cursor = entry.sequence
                    accepted += 1
                conn.execute(
                    "UPDATE sync_stream_cursors SET acknowledged_sequence=%s,updated_at=now() "
                    "WHERE edge_id=%s AND stream=%s",
                    (cursor, batch.edge_id, batch.stream),
                )
            return SyncAck(
                edge_id=batch.edge_id,
                stream=batch.stream,
                acknowledged_sequence=batch.entries[-1].sequence,
                accepted=accepted,
                replayed=replayed,
                committed_at=datetime.now(UTC),
            )
        except CloudRejected as exc:
            if exc.stream:
                with psycopg.connect(self.dsn) as conn:
                    conn.execute(
                        "INSERT INTO sync_conflict_audit(edge_id,stream,sequence,code) "
                        "VALUES (%s,%s,%s,%s)",
                        (batch.edge_id, exc.stream, exc.sequence, exc.code),
                    )
            raise
