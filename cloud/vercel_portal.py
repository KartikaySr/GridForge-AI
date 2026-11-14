"""ASGI entrypoint for Vercel; provision schema separately before serving traffic."""

import os

from cloud.portal import create_portal_app

app = create_portal_app(
    os.environ["GRIDFORGE_CLOUD_DATABASE_URL"],
    os.environ["GRIDFORGE_WEB_ORIGIN"],
    secure=True,
    migrate=False,
)
