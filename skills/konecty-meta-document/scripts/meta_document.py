#!/usr/bin/env python3
"""
Konecty Meta Document: manage document metadata definitions.
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

CREDENTIALS_DIR = os.path.expanduser("~/.konecty")
ENV_FILE = os.path.join(CREDENTIALS_DIR, ".env")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials")
API_PREFIX = "/api/admin/meta"


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
        import configparser
        config = configparser.ConfigParser()
        config.read(CREDENTIALS_FILE, encoding="utf-8")
        if "default" in config:
            url = url or config["default"].get("host", "")
            token = token or config["default"].get("authid", "")
    return url.rstrip("/"), token


def _get_creds(args: argparse.Namespace) -> tuple[str, str]:
    host, token = args.host or "", args.token or ""
    if not host or not token:
        h, t = _load_credentials()
        host = host or h
        token = token or t
    if not host or not token:
        print("Missing credentials. Run konecty-session first.", file=sys.stderr)
        sys.exit(1)
    return host, token


def _api_request(host: str, token: str, method: str, path: str, body: Any = None) -> dict:
    url = f"{host}{API_PREFIX}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": token,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body_text}", file=sys.stderr)
        sys.exit(1)


def cmd_show(args: argparse.Namespace) -> None:
    host, token = _get_creds(args)
    result = _api_request(host, token, "GET", f"/{args.document}/document/{args.document}")
    print(json.dumps(result.get("data", result), indent=2, ensure_ascii=False))


def cmd_fields(args: argparse.Namespace) -> None:
    host, token = _get_creds(args)
    result = _api_request(host, token, "GET", f"/{args.document}/document/{args.document}")
    data = result.get("data", {})
    fields = data.get("fields", {})

    if args.format == "json":
        print(json.dumps(fields, indent=2, ensure_ascii=False))
        return

    print(f"{'name':<30} {'type':<15} {'required':<10} {'label'}")
    print("-" * 85)
    for name, field in sorted(fields.items()):
        label = field.get("label", {})
        lbl = label.get("pt_BR", label.get("en", ""))
        req = "yes" if field.get("isRequired") else ""
        print(f"{name:<30} {field.get('type', ''):<15} {req:<10} {lbl}")


def cmd_add_field(args: argparse.Namespace) -> None:
    host, token = _get_creds(args)
    result = _api_request(host, token, "GET", f"/{args.document}/document/{args.document}")
    doc = result.get("data", {})

    field_def: dict[str, Any] = {"type": args.type, "name": args.field_name}
    if args.label_en or args.label_pt:
        field_def["label"] = {}
        if args.label_en:
            field_def["label"]["en"] = args.label_en
        if args.label_pt:
            field_def["label"]["pt_BR"] = args.label_pt
    if args.required:
        field_def["isRequired"] = True

    fields = doc.get("fields", {})
    if args.field_name in fields:
        print(f"Field {args.field_name} already exists. Use update-field instead.", file=sys.stderr)
        sys.exit(1)

    fields[args.field_name] = field_def
    doc["fields"] = fields

    _api_request(host, token, "PUT", f"/{args.document}/document/{args.document}", doc)
    print(f"Field {args.field_name} added to {args.document}")


def cmd_remove_field(args: argparse.Namespace) -> None:
    host, token = _get_creds(args)
    result = _api_request(host, token, "GET", f"/{args.document}/document/{args.document}")
    doc = result.get("data", {})

    fields = doc.get("fields", {})
    if args.field_name not in fields:
        print(f"Field {args.field_name} not found in {args.document}.", file=sys.stderr)
        sys.exit(1)

    del fields[args.field_name]
    doc["fields"] = fields

    _api_request(host, token, "PUT", f"/{args.document}/document/{args.document}", doc)
    print(f"Field {args.field_name} removed from {args.document}")


def cmd_update_field(args: argparse.Namespace) -> None:
    host, token = _get_creds(args)
    result = _api_request(host, token, "GET", f"/{args.document}/document/{args.document}")
    doc = result.get("data", {})

    fields = doc.get("fields", {})
    if args.field_name not in fields:
        print(f"Field {args.field_name} not found in {args.document}.", file=sys.stderr)
        sys.exit(1)

    field = fields[args.field_name]
    for kv in args.set:
        key, _, value = kv.partition("=")
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        elif value.isdigit():
            value = int(value)

        parts = key.split(".")
        target = field
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value

    doc["fields"] = fields
    _api_request(host, token, "PUT", f"/{args.document}/document/{args.document}", doc)
    print(f"Field {args.field_name} updated in {args.document}")


def cmd_upsert(args: argparse.Namespace) -> None:
    host, token = _get_creds(args)
    with open(args.file, "r", encoding="utf-8") as f:
        doc = json.load(f)
    _api_request(host, token, "PUT", f"/{args.document}/document/{args.document}", doc)
    print(f"Document {args.document} upserted")


def cmd_events(args: argparse.Namespace) -> None:
    host, token = _get_creds(args)
    result = _api_request(host, token, "GET", f"/{args.document}/document/{args.document}")
    data = result.get("data", {})
    events = data.get("events", [])
    if not events:
        print(f"No events defined for {args.document}")
        return
    print(json.dumps(events, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Konecty Meta Document")
    parser.add_argument("--host", default="")
    parser.add_argument("--token", default="")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("show")
    p.add_argument("document")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("fields")
    p.add_argument("document")
    p.add_argument("--format", choices=["table", "json"], default="table")
    p.set_defaults(func=cmd_fields)

    p = sub.add_parser("add-field")
    p.add_argument("document")
    p.add_argument("field_name")
    p.add_argument("--type", required=True)
    p.add_argument("--label-en", default="")
    p.add_argument("--label-pt", default="")
    p.add_argument("--required", action="store_true")
    p.set_defaults(func=cmd_add_field)

    p = sub.add_parser("remove-field")
    p.add_argument("document")
    p.add_argument("field_name")
    p.set_defaults(func=cmd_remove_field)

    p = sub.add_parser("update-field")
    p.add_argument("document")
    p.add_argument("field_name")
    p.add_argument("--set", nargs="+", required=True, help="key=value pairs (dot notation for nested)")
    p.set_defaults(func=cmd_update_field)

    p = sub.add_parser("upsert")
    p.add_argument("document")
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_upsert)

    p = sub.add_parser("events")
    p.add_argument("document")
    p.set_defaults(func=cmd_events)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
