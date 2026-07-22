"""Local Konecty URL cache (T20, MCP-first; 0.3.0 dropped the legacy manual
login / Bearer-header credential flow).

Auth is OAuth end to end — both the user MCP and the admin MCP (trusted
client, ADR-0011) — handled entirely by Claude Code. This module keeps no
token of any kind; it only caches the company URL in ``~/.konecty/.env`` so
``status``/``doctor`` can probe the deployment without asking again.
"""
from __future__ import annotations

import os
import urllib.parse
from pathlib import Path

DEFAULT_ENV_PATH: Path = Path.home() / ".konecty" / ".env"


def current_env(path: Path = DEFAULT_ENV_PATH) -> dict:
    """Parse the .env file and return the cached URL.

    Returns a dict with key "url" (None when missing).
    """
    result: dict = {"url": None}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("KONECTY_URL="):
                    result["url"] = stripped[len("KONECTY_URL="):] or None
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


def write_url_only(url: str, path: Path = DEFAULT_ENV_PATH) -> None:
    """Write/merge KONECTY_URL into the .env file."""
    _merge_env({"KONECTY_URL": url}, path)
