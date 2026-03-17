#!/usr/bin/env python3
"""
Konecty Meta Read: list meta documents, get specific metas, list types, diff.
Credentials loaded from ~/.konecty/.env (KONECTY_URL + KONECTY_TOKEN).
Stdlib only: urllib, json, os, sys, argparse.
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
        section = "default"
        if section in config:
            if not url:
                url = config[section].get("host", "")
            if not token:
                token = config[section].get("authid", "")

    return url.rstrip("/"), token


def _api_get(host: str, token: str, path: str) -> dict[str, Any]:
    url = f"{host}{API_PREFIX}{path}"
    req = urllib.request.Request(url, headers={"Authorization": token})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args: argparse.Namespace) -> None:
    host, token = args.host or "", args.token or ""
    if not host or not token:
        h, t = _load_credentials()
        host = host or h
        token = token or t

    if not host or not token:
        print("Missing credentials. Run konecty-session first.", file=sys.stderr)
        sys.exit(1)

    result = _api_get(host, token, "/")
    if not result.get("success"):
        print(json.dumps(result, indent=2))
        sys.exit(1)

    docs = result["data"]
    fmt = args.format

    if fmt == "json":
        print(json.dumps(docs, indent=2, ensure_ascii=False))
    else:
        print(f"{'_id':<30} {'type':<12} {'label'}")
        print("-" * 70)
        for doc in sorted(docs, key=lambda d: d.get("_id", "")):
            label = doc.get("label", {})
            lbl = label.get("pt_BR", label.get("en", ""))
            print(f"{doc['_id']:<30} {doc.get('type', ''):<12} {lbl}")


def cmd_get(args: argparse.Namespace) -> None:
    host, token = args.host or "", args.token or ""
    if not host or not token:
        h, t = _load_credentials()
        host = host or h
        token = token or t

    if not host or not token:
        print("Missing credentials. Run konecty-session first.", file=sys.stderr)
        sys.exit(1)

    document = args.document

    if args.type and args.name:
        path = f"/{document}/{args.type}/{args.name}"
    else:
        path = f"/{document}"

    result = _api_get(host, token, path)
    if not result.get("success"):
        print(json.dumps(result, indent=2))
        sys.exit(1)

    print(json.dumps(result["data"], indent=2, ensure_ascii=False))


def cmd_hook(args: argparse.Namespace) -> None:
    host, token = args.host or "", args.token or ""
    if not host or not token:
        h, t = _load_credentials()
        host = host or h
        token = token or t

    if not host or not token:
        print("Missing credentials. Run konecty-session first.", file=sys.stderr)
        sys.exit(1)

    path = f"/{args.document}/hook/{args.hook_name}"
    result = _api_get(host, token, path)
    if not result.get("success"):
        print(json.dumps(result, indent=2))
        sys.exit(1)

    data = result["data"]
    value = data.get("value", "")

    if isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False))


def cmd_types(args: argparse.Namespace) -> None:
    host, token = args.host or "", args.token or ""
    if not host or not token:
        h, t = _load_credentials()
        host = host or h
        token = token or t

    if not host or not token:
        print("Missing credentials. Run konecty-session first.", file=sys.stderr)
        sys.exit(1)

    document = args.document
    result = _api_get(host, token, f"/{document}")
    if not result.get("success"):
        print(json.dumps(result, indent=2))
        sys.exit(1)

    metas = result["data"]
    types: dict[str, list[str]] = {}
    for meta in metas:
        t = meta.get("type", "unknown")
        types.setdefault(t, []).append(meta.get("_id", ""))

    for t in sorted(types.keys()):
        items = sorted(types[t])
        print(f"\n{t} ({len(items)}):")
        for item in items:
            print(f"  {item}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Konecty Meta Read")
    parser.add_argument("--host", default="", help="Konecty URL override")
    parser.add_argument("--token", default="", help="Auth token override")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List all document/composite metas")
    p_list.add_argument("--format", choices=["table", "json"], default="table")
    p_list.set_defaults(func=cmd_list)

    p_get = sub.add_parser("get", help="Get meta(s) for a document")
    p_get.add_argument("document", help="Document name (e.g. Contact)")
    p_get.add_argument("--type", help="Meta type (e.g. list, view, access)")
    p_get.add_argument("--name", help="Meta name (e.g. Default)")
    p_get.set_defaults(func=cmd_get)

    p_hook = sub.add_parser("hook", help="Get hook code/JSON for a document")
    p_hook.add_argument("document", help="Document name")
    p_hook.add_argument("hook_name", help="Hook name: scriptBeforeValidation, validationData, validationScript, scriptAfterSave")
    p_hook.set_defaults(func=cmd_hook)

    p_types = sub.add_parser("types", help="List meta types for a document")
    p_types.add_argument("document", help="Document name")
    p_types.set_defaults(func=cmd_types)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
