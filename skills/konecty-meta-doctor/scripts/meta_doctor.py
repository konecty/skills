#!/usr/bin/env python3
"""Konecty Meta Doctor: validate metadata integrity. Stdlib only."""
from __future__ import annotations

import argparse, json, os, sys, urllib.error, urllib.request
from typing import Any

CREDENTIALS_DIR = os.path.expanduser("~/.konecty")
ENV_FILE = os.path.join(CREDENTIALS_DIR, ".env")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials")
API_PREFIX = "/api/admin/meta"


def _load_credentials() -> tuple[str, str]:
    url, token = os.environ.get("KONECTY_URL", ""), os.environ.get("KONECTY_TOKEN", "")
    if os.path.isfile(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("KONECTY_URL=") and not url: url = line.split("=", 1)[1].strip()
                elif line.startswith("KONECTY_TOKEN=") and not token: token = line.split("=", 1)[1].strip()
    if (not url or not token) and os.path.isfile(CREDENTIALS_FILE):
        import configparser; config = configparser.ConfigParser(); config.read(CREDENTIALS_FILE)
        if "default" in config: url = url or config["default"].get("host", ""); token = token or config["default"].get("authid", "")
    return url.rstrip("/"), token


def _creds(args): host, token = args.host or "", args.token or ""; h, t = _load_credentials(); host = host or h; token = token or t; return host, token


def _api(host, token, method, path, body=None):
    url = f"{host}{API_PREFIX}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r: return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"success": False, "errors": [f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}"]}


def _run_doctor(host: str, token: str, document: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if document:
        body["document"] = document
    return _api(host, token, "POST", "/doctor", body)


def cmd_check(args):
    host, token = _creds(args)
    result = _run_doctor(host, token, args.document)
    if result.get("success") is not True:
        errors = result.get("errors", ["Doctor request failed"])
        print("Doctor failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)
    issues = result.get("issues", [])
    summary = result.get("summary", {})

    if args.format == "json":
        print(json.dumps({"summary": summary, "issues": issues}, indent=2, ensure_ascii=False))
        return

    print(
        f"Summary: total={summary.get('total', 0)} valid={summary.get('valid', 0)} "
        f"warnings={summary.get('warnings', 0)} errors={summary.get('errors', 0)}"
    )
    if not issues:
        print("No issues found.")
        return
    print()
    for issue in issues:
        severity = str(issue.get("severity", "warning")).upper()
        meta_id = issue.get("metaId", "?")
        message = issue.get("message", "")
        print(f"  [{severity}] {meta_id}: {message}")


def cmd_check_queues(args):
    host, token = _creds(args)
    result = _run_doctor(host, token, None)
    if result.get("success") is not True:
        errors = result.get("errors", ["Doctor request failed"])
        print("Doctor failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)

    issues = [
        issue for issue in result.get("issues", [])
        if "queue" in str(issue.get("message", "")).lower()
        or "queueconfig" in str(issue.get("message", "")).lower()
    ]

    if args.format == "json":
        print(json.dumps(issues, indent=2, ensure_ascii=False))
    else:
        if not issues:
            print("Queue configuration is consistent.")
            return
        for issue in issues:
            icon = "ERROR" if issue.get("severity") == "error" else "WARN"
            print(f"  [{icon}] {issue.get('metaId', '?')}: {issue.get('message', '')}")


def main():
    parser = argparse.ArgumentParser(description="Konecty Meta Doctor")
    parser.add_argument("--host", default=""); parser.add_argument("--token", default="")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check"); p.add_argument("--document"); p.add_argument("--format", choices=["table", "json"], default="table"); p.set_defaults(func=cmd_check)
    p = sub.add_parser("check-queues"); p.add_argument("--format", choices=["table", "json"], default="table"); p.set_defaults(func=cmd_check_queues)

    args = parser.parse_args(); args.func(args)


if __name__ == "__main__": main()
