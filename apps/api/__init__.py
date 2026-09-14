"""apps/api: thin shim — the FastAPI app lives at acp.api:app (src/acp/api/app.py)."""
from acp.api.app import app, create_app

__all__ = ["app", "create_app"]
