# ADR 0011: local identity, audit, recovery and packaged simulation release

Status: accepted for Phase 10 prototype scope.

## Decision

Keep the modular monolith and add server-owned local accounts to the existing native transport authentication. Use an eight-role capability map, a facility-scoped principal, eight-hour sessions and revision-based revocation. Trusted explicit principals remain available only to Python composition/tests, never as HTTP fields. All operational routes have a permission gate; domain checks remain authoritative.

Store identities, sessions, tamper-evident audit, bounded-label metrics and migration checksums in SQLite schema 9. Preserve durable domain outboxes and independent traceability throughout the control chain. Copy redacted diagnostics only at an authorized user's request. Restore backups into new files after checksum/integrity validation. Runtime crashes retain committed WAL/outbox data; uncommitted work rolls back.

Package the runtime with PyInstaller inside a Tauri macOS release app, using application-data storage and the same loopback/private-pipe protocol. The local build uses ad-hoc signing. Automatic updates stay disabled pending a protected signing pipeline, feed and pinned update key. See the operating guide for the release/signing/update architecture.

## Consequences

The desktop can be tested without an external identity provider or source checkout. Restart requires sign-in; the simulator continues ingestion while signed out. UI visibility is not an authorization boundary. Existing domain tests explicitly use a trusted test composition; new identity tests exercise the secure default.

Local SUPER_ADMIN is still constrained to one edge scope. Enterprise identity federation, cross-facility account administration, external audit anchoring, credential recovery, platform signing/notarization and update publication require deployment work. Hash chaining does not defeat an operating-system owner rewriting an entire database. This is a hardened simulation prototype, not an OT safety certification or a production deployment claim.
