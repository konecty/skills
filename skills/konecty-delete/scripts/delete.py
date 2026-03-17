#!/usr/bin/env python3
"""
Konecty Delete: permanently remove ONE record via DELETE /rest/data/:document.

Safety layers enforced by this script:
  1. One record at a time — batch deletion is intentionally unsupported.
  2. Preview before delete — always shows the full record before acting.
  3. Explicit --confirm flag — deletion is refused without it.
  4. Irreversibility warning — printed on every execution.
  5. _updatedAt freshness — fetched live and validated server-side.

Server-side guards (enforced by Konecty, not this script):
  - Permission check (isDeletable)
  - _updatedAt optimistic locking (real-time, not commented out)
  - Foreign key check (blocks if other records reference this one)
  - Archival to .Trash before hard delete

Subcommands:
  preview <Document> <term>          — show the record without deleting
  delete  <Document> <term> --confirm — delete after confirmation

Credentials from ~/.konecty/.env or ~/.konecty/credentials. Stdlib only.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

CREDENTIALS_DIR = os.path.expanduser("~/.konecty")
ENV_FILE = os.path.join(CREDENTIALS_DIR, ".env")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials")

IRREVERSIBILITY_WARNING = """\
⚠️  WARNING: Deletion in Konecty is IRREVERSIBLE from the application's perspective.
   The record is archived to a .Trash collection and permanently removed from the
   main collection. It cannot be restored via the standard API.
