#!/usr/bin/env python3
"""
Konecty Update: update records via PUT /rest/data/:document.
Always requires _updatedAt from the current record (optimistic locking guard).
Subcommands:
  fetch  <Document> <term>         — fetch a record's _id and _updatedAt by code or _id
  update <Document> --ids --data   — PUT update (full control)
  patch  <Document> <term> --data  — convenience: fetch + update in one step
Credentials from ~/.konecty/.env or ~/.konecty/credentials. Stdlib only.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

CREDENTIALS_DIR = os.path.expanduser("~/.konecty")
ENV_FILE = os.path.join(CREDENTIALS_DIR, ".env")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials")


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


def _http_put(host: str, token: str, path: str, body: dict) -> Any:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{host}{path}",
        data=data,
        headers={"Authorization": token, "Content-Type": "application/json",
                 "Accept": "application/json"},
        method="PUT",
    )
    return _do_request(req)


def _find_record(host: str, token: str, document: str, term: str, extra_fields: str = "") -> dict:
    """Find a single record by code (numeric) or exact _id. Returns full record."""
    fields = "_id,_updatedAt,code"
    if extra_fields:
        fields += f",{extra_fields}"

    try:
        code_as_int = int(term)
        fil: dict = {"match": "and", "conditions": [{"term": "code", "operator": "equals", "value": code_as_int}]}
    except ValueError:
        # Assume it's a direct _id
        fil = {"match": "and", "conditions": [{"term": "_id", "operator": "equals", "value": term}]}

    body: dict = {"document": document, "filter": fil, "fields": fields, "limit": 2}
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
            f"Multiple records found in '{document}' for: {term}. Use the exact _id instead."
        )
    return rows[0]


def cmd_fetch(host: str, token: str, args: argparse.Namespace) -> None:
    """Fetch a record showing _id and _updatedAt prominently."""
    record = _find_record(host, token, args.document, args.term, args.fields or "")
    _id = record.get("_id")
    updated_at = record.get("_updatedAt")

    print(f'_id:        "{_id}"')
    print(f'_updatedAt: "{updated_at}"')

    # Show remaining fields
    rest = {k: v for k, v in record.items() if k not in ("_id", "_updatedAt")}
    if rest:
        print(f"fields:     {json.dumps(rest, ensure_ascii=False)}")

    print()
    print("Use in update command:")
    print(f'  --ids \'[{{"_id":"{_id}","_updatedAt":"{updated_at}"}}]\'')


def cmd_update(host: str, token: str, args: argparse.Namespace) -> None:
    """PUT /rest/data/:document with explicit ids and data."""
    try:
        ids = json.loads(args.ids)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid --ids JSON: {e}")

    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid --data JSON: {e}")

    if not isinstance(ids, list) or not ids:
        raise SystemExit("--ids must be a non-empty JSON array")
    if not isinstance(data, dict) or not data:
        raise SystemExit("--data must be a non-empty JSON object")

    # Normalize _updatedAt to $date format expected by the API
    for entry in ids:
        if "_updatedAt" in entry and not isinstance(entry["_updatedAt"], dict):
            entry["_updatedAt"] = {"$date": entry["_updatedAt"]}

    payload = {"ids": ids, "data": data}
    result = _http_put(host, token, f"/rest/data/{args.document}", payload)
    _print_result(result)


def cmd_patch(host: str, token: str, args: argparse.Namespace) -> None:
    """Convenience: fetch record then update in one step."""
    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid --data JSON: {e}")

    record = _find_record(host, token, args.document, args.term)
    _id = record.get("_id")
    updated_at = record.get("_updatedAt")

    print(f"Fetched: _id={_id}  _updatedAt={updated_at}", file=sys.stderr)

    payload = {
        "ids": [{"_id": _id, "_updatedAt": {"$date": updated_at}}],
        "data": data,
    }
    result = _http_put(host, token, f"/rest/data/{args.document}", payload)
    _print_result(result)


def _print_result(result: Any) -> None:
    if isinstance(result, dict):
        if result.get("success"):
            records = result.get("data", [])
            print(json.dumps(records[0] if len(records) == 1 else records, ensure_ascii=False, indent=2))
        else:
            for err in result.get("errors", []):
                print(f"ERROR: {err.get('message', err)}", file=sys.stderr)
            sys.exit(1)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Konecty record update. Credentials from ~/.konecty/.env or ~/.konecty/credentials."
    )
    parser.add_argument("--host", default="", help="Override KONECTY_URL")
    parser.add_argument("--token", default="", help="Override KONECTY_TOKEN")

    sub = parser.add_subparsers(dest="command", required=True)

    # fetch subcommand
    p_fetch = sub.add_parser("fetch", help="Fetch a record's _id and _updatedAt by code or _id")
    p_fetch.add_argument("document", help="Document/module name")
    p_fetch.add_argument("term", help="Numeric code or exact _id of the record")
    p_fetch.add_argument("--fields", default="", help="Extra fields to display alongside _id and _updatedAt")

    # update subcommand
    p_update = sub.add_parser("update", help="PUT update with explicit ids array and data (full control)")
    p_update.add_argument("document", help="Document/module name")
    p_update.add_argument(
        "--ids",
        required=True,
        help='Array of ids as JSON: \'[{"_id":"...","_updatedAt":"..."}]\' — _updatedAt can be ISO string or $date object',
    )
    p_update.add_argument(
        "--data",
        required=True,
        help='Fields to update as JSON object: \'{"status":"Inativo"}\' — null clears a field',
    )

    # patch subcommand (fetch + update)
    p_patch = sub.add_parser("patch", help="Fetch the record first, then update (convenience shortcut)")
    p_patch.add_argument("document", help="Document/module name")
    p_patch.add_argument("term", help="Numeric code or exact _id of the record to update")
    p_patch.add_argument(
        "--data",
        required=True,
        help='Fields to update as JSON object: \'{"status":"Inativo"}\'',
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

    if args.command == "fetch":
        cmd_fetch(host, token, args)
    elif args.command == "update":
        cmd_update(host, token, args)
    elif args.command == "patch":
        cmd_patch(host, token, args)


if __name__ == "__main__":
    main()
