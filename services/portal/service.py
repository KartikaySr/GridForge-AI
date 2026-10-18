import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg

from services.portal.contracts import (
    PortalEvent,
    PortalFacility,
    PortalHistory,
    PortalIdentity,
    PortalLogin,
    Portfolio,
)
from services.security.identity import password_hash
from services.sync.contracts import Stream


class PortalDenied(ValueError):
    pass


class PortalService:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def migrate(self) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                (Path(__file__).parents[2] / "database/migrations/0006_portal.sql").read_text()
            )

    def provision(self, login: PortalLogin, org_id: UUID, facility_id: UUID) -> UUID:
        """Local administrative provisioning; no browser-accessible registration endpoint."""
        identifier, salt = uuid4(), secrets.token_hex(16)
        hashed = password_hash(login.password, salt)
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "INSERT INTO portal_users(id,username,salt,password_hash) VALUES(%s,%s,%s,%s)",
                (identifier, login.username, salt, hashed),
            )
            conn.execute(
                "INSERT INTO portal_memberships VALUES(%s,%s,%s)", (identifier, org_id, facility_id)
            )
        return identifier

    def login(self, login: PortalLogin) -> tuple[str, PortalIdentity]:
        # A shared, durable global ceiling prevents unlimited parallel expensive password checks.
        with psycopg.connect(self.dsn) as conn:
            start, attempts = conn.execute(
                "SELECT window_start,attempts FROM portal_login_limit WHERE singleton=1 FOR UPDATE"
            ).fetchone() or (datetime.now(UTC), 20)
            now = datetime.now(UTC)
            if now - start >= timedelta(minutes=1):
                start, attempts = now, 0
            if attempts >= 20:
                raise PortalDenied("LOGIN_RATE_LIMIT")
            conn.execute(
                "UPDATE portal_login_limit SET window_start=%s,attempts=%s WHERE singleton=1",
                (start, attempts + 1),
            )
            row = conn.execute(
                "SELECT id,username,salt,password_hash,enabled FROM portal_users WHERE username=%s",
                (login.username,),
            ).fetchone()
        salt = row[2] if row else "0" * 32
        candidate = password_hash(login.password, salt)
        if not row or not hmac.compare_digest(candidate, row[3]) or not row[4]:
            raise PortalDenied("AUTH_REQUIRED")
        token = secrets.token_hex(32)
        expiry = datetime.now(UTC) + timedelta(hours=1)
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "DELETE FROM portal_sessions WHERE user_id=%s OR expires_at<=now()", (row[0],)
            )
            conn.execute(
                "INSERT INTO portal_sessions VALUES(%s,%s,%s)",
                (hashlib.sha256(token.encode()).hexdigest(), row[0], expiry),
            )
        return token, PortalIdentity(id=row[0], username=row[1], expires_at=expiry)

    def identity(self, token: str | None) -> PortalIdentity:
        if not token or len(token) != 64:
            raise PortalDenied("AUTH_REQUIRED")
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(
                "SELECT u.id,u.username,s.expires_at FROM portal_sessions s "
                "JOIN portal_users u ON u.id=s.user_id WHERE s.token_hash=%s "
                "AND s.expires_at>now() AND u.enabled",
                (hashlib.sha256(token.encode()).hexdigest(),),
            ).fetchone()
        if not row:
            raise PortalDenied("AUTH_REQUIRED")
        return PortalIdentity(id=row[0], username=row[1], expires_at=row[2])

    def logout(self, token: str | None) -> None:
        with psycopg.connect(self.dsn) as conn:
            conn.execute(
                "DELETE FROM portal_sessions WHERE token_hash=%s",
                (hashlib.sha256((token or "").encode()).hexdigest(),),
            )

    @staticmethod
    def restrict(conn: psycopg.Connection[tuple[object, ...]], user: PortalIdentity) -> None:
        conn.execute("SELECT set_config('gridforge.portal_user',%s,true)", (str(user.id),))
        conn.execute("SET LOCAL ROLE gridforge_portal_reader")
        conn.execute("SET LOCAL statement_timeout='2000ms'")

    def portfolio(self, user: PortalIdentity) -> Portfolio:
        with psycopg.connect(self.dsn) as conn:
            self.restrict(conn, user)
            rows = conn.execute(
                "SELECT e.edge_id,e.org_id,e.facility_id,e.enabled,max(v.received_at) "
                "FROM sync_edges e LEFT JOIN sync_events v ON v.edge_id=e.edge_id "
                "GROUP BY e.edge_id ORDER BY e.edge_id LIMIT 100"
            ).fetchall()
        now = datetime.now(UTC)
        return Portfolio(
            observed_at=now,
            facilities=[
                PortalFacility(
                    edge_id=r[0],
                    org_id=r[1],
                    facility_id=r[2],
                    enabled=r[3],
                    last_received_at=r[4],
                    freshness="NO_DATA"
                    if r[4] is None
                    else "RECENT_RECEIPT"
                    if timedelta(0) <= now - r[4] <= timedelta(seconds=30)
                    else "STALE",
                )
                for r in rows
            ],
        )

    def history(
        self, user: PortalIdentity, edge_id: UUID, stream: Stream, before: int
    ) -> PortalHistory:
        with psycopg.connect(self.dsn) as conn:
            self.restrict(conn, user)
            if not conn.execute("SELECT 1 FROM sync_edges WHERE edge_id=%s", (edge_id,)).fetchone():
                raise PortalDenied("FACILITY_UNAVAILABLE")
            rows = conn.execute(
                "SELECT event_id,sequence,stream,event_type,received_at,body FROM sync_events "
                "WHERE edge_id=%s AND stream=%s AND sequence<%s "
                "ORDER BY sequence DESC LIMIT 25",
                (edge_id, stream, before),
            ).fetchall()
        return PortalHistory(
            observed_at=datetime.now(UTC),
            edge_id=edge_id,
            stream=stream,
            events=[
                PortalEvent(
                    event_id=r[0],
                    sequence=r[1],
                    stream=r[2],
                    event_type=r[3],
                    received_at=r[4],
                    body=r[5],
                )
                for r in rows
            ],
            next_before=rows[-1][1] if len(rows) == 25 else None,
        )
