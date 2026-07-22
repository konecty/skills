"""Claude Code MCP registration for the Konecty servers. Implemented in T17.

Builds and (when the ``claude`` CLI is present) executes the ``claude mcp
add|remove|list`` commands that register Konecty's two MCP servers, plus the
URL validation helpers (https-only normalization and the
``/.well-known/oauth-protected-resource`` probe).

The command shapes here are the single source of truth shared with the
``konecty-setup`` skill (skills/konecty-setup/SKILL.md) — keep them identical.
Stdlib only.
"""
from __future__ import annotations

import json
import shutil
import subprocess  # nosec B404 - drives the claude CLI (arg list, no shell=True)
import urllib.error
import urllib.parse
import urllib.request

from . import __version__

USER_SERVER = "konecty"
ADMIN_SERVER = "konecty-admin"
WELL_KNOWN_PATH = "/.well-known/oauth-protected-resource"

# WAFs commonly block the default "Python-urllib/x.y" agent with 403 (seen live
# on customer deployments) — every HTTP call identifies itself as the CLI.
USER_AGENT = f"konecty-skills/{__version__}"


class UrlValidationError(ValueError):
    """Raised when a Konecty base URL cannot be normalized to a valid form."""


# --- URL validation ----------------------------------------------------------

def normalize_url(raw: str) -> str:
    """Normalize *raw* into ``https://host[:port]`` or raise UrlValidationError.

    Rules (spec Edge Cases): https-only; trailing slash, path, query and
    fragment are stripped; surrounding whitespace ignored.
    """
    candidate = (raw or "").strip()
    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme != "https":
        raise UrlValidationError(
            f"Konecty URL must be https:// (got {candidate!r})."
        )
    if not parsed.netloc:
        raise UrlValidationError(f"Konecty URL has no host: {candidate!r}.")
    return f"https://{parsed.netloc}"


