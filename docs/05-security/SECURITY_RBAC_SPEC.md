# Security & RBAC

Roles: SUPER_ADMIN, ORG_ADMIN, FACILITY_MANAGER, ENERGY_MANAGER, OPERATOR, OT_ENGINEER, ANALYST, VIEWER.
Permissions are capabilities: facility.read/update, asset.read/update, telemetry.read, device.read/configure,
tariff.read/update, forecast.read, optimization.read/run, dispatch.read/approve/cancel, finance.read/finalize,
ai.use/inspect, report.read/create, user.read/manage, audit.read, system.configure.

Cloud auth is OIDC/OAuth-compatible; desktop has secure user session + edge identity. Store tokens in OS credential
facility where possible; never log them. Backend enforces permission + org/facility scope; hidden buttons are not
authorization. RLS is defense-in-depth.

Desktop: loopback local service, authenticated IPC/API, minimal Tauri capabilities, signed production builds/updates,
session expiry for sensitive actions. Audit actor/action/resource/time/request-correlation/scope/outcome; append-oriented.

Threat tests: IDOR/tenant escape, privilege escalation, command replay, sync replay, malicious RAG prompt/SQL,
malformed/oversized telemetry, connector spoofing, token theft, exposed local API, update tampering.
