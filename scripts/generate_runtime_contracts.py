"""Export the local API contract without starting services or accessing user state."""

import json
from pathlib import Path
from uuid import uuid4

from edge.runtime.app import create_app

app = create_app("0" * 64, uuid4())  # Schema-only instance; never listens on a socket.
schema = app.openapi()
schema["components"]["securitySchemes"] = {"LocalSession": {"type": "http", "scheme": "bearer"}}
schema["security"] = [{"LocalSession": []}]
Path("packages/api-client/runtime.openapi.json").write_text(json.dumps(schema, indent=2) + "\n")
