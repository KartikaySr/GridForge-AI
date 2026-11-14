import json
from pathlib import Path

from cloud.portal import create_portal_app

schema = create_portal_app("", "https://gridforge.example", migrate=False).openapi()
schema["components"]["securitySchemes"] = {
    "PortalSession": {"type": "apiKey", "in": "cookie", "name": "gridforge_portal_session"},
    "MobileSession": {"type": "http", "scheme": "bearer"},
}
for path, operations in schema["paths"].items():
    if path not in ["/api/v1/login", "/api/v1/health", "/api/v1/mobile/login"]:
        for operation in operations.values():
            operation["security"] = [
                {"MobileSession" if "/mobile/" in path else "PortalSession": []}
            ]
Path("packages/api-client/portal.openapi.json").write_text(json.dumps(schema, indent=2) + "\n")
