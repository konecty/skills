"""Fixtures for the MCP-first e2e suites.

Requires the disposable stack from ``make e2e-up`` (default
``http://localhost:3200``). All suites are skipped when the stack is
unreachable, so ``make check`` and plain ``pytest`` stay offline-green.

Auth model (see Konecty docs/en/mcp.md):
- ``admin_token`` — first-party ``authTokenId`` from ``POST /rest/auth/login``
  with the first-boot admin password extracted from the container logs
  (same trick as ``make e2e-token``). Sent as ``Authorization: Bearer`` it
  gives implicit full scopes on ``/mcp`` and admin access on ``/admin-mcp``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "e2e" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp_client import McpClient  # noqa: E402

E2E_URL = os.environ.get("E2E_KONECTY_URL", "http://localhost:3200")
E2E_CONTAINER = os.environ.get("E2E_KONECTY_CONTAINER", "konecty-e2e-konecty")
E2E_MONGO_CONTAINER = os.environ.get("E2E_MONGO_CONTAINER", "konecty-e2e-mongodb")
E2E_MONGO_DB = os.environ.get("E2E_MONGO_DB", "e2e")


def _liveness(url: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/liveness", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _stack_available() -> bool:
    return _liveness(E2E_URL)


STACK_UP = _stack_available()

requires_stack = pytest.mark.skipif(
    not STACK_UP, reason=f"e2e stack unreachable at {E2E_URL} (run `make e2e-up`)"
)


def mongo_eval(js: str) -> str:
    """Run a mongosh eval inside the e2e mongo container; return stdout."""
    result = subprocess.run(
        ["docker", "exec", E2E_MONGO_CONTAINER, "mongosh", E2E_MONGO_DB, "--quiet", "--eval", js],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def mongo_eval_json(js: str):
    """mongo_eval wrapper for scripts that print a single JSON document."""
    out = mongo_eval(js)
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{") or line.startswith("["):
            return json.loads(line)
    raise AssertionError(f"no JSON in mongosh output: {out!r}")


@pytest.fixture(scope="session")
def admin_token() -> str:
    """First-party admin authTokenId (password recovered from container logs)."""
    sys.path.insert(0, str(REPO_ROOT / "e2e" / "scripts"))
    import konecty_admin_token as kat  # noqa: PLC0415

    password = kat.password_from_logs(E2E_CONTAINER)
    if password is None:
        pytest.skip("admin password not found in container logs")
    token = kat.login(E2E_URL, "admin", password)
    assert token, "admin login returned no token"
    return token


@pytest.fixture(scope="session")
def user_mcp(admin_token: str) -> McpClient:
    return McpClient(f"{E2E_URL}/mcp", token=admin_token)


@pytest.fixture(scope="session")
def admin_mcp(admin_token: str) -> McpClient:
    return McpClient(f"{E2E_URL}/admin-mcp", token=admin_token)


@pytest.fixture()
def anon_user_mcp() -> McpClient:
    return McpClient(f"{E2E_URL}/mcp", token=None)
