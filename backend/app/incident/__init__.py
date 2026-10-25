"""Server-side incident mirror and the virtual (software) door controller for the no-hardware demo."""
from backend.app.incident.routes import build_incident_router

__all__ = ["build_incident_router"]
