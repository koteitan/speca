"""FastAPI app factory for the SPECA web backend.

The app is intentionally tiny in Slice 0. Other slices wire in routers via the
anchor comments below — each anchor reserves a stable location for a follow-up
patch so that parallel slices can land without conflicting with each other.
"""

from __future__ import annotations

from fastapi import FastAPI

# === routers: auth ===
from web.server.routers import auth
# === routers: runs ===
from web.server.routers import runs as runs_router
# === routers: findings ===
from web.server.routers import findings as findings_router
# === routers: integrations ===
from web.server.routers import integrations as integrations_router
# === routers: chat ===
from web.server.routers import chat as chat_router
# === routers: picker ===
from web.server.routers import picker as picker_router


def create_app() -> FastAPI:
    """Build the FastAPI application.

    The factory pattern keeps test setup ergonomic (one app per test) and
    makes the wiring of routers explicit so reviewers can see in one place
    which slices are landed.
    """

    app = FastAPI(
        title="SPECA Web API",
        version="0.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # === include_router: auth ===
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    # === include_router: runs ===
    app.include_router(runs_router.router)
    # === include_router: findings ===
    app.include_router(findings_router.router)
    # === include_router: integrations ===
    app.include_router(
        integrations_router.router,
        prefix="/api/integrations",
        tags=["integrations"],
    )
    # === include_router: chat ===
    app.include_router(chat_router.router)
    # === include_router: picker ===
    app.include_router(picker_router.router)

    return app


app = create_app()
