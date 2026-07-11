#!/usr/bin/env python3
"""Poll the Konecty liveness endpoint until it responds or the timeout expires.

Makes repeated ``GET <url>/liveness`` requests via urllib (stdlib only) until
the server returns HTTP 200, then exits 0. If the timeout is reached first the
script prints an error to stderr and exits 1.

Usage::

    python e2e/scripts/wait_for_konecty.py [--url http://localhost:3100] \
        [--timeout 120] [--interval 3]
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request


def wait(url: str, timeout: float, interval: float) -> int:
    """Poll ``<url>/liveness`` until 200 or timeout.

    Prints one dot per poll attempt to *stderr* so CI log streams show
    progress without polluting stdout.

    Returns 0 on success, 1 on timeout.
    """
    liveness_url = f"{url.rstrip('/')}/liveness"
    deadline = time.monotonic() + timeout

    print(f"Waiting for Konecty at {liveness_url} …", file=sys.stderr)

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(liveness_url, timeout=interval) as resp:
                if resp.status == 200:
                    print(f"\nKonecty is healthy at {url}", flush=True)
                    return 0
                print(f".", end="", file=sys.stderr, flush=True)
        except urllib.error.HTTPError as exc:
            # Server responded but with a non-2xx code; keep waiting.
            print(f".", end="", file=sys.stderr, flush=True)
        except (urllib.error.URLError, OSError):
            # Connection refused / network unreachable — server not up yet.
            print(f".", end="", file=sys.stderr, flush=True)

        time.sleep(interval)

    print(
        f"\nTimed out after {timeout}s waiting for Konecty at {liveness_url}",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Poll the Konecty liveness endpoint until ready or timeout."
    )
    parser.add_argument(
        "--url",
        default="http://localhost:3100",
        help="Base URL of the Konecty instance (default: http://localhost:3100)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120,
        metavar="SECONDS",
        help="Total time to wait before giving up (default: 120)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3,
        metavar="SECONDS",
        help="Seconds between poll attempts (default: 3)",
    )
    args = parser.parse_args(argv)
    return wait(args.url, args.timeout, args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