"""


def _load_credentials() -> tuple[str, str]:
    url = os.environ.get("KONECTY_URL", "")
    token = os.environ.get("KONECTY_TOKEN", "")

    if os.path.isfile(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("KONECTY_URL=") and not url:
                    url = line.split("=", 1)[1].strip()
                elif line.startswith("KONECTY_TOKEN=") and not token:
                    token = line.split("=", 1)[1].strip()

    if (not url or not token) and os.path.isfile(CREDENTIALS_FILE):
        config = configparser.ConfigParser()
        config.read(CREDENTIALS_FILE, encoding="utf-8")
        section = "default"
        if section in config:
            if not url:
                url = config[section].get("host", "")
            if not token:
                token = config[section].get("authid", "")

    return url.rstrip("/"), token


def _do_request(req: urllib.request.Request) -> Any:
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            content_type = resp.headers.get("Content-Type", "")
            if "ndjson" in content_type:
                lines = [line for line in raw.strip().splitlines() if line.strip()]
                return [json.loads(line) for line in lines]
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
            msg = body.get("errors") or body.get("message") or str(body)
        except Exception:
            msg = e.reason
        raise SystemExit(f"HTTP {e.code}: {msg}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Connection error: {e.reason}")


def _http_post(host: str, token: str, path: str, body: dict) -> Any:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{host}{path}",
        data=data,
        headers={"Authorization": token, "Content-Type": "application/json",
                 "Accept": "application/json, application/x-ndjson"},
        method="POST",
    )
    return _do_request(req)


def _http_delete(host: str, token: str, document: str, _id: str, updated_at: str) -> Any:
    payload = {"ids": [{"_id": _id, "_updatedAt": {"$date": updated_at}}]}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/rest/data/{document}",
        data=data,
        headers={"Authorization": token, "Content-Type": "application/json",
                 "Accept": "application/json"},
        method="DELETE",
    )
    return _do_request(req)


def _fetch_one(host: str, token: str, document: str, term: str) -> dict:
    """Find exactly one record by numeric code or exact _id."""
    try:
        code_as_int = int(term)
        fil: dict = {"match": "and", "conditions": [{"term": "code", "operator": "equals", "value": code_as_int}]}
    except ValueError:
        fil = {"match": "and", "conditions": [{"term": "_id", "operator": "equals", "value": term}]}

    body: dict = {"document": document, "filter": fil, "limit": 2}
    result = _http_post(host, token, "/rest/query/json", body)

    rows: list = []
    if isinstance(result, list):
        rows = [r for r in result if "_meta" not in r]
    elif isinstance(result, dict):
        rows = result.get("data", [])

    if not rows:
        raise SystemExit(f"No record found in '{document}' for: {term}")
    if len(rows) > 1:
        raise SystemExit(
            f"Multiple records found in '{document}' for: {term}. "
            "Provide the exact _id to avoid ambiguity."
        )
    return rows[0]


def _print_record_summary(document: str, record: dict) -> None:
    _id = record.get("_id", "?")
    updated_at = record.get("_updatedAt", "?")
    code = record.get("code")
    # Build a compact display of key fields (skip internal _ fields except _id/_updatedAt)
    display = {
        k: v for k, v in record.items()
        if not k.startswith("_") and v is not None
    }
    print(f"  Document  : {document}")
    print(f"  _id       : {_id}")
    if code is not None:
        print(f"  code      : {code}")
    print(f"  _updatedAt: {updated_at}")
    if display:
        print(f"  fields    : {json.dumps(display, ensure_ascii=False, indent=4)}")


def cmd_preview(host: str, token: str, args: argparse.Namespace) -> None:
    """Show the record that would be deleted, with safety warnings."""
    record = _fetch_one(host, token, args.document, args.term)

    print(IRREVERSIBILITY_WARNING)
    print("Record that would be deleted:")
    print("-" * 40)
    _print_record_summary(args.document, record)
    print("-" * 40)
    print()
    print("To proceed with deletion, run:")
    _id = record.get("_id")
    print(f"  python3 delete.py delete {args.document} {_id} --confirm")
    print()
    print("IMPORTANT: Pass the exact _id (not the code) to the delete command.")


def cmd_delete(host: str, token: str, args: argparse.Namespace) -> None:
    """Delete ONE record after explicit confirmation."""
    if not args.confirm:
        print("Deletion refused: --confirm flag is required.", file=sys.stderr)
        print("Run 'preview' first to inspect the record, then add --confirm.", file=sys.stderr)
        sys.exit(1)

    # Always fetch live to get the freshest _updatedAt
    record = _fetch_one(host, token, args.document, args.term)
    _id = record.get("_id")
    updated_at = record.get("_updatedAt")

    print(IRREVERSIBILITY_WARNING)
    print("About to permanently delete:")
    print("-" * 40)
    _print_record_summary(args.document, record)
    print("-" * 40)
    print()

    result = _http_delete(host, token, args.document, _id, updated_at)

    if isinstance(result, dict):
        if result.get("success"):
            deleted_ids = result.get("data", [])
            print(f"✓ Deleted successfully. ID: {deleted_ids}")
        else:
            errors = result.get("errors", [])
            for err in errors:
                msg = err.get("message", str(err))
                print(f"ERROR: {msg}", file=sys.stderr)
                # Provide actionable guidance for common errors
                if "referenced by" in msg:
                    print(
                        "  → This record is referenced by another module. Remove or update those "
                        "references before deleting.",
                        file=sys.stderr,
                    )
                elif "new version" in msg:
                    print(
                        "  → The record was modified after you fetched it. "
                        "Run 'preview' again to get the latest version.",
                        file=sys.stderr,
                    )
                elif "permission" in msg.lower():
                    print(
                        "  → Your account does not have delete permission for this module.",
                        file=sys.stderr,
                    )
            sys.exit(1)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Konecty record deletion — one record at a time, with mandatory confirmation.\n"
            "Always run 'preview' before 'delete'."
        )
    )
    parser.add_argument("--host", default="", help="Override KONECTY_URL")
    parser.add_argument("--token", default="", help="Override KONECTY_TOKEN")

    sub = parser.add_subparsers(dest="command", required=True)

    # preview
    p_preview = sub.add_parser(
        "preview",
        help="Inspect the record that would be deleted — no changes made",
    )
    p_preview.add_argument("document", help="Document/module name (e.g. Message, Contact)")
    p_preview.add_argument(
        "term",
        help="Numeric code or exact _id of the record to inspect",
    )

    # delete
    p_delete = sub.add_parser(
        "delete",
        help="Permanently delete ONE record (irreversible — requires --confirm)",
    )
    p_delete.add_argument("document", help="Document/module name")
    p_delete.add_argument(
        "term",
        help="Numeric code or exact _id of the record to delete",
    )
    p_delete.add_argument(
        "--confirm",
        action="store_true",
        required=True,
        help="Required: explicitly acknowledge that deletion is irreversible",
    )

    args = parser.parse_args()

    env_url, env_token = _load_credentials()
    host = (args.host or env_url).rstrip("/")
    token = args.token or env_token

    if not host:
        print("Missing KONECTY_URL. Set it in ~/.konecty/.env or pass --host.", file=sys.stderr)
        sys.exit(1)
    if not token:
        print("Missing KONECTY_TOKEN. Run konecty-session skill first.", file=sys.stderr)
        sys.exit(1)

    if args.command == "preview":
        cmd_preview(host, token, args)
    elif args.command == "delete":
        cmd_delete(host, token, args)


if __name__ == "__main__":
    main()
