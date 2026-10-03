from typing import Any

from fastapi import FastAPI

from edge.runtime.app import create_app as runtime_app


def create_app(*args: Any, **kwargs: Any) -> FastAPI:
    """Explicit trusted principal composition for pre-identity domain/transport tests."""
    return runtime_app(*args, identity_required=False, **kwargs)
