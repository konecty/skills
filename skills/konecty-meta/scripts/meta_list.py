#!/usr/bin/env python3
"""Konecty Meta List: manage list view metadata. Stdlib only."""
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
    headers = {"Authorization": token}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r: return json.loads(r.read().decode())
    except urllib.error.HTTPError as e: print(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}", file=sys.stderr); sys.exit(1)


def cmd_show(args):
    host, token = _creds(args)
    result = _api(host, token, "GET", f"/{args.document}/list/{args.name}")
    print(json.dumps(result.get("data", result), indent=2, ensure_ascii=False))


def cmd_columns(args):
    host, token = _creds(args)
    result = _api(host, token, "GET", f"/{args.document}/list/{args.name}")
    cols = result.get("data", {}).get("columns", {})
    print(f"{'name':<25} {'linkField':<25} {'visible':<10} {'sort':<8} {'minWidth'}")
    print("-" * 80)
    for name, col in sorted(cols.items(), key=lambda x: x[1].get("sort", 999)):
        print(f"{name:<25} {col.get('linkField',''):<25} {str(col.get('visible','')):<10} {str(col.get('sort','')):<8} {col.get('minWidth','')}")


def cmd_add_column(args):
    host, token = _creds(args)
    result = _api(host, token, "GET", f"/{args.document}/list/{args.name}")
    doc = result.get("data", {})
    cols = doc.get("columns", {})
    if args.field in cols: print(f"Column {args.field} already exists.", file=sys.stderr); sys.exit(1)
    col: dict[str, Any] = {"name": args.field, "linkField": args.field, "visible": args.visible}
    if args.sort is not None: col["sort"] = args.sort
    if args.min_width is not None: col["minWidth"] = args.min_width
    cols[args.field] = col; doc["columns"] = cols
    _api(host, token, "PUT", f"/{args.document}/list/{args.name}", doc)
    print(f"Column {args.field} added to {args.document}:list:{args.name}")


def cmd_remove_column(args):
    host, token = _creds(args)
    result = _api(host, token, "GET", f"/{args.document}/list/{args.name}")
    doc = result.get("data", {})
    cols = doc.get("columns", {})
    if args.field not in cols: print(f"Column {args.field} not found.", file=sys.stderr); sys.exit(1)
    del cols[args.field]; doc["columns"] = cols
    _api(host, token, "PUT", f"/{args.document}/list/{args.name}", doc)
    print(f"Column {args.field} removed")


def cmd_upsert(args):
    host, token = _creds(args)
    with open(args.file, "r", encoding="utf-8") as f: doc = json.load(f)
    _api(host, token, "PUT", f"/{args.document}/list/{args.name}", doc)
    print(f"List {args.document}:list:{args.name} upserted")


def main():
    parser = argparse.ArgumentParser(description="Konecty Meta List")
    parser.add_argument("--host", default=""); parser.add_argument("--token", default="")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in [("show", cmd_show), ("columns", cmd_columns)]:
        p = sub.add_parser(name); p.add_argument("document"); p.add_argument("name"); p.set_defaults(func=fn)
    p = sub.add_parser("add-column"); p.add_argument("document"); p.add_argument("name"); p.add_argument("field")
    p.add_argument("--visible", action="store_true", default=True); p.add_argument("--sort", type=int)
    p.add_argument("--min-width", type=int); p.set_defaults(func=cmd_add_column)
    p = sub.add_parser("remove-column"); p.add_argument("document"); p.add_argument("name"); p.add_argument("field"); p.set_defaults(func=cmd_remove_column)
    p = sub.add_parser("upsert"); p.add_argument("document"); p.add_argument("name"); p.add_argument("--file", required=True); p.set_defaults(func=cmd_upsert)
    args = parser.parse_args(); args.func(args)


if __name__ == "__main__": main()
