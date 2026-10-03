"""Local development entry point; put a TLS reverse proxy in front of a deployed receiver."""

import os

import uvicorn

from cloud.app import create_cloud_app


def main() -> None:
    dsn = os.environ["GRIDFORGE_CLOUD_DATABASE_URL"]
    port = int(os.environ.get("GRIDFORGE_CLOUD_PORT", "8081"))
    app = create_cloud_app(dsn)
    uvicorn.run(app, host="127.0.0.1", port=port, proxy_headers=False, server_header=False)


if __name__ == "__main__":
    main()
