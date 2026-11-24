"""Single entry point to Gold: the approved serving cache through scripts/gold_query.py.

The contract, validation and SQL generation live in the Gold layer; the API
never duplicates them. At first use the API opens the load approved in the
catalog (``<datos>/releases.sqlite3``, see scripts/releases.py) and fixes its
serving cache and certified queries for the life of the process: a newly
promoted load is picked up on restart. Files outside the catalog are never
adopted as current. The cache is verified once, under a lock, even when
several requests arrive during a cold start.

Overrides, for tests and ad hoc inspection:
  AGENT_GOLD_SERVING       serving cache to open instead of the approved one
  AGENT_CERTIFIED_QUERIES  certified queries to use with it
Both must belong to the same load (and to its ready_for_agent report, when the
serving cache sits in a version directory); otherwise Gold is unavailable.
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


def open_analytics() -> Analytics:
    serving = os.environ.get("AGENT_GOLD_SERVING") or None
    certified = os.environ.get("AGENT_CERTIFIED_QUERIES") or None
    analytics = Analytics(root=ROOT, serving=serving, certified_path=certified)
    problems = analytics.coherence_problems()
    if problems:
        raise GoldUnavailable("Gold no es una carga coherente: " + "; ".join(problems))
    return analytics


def get_analytics() -> Analytics:
    global _analytics
    with _lock:
        if _analytics is None:
            _analytics = open_analytics()
        return _analytics


def reset() -> None:
    """Forget the cached instance (tests, or to load a newly promoted version)."""
    global _analytics
    with _lock:
        _analytics = None
