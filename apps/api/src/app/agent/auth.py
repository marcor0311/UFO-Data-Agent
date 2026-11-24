"""Official Sign in with ChatGPT (public client): owner-only local credentials.

Same protocol as the Messi data agent: dynamic registration, PKCE, state and
nonce, signed ID-token validation against the issuer JWKS, refresh-token
rotation and revocation on logout. Tokens never reach the browser.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import HTTPException
import httpx
import jwt

from app.config import ROOT

ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
AUTHORIZE = ISSUER + "/api/accounts/authorize"
TOKEN = ISSUER + "/api/accounts/oauth/token"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
DIRECT_SCOPE = "chatgpt.tokens.use.direct"
COOKIE = "ufo_session"
OAUTH_COOKIE = "ufo_oauth"
AUTH_STATE_KEY = "AGENT_AUTH_STATE_B64"
SESSION_SECONDS = 30 * 86400


def callback_uri() -> str:
    uri = os.environ.get("AGENT_CALLBACK", "http://127.0.0.1:8000/auth/callback")
    if not uri.startswith("http://127.0.0.1:") or not uri.endswith("/auth/callback"):
        raise ValueError("AGENT_CALLBACK debe ser una URI loopback http://127.0.0.1:<puerto>/auth/callback")
    return uri


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _read_env_state(path: Path):
    if not path.exists():
        return None
    for line in path.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == AUTH_STATE_KEY:
            try:
                return json.loads(base64.urlsafe_b64decode(value.strip().encode()).decode())
            except (ValueError, UnicodeDecodeError) as exc:
                raise RuntimeError("AGENT_AUTH_STATE_B64 del .env raíz no es válido") from exc
    return None


def _write_env_state(path: Path, state: dict) -> None:
    encoded = base64.urlsafe_b64encode(json.dumps(state, separators=(",", ":")).encode()).decode()
    lines = path.read_text().splitlines() if path.exists() else []
    output, found = [], False
    for line in lines:
        if line.partition("=")[0].strip() == AUTH_STATE_KEY:
            if not found:
                output.append(AUTH_STATE_KEY + "=" + encoded)
            found = True
        else:
            output.append(line)
    if not found:
        output.append(AUTH_STATE_KEY + "=" + encoded)
    _atomic_write(path, "\n".join(output) + "\n")


class Auth:
    """State lives in the root .env (AGENT_AUTH_STATE_B64), or in a JSON file for tests."""

    def __init__(self, path: Path | None = None, http: httpx.Client | None = None):
        self.file_path = Path(path) if path else None
        self.path = self.file_path or ROOT / ".env"
        self.http = http
        self.lock = threading.RLock()
        if self.file_path:
            self.state = json.loads(self.path.read_text()) if self.path.exists() else None
        else:
            self.state = _read_env_state(self.path)
        if self.state is None:
            self.state = {"host_id": "urn:uuid:" + str(uuid4()), "accounts": {}, "sessions": {}, "pending": {}}
        self.save()

    def _request(self, method: str, url: str, **kw):
        if self.http is not None:
            return self.http.request(method, url, **kw)
        with httpx.Client(timeout=30) as client:
            return client.request(method, url, **kw)

    def save(self) -> None:
        if self.file_path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(self.path, json.dumps(self.state))
        else:
            _write_env_state(self.path, self.state)

    def start(self, account_id: str | None = None) -> tuple[str, str]:
        with self.lock:
            account = self.state["accounts"].get(account_id) if account_id else None
            if account_id and not account:
                raise HTTPException(400, "Cuenta desconocida")
            state, nonce, verifier = (secrets.token_urlsafe(40) for _ in range(3))
            client_id = account["client_id"] if account else "dynamic_agent_client"
            now = time.time()
            self.state["pending"] = {k: v for k, v in self.state["pending"].items() if v["expires"] > now}
            self.state["pending"][state] = {"nonce": nonce, "verifier": verifier, "client_id": client_id,
                                            "account_id": account_id, "expires": now + 600}
            self.save()
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            params = dict(client_id=client_id, ext_agent_host_id=self.state["host_id"], response_type="code",
                          redirect_uri=callback_uri(), scope=SCOPES, resource=RESOURCE, state=state, nonce=nonce,
                          code_challenge_method="S256", code_challenge=challenge)
            if account:
                if account.get("id_token"):
                    params["id_token_hint"] = account["id_token"]
                if account.get("email"):
                    params["login_hint"] = account["email"]
            else:
                params["agent_name_hint"] = "UFO Gold Data Agent"
            return AUTHORIZE + "?" + urlencode(params), state

    def validate_id(self, token: str, client_id: str, nonce: str) -> dict:
        discovery = self._request("GET", ISSUER + "/.well-known/openid-configuration")
        discovery.raise_for_status()
        uri = discovery.json()["jwks_uri"]
        if not uri.startswith(ISSUER + "/"):
            raise ValueError("Origen JWKS inválido")
        keys = self._request("GET", uri)
        keys.raise_for_status()
        header = jwt.get_unverified_header(token)
        key = next((jwt.PyJWK(k) for k in keys.json()["keys"] if k.get("kid") == header.get("kid")), None)
        if key is None:
            raise ValueError("Firma de identidad desconocida")
        claims = jwt.decode(token, key.key, algorithms=["RS256"], audience=client_id, issuer=ISSUER,
                            options={"require": ["exp", "iat", "sub", "aud", "iss", "nonce"]})
        if not secrets.compare_digest(claims["nonce"], nonce):
            raise ValueError("Nonce inválido")
        return claims

    def callback(self, state: str, browser_state: str | None, code: str | None = None,
                 client_id: str | None = None, error: str | None = None) -> str:
        with self.lock:
            if not state or not browser_state or not secrets.compare_digest(state.encode(), browser_state.encode()):
                raise HTTPException(400, "Estado OAuth inválido. Regresa al agente y selecciona “Continuar con ChatGPT” de nuevo.")
            pending = self.state["pending"].pop(state, None)
            self.save()
            if not pending or pending["expires"] < time.time():
                raise HTTPException(400, "Autorización expirada")
            if error:
                raise HTTPException(400, "Autorización rechazada: " + error[:80])
            issued = pending["client_id"]
            if issued == "dynamic_agent_client":
                if not client_id or client_id == "dynamic_agent_client":
                    raise HTTPException(400, "Registro incompleto: falta el client_id emitido")
                issued = client_id
            elif client_id and client_id != issued:
                raise HTTPException(400, "Registro de cuenta incompatible")
            if not code:
                raise HTTPException(400, "Falta el código de autorización")
            try:
                response = self._request("POST", TOKEN, data=dict(grant_type="authorization_code", client_id=issued, code=code,
                                                                  code_verifier=pending["verifier"], redirect_uri=callback_uri(),
                                                                  resource=RESOURCE))
                response.raise_for_status()
                tokens = response.json()
                claims = self.validate_id(tokens["id_token"], issued, pending["nonce"])
                if DIRECT_SCOPE not in tokens.get("scope", "").split():
                    raise ValueError("No se concedió el permiso de uso del plan de ChatGPT")
                previous = self.state["accounts"].get(pending["account_id"])
                if previous and claims["sub"] != previous["subject"]:
                    raise ValueError("Identidad incompatible con la cuenta seleccionada")
                key = fingerprint(issued + "|" + claims["sub"])
                self.state["accounts"][key] = {**tokens, "client_id": issued, "subject": claims["sub"],
                                               "email": claims.get("email", "Cuenta ChatGPT"),
                                               "expires_at": time.time() + tokens["expires_in"]}
                session = secrets.token_urlsafe(48)
                self.state["sessions"][fingerprint(session)] = {"account_id": key, "expires": time.time() + SESSION_SECONDS}
                self.save()
                return session
            except (httpx.HTTPError, ValueError, KeyError, jwt.PyJWTError) as exc:
                raise HTTPException(401, "No se pudo verificar la autorización oficial. Inicia sesión de nuevo.") from exc

    def account(self, session: str | None) -> tuple[str, dict]:
        with self.lock:
            record = self.state["sessions"].get(fingerprint(session or ""))
            if not record or record["expires"] < time.time():
                raise HTTPException(401, "Continúa con ChatGPT para consultar al agente.")
            return self.account_by_key(record["account_id"])

    def account_by_key(self, key: str) -> tuple[str, dict]:
        """Fresh credentials of a stored account (refreshed when about to expire)."""
        with self.lock:
            account = self.state["accounts"].get(key)
            if not account or not account.get("access_token"):
                raise HTTPException(401, "Sesión cerrada")
            if account["expires_at"] < time.time() + 60:
                try:
                    response = self._request("POST", TOKEN, data=dict(grant_type="refresh_token", client_id=account["client_id"],
                                                                      refresh_token=account["refresh_token"], resource=RESOURCE))
                    response.raise_for_status()
                    replacement = response.json()
                    updated = {**account, **replacement, "expires_at": time.time() + replacement["expires_in"]}
                    if DIRECT_SCOPE not in updated.get("scope", "").split():
                        raise ValueError("Permiso revocado")
                    self.state["accounts"][key] = updated
                    self.save()
                    account = updated
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    raise HTTPException(401, "La sesión expiró o fue revocada. Continúa de nuevo con ChatGPT.") from exc
            return key, dict(account)

    def logout(self, session: str | None) -> dict:
        with self.lock:
            record = self.state["sessions"].pop(fingerprint(session or ""), None)
            confirmed = True
            if record:
                key = record["account_id"]
                account = self.state["accounts"][key]
                if account.get("refresh_token"):
                    confirmed = False
                    for _ in range(2):
                        try:
                            discovery = self._request("GET", ISSUER + "/.well-known/openid-configuration")
                            discovery.raise_for_status()
                            uri = discovery.json()["revocation_endpoint"]
                            if not uri.startswith(ISSUER + "/"):
                                raise ValueError("Origen de revocación inválido")
                            response = self._request("POST", uri, data={"token": account["refresh_token"],
                                                                        "token_type_hint": "refresh_token",
                                                                        "client_id": account["client_id"]})
                            confirmed = response.status_code == 200
                            if confirmed:
                                break
                        except (httpx.HTTPError, ValueError, KeyError):
                            pass
                self.state["accounts"][key] = {k: v for k, v in account.items() if k in ("client_id", "subject", "email")}
                self.state["sessions"] = {k: v for k, v in self.state["sessions"].items() if v["account_id"] != key}
            self.save()
            return {"remote_revocation_confirmed": confirmed,
                    "message": "Sesión cerrada" if confirmed else
                    "Sesión local cerrada. Revocación remota sin confirmar; desconecta la app en la configuración de ChatGPT."}
