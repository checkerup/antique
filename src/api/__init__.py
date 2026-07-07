"""FastAPI server + AdsPower-compatible routes."""
from .server import create_app, main
from .routes import router

__all__ = ["create_app", "main", "router"]