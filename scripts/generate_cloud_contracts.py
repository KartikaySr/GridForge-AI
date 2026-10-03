"""Export cloud API contracts without connecting to PostgreSQL."""

import json
from pathlib import Path

from cloud.app import create_cloud_app

schema = create_cloud_app("", migrate=False).openapi()
schema["components"]["securitySchemes"] = {"EdgeToken": {"type": "http", "scheme": "bearer"}}
schema["security"] = [{"EdgeToken": []}]
Path("packages/api-client/cloud.openapi.json").write_text(json.dumps(schema, indent=2) + "\n")
