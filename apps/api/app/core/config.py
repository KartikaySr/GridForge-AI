"""Prototype configuration; no production or physical-control mode is supported."""

import os
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    mode: str
    cors_origins: tuple[str, ...]


def load_settings() -> Settings:
    mode = os.getenv("GRIDFORGE_MODE", "SIMULATION")
    if mode != "SIMULATION":
        raise ValueError("Only SIMULATION mode is supported")
    origins = tuple(
        origin.strip()
        for origin in os.getenv(
            "GRIDFORGE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
    )
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Prototype CORS origins must be explicit loopback HTTP origins")
        # Accessing port also validates malformed port values.
        _ = parsed.port
    return Settings(mode=mode, cors_origins=origins)
