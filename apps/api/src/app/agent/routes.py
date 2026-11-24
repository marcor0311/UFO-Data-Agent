"""HTTP routes of the data agent. Deterministic Gold exploration is public to the
local process; authenticated chat and history are scoped to the session owner."""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import json
import threading
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from app.agent.auth import COOKIE, OAUTH_COOKIE, SESSION_SECONDS, Auth
from app.agent.runtime import DataAgent, model_catalog, response_stream
from app.agent.store import MAX_TURNS, ConversationStore
from app.config import ROOT, chats_path, web_origin
from app.gold import VIEWS, Analytics, QueryError, get_analytics

router = APIRouter()
_chat_lock = threading.Lock()
_auth_lock = threading.Lock()


@lru_cache
def _auth() -> Auth:
    return Auth()


def get_auth() -> Auth:
    with _auth_lock:
        return _auth()


@lru_cache
def get_store() -> ConversationStore:
    return ConversationStore(chats_path())


def get_models():
    return model_catalog


def get_stream():
    return response_stream


def identity(request: Request, auth: Auth = Depends(get_auth)) -> tuple[str, dict]:
    return auth.account(request.cookies.get(COOKIE))


def safe_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in (web_origin(), "http://127.0.0.1:8000"):
        raise HTTPException(403, "Origen no permitido")


# -- authentication ------------------------------------------------------
@router.get("/api/auth/start")
def auth_start(account_id: str | None = None, auth: Auth = Depends(get_auth)):
    url, state = auth.start(account_id)
    response = RedirectResponse(url)
    response.set_cookie(OAUTH_COOKIE, state, httponly=True, samesite="lax", max_age=600)
    return response


@router.get("/auth/callback")
def auth_callback(request: Request, state: str = "", code: str | None = None, client_id: str | None = None,
                  error: str | None = None, auth: Auth = Depends(get_auth)):
    try:
        session = auth.callback(state, request.cookies.get(OAUTH_COOKIE), code, client_id, error)
    except HTTPException as exc:
        return JSONResponse(
            {"detail": exc.detail},
            status_code=exc.status_code,
            headers=exc.headers,
            media_type="application/json; charset=utf-8",
        )
    response = RedirectResponse(web_origin() + "/agent", status_code=303)
    response.set_cookie(COOKIE, session, httponly=True, samesite="lax", max_age=SESSION_SECONDS)
    response.delete_cookie(OAUTH_COOKIE)
    return response


@router.get("/api/auth/status")
def auth_status(request: Request, auth: Auth = Depends(get_auth)):
    try:
        key, account = auth.account(request.cookies.get(COOKIE))
        return {"authenticated": True, "account_id": key, "email": account["email"]}
    except HTTPException as exc:
        return {"authenticated": False, "detail": exc.detail}


@router.get("/api/auth/accounts")
def auth_accounts(auth: Auth = Depends(get_auth)):
    return [{"account_id": k, "label": v["email"] + " (" + v["client_id"][-8:] + ")"} for k, v in auth.state["accounts"].items()]


@router.post("/api/auth/logout", dependencies=[Depends(safe_origin)])
def auth_logout(request: Request, auth: Auth = Depends(get_auth)):
    response = JSONResponse(auth.logout(request.cookies.get(COOKIE)))
    response.delete_cookie(COOKIE)
    return response


# -- deterministic Gold exploration --------------------------------------
@router.get("/api/agent/catalog")
def catalog(a: Analytics = Depends(get_analytics)):
    certified = [{"id": q["id"], "title": q["title"], "description": q["description"], "examples": q["examples"],
                  "recommended_views": q.get("recommended_views", []), "limitation": q["limitation"],
                  "valid": a.certification_status(q)["valid"]} for q in a.certified()["queries"]]
    return {"load_id": a.load_id, "datasets": a.describe(), "views": VIEWS,
            "metrics": {k: {"label": m["label"], "type": m["type"], "unit": m["unit"],
                            **({"denominator": m["denominator"]} if m["type"] == "ratio" else {})}
                        for k, m in a.metrics.items()},
            "dimensions": {k: {"label": d["label"]} for k, d in a.dimensions.items()},
            "eligibility": {k: v["label"] for k, v in a.eligibility.items()},
            "certified_queries": certified, "limitations": list(a.limitations.values()),
            "country_m49": country_m49()}


