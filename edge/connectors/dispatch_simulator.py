"""Idempotent simulator command adapter; no OT transport or physical write support."""

import hashlib
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from edge.storage.repository import Rejected
from services.dispatch.contracts import DispatchCommand

if TYPE_CHECKING:
    from edge.storage.repository import Repository


class DispatchSimulator:
    def __init__(self, repo: "Repository") -> None:
        self.repo = repo

    def send(self, command: DispatchCommand, now: datetime) -> None:
        # Called in the dispatch transaction. Retry identity never changes.
        fingerprint = hashlib.sha256(
            (
                str(command.id)
                + str(command.duration_seconds)
                + command.behavior
                + "".join(a.model_dump_json() for a in command.actions)
            ).encode()
        ).hexdigest()
        row = self.repo.db.execute(
            "SELECT fingerprint FROM simulator_commands WHERE command_id=?", (str(command.id),)
        ).fetchone()
        if row:
            if row[0] != fingerprint:
                raise Rejected("SIMULATOR_REPLAY_CONFLICT")
            return
        delay = 7 if command.behavior == "delayed_ack" else 1
        ack = (
            None
            if command.behavior in ("missing_ack", "failed_command")
            else (now + timedelta(seconds=delay)).isoformat()
        )
        self.repo.db.execute(
            (
                "INSERT INTO simulator_commands(command_id,fingerprint,accepted_at,ack_at) "
                "VALUES (?,?,?,?)"
            ),
            (str(command.id), fingerprint, now.isoformat(), ack),
        )

    def acknowledged(self, command: DispatchCommand, now: datetime) -> bool:
        row = self.repo.db.execute(
            "SELECT ack_at FROM simulator_commands WHERE command_id=?", (str(command.id),)
        ).fetchone()
        return bool(row and row[0] and datetime.fromisoformat(row[0]) <= now)

    def start(self, command: DispatchCommand, now: datetime) -> None:
        end = now + timedelta(seconds=command.duration_seconds)
        self.repo.db.execute(
            (
                "UPDATE simulator_commands SET active=1,started_at=?,ends_at=? "
                "WHERE command_id=? AND started_at IS NULL"
            ),
            (now.isoformat(), end.isoformat(), str(command.id)),
        )

    def stop(self, command: DispatchCommand) -> None:
        self.repo.db.execute(
            "UPDATE simulator_commands SET active=0 WHERE command_id=?", (str(command.id),)
        )

    def reductions(self, now: datetime) -> dict[str, float]:
        with self.repo.lock:
            rows = self.repo.db.execute(
                "SELECT d.body,s.started_at,s.ends_at FROM simulator_commands s "
                "JOIN dispatch_commands d ON d.id=s.command_id "
                "WHERE s.active=1 AND d.state='EXECUTING'"
            ).fetchall()
            values = {}
            for row in rows:
                if datetime.fromisoformat(row[1]) <= now < datetime.fromisoformat(row[2]):
                    command = DispatchCommand.model_validate_json(row[0])
                    values.update({a.asset_id: a.reduction_kw for a in command.actions})
            return values
