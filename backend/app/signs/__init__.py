"""Phone exit signs and phone hazard proposals for the no-hardware demo (docs/plans/contracts/signs.md).

``build_signs_router`` is mounted by main.py; ``scoped_access`` is NetworkGuard's hook for non-loopback phones;
``forwarded_from_remote`` optionally hardens NetworkGuard against the ``vite --host`` proxy trap.
"""
from backend.app.signs.guard import forwarded_from_remote, scoped_access
from backend.app.signs.routes import build_signs_router

__all__ = ["build_signs_router", "forwarded_from_remote", "scoped_access"]