@lru_cache
def country_m49() -> dict:
    """ISO2 → UN M49 numeric code, which is the id used by the world map geometry."""
    data = json.loads((ROOT / "config/countries.json").read_text(encoding="utf-8"))
    return {c["alpha2"]: c["m49"] for c in data["countries"] if c.get("m49")}


@router.get("/api/agent/entities")
def entities(text: str, kind: str | None = None, a: Analytics = Depends(get_analytics)):
    return a.find_entities(text, kind=kind)


@router.get("/api/agent/certified/{certified_id}")
def certified(certified_id: str, a: Analytics = Depends(get_analytics)):
    try:
        return a.run_certified(certified_id)
    except QueryError as exc:
        raise HTTPException(404 if exc.code == "certified_unknown" else 422, {"code": exc.code, "message": str(exc)}) from exc


@router.post("/api/agent/query", dependencies=[Depends(safe_origin)])
def query(body: dict, a: Analytics = Depends(get_analytics)):
    try:
        return a.query(body)
    except QueryError as exc:
        raise HTTPException(422, {"code": exc.code, "message": str(exc)}) from exc


# -- authenticated agent ---------------------------------------------------
class Chat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: UUID | None = None
    model: str | None = Field(default=None, max_length=120)


class ContinueExample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: UUID | None = None


@router.post("/api/agent/conversations/examples/{certified_id}", dependencies=[Depends(safe_origin)])
def continue_example(certified_id: str, body: ContinueExample, user=Depends(identity),
                     a: Analytics = Depends(get_analytics), store: ConversationStore = Depends(get_store)):
    if not _chat_lock.acquire(blocking=False):
        raise HTTPException(409, "Ya hay una consulta en curso; espera a que termine.")
    try:
        cid = str(body.conversation_id or uuid4())
        previous = store.get(cid, user[0]) if body.conversation_id else []
        if previous is None:
            raise HTTPException(404, "Conversación no encontrada")
        if len(previous) >= MAX_TURNS - 1:
            raise HTTPException(422, "Inicia una conversación nueva para continuar.")
        result = certified(certified_id, a)
        item = next(q for q in a.certified()["queries"] if q["id"] == certified_id)
        turn = {
            "question": next(iter(item["examples"]), item["title"]),
            "answer": f'{item["description"]} {item["limitation"]}',
            "visualizations": [result], "trace": [{"tool": "run_certified", "ok": True}],
            "model": "", "load_id": a.load_id, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        turns = [*previous, turn]
        store.save(cid, user[0], turns)
        return {"conversation_id": cid, "turns": turns}
    finally:
        _chat_lock.release()


@router.get("/api/agent/models")
def models(user=Depends(identity), catalog_fn=Depends(get_models)):
    choices = catalog_fn(user[1])
    return {"models": choices, "selected": choices[0]["slug"],
            "selection": "Primer modelo del catálogo oficial de la cuenta; se puede elegir por pregunta."}


@router.get("/api/agent/conversations")
def conversations(user=Depends(identity), store: ConversationStore = Depends(get_store)):
    return store.list(user[0])


@router.get("/api/agent/conversations/{conversation_id}")
def history(conversation_id: UUID, user=Depends(identity), store: ConversationStore = Depends(get_store)):
    turns = store.get(str(conversation_id), user[0])
    if turns is None:
        raise HTTPException(404, "Conversación no encontrada")
    return {"conversation_id": str(conversation_id), "turns": turns}


@router.post("/api/agent/chat", dependencies=[Depends(safe_origin)])
def chat(body: Chat, user=Depends(identity), a: Analytics = Depends(get_analytics),
         store: ConversationStore = Depends(get_store), catalog_fn=Depends(get_models), stream=Depends(get_stream)):
    if not _chat_lock.acquire(blocking=False):
        raise HTTPException(409, "Ya hay una consulta en curso; espera a que termine.")
    try:
        choices = catalog_fn(user[1])
        selected = body.model or choices[0]["slug"]
        if selected not in [m["slug"] for m in choices]:
            raise HTTPException(422, "Modelo no disponible para esta cuenta")
        cid = str(body.conversation_id or uuid4())
        previous = store.get(cid, user[0]) if body.conversation_id else []
        if previous is None:
            raise HTTPException(404, "Conversación no encontrada")
        if len(previous) >= MAX_TURNS:
            raise HTTPException(422, "Inicia una conversación nueva para continuar.")
        turn = DataAgent(a, stream=stream).answer(user[1], body.question, previous, selected)
        store.save(cid, user[0], [*previous, turn])
        return {"conversation_id": cid, "turn": turn}
    finally:
        _chat_lock.release()
