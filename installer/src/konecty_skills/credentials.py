"""Interim admin-token store (T20, MCP-first).

Since the MCP-first refactor, ``~/.konecty/.env`` is no longer the general auth
foundation — user auth is OAuth handled by Claude Code. This module only keeps
the **interim admin token**: OTP over HTTP (request-otp → verify-otp) against
the informed Konecty URL, stored as ``KONECTY_URL``/``KONECTY_TOKEN`` and used
as the Bearer header of the ``konecty-admin`` MCP entry.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_ENV_PATH: Path = Path.home() / ".konecty" / ".env"


def current_env(path: Path = DEFAULT_ENV_PATH) -> dict:
    """Parse the .env file and return url/token values.

    Returns a dict with keys "url" and "token"; each is None when missing.
    """
    result: dict = {"url": None, "token": None}  # nosec B105 - dict of None defaults, not a secret
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("KONECTY_URL="):
                    result["url"] = stripped[len("KONECTY_URL="):] or None
                elif stripped.startswith("KONECTY_TOKEN="):
                    result["token"] = stripped[len("KONECTY_TOKEN="):] or None
    except FileNotFoundError:
        pass
    return result


def validate_url(url: str) -> bool:
    """Return True only if *url* has an http/https scheme and a non-empty netloc."""
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def prompt_url(default: str | None = None) -> str:
    """Prompt the user for a Konecty URL, re-asking until validate_url passes.

    Empty input uses *default* when it is a valid URL.
    """
    while True:
        hint = f" [{default}]" if default else ""
        raw = input(f"Konecty URL{hint}: ").strip()
        candidate = raw if raw else (default or "")
        if validate_url(candidate):
            return candidate
        print("Invalid URL. Please enter a full http:// or https:// address.")


# --- interim admin token: OTP over HTTP (T18, MCP-first) ---------------------

def _post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    """POST *payload* as JSON to *url*; return the parsed JSON response.

    Returns an empty dict on any network/HTTP/JSON failure (never raises).
    """
    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        return {}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310 - scheme guarded above
            return json.load(resp)
    except Exception:  # noqa: BLE001 - HTTPError, URLError, timeout, bad JSON
        return {}


def _identifier_payload(identifier: str) -> dict:
    """Map an identifier to the Konecty OTP payload key (email vs phoneNumber)."""
    if "@" in identifier:
        return {"email": identifier}
    return {"phoneNumber": identifier}


def request_otp(url: str, identifier: str) -> bool:
    """POST /api/auth/request-otp; True when the server accepted the request."""
    endpoint = f"{url.rstrip('/')}/api/auth/request-otp"
    result = _post_json(endpoint, _identifier_payload(identifier))
    return bool(result.get("success"))


def verify_otp(url: str, identifier: str, code: str) -> str | None:
    """POST /api/auth/verify-otp; return the authId token or None on failure."""
    endpoint = f"{url.rstrip('/')}/api/auth/verify-otp"
    payload = _identifier_payload(identifier)
    payload["otpCode"] = code.strip()
    result = _post_json(endpoint, payload)
    if result.get("success") and result.get("logged") and result.get("authId"):
        return str(result["authId"])
    return None


def otp_login(url: str, identifier: str) -> str | None:
    """Full interim-admin OTP flow: request → prompt for the code → verify.

    Returns the ``authId`` token, or None on any failure (never raises).
    """
    if not request_otp(url, identifier):
        return None
    code = input("Enter the 6-digit OTP code: ").strip()
    return verify_otp(url, identifier, code)


def _merge_env(values: dict, path: Path) -> None:
    """Write/merge *values* (VAR → value) into the .env file.

    Existing lines for the given keys are replaced; every other line is
    preserved.  The parent directory is created with mode 0o700; the file
    is chmod'd to 0o600 after writing.
    """
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    existing_lines: list[str] = []
    if path.is_file():
        with open(path, "r", encoding="utf-8") as fh:
            existing_lines = fh.readlines()

    prefixes = tuple(f"{key}=" for key in values)
    filtered = [ln for ln in existing_lines if not ln.strip().startswith(prefixes)]
    filtered.extend(f"{key}={value}\n" for key, value in values.items())

    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(filtered)

    os.chmod(path, 0o600)


def write_env(url: str, token: str, path: Path = DEFAULT_ENV_PATH) -> None:
    """Write/merge KONECTY_URL and KONECTY_TOKEN (the interim admin token store)."""
    _merge_env({"KONECTY_URL": url, "KONECTY_TOKEN": token}, path)


def write_url_only(url: str, path: Path = DEFAULT_ENV_PATH) -> None:
    """Write/merge KONECTY_URL into the .env file (token untouched)."""
    _merge_env({"KONECTY_URL": url}, path)
