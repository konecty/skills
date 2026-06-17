"""Credential setup: URL prompt + OTP via auth.py subprocess. Implemented in T7."""
from __future__ import annotations

import os
import subprocess
import sys
import urllib.parse
from pathlib import Path

DEFAULT_ENV_PATH: Path = Path.home() / ".konecty" / ".env"


def current_env(path: Path = DEFAULT_ENV_PATH) -> dict:
    """Parse the .env file and return url/token values.

    Returns a dict with keys "url" and "token"; each is None when missing.
    """
    result: dict = {"url": None, "token": None}
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


def run_otp(url: str, auth_py: Path, identifier: str) -> bool:
    """Drive auth.py via subprocess to request and verify an OTP.

    *identifier* is treated as an email when it contains "@", otherwise phone.
    Returns True on success, False on any failure (never raises).
    """
    flag = "--email" if "@" in identifier else "--phone"
    try:
        req_result = subprocess.run(
            [sys.executable, str(auth_py), "request-otp", "--host", url, flag, identifier],
            check=False,
        )
        if req_result.returncode != 0:
            return False

        code = input("Enter the 6-digit OTP code: ").strip()

        ver_result = subprocess.run(
            [
                sys.executable,
                str(auth_py),
                "verify-otp",
                "--host",
                url,
                flag,
                identifier,
                "--otp",
                code,
            ],
            check=False,
        )
        return ver_result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def write_url_only(url: str, path: Path = DEFAULT_ENV_PATH) -> None:
    """Write/merge KONECTY_URL into the .env file.

    Preserves all existing lines except the KONECTY_URL line, which is
    replaced (or appended when absent).  The parent directory is created
    with mode 0o700; the file is chmod'd to 0o600 after writing.
    """
    parent = path.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)

    existing_lines: list[str] = []
    if path.is_file():
        with open(path, "r", encoding="utf-8") as fh:
            existing_lines = fh.readlines()

    # Remove any existing KONECTY_URL line; keep everything else.
    filtered = [ln for ln in existing_lines if not ln.strip().startswith("KONECTY_URL=")]
    filtered.append(f"KONECTY_URL={url}\n")

    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(filtered)

    os.chmod(path, 0o600)
