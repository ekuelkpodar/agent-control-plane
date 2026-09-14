"""API package. ``acp.api:app`` is the ASGI application (uvicorn acp.api:app)."""

from __future__ import annotations

from acp.api.app import app

__all__ = ["app"]
