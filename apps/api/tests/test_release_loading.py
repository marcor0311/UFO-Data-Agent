"""The API opens the load approved in the catalog, and only that load."""
from __future__ import annotations

import json
import shutil

import pytest

from pipeline_fixture import changed_rows, pipeline_env, promote_silver, run_gold
import releases


@pytest.fixture
def api(tmp_path, monkeypatch):
    """App without injected Gold: it must resolve Gold from UFO_DATA_DIR itself."""
    from fastapi.testclient import TestClient
    from app import gold as gold_module
    from app.main import app
    env = pipeline_env(tmp_path)
    monkeypatch.setenv("UFO_DATA_DIR", str(env["data"]))
    monkeypatch.delenv("AGENT_GOLD_SERVING", raising=False)
    monkeypatch.delenv("AGENT_CERTIFIED_QUERIES", raising=False)
    gold_module.reset()
    client = TestClient(app)
    client.env, client.restart = env, gold_module.reset
    yield client
    gold_module.reset()


def approved_files(env):
    item = releases.approved(env["data"], "gold")
    layout = releases.GoldLayout(item["path"])
    return item, {"serving": json.loads(layout.serving_manifest.read_text())["load_id"],
                  "readiness": json.loads(layout.readiness.read_text())["load_id"]}


def test_health_shows_the_approved_load_and_a_new_one_after_restart(api):
    assert run_gold(api.env) == 0
    first, files = approved_files(api.env)
    health = api.get("/api/health").json()
    assert health["source"] == "catalog" and health["gold_version"] == first["version"]
    assert health["gold_load_id"] == health["serving_load_id"] == health["readiness_load_id"] == first["identity"]
    assert files == {"serving": first["identity"], "readiness": first["identity"]}
    assert api.get("/api/agent/catalog").json()["load_id"] == first["identity"]

    promote_silver(api.env, changed_rows())
    assert run_gold(api.env) == 0
    second, files = approved_files(api.env)
    assert second["identity"] != first["identity"]
    assert api.get("/api/health").json()["gold_load_id"] == first["identity"]     # same process: same load
    api.restart()                                                                 # restart the API
    health = api.get("/api/health").json()
    assert health["gold_load_id"] == health["serving_load_id"] == health["readiness_load_id"] == second["identity"]
    assert files == {"serving": second["identity"], "readiness": second["identity"]}
    assert health["gold_version"] == second["version"]


def test_failed_promotion_keeps_serving_the_previous_load(api):
    assert run_gold(api.env) == 0
    first, _ = approved_files(api.env)
    promote_silver(api.env, changed_rows())

    def fail(layer, candidate):
        raise KeyboardInterrupt
    assert run_gold(api.env, before_promote=fail) == 130
    api.restart()
    assert api.get("/api/health").json()["gold_load_id"] == first["identity"]


def test_files_outside_the_catalog_are_not_adopted(api):
    assert run_gold(api.env) == 0
    item, _ = approved_files(api.env)
    legacy = api.env["data"] / "gold"
    shutil.copytree(releases.GoldLayout(item["path"]).serving.parent, legacy / "serving")   # the pre-catalog layout
    releases.catalog_path(api.env["data"]).unlink()
    api.restart()
    response = api.get("/api/health")
    assert response.status_code == 503
    assert "No hay una carga Gold aprobada" in response.json()["detail"]


def test_tampered_release_is_unavailable(api):
    assert run_gold(api.env) == 0
    item, _ = approved_files(api.env)
    readiness = releases.GoldLayout(item["path"]).readiness
    readiness.write_text(readiness.read_text().replace('"ready_for_agent": true', '"ready_for_agent": false'))
    api.restart()
    assert api.get("/api/health").status_code == 503


def test_overrides_must_be_one_load(api, monkeypatch):
    assert run_gold(api.env) == 0
    item, _ = approved_files(api.env)
    layout = releases.GoldLayout(item["path"])
    monkeypatch.setenv("AGENT_GOLD_SERVING", str(layout.serving))
    api.restart()
    health = api.get("/api/health").json()
    assert health["source"] == "override" and health["gold_load_id"] == health["readiness_load_id"] == item["identity"]

    stale = api.env["folder"] / "stale_certified.json"
    data = json.loads(layout.certified.read_text())
    data["queries"][0]["verification"]["load_id"] = "otra-carga"
    stale.write_text(json.dumps(data))
    monkeypatch.setenv("AGENT_CERTIFIED_QUERIES", str(stale))
    api.restart()
    response = api.get("/api/health")
    assert response.status_code == 503
    assert "no se verificaron con la carga" in response.json()["detail"]
