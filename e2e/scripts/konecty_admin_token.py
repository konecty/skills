#!/usr/bin/env python3
"""Fetch the Konecty admin token and write credentials to the env file.

On first boot Konecty creates an ``admin`` user with a random password and logs
it once. This script reads that password from the Docker container logs (or
accepts ``--password``), logs in via ``POST /rest/auth/login``, and either
writes ``KONECTY_URL`` + ``KONECTY_TOKEN`` to the env file or prints the token
to stdout when ``--print-only`` is given.

All HTTP is done via :mod:`urllib` (Python stdlib — no httpx/requests).

Usage::

    # Derive password from container logs, write ~/.konecty/.env
    python e2e/scripts/konecty_admin_token.py

    # Supply password explicitly, just print the token
    python e2e/scripts/konecty_admin_token.py --password MySecret --print-only

    # Custom URL and container
    python e2e/scripts/konecty_admin_token.py \
        --url http://localhost:3100 \
        --container konecty-e2e-konecty \
        --env-file ~/.konecty/.env
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Match the first-boot log line:
#   Create first user (admin) with password FcpWAE6B
# Stop at whitespace *or* a JSON-delimiter quote so the regex does not
# swallow trailing characters when the log line is JSON-encoded
# (e.g. ``...with password FcpWAE6B"}``).
_PW_RE = re.compile(r"admin\) with password ([^\s\"]+)")


def password_from_logs(container: str) -> str | None:
    """Extract the admin password from *container* Docker logs.

    Runs ``docker logs <container>`` and returns the password found in the
    **last** matching log line (most recent boot). Returns ``None`` when no
    match is found.

    Calls :func:`sys.exit` with a clear message if ``docker`` is not on PATH.
    """
    try:
        result = subprocess.run(
            ["docker", "logs", container],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        sys.exit(
            "docker not found on PATH — install Docker or pass --password directly"
        )

    logs = result.stdout + result.stderr
    matches = _PW_RE.findall(logs)
    return matches[-1] if matches else None


def _attempt_login(url: str, body: dict) -> tuple[int, dict | str]:
    """POST a login *body* to Konecty; return ``(status, parsed-or-raw)``.

    Sends ``Sec-Fetch-Site: none`` so the request passes the strict-CORS zone
    (``/rest/auth/*``) without depending on an allow-listed ``Origin`` — newer
    Konecty (3.8.x) returns ``403 Origin header required`` otherwise.
    """
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{url.rstrip('/')}/rest/auth/login",
        data=payload,
        headers={"Content-Type": "application/json", "Sec-Fetch-Site": "none"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")


def login(url: str, user: str, password: str) -> str:
    """Log in to Konecty and return the ``authId`` token.

    Konecty 3.8.x expects the **raw password** (the server hashes it). Older
    builds (3.2.x) accepted the SHA-256 hex digest via ``password_SHA256``.
    We try the raw password first and fall back to the digest so the script
    works across versions.

    Calls :func:`sys.exit` when neither scheme yields an ``authId``.
    """
    status, data = _attempt_login(url, {"user": user, "password": password})
    if status == 200 and isinstance(data, dict) and data.get("authId"):
        return data["authId"]

    # Fall back to the legacy SHA-256 scheme (Konecty <= 3.2.x).
    sha = hashlib.sha256(password.encode()).hexdigest()
    status2, data2 = _attempt_login(url, {"user": user, "password_SHA256": sha})
    if status2 == 200 and isinstance(data2, dict) and data2.get("authId"):
        return data2["authId"]

    sys.exit(
        "login failed for both raw-password and SHA-256 schemes:\n"
        f"  raw    ({status}): {data}\n"
        f"  sha256 ({status2}): {data2}"
    )


def write_env_file(path: str, url: str, token: str) -> None:
    """Write ``KONECTY_URL`` and ``KONECTY_TOKEN`` to *path*.

    Expands ``~`` in *path*, creates parent directories as needed, and
    overwrites the entire file (it is expected to contain only these two keys).
    """
    env_path = Path(os.path.expanduser(path))
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        f"KONECTY_URL={url}\nKONECTY_TOKEN={token}\n",
        encoding="utf-8",
    )
    print(f"Credentials written to {env_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch the Konecty admin token and write credentials."
    )
    parser.add_argument(
        "--url",
        default="http://localhost:3200",
        help="Base URL of the Konecty instance (default: http://localhost:3200)",
    )
    parser.add_argument(
        "--container",
        default="konecty-e2e-konecty",
        help="Docker container name to read the admin password from "
        "(default: konecty-e2e-konecty)",
    )
    parser.add_argument(
        "--user",
        default="admin",
        help="Konecty username to log in as (default: admin)",
    )
    parser.add_argument(
        "--password",
        default=None,
        metavar="PW",
        help="Admin password; if omitted the password is read from container logs",
    )
    parser.add_argument(
        "--env-file",
        default="~/.konecty/.env",
        metavar="PATH",
        help="Path to write KONECTY_URL and KONECTY_TOKEN (default: ~/.konecty/.env)",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the token to stdout and skip writing the env file",
    )
    args = parser.parse_args(argv)

    # Resolve password: explicit flag takes priority, fall back to container logs.
    password = args.password or password_from_logs(args.container)
    if not password:
        sys.exit(
            f"Could not find the admin password in container logs for "
            f"'{args.container}'.\n"
            f"Tip: docker logs {args.container} | grep password\n"
            f"     Then pass it explicitly: --password <PW>"
        )

    token = login(args.url, args.user, password)

    if args.print_only:
        print(token)
    else:
        write_env_file(args.env_file, args.url, token)
        print(token)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
