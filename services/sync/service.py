"""One-way durable sync. Cloud ACK may advance local cursors; it cannot dispatch commands."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol
from urllib.parse import urlparse
from uuid import UUID

import httpx

from edge.storage.repository import Repository
from services.dispatch.permissions import Principal
from services.sync.codec import OUTBOX_TABLES, STREAMS, digest
from services.sync.contracts import (
    CloudSyncState,
    Stream,
    SyncAck,
    SyncBatch,
    SyncConflict,
    SyncEntry,
    SyncSnapshot,
    SyncStreamStatus,
)


class SyncFailure(ValueError):
    def __init__(self, code: str, stream: Stream | None = None, sequence: int = 0) -> None:
        super().__init__(code)
        self.code = code
        self.stream = stream
        self.sequence = sequence


class CloudTransport(Protocol):
    def state(self, edge_id: UUID, token: str) -> CloudSyncState: ...

    def upload(self, batch: SyncBatch, token: str) -> SyncAck: ...


class HttpCloudTransport:
    def __init__(self, url: str) -> None:
        parsed = urlparse(url)
        if (
            (
                parsed.scheme != "https"
                and not (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost"))
            )
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Cloud URL must use HTTPS or local loopback HTTP")
        self.url = url.rstrip("/")

    def request(
        self, method: str, route: str, edge_id: UUID, token: str, body: SyncBatch | None = None
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}", "X-Edge-ID": str(edge_id)}
        try:
            with httpx.Client(timeout=3, trust_env=False) as client:
                response = client.request(
                    method,
                    self.url + route,
                    headers=headers,
                    json=body.model_dump(mode="json") if body else None,
                )
        except httpx.HTTPError:
            raise SyncFailure("CLOUD_UNAVAILABLE") from None
        if response.status_code in (401, 403):
            raise SyncFailure("EDGE_AUTH_DENIED")
        if response.status_code in (413, 422):
            raise SyncFailure(
                "BATCH_TOO_LARGE" if response.status_code == 413 else "REMOTE_CONTRACT_REJECTED",
                body.stream if body else None,
                body.entries[0].sequence if body else 0,
            )
        if response.status_code == 409:
            try:
                code = response.json().get("code", "REMOTE_CONFLICT")
            except ValueError:
                code = "REMOTE_CONFLICT"
            raise SyncFailure(
                code if isinstance(code, str) else "REMOTE_CONFLICT",
                body.stream if body else None,
                body.entries[0].sequence if body else 0,
            )
        if response.status_code != 200:
            raise SyncFailure("CLOUD_UNAVAILABLE")
        try:
            value = response.json()
        except ValueError:
            raise SyncFailure("INVALID_CLOUD_RESPONSE") from None
        if not isinstance(value, dict):
            raise SyncFailure("INVALID_CLOUD_RESPONSE")
        return value

    def state(self, edge_id: UUID, token: str) -> CloudSyncState:
        return CloudSyncState.model_validate(
            self.request("GET", "/api/v1/sync/state", edge_id, token)
        )

    def upload(self, batch: SyncBatch, token: str) -> SyncAck:
        return SyncAck.model_validate(
            self.request("POST", "/api/v1/sync/batches", batch.edge_id, token, batch)
        )


class SyncService:
    def __init__(
        self,
        repo: Repository,
        url: str | None = None,
        token: str | None = None,
        transport: CloudTransport | None = None,
    ) -> None:
        self.repo = repo
        self.token = (
            token
            if token and len(token) == 64 and all(c in "0123456789abcdef" for c in token)
            else None
        )
        self.transport = transport or (HttpCloudTransport(url) if url and self.token else None)
        self.configured = self.token is not None and self.transport is not None
        self.state: Literal["NOT_CONFIGURED", "OFFLINE", "SYNCING", "SYNCHRONIZED", "CONFLICT"] = (
            "OFFLINE" if self.configured else "NOT_CONFIGURED"
        )
        self.message = (
            "Awaiting cloud connection"
            if self.configured
            else "Cloud endpoint and edge token not configured"
        )
        self.next_attempt_at: datetime | None = None
        self.backoff_seconds = 1

    def pending_batch(self, stream: Stream) -> SyncBatch | None:
        table, key, body = OUTBOX_TABLES[stream]
        with self.repo.lock:
            cursor = self.repo.db.execute(
                "SELECT acknowledged_sequence FROM sync_streams WHERE stream=?", (stream,)
            ).fetchone()[0]
            rows = self.repo.db.execute(
                f"SELECT {key},{body} FROM {table} WHERE {key}>? ORDER BY {key} LIMIT 20",
                (cursor,),
            ).fetchall()
        if not rows:
            return None
        entries = []
        for row in rows:
            try:
                payload = json.loads(row[1])
                entries.append(
                    SyncEntry(
                        sequence=row[0],
                        event_id=UUID(payload["event_id"]),
                        digest=digest(payload),
                        body=payload,
                    )
                )
            except (ValueError, KeyError, TypeError):
                raise SyncFailure("LOCAL_EVENT_INVALID", stream, row[0]) from None
        if entries[0].sequence != cursor + 1 or any(
            item.sequence != previous.sequence + 1
            for previous, item in zip(entries, entries[1:], strict=False)
        ):
            raise SyncFailure("LOCAL_SEQUENCE_GAP", stream, entries[0].sequence)
        batch = SyncBatch(edge_id=self.repo.edge_id, stream=stream, entries=entries)
        while len(batch.model_dump_json().encode()) > 48000:
            if len(entries) == 1:
                raise SyncFailure("LOCAL_EVENT_TOO_LARGE", stream, entries[0].sequence)
            entries.pop()
            batch = SyncBatch(edge_id=self.repo.edge_id, stream=stream, entries=entries)
        return batch

    def acknowledge(self, batch: SyncBatch, ack: SyncAck, now: datetime) -> None:
        if (
            ack.edge_id != self.repo.edge_id
            or ack.stream != batch.stream
            or ack.acknowledged_sequence != batch.entries[-1].sequence
            or ack.accepted + ack.replayed != len(batch.entries)
        ):
            raise SyncFailure("INVALID_CLOUD_ACK", batch.stream, batch.entries[0].sequence)
        table, key, _ = OUTBOX_TABLES[batch.stream]
        with self.repo.lock, self.repo.db:
            cursor = self.repo.db.execute(
                "SELECT acknowledged_sequence FROM sync_streams WHERE stream=?", (batch.stream,)
            ).fetchone()[0]
            if cursor != batch.entries[0].sequence - 1:
                raise SyncFailure("LOCAL_CURSOR_CHANGED", batch.stream, batch.entries[0].sequence)
            self.repo.db.execute(
                f"UPDATE {table} SET acknowledged=1 WHERE {key}>? AND {key}<=?",
                (cursor, ack.acknowledged_sequence),
            )
            self.repo.db.execute(
                "UPDATE sync_streams SET acknowledged_sequence=?,last_success_at=?,last_error=NULL "
                "WHERE stream=?",
                (ack.acknowledged_sequence, now.isoformat(), batch.stream),
            )

    def conflict(self, error: SyncFailure, now: datetime) -> None:
        if error.stream is None:
            return
        with self.repo.lock, self.repo.db:
            existing = self.repo.db.execute(
                "SELECT conflict_code FROM sync_streams WHERE stream=?", (error.stream,)
            ).fetchone()[0]
            if existing:
                return
            self.repo.db.execute(
                "INSERT INTO sync_conflicts(stream,sequence,code,detected_at,detail) "
                "VALUES (?,?,?,?,?)",
                (
                    error.stream,
                    error.sequence,
                    error.code,
                    now.isoformat(),
                    "Stream quarantined; no events discarded or overwritten",
                ),
            )
            self.repo.db.execute(
                "UPDATE sync_streams SET conflict_code=?,last_error=? WHERE stream=?",
                (error.code, error.code, error.stream),
            )

    def tick(self, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        if not self.configured or not self.transport or not self.token:
            return
        if self.next_attempt_at and now < self.next_attempt_at:
            return
        self.state = "SYNCING"
        self.message = "Reconciling cloud cursors and uploading durable events"
        try:
            remote = self.transport.state(self.repo.edge_id, self.token)
            if (remote.edge_id, remote.org_id, remote.facility_id) != (
                self.repo.edge_id,
                self.repo.org_id,
                self.repo.facility_id,
            ):
                raise SyncFailure("REMOTE_SCOPE_MISMATCH")
            cursors = {row.stream: row.acknowledged_sequence for row in remote.cursors}
            if set(cursors) != set(STREAMS):
                raise SyncFailure("REMOTE_CURSOR_SET_INVALID")
            for stream in STREAMS:
                with self.repo.lock:
                    local = self.repo.db.execute(
                        "SELECT acknowledged_sequence,conflict_code FROM sync_streams "
                        "WHERE stream=?",
                        (stream,),
                    ).fetchone()
                    table, key, _ = OUTBOX_TABLES[stream]
                    last = self.repo.db.execute(
                        f"SELECT COALESCE(MAX({key}),0) FROM {table}"
                    ).fetchone()[0]
                if local[1]:
                    continue
                try:
                    if cursors[stream] < local[0] or cursors[stream] > last:
                        raise SyncFailure("CURSOR_DIVERGENCE", stream, int(cursors[stream]))
                    for _ in range(5):
                        batch = self.pending_batch(stream)
                        if not batch:
                            break
                        ack = self.transport.upload(batch, self.token)
                        self.acknowledge(batch, ack, now)
                except SyncFailure as exc:
                    if exc.code in (
                        "CLOUD_UNAVAILABLE",
                        "EDGE_AUTH_DENIED",
                        "INVALID_CLOUD_RESPONSE",
                    ):
                        raise
                    self.conflict(exc, now)
            self.backoff_seconds = 1
            self.next_attempt_at = None
            self.state = (
                "CONFLICT"
                if self.snapshot_state_has_conflict()
                else ("SYNCHRONIZED" if self.pending_count() == 0 else "SYNCING")
            )
            self.message = (
                "One or more streams quarantined for reconciliation"
                if self.state == "CONFLICT"
                else "All cloud streams acknowledged"
                if self.state == "SYNCHRONIZED"
                else "Uploading pending events"
            )
        except Exception:
            self.state = "OFFLINE"
            self.message = "Cloud unavailable or identity rejected; local operation continues"
            self.next_attempt_at = now + timedelta(seconds=self.backoff_seconds)
            self.backoff_seconds = min(self.backoff_seconds * 2, 60)

    def snapshot_state_has_conflict(self) -> bool:
        with self.repo.lock:
            return bool(
                self.repo.db.execute(
                    "SELECT 1 FROM sync_streams WHERE conflict_code IS NOT NULL LIMIT 1"
                ).fetchone()
            )

    def pending_count(self) -> int:
        with self.repo.lock:
            return sum(
                int(
                    self.repo.db.execute(
                        f"SELECT COUNT(*) FROM {OUTBOX_TABLES[stream][0]} WHERE acknowledged=0"
                    ).fetchone()[0]
                )
                for stream in STREAMS
            )

    def snapshot(self, principal: Principal, now: datetime | None = None) -> SyncSnapshot:
        now = now or datetime.now(UTC)
        principal.require("sync.read", self.repo.org_id, self.repo.facility_id, now)
        streams = []
        oldest: datetime | None = None
        with self.repo.lock:
            for stream in STREAMS:
                table, key, body = OUTBOX_TABLES[stream]
                row = self.repo.db.execute(
                    "SELECT acknowledged_sequence,last_success_at,last_error,conflict_code "
                    "FROM sync_streams WHERE stream=?",
                    (stream,),
                ).fetchone()
                last = self.repo.db.execute(
                    f"SELECT COALESCE(MAX({key}),0) FROM {table}"
                ).fetchone()[0]
                pending = self.repo.db.execute(
                    f"SELECT COUNT(*),MIN(json_extract({body},'$.occurred_at')) "
                    f"FROM {table} WHERE acknowledged=0"
                ).fetchone()
                age_at = datetime.fromisoformat(pending[1]) if pending[1] else None
                if age_at and (oldest is None or age_at < oldest):
                    oldest = age_at
                streams.append(
                    SyncStreamStatus(
                        stream=stream,
                        local_last_sequence=last,
                        acknowledged_sequence=row[0],
                        pending_count=pending[0],
                        oldest_pending_at=age_at,
                        last_success_at=datetime.fromisoformat(row[1]) if row[1] else None,
                        last_error=row[2],
                        conflict_code=row[3],
                    )
                )
            conflict_count = self.repo.db.execute(
                "SELECT COUNT(*) FROM sync_conflicts WHERE resolved=0"
            ).fetchone()[0]
            conflicts = [
                SyncConflict(
                    id=row[0],
                    stream=row[1],
                    sequence=row[2],
                    code=row[3],
                    detected_at=datetime.fromisoformat(row[4]),
                    detail=row[5],
                    resolved=bool(row[6]),
                )
                for row in self.repo.db.execute(
                    "SELECT id,stream,sequence,code,detected_at,detail,resolved "
                    "FROM sync_conflicts ORDER BY id DESC LIMIT 20"
                )
            ]
        total = sum(item.pending_count for item in streams)
        successes = [item.last_success_at for item in streams if item.last_success_at]
        state = "CONFLICT" if conflict_count else self.state
        return SyncSnapshot(
            edge_id=self.repo.edge_id,
            org_id=self.repo.org_id,
            facility_id=self.repo.facility_id,
            observed_at=now,
            state=state,
            configured=self.configured,
            pending_count=total,
            oldest_pending_at=oldest,
            oldest_pending_age_seconds=max(0, (now - oldest).total_seconds()) if oldest else None,
            last_success_at=max(successes) if successes else None,
            conflict_count=conflict_count,
            streams=streams,
            conflicts=conflicts,
            message=self.message,
        )
