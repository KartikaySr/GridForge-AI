"""Offline baselines behind a provider boundary; these are not trained language models."""

import hashlib
import math
import re
from typing import Protocol

from services.ai.contracts import Evidence

EMBEDDING_MODEL = "token-hash-256-v1"
DIMENSIONS = 256


def embed(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for word in re.findall(r"[a-z0-9]{2,}", text.lower()):
        raw = hashlib.sha256(word.encode()).digest()
        vector[int.from_bytes(raw[:2]) % DIMENSIONS] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1
    return [v / norm for v in vector]


class AdvisoryProvider(Protocol):
    name: str
    available: bool

    def answer(self, question: str, evidence: list[Evidence]) -> str: ...

    def sql(self, question: str) -> str | None: ...


class LocalEvidenceProvider:
    name = "local-extractive-v1"
    available = True

    def answer(self, question: str, evidence: list[Evidence]) -> str:
        # No document is interpreted as an instruction; citations quote source data verbatim.
        return "Retrieved source excerpts (untrusted document content; advisory only):\n\n" + (
            "\n\n".join(f"[{item.citation}] {item.excerpt}" for item in evidence)
        )

    def sql(self, question: str) -> str | None:
        words = set(re.findall(r"[a-z]+", question.lower()))
        if words & {"telemetry", "load", "power"}:
            return (
                "SELECT asset_id, value_kw, quality, flags, observed_at "
                "FROM ai_telemetry ORDER BY observed_at DESC LIMIT 20"
            )
        if words & {"dispatch", "commands", "command"}:
            return (
                "SELECT command_id, state, observed_at FROM ai_dispatch "
                "ORDER BY observed_at DESC LIMIT 20"
            )
        if words & {"savings", "ledger", "finance"}:
            return (
                "SELECT entry_id, status, currency, amount, observed_at "
                "FROM ai_savings ORDER BY observed_at DESC LIMIT 20"
            )
        return None


class UnavailableProvider:
    name = "unavailable"
    available = False

    def answer(self, question: str, evidence: list[Evidence]) -> str:
        raise RuntimeError("Provider unavailable")

    def sql(self, question: str) -> str | None:
        raise RuntimeError("Provider unavailable")
