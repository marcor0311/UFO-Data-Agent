"""Sign in with ChatGPT protocol checks with test keys and a mocked issuer."""
import json
import time
from urllib.parse import parse_qs, urlparse

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
import httpx
import jwt
import pytest

from app.agent.auth import ISSUER, TOKEN, Auth, fingerprint

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWK = {**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key())), "kid": "k1", "use": "sig", "alg": "RS256"}


class Issuer:
    def __init__(self):
        self.scope = "openid email chatgpt.tokens.use.direct"
        self.nonce = None
        self.client_id = "client-123"
        self.revoked = []
        self.token_requests = []

    def id_token(self, **over):
        claims = {"iss": ISSUER, "aud": self.client_id, "sub": "user-1", "email": "dueno@example.com", "nonce": self.nonce,
                  "iat": int(time.time()), "exp": int(time.time()) + 600, **over}
        return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "k1"})

    def handler(self, request):
        url = str(request.url)
        if url.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json={"jwks_uri": ISSUER + "/jwks", "revocation_endpoint": ISSUER + "/revoke"})
        if url == ISSUER + "/jwks":
            return httpx.Response(200, json={"keys": [JWK]})
        if url == TOKEN:
            form = parse_qs(request.content.decode())
            self.token_requests.append(form)
            if form["grant_type"] == ["refresh_token"]:
                return httpx.Response(200, json={"access_token": "new", "refresh_token": "r2", "expires_in": 3600, "scope": self.scope})
            return httpx.Response(200, json={"access_token": "a", "refresh_token": "r", "expires_in": 3600, "scope": self.scope,
                                             "id_token": self.id_token(**getattr(self, "override", {}))})
        if url == ISSUER + "/revoke":
            self.revoked.append(parse_qs(request.content.decode()))
            return httpx.Response(200)
        return httpx.Response(404)


@pytest.fixture
def issuer():
    return Issuer()


@pytest.fixture
def auth(tmp_path, issuer):
    return Auth(path=tmp_path / "auth.json", http=httpx.Client(transport=httpx.MockTransport(issuer.handler)))


def begin(auth, issuer):
    url, state = auth.start()
    params = parse_qs(urlparse(url).query)
    issuer.nonce = params["nonce"][0]
    assert params["code_challenge_method"] == ["S256"] and params["redirect_uri"][0].startswith("http://127.0.0.1:")
    assert "chatgpt.tokens.use.direct" in params["scope"][0]
    return state


def test_full_login_refresh_and_logout(auth, issuer, tmp_path):
    state = begin(auth, issuer)
    session = auth.callback(state, state, code="code", client_id="client-123")
    key, account = auth.account(session)
    assert account["email"] == "dueno@example.com" and key == fingerprint("client-123|user-1")
    assert (tmp_path / "auth.json").stat().st_mode & 0o777 == 0o600
    auth.state["accounts"][key]["expires_at"] = time.time()          # force refresh
    _, refreshed = auth.account(session)
    assert refreshed["access_token"] == "new" and issuer.token_requests[-1]["grant_type"] == ["refresh_token"]
    result = auth.logout(session)
    assert result["remote_revocation_confirmed"] and issuer.revoked[0]["token"] == ["r2"]
    with pytest.raises(HTTPException):
        auth.account(session)
    assert "access_token" not in auth.state["accounts"][key]


@pytest.mark.parametrize("browser_state", [None, "other"])
def test_state_must_match(auth, issuer, browser_state):
    state = begin(auth, issuer)
    with pytest.raises(HTTPException) as err:
        auth.callback(state, browser_state, code="code", client_id="client-123")
    assert err.value.status_code == 400


def test_state_is_single_use_and_expires(auth, issuer):
    state = begin(auth, issuer)
    auth.callback(state, state, code="code", client_id="client-123")
    with pytest.raises(HTTPException):
        auth.callback(state, state, code="code", client_id="client-123")
    state = begin(auth, issuer)
    auth.state["pending"][state]["expires"] = time.time() - 1
    with pytest.raises(HTTPException):
        auth.callback(state, state, code="code", client_id="client-123")


def test_dynamic_registration_requires_issued_client(auth, issuer):
    state = begin(auth, issuer)
    with pytest.raises(HTTPException):
        auth.callback(state, state, code="code", client_id=None)


@pytest.mark.parametrize("override", [{"nonce": "replayed"}, {"aud": "other-client"}, {"iss": "https://evil.example"},
                                      {"exp": int(time.time()) - 10}])
def test_id_token_is_validated(auth, issuer, override):
    state = begin(auth, issuer)
    issuer.override = override
    with pytest.raises(HTTPException) as err:
        auth.callback(state, state, code="code", client_id="client-123")
    assert err.value.status_code == 401


def test_direct_scope_is_required(auth, issuer):
    issuer.scope = "openid email"
    state = begin(auth, issuer)
    with pytest.raises(HTTPException) as err:
        auth.callback(state, state, code="code", client_id="client-123")
    assert err.value.status_code == 401


def test_unknown_session(auth):
    with pytest.raises(HTTPException) as err:
        auth.account("nope")
    assert err.value.status_code == 401
