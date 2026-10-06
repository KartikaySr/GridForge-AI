from typing import Literal

Role = Literal[
    "SUPER_ADMIN",
    "ORG_ADMIN",
    "FACILITY_MANAGER",
    "ENERGY_MANAGER",
    "OPERATOR",
    "OT_ENGINEER",
    "ANALYST",
    "VIEWER",
]
READ = frozenset(
    {
        "registry.read",
        "telemetry.read",
        "forecast.read",
        "optimization.read",
        "dispatch.read",
        "finance.read",
        "tariff.read",
        "sync.read",
        "system.read",
        "report.read",
        "alert.read",
    }
)
ALL = READ | frozenset(
    {
        "facility.update",
        "asset.update",
        "device.configure",
        "telemetry.ingest",
        "optimization.run",
        "optimization.configure",
        "dispatch.request",
        "dispatch.approve",
        "dispatch.cancel",
        "finance.verify",
        "report.create",
        "alert.manage",
        "tariff.update",
        "ai.use",
        "ai.inspect",
        "ai.ingest",
        "system.configure",
        "system.diagnostics",
        "simulator.control",
        "user.manage",
        "audit.read",
    }
)
ROLES: dict[str, frozenset[str]] = {
    "SUPER_ADMIN": ALL,
    "ORG_ADMIN": ALL,
    "FACILITY_MANAGER": ALL - {"user.manage"},
    "ENERGY_MANAGER": READ
    | {
        "optimization.run",
        "optimization.configure",
        "dispatch.request",
        "dispatch.approve",
        "dispatch.cancel",
        "finance.verify",
        "report.create",
        "alert.manage",
        "tariff.update",
        "ai.use",
        "ai.inspect",
        "ai.ingest",
        "audit.read",
    },
    "OPERATOR": READ | {"dispatch.request", "dispatch.cancel", "ai.use", "alert.manage"},
    "OT_ENGINEER": READ
    | {
        "asset.update",
        "device.configure",
        "telemetry.ingest",
        "simulator.control",
        "system.diagnostics",
        "ai.use",
        "ai.ingest",
    },
    "ANALYST": READ | {"ai.use", "ai.inspect", "audit.read"},
    "VIEWER": READ,
}


def route_permission(method: str, path: str, kind: str | None = None) -> str | None:
    if path in {
        "/api/v1/system/health",
        "/api/v1/system/diagnostics",
        "/api/v1/identity",
        "/api/v1/identity/login",
        "/api/v1/identity/bootstrap",
        "/api/v1/identity/logout",
    }:
        return None
    if path.startswith("/api/v1/incidents"):
        return "alert.manage" if path.endswith("/actions") else "alert.read"
    if path.startswith("/api/v1/reports"):
        return "report.create" if path.endswith("/production") else "report.read"
    if path.startswith("/api/v1/demo"):
        return "system.configure"
    if path.startswith("/api/v1/identity/users"):
        return "user.manage"
    if path.startswith("/api/v1/security"):
        return "audit.read"
    if path.startswith("/api/v1/system/bundle"):
        return "system.diagnostics"
    if path.startswith("/api/v1/system/metrics"):
        return "system.read"
    if path.startswith("/api/v1/system/authorize"):
        return "system.configure"
    if path.startswith("/api/v1/simulator"):
        return "simulator.control"
    if path.startswith("/api/v1/registry"):
        return (
            (
                "facility.update"
                if kind in {"organization", "facility", "line"}
                else "device.configure"
                if kind in {"device", "mapping", "metric"}
                else "asset.update"
            )
            if method == "POST"
            else "registry.read"
        )
    if path.startswith("/api/v1/telemetry"):
        return "telemetry.ingest" if method == "POST" else "telemetry.read"
    if path.startswith(("/api/v1/forecasts", "/api/v1/intelligence")):
        return "forecast.read"
    if path.startswith("/api/v1/optimization"):
        return (
            ("optimization.configure" if path.endswith("/policies") else "optimization.run")
            if method == "POST"
            else "optimization.read"
        )
    if path.startswith("/api/v1/dispatch"):
        # The service enforces approve/cancel separately from the common dispatch read gate.
        return "dispatch.request" if path.endswith("/requests") else "dispatch.read"
    if path.startswith("/api/v1/finance"):
        return (
            ("tariff.update" if path.endswith("/tariffs") else "finance.verify")
            if method == "POST"
            else "finance.read"
        )
    if path.startswith("/api/v1/ai"):
        return (
            "ai.ingest"
            if path.endswith("/documents")
            else "ai.inspect"
            if "/queries/" in path
            else "ai.use"
        )
    if path.startswith("/api/v1/sync"):
        return "sync.read"
    return "unknown.deny"
