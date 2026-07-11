"""Shared pytest fixtures for the Konecty skills test suites.

Two worlds:

- **Live** (`konecty-data`): tests that talk to a real, disposable Konecty
  stack (default ``http://localhost:3200``, brought up via ``make e2e-up``).
  The ``live_creds`` fixture fetches an admin token from the container logs and
  ``pytest.skip``s the whole live suite if the stack is unreachable.

- **Mocked** (`konecty-meta`): the ``/api/admin/meta/*`` admin API is not in a
  published image yet (Konecty PR #299), so those tests run the real skill
  scripts against an in-memory :class:`MockKonecty` by monkeypatching
  ``urllib.request.urlopen``. See ``.specs/project/STATE.md`` D6–D8.
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
# Make the e2e helper package importable as top-level ``e2e`` from tests.
sys.path.insert(0, str(REPO_ROOT / "tests"))

from e2e.agent import PseudoAgent, set_default_creds  # noqa: E402
from e2e.mock_konecty import MockKonecty  # noqa: E402

E2E_URL = os.environ.get("E2E_KONECTY_URL", "http://localhost:3200")
E2E_CONTAINER = os.environ.get("E2E_KONECTY_CONTAINER", "konecty-e2e-konecty")
TOKEN_SCRIPT = REPO_ROOT / "e2e" / "scripts" / "konecty_admin_token.py"


def _liveness(url: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/liveness", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _fetch_token(url: str, container: str) -> str | None:
    try:
        proc = subprocess.run(
            [sys.executable, str(TOKEN_SCRIPT), "--url", url,
             "--container", container, "--print-only"],
            capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    token = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    return token or None


@pytest.fixture(scope="session")
def live_creds() -> tuple[str, str]:
    """(url, token) for the disposable stack; skips the suite if it's down."""
    if not _liveness(E2E_URL):
        pytest.skip(f"Konecty e2e stack not reachable at {E2E_URL} — run `make e2e-up`")
    token = _fetch_token(E2E_URL, E2E_CONTAINER)
    if not token:
        pytest.skip("could not obtain an admin token from the e2e container logs")
    set_default_creds(E2E_URL, token)
    return E2E_URL, token


@pytest.fixture
def live_agent(live_creds) -> PseudoAgent:
    """PseudoAgent wired to the live stack."""
    host, token = live_creds
    return PseudoAgent(host=host, token=token)


@pytest.fixture
def agent() -> PseudoAgent:
    """Bare PseudoAgent (used with the mock, or for clean-env smoke tests)."""
    return PseudoAgent()


@pytest.fixture
def mock_konecty():
    """In-memory `/api/admin/meta/*` mock for konecty-meta tests.

    Sets non-empty dummy credentials (the scripts fast-fail on empty creds even
    though the HTTP layer is intercepted) and yields the store. Tests wrap their
    agent calls in ``with mock_konecty.patch():``.
    """
    set_default_creds("http://mock.konecty.local", "mock-admin-token")
    yield MockKonecty()
