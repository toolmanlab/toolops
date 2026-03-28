"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from toolops.api.routes import correlate, infra, logs, metrics, overview, traces


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ToolOps API",
        description="AI application observability platform",
        version="0.2.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3001",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(overview.router)
    app.include_router(metrics.router)
    app.include_router(traces.router)
    app.include_router(logs.router)
    app.include_router(correlate.router)
    app.include_router(infra.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
