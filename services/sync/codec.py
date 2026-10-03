import hashlib
import json
from typing import Any

from services.sync.contracts import Stream

STREAMS: tuple[Stream, ...] = (
    "telemetry",
    "registry",
    "intelligence",
    "optimization",
    "dispatch",
    "finance",
    "ai",
)
PRODUCERS: dict[Stream, str] = {
    "telemetry": "edge.telemetry",
    "registry": "edge.registry",
    "intelligence": "edge.intelligence",
    "optimization": "edge.optimization",
    "dispatch": "edge.dispatch",
    "finance": "edge.finance",
    "ai": "edge.ai",
}
OUTBOX_TABLES: dict[Stream, tuple[str, str, str]] = {
    "telemetry": ("outbox", "id", "payload"),
    "registry": ("configuration_outbox", "sequence", "body"),
    "intelligence": ("intelligence_outbox", "sequence", "body"),
    "optimization": ("optimization_outbox", "sequence", "body"),
    "dispatch": ("dispatch_outbox", "sequence", "body"),
    "finance": ("finance_outbox", "sequence", "body"),
    "ai": ("ai_outbox", "sequence", "body"),
}


def digest(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()
