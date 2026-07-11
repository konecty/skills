#!/usr/bin/env python3
"""
Konecty Find: search documents via /rest/data/:document/find and /rest/query/json.
Credentials loaded from ~/.konecty/.env (KONECTY_URL + KONECTY_TOKEN).
Stdlib only: urllib, json, configparser.
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
        with urllib.request.urlopen(req, timeout=60) as resp:
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


def _http_get(host: str, token: str, path: str, params: dict | None = None) -> Any:
    url = f"{host}{path}"
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(
        url,
        headers={"Authorization": token, "Accept": "application/json"},
        method="GET",
    )
    return _do_request(req)


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


def _parse_json_arg(value: str | None, name: str) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid {name} JSON: {e}")


def _parse_sort(sort_str: str | None) -> list | None:
    if not sort_str:
        return None
    try:
        parsed = json.loads(sort_str)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        # Shorthand: "field:asc,field2:desc"
        items = []
        for part in sort_str.split(","):
            part = part.strip()
            if ":" in part:
                field, direction = part.split(":", 1)
                items.append({"property": field.strip(), "direction": direction.strip().upper()})
            else:
                items.append({"property": part, "direction": "ASC"})
        return items


def _print_results(data: Any, output_format: str) -> None:
    if output_format == "ndjson":
        items = data if isinstance(data, list) else [data]
        for item in items:
            print(json.dumps(item, ensure_ascii=False))
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_find(host: str, token: str, args: argparse.Namespace) -> None:
    """Search via /rest/data/:document/find (GET without filter, POST with filter)."""
    document = args.document
    fil = _parse_json_arg(args.filter, "--filter")
    sort = _parse_sort(args.sort)

    if fil or args.post:
        body: dict = {}
        if fil:
            body["filter"] = fil
        if args.fields:
            body["fields"] = args.fields
        if sort:
            body["sort"] = sort
        if args.limit is not None:
            body["limit"] = args.limit
        if args.start is not None:
            body["start"] = args.start
        result = _http_post(host, token, f"/rest/data/{document}/find", body)
    else:
        params: dict = {}
        if args.fields:
            params["fields"] = args.fields
        if sort:
            params["sort"] = json.dumps(sort)
        if args.limit is not None:
            params["limit"] = str(args.limit)
        if args.start is not None:
            params["start"] = str(args.start)
        result = _http_get(host, token, f"/rest/data/{document}/find", params or None)

    if isinstance(result, dict):
        total = result.get("total")
        data = result.get("data", [])
        if total is not None:
            print(f"# Total: {total}  Returned: {len(data)}", file=sys.stderr)
        _print_results(data, args.output)
    elif isinstance(result, list):
        meta = next((r for r in result if "_meta" in r), None)
        rows = [r for r in result if r is not meta]
        print(f"# Returned: {len(rows)}", file=sys.stderr)
        _print_results(rows, args.output)
    else:
        _print_results(result, args.output)


def cmd_query(host: str, token: str, args: argparse.Namespace) -> None:
    """Cross-module query via /rest/query/json."""
    document = args.document
    fil = _parse_json_arg(args.filter, "--filter")
    sort = _parse_sort(args.sort)
    relations = _parse_json_arg(args.relations, "--relations")

    body: dict = {"document": document}
    if fil:
        body["filter"] = fil
    if args.fields:
        body["fields"] = args.fields
    if sort:
        body["sort"] = sort
    if args.limit is not None:
        body["limit"] = args.limit
    if args.start is not None:
        body["start"] = args.start
    if relations:
        body["relations"] = relations if isinstance(relations, list) else [relations]
    if args.include_meta:
        body["includeMeta"] = True
    if not args.include_total:
        body["includeTotal"] = False

    result = _http_post(host, token, "/rest/query/json", body)

    if isinstance(result, list):
        meta_line = next((r for r in result if "_meta" in r), None)
        rows = [r for r in result if r is not meta_line]
        if meta_line:
            meta = meta_line.get("_meta", {})
            total = meta.get("total")
            if total is not None:
                print(f"# Total: {total}  Returned: {len(rows)}", file=sys.stderr)
        else:
            print(f"# Returned: {len(rows)}", file=sys.stderr)
        _print_results(rows, args.output)
    else:
        _print_results(result, args.output)


def cmd_sql(host: str, token: str, args: argparse.Namespace) -> None:
    """SQL query via /rest/query/sql."""
    body: dict = {"sql": args.sql}
    if args.include_meta:
        body["includeMeta"] = True
    if not args.include_total:
        body["includeTotal"] = False

    result = _http_post(host, token, "/rest/query/sql", body)

    if isinstance(result, list):
        meta_line = next((r for r in result if "_meta" in r), None)
        rows = [r for r in result if r is not meta_line]
        if meta_line:
            meta = meta_line.get("_meta", {})
            total = meta.get("total")
            if total is not None:
                print(f"# Total: {total}  Returned: {len(rows)}", file=sys.stderr)
        else:
            print(f"# Returned: {len(rows)}", file=sys.stderr)
        _print_results(rows, args.output)
    else:
        _print_results(result, args.output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Konecty document search. Credentials from ~/.konecty/.env."
    )
    parser.add_argument("--host", default="", help="Override KONECTY_URL")
    parser.add_argument("--token", default="", help="Override KONECTY_TOKEN")
    parser.add_argument(
        "--output", choices=["json", "ndjson"], default="json", help="Output format (default: json)"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # find subcommand
    p_find = sub.add_parser("find", help="Search via /rest/data/:document/find")
    p_find.add_argument("document", help="Document/module name (e.g. Contact, Opportunity)")
    p_find.add_argument(
        "--filter",
        help='KonFilter as JSON, e.g. \'{"match":"and","conditions":[{"term":"status","operator":"equals","value":"active"}]}\'',
    )
    p_find.add_argument("--fields", help="Comma-separated field names to return")
    p_find.add_argument(
        "--sort", help='Sort: JSON array or shorthand "field:asc,field2:desc"'
    )
    p_find.add_argument(
        "--limit", type=int, default=50, help="Max records (default: 50, -1 for no limit)"
    )
    p_find.add_argument("--start", type=int, default=0, help="Offset/skip (default: 0)")
    p_find.add_argument("--post", action="store_true", help="Force POST even without filter")

    # query subcommand
    p_query = sub.add_parser("query", help="Cross-module query via /rest/query/json")
    p_query.add_argument("document", help="Primary document/module name")
    p_query.add_argument("--filter", help="KonFilter as JSON string")
    p_query.add_argument("--fields", help="Comma-separated field names to return")
    p_query.add_argument(
        "--sort", help='Sort: JSON array or shorthand "field:asc,field2:desc"'
    )
    p_query.add_argument(
        "--limit", type=int, default=1000, help="Max records (default: 1000)"
    )
    p_query.add_argument("--start", type=int, default=0, help="Offset/skip (default: 0)")
    p_query.add_argument("--relations", help="Relations array as JSON string")
    p_query.add_argument(
        "--include-meta",
        action="store_true",
        dest="include_meta",
        help="Request _meta line in NDJSON response",
    )
    p_query.add_argument(
        "--no-total",
        action="store_false",
        dest="include_total",
        help="Skip total count calculation",
    )

    # sql subcommand
    p_sql = sub.add_parser("sql", help="SQL query via /rest/query/sql")
    p_sql.add_argument("sql", help="SQL SELECT statement")
    p_sql.add_argument(
        "--include-meta",
        action="store_true",
        dest="include_meta",
        help="Request _meta line in NDJSON response",
    )
    p_sql.add_argument(
        "--no-total",
        action="store_false",
        dest="include_total",
        help="Skip total count calculation",
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

    if args.command == "find":
        cmd_find(host, token, args)
    elif args.command == "query":
        cmd_query(host, token, args)
    elif args.command == "sql":
        cmd_sql(host, token, args)


if __name__ == "__main__":
    main()
