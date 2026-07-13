"""T24 — OAuth e2e suite: browser flow scripted over HTTP (MCPF-03, MCPF-17).

Black-box mirror of the Konecty PR #453 integration matrix:
1. DCR client → authorize (PKCE S256) → consent decision approve → token →
   /mcp call succeeds (the Claude Code user-MCP path).
2. Trusted client (e2e-admin, OAUTH_CLIENTS_JSON) + admin user: consent offers
   `admin` (unchecked ⇒ opt-in via effective_scope) → token carries admin →
   /admin-mcp accepts. Approving WITHOUT selecting admin never grants it.
3. Untrusted client requesting `admin` → invalid_scope at authorize
   (DCR/normal clients don't have admin in allowedScopes).

The consent SPA is external; the suite drives its HTTP contract directly:
GET /oauth/authorization-requests/:id + POST /oauth/authorize/decision with a
first-party session token (Authorization: Bearer <authTokenId>).
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request

import pytest

from conftest import E2E_URL, requires_stack
from mcp_client import McpClient, McpHttpError

pytestmark = requires_stack

MCP_RESOURCE = f"{E2E_URL}/mcp"
TRUSTED_CLIENT_ID = "e2e-admin"
TRUSTED_REDIRECT = "http://localhost:19819/callback"
NORMAL_CLIENT_ID = "e2e-user"
NORMAL_REDIRECT = "http://localhost:19818/callback"


# ── HTTP helpers (no redirect following) ──────────────────────────────────


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _request(url: str, method: str = "GET", data: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        resp = _OPENER.open(req, timeout=30)
        return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8", "replace")


def _location(headers: dict) -> str:
    for key, value in headers.items():
        if key.lower() == "location":
            return value
    raise AssertionError(f"no Location header in {list(headers)}")


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _authorize(client_id: str, redirect_uri: str, scope: str, challenge: str):
    """GET /oauth/authorize; returns (status, headers, body)."""
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": "e2e-state",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": MCP_RESOURCE,
        }
    )
    return _request(f"{E2E_URL}/oauth/authorize?{query}")


def _authorization_request_id(location: str) -> str:
    parsed = urllib.parse.urlparse(location)
    params = urllib.parse.parse_qs(parsed.query)
    assert "authorization_request_id" in params, f"no authorization_request_id in {location}"
    return params["authorization_request_id"][0]


def _consent(admin_token: str, request_id: str) -> dict:
    status, _, body = _request(
        f"{E2E_URL}/oauth/authorization-requests/{request_id}",
        headers={"Authorization": f"Bearer {admin_token}", "Accept": "application/json"},
    )
    assert status == 200, f"consent lookup failed: {status} {body[:200]}"
    return json.loads(body)


def _decide(admin_token: str, request_id: str, effective_scope: str | None) -> str:
    """POST decision approve; returns the authorization code."""
    payload: dict = {"authorization_request_id": request_id, "decision": "approve"}
    if effective_scope is not None:
        payload["effective_scope"] = effective_scope
    status, _, body = _request(
        f"{E2E_URL}/oauth/authorize/decision",
        method="POST",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    assert status == 200, f"decision failed: {status} {body[:300]}"
    redirect_url = json.loads(body)["redirectUrl"]
    params = urllib.parse.parse_qs(urllib.parse.urlparse(redirect_url).query)
    assert "code" in params, f"no code in decision redirect: {redirect_url}"
    assert params["state"] == ["e2e-state"]
    return params["code"][0]


def _token(client_id: str, redirect_uri: str, code: str, verifier: str) -> dict:
    data = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": verifier,
        }
    ).encode()
    status, _, body = _request(
        f"{E2E_URL}/oauth/token",
        method="POST",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert status == 200, f"token exchange failed: {status} {body[:300]}"
    return json.loads(body)


def _oauth_flow(admin_token: str, client_id: str, redirect_uri: str, scope: str,
                effective_scope: str | None = None) -> dict:
    verifier, challenge = _pkce_pair()
    status, headers, body = _authorize(client_id, redirect_uri, scope, challenge)
    assert status in (302, 303), f"authorize did not redirect: {status} {body[:300]}"
    request_id = _authorization_request_id(_location(headers))
    code = _decide(admin_token, request_id, effective_scope)
    return _token(client_id, redirect_uri, code, verifier)


# ── discovery ──────────────────────────────────────────────────────────────


def test_well_known_authorization_server_metadata():
    status, _, body = _request(f"{E2E_URL}/.well-known/oauth-authorization-server")
    assert status == 200
    metadata = json.loads(body)
    assert metadata["issuer"].rstrip("/") == E2E_URL
    assert metadata["authorization_endpoint"].endswith("/oauth/authorize")
    assert metadata["token_endpoint"].endswith("/oauth/token")


# ── scenario 1: DCR client full flow → /mcp (MCPF-03) ─────────────────────


def test_dcr_client_full_oauth_flow_reaches_user_mcp(admin_token):
    status, _, body = _request(
        f"{E2E_URL}/oauth/register",
        method="POST",
        data=json.dumps({"client_name": "E2E DCR", "redirect_uris": ["http://localhost:19820/cb"]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert status == 201, f"DCR failed: {status} {body[:300]}"
    registration = json.loads(body)
    assert registration["scope"] == "read write"
    client_id = registration["client_id"]

    tokens = _oauth_flow(admin_token, client_id, "http://localhost:19820/cb", "read write")
    assert tokens["token_type"].lower() == "bearer"
    assert "admin" not in tokens.get("scope", "")

    mcp = McpClient(MCP_RESOURCE, token=tokens["access_token"])
    modules = mcp.call("modules_list").structured["modules"]
    assert any(m["document"] == "Contact" for m in modules)


# ── scenario 2: trusted client + admin user → /admin-mcp (MCPF-17) ────────


def test_trusted_client_admin_consent_grants_admin_mcp(admin_token):
    verifier, challenge = _pkce_pair()
    status, headers, _ = _authorize(TRUSTED_CLIENT_ID, TRUSTED_REDIRECT, "read write admin", challenge)
    assert status in (302, 303)
    request_id = _authorization_request_id(_location(headers))

    consent = _consent(admin_token, request_id)
    assert "admin" in consent["availableScopes"], "trusted client + admin user must be offered admin"

    code = _decide(admin_token, request_id, effective_scope="read write admin")
    tokens = _token(TRUSTED_CLIENT_ID, TRUSTED_REDIRECT, code, verifier)
    assert "admin" in tokens["scope"]

    admin_mcp = McpClient(f"{E2E_URL}/admin-mcp", token=tokens["access_token"])
    meta = admin_mcp.call("meta_read", {"name": "Contact"}).structured["meta"]
    assert meta["_id"] == "Contact"


def test_trusted_client_approve_without_selecting_admin_never_grants_it(admin_token):
    # absent effective_scope = grant all requested EXCEPT admin (opt-in only)
    tokens = _oauth_flow(
        admin_token, TRUSTED_CLIENT_ID, TRUSTED_REDIRECT, "read write admin", effective_scope=None
    )
    assert "admin" not in tokens["scope"], "admin must never be granted implicitly"

    admin_mcp = McpClient(f"{E2E_URL}/admin-mcp", token=tokens["access_token"])
    with pytest.raises(McpHttpError) as excinfo:
        admin_mcp.rpc("tools/list")
    assert excinfo.value.status in (401, 403)


# ── scenario 3: untrusted client requesting admin → invalid_scope ─────────


def test_untrusted_client_requesting_admin_gets_invalid_scope():
    verifier, challenge = _pkce_pair()
    status, headers, body = _authorize(NORMAL_CLIENT_ID, NORMAL_REDIRECT, "read admin", challenge)
    # admin ∉ allowedScopes for normal clients → invalid_scope, delivered as an
    # OAuth error redirect to the (valid) redirect_uri
    assert status in (302, 303), f"expected error redirect, got {status}: {body[:200]}"
    params = urllib.parse.parse_qs(urllib.parse.urlparse(_location(headers)).query)
    assert params["error"] == ["invalid_scope"]


def test_pkce_plain_method_rejected():
    query = urllib.parse.urlencode(
        {
            "client_id": NORMAL_CLIENT_ID,
            "redirect_uri": NORMAL_REDIRECT,
            "response_type": "code",
            "scope": "read",
            "code_challenge": "x" * 48,
            "code_challenge_method": "plain",
            "resource": MCP_RESOURCE,
        }
    )
    status, headers, body = _request(f"{E2E_URL}/oauth/authorize?{query}")
    if status in (302, 303):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(_location(headers)).query)
        assert params["error"] == ["invalid_request"]
    else:
        assert status == 400
