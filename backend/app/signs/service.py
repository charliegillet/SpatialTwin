"""Process-wide sign state shared by NetworkGuard's hook and the router: the token signer, the proposal queue, and
counters of connected sign streams (the presenter's preflight shows "N phones connected").

NetworkGuard (main.py) and the routes must agree on one signer, so both resolve ``default_service()`` at request time;
tests swap it with ``set_default_service`` (same pattern as incident.routes.set_default_manager).
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from backend.app.signs.network import detect_lan_ip, probe_listening
from backend.app.signs.proposals import ProposalQueue
from backend.app.signs.tokens import TokenSigner

MAX_SIGN_STREAMS = 64


class SignsService:
    def __init__(self, signer: Optional[TokenSigner] = None, proposals: Optional[ProposalQueue] = None,
                 lan_ip: Callable[[], Optional[str]] = detect_lan_ip,
                 probe: Callable[[str, int], Optional[bool]] = probe_listening,
                 max_streams: int = MAX_SIGN_STREAMS):
        self.signer = signer or TokenSigner()
        self.proposals = proposals or ProposalQueue()
        self.lan_ip = lan_ip
        self.probe = probe
        self.max_streams = max_streams
        self.streams: Dict[str, int] = {}
        self.minted = 0

    @property
    def stream_count(self) -> int:
        return sum(self.streams.values())

    def stream_opened(self, key: str) -> None:
        self.streams[key] = self.streams.get(key, 0) + 1

    def stream_closed(self, key: str) -> None:
        left = self.streams.get(key, 0) - 1
        if left > 0:
            self.streams[key] = left
        else:
            self.streams.pop(key, None)


_default: Optional[SignsService] = None


def default_service() -> SignsService:
    global _default
    if _default is None:
        _default = SignsService()
    return _default


def set_default_service(service: Optional[SignsService]) -> None:
    """Test hook."""
    global _default
    _default = service
