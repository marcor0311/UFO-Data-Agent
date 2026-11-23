"""Shared fixtures: a synthetic Gold serving cache and an isolated app."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps/api/src"))


@pytest.fixture(scope="session")
def gold(tmp_path_factory):
    """Gold built from the synthetic Silver fixture, with its serving cache and certified queries."""
    from gold_fixture import serving_fixture
    folder = tmp_path_factory.mktemp("gold")
    analytics, manifest, _ = serving_fixture(folder)
    return analytics


@pytest.fixture
def client(gold, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import gold as gold_module
    from app.agent import routes
    from app.agent.auth import Auth
    from app.agent.store import ConversationStore
    from app.main import app
    monkeypatch.setattr(gold_module, "_analytics", gold)
    auth = Auth(path=tmp_path / "auth.json")
    store = ConversationStore(tmp_path / "chats.sqlite3")
    app.dependency_overrides[routes.get_auth] = lambda: auth
    app.dependency_overrides[routes.get_store] = lambda: store
    app.dependency_overrides[routes.get_models] = lambda: (lambda account: [{"slug": "model-a", "display_name": "Modelo A"},
                                                                             {"slug": "model-b", "display_name": "Modelo B"}])
    test_client = TestClient(app)
    test_client.agent_auth, test_client.agent_store = auth, store
    yield test_client
    app.dependency_overrides.clear()


def login(client, owner="owner-1", email="dueno@example.com"):
    """Create a valid local session without the network."""
    import time
    from app.agent.auth import COOKIE, fingerprint
    session = "session-" + owner
    client.agent_auth.state["accounts"][owner] = {"access_token": "token", "refresh_token": "refresh", "client_id": "client-123",
                                            "subject": owner, "email": email, "expires_at": time.time() + 3600,
                                            "scope": "openid chatgpt.tokens.use.direct"}
    client.agent_auth.state["sessions"][fingerprint(session)] = {"account_id": owner, "expires": time.time() + 3600}
    client.cookies.set(COOKIE, session)
    return session


class ScriptedStream:
    """Fake Responses stream: returns scripted outputs and records each payload."""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.payloads = []

    def __call__(self, account, payload):
        self.payloads.append(json.loads(json.dumps(payload, default=str)))
        if not self.outputs:
            raise AssertionError("Llamada inesperada al modelo")
        return {"output": self.outputs.pop(0)}


def call(name, arguments, call_id="c1"):
    return {"type": "function_call", "name": name, "arguments": json.dumps(arguments), "call_id": call_id}


def message(text):
    return {"type": "message", "content": [{"type": "output_text", "text": text}]}
