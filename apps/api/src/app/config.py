"""Paths and environment, resolved once. No secrets live here."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default


def web_origin() -> str:
    return os.environ.get("AGENT_WEB_ORIGIN", "http://127.0.0.1:3000")


def chats_path() -> Path:
    return env_path("AGENT_CHATS_DB", ROOT / "data/agent/chats.sqlite3")