def probe_well_known(url: str, timeout: int = 10) -> dict:
    """GET ``<url>/.well-known/oauth-protected-resource`` and classify the result.

    Returns a dict ``{"status": ..., "resource": str | None, "detail": str}``
    where status is one of:

    - ``"ok"``          — 200 JSON whose ``resource`` matches ``<url>/mcp``
    - ``"mismatch"``    — 200 JSON but ``resource`` differs (audience
                          misconfiguration: ``PLATFORM_MCP_RESOURCE_URL``)
    - ``"no_mcp"``      — 404 (old Konecty without MCP support)
    - ``"bad_json"``    — 200 but the body is not valid JSON
    - ``"unreachable"`` — any other HTTP or network failure

    Never raises.
    """
    probe_url = f"{url}{WELL_KNOWN_PATH}"
    req = urllib.request.Request(probe_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310 - https enforced by normalize_url
            body = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {
                "status": "no_mcp",
                "resource": None,
                "detail": f"HTTP 404 at {probe_url} — this Konecty does not expose MCP.",
            }
        return {"status": "unreachable", "resource": None, "detail": f"HTTP {exc.code} at {probe_url}."}
    except Exception as exc:  # noqa: BLE001 - URLError, timeout, SSL, ...
        return {"status": "unreachable", "resource": None, "detail": str(exc)}

    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        return {"status": "bad_json", "resource": None, "detail": f"Invalid JSON body: {exc}"}

    resource = data.get("resource") if isinstance(data, dict) else None
    issuer, issuer_warning = _check_issuer(data, url)
    expected = f"{url}/mcp"
    if resource == expected:
        return {
            "status": "ok",
            "resource": resource,
            "issuer": issuer,
            "issuer_warning": issuer_warning,
            "detail": "well-known OK",
        }
    return {
        "status": "mismatch",
        "resource": resource,
        "issuer": issuer,
        "issuer_warning": issuer_warning,
        "detail": (
            f"well-known resource is {resource!r} but the MCP URL is {expected!r} — "
            "audience misconfiguration (PLATFORM_MCP_RESOURCE_URL)."
        ),
    }


def _check_issuer(data: object, url: str) -> tuple[str | None, str | None]:
    """Validate ``authorization_servers[0]`` against the company URL.

    Returns ``(issuer, warning)``. The OAuth login happens against the issuer,
    so a bad value (the server's ``http://localhost:3000`` fallback when
    ``KONECTY_URL``/``OAUTH_ISSUER_URL`` is unset) breaks discovery even when
    the resource is right.
    """
    servers = data.get("authorization_servers") if isinstance(data, dict) else None
    issuer = servers[0] if isinstance(servers, list) and servers else None
    if issuer is None:
        return None, "well-known lists no authorization_servers — OAuth discovery will fail."
    issuer_host = urllib.parse.urlparse(issuer).hostname or ""
    url_host = urllib.parse.urlparse(url).hostname or ""
    if issuer_host in ("localhost", "127.0.0.1") or issuer_host != url_host:
        return issuer, (
            f"OAuth issuer is {issuer!r} (expected host {url_host!r}) — the deployment "
            "is missing KONECTY_URL/OAUTH_ISSUER_URL; browser login will fail until it is set."
        )
    return issuer, None


# --- command builders (must mirror skills/konecty-setup/SKILL.md) ------------

def build_add_user(url: str) -> list[str]:
    """``claude mcp add`` argv for the user MCP server."""
    return [
        "claude", "mcp", "add",
        "--transport", "http",
        "--scope", "user",
        USER_SERVER, f"{url}/mcp",
    ]


def build_add_admin_oauth(url: str, client_id: str, callback_port: int) -> list[str]:
    """``claude mcp add`` argv for the admin MCP — OAuth trusted-client path."""
    return [
        "claude", "mcp", "add",
        "--transport", "http",
        "--scope", "user",
        ADMIN_SERVER, f"{url}/admin-mcp",
        "--client-id", client_id,
        "--callback-port", str(callback_port),
    ]


def build_remove(name: str) -> list[str]:
    """``claude mcp remove`` argv for *name* (user scope)."""
    return ["claude", "mcp", "remove", "--scope", "user", name]


def build_list() -> list[str]:
    """``claude mcp list`` argv."""
    return ["claude", "mcp", "list"]


def format_command(argv: list[str]) -> str:
    """Printable form of *argv*, double-quoting args that contain spaces.

    Matches the templates shown in the konecty-setup skill byte-for-byte.
    """
    return " ".join(f'"{a}"' if " " in a else a for a in argv)


# --- execution ----------------------------------------------------------------

def cli_available() -> bool:
    """Return True when the ``claude`` CLI is on PATH."""
    return shutil.which("claude") is not None


def run_command(argv: list[str]) -> tuple[bool, str]:
    """Run *argv*; return ``(ok, combined stdout+stderr)``. Never raises."""
    try:
        completed = subprocess.run(  # nosec B603 - arg list, no shell
            argv, capture_output=True, text=True, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    detail = (completed.stdout or "") + (completed.stderr or "")
    return completed.returncode == 0, detail


def list_servers() -> list[str]:
    """Names currently registered in Claude Code (parsed from ``claude mcp list``).

    Returns an empty list when the command fails.
    """
    ok, out = run_command(build_list())
    if not ok:
        return []
    names: list[str] = []
    for line in out.splitlines():
        if ":" not in line:
            continue
        name = line.split(":", 1)[0].strip()
        # Server names are single tokens; skip prose lines ("Checking MCP ...").
        if name and " " not in name:
            names.append(name)
    return names


def register(name: str, add_argv: list[str]) -> dict:
    """Register (or replace) the MCP server *name* using *add_argv*.

    Replace-not-duplicate: when *name* is already registered, ``claude mcp
    remove`` runs first (MCPF-23). When the ``claude`` CLI is absent, nothing
    executes — the exact commands are returned for manual execution (MCPF-21).

    Returns
    -------
    dict
        CLI absent : ``{"executed": False, "commands": [<remove str>, <add str>]}``
        CLI present: ``{"executed": True, "ok": bool, "detail": str}``
    """
    if not cli_available():
        return {
            "executed": False,
            "commands": [format_command(build_remove(name)), format_command(add_argv)],
        }

    if name in list_servers():
        run_command(build_remove(name))

    ok, detail = run_command(add_argv)
    return {"executed": True, "ok": ok, "detail": detail}
