#!/usr/bin/env python3
"""
Konecty Create: create records via POST /rest/data/:document.
Also provides a lookup helper to resolve _ids before creating.
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
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
            "Accept": "application/json, application/x-ndjson",
        },
        method="POST",
    )
    return _do_request(req)


def cmd_create(host: str, token: str, args: argparse.Namespace) -> None:
    """POST /rest/data/:document — create a new record."""
    try:
        payload = json.loads(args.data)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid --data JSON: {e}")

    if not isinstance(payload, dict):
        raise SystemExit("--data must be a JSON object (dict)")

    result = _http_post(host, token, f"/rest/data/{args.document}", payload)

    if isinstance(result, dict):
        if result.get("success"):
            records = result.get("data", [])
            if records:
                print(json.dumps(records[0], ensure_ascii=False, indent=2))
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            errors = result.get("errors", [])
            for err in errors:
                print(f"ERROR: {err.get('message', err)}", file=sys.stderr)
            sys.exit(1)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_lookup(host: str, token: str, args: argparse.Namespace) -> None:
    """Search a document by text to find the _id for use in lookup fields."""
    document = args.document
    term = args.term
    fields = args.fields or "code,name"
    limit = args.limit

    # Build filter: textSearch or contains on code/name
    try:
        code_as_int = int(term)
        fil: dict = {
            "match": "and",
            "conditions": [{"term": "code", "operator": "equals", "value": code_as_int}],
        }
    except ValueError:
        fil = {"match": "and", "textSearch": term}

    body: dict = {
        "document": document,
        "filter": fil,
        "fields": f"_id,{fields}",
        "limit": limit,
    }

    result = _http_post(host, token, "/rest/query/json", body)

    rows: list = []
    if isinstance(result, list):
        rows = [r for r in result if "_meta" not in r]
    elif isinstance(result, dict):
        rows = result.get("data", [])

    if not rows:
        print(f"No records found in '{document}' for term: {term}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(rows)} record(s) in {document}:\n")
    for r in rows:
        _id = r.get("_id", "?")
        display = {k: v for k, v in r.items() if k != "_id"}
        print(f'  _id: "{_id}"  {json.dumps(display, ensure_ascii=False)}')


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Konecty record creation. Credentials from ~/.konecty/.env or ~/.konecty/credentials."
    )
    parser.add_argument("--host", default="", help="Override KONECTY_URL")
    parser.add_argument("--token", default="", help="Override KONECTY_TOKEN")

    sub = parser.add_subparsers(dest="command", required=True)

    # create subcommand
    p_create = sub.add_parser("create", help="Create a new record via POST /rest/data/:document")
    p_create.add_argument("document", help="Document/module name (e.g. Message, Contact)")
    p_create.add_argument(
        "--data",
        required=True,
        help='Record payload as JSON object, e.g. \'{"subject":"Hello","status":"Nova","contact":{"_id":"..."}}\''
    )

    # lookup subcommand
    p_lookup = sub.add_parser(
        "lookup",
        help="Find a record's _id for use in lookup fields (search by code or text)"
    )
    p_lookup.add_argument("document", help="Document to search in (e.g. Contact, Campaign)")
    p_lookup.add_argument("term", help="Search term: numeric code or text (uses textSearch)")
    p_lookup.add_argument("--fields", default="", help="Extra fields to display (default: code,name)")
    p_lookup.add_argument("--limit", type=int, default=5, help="Max results (default: 5)")

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

    if args.command == "create":
        cmd_create(host, token, args)
    elif args.command == "lookup":
        cmd_lookup(host, token, args)


if __name__ == "__main__":
    main()
