"""FastAPI application of the UFO-Data-Agent data agent."""
from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.agent.routes import router
from app.gold import Analytics, GoldUnavailable, get_analytics

app = FastAPI(title="UFO-Data-Agent API", version="0.1.0")
logger = logging.getLogger(__name__)


@app.exception_handler(GoldUnavailable)
async def gold_unavailable(request: Request, exc: GoldUnavailable):
    logger.warning("Gold no disponible", exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": str(exc), "recoverable": True})


@app.exception_handler(RequestValidationError)
async def invalid(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Solicitud inválida", "errors": exc.errors()[:5], "recoverable": True})


@app.exception_handler(Exception)
async def failed(request: Request, exc: Exception):
    logger.exception("La solicitud falló", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "No se pudo completar la consulta. Tu resultado anterior se conserva. Intenta de nuevo.",
                                                  "recoverable": True})


@app.get("/api/health")
def health(a: Analytics = Depends(get_analytics)):
    release = getattr(a, "release", None) or {}
    return {"status": "ok", "gold_load_id": a.load_id, "serving_load_id": a.cache["load_id"],
            "readiness_load_id": release.get("readiness_load_id"), "gold_version": release.get("version"),
            "source": release.get("source"), "promoted_at": release.get("promoted_at"),
            "gold_sha256": a.cache["gold_sha256"], "serving_sha256": a.cache["sha256"],
            "cache_version": a.cache["cache_version"]}


app.include_router(router)
