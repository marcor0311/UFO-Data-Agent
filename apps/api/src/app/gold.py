"""Single entry point to Gold: the verified serving cache through scripts/gold_query.py.

The contract, validation and SQL generation live in the Gold layer; the API
never duplicates them. The cache is verified once, under a lock, even when
several requests arrive during a cold start.
"""
from __future__ import annotations

import os
import sys
import threading

from app.config import ROOT

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import gold_query  # noqa: E402
from gold_query import OPS, VIEWS, Analytics, GoldUnavailable, Query, QueryError  # noqa: E402,F401

_lock = threading.Lock()
_analytics: Analytics | None = None


def get_analytics() -> Analytics:
    global _analytics
    with _lock:
        if _analytics is None:
            serving = os.environ.get("AGENT_GOLD_SERVING")
            certified = os.environ.get("AGENT_CERTIFIED_QUERIES")
            _analytics = Analytics(root=ROOT, serving=serving or None, certified_path=certified or None)
        return _analytics


def reset() -> None:
    """Forget the cached instance (tests, or after rebuilding the cache)."""
    global _analytics
    with _lock:
        _analytics = None
