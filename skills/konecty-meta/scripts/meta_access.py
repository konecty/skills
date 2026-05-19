#!/usr/bin/env python3
"""Konecty Meta Access: manage access profile metadata. Stdlib only."""
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
    result = _api(host, token, "GET", f"/{args.document}/access/{args.name}")
    print(json.dumps(result.get("data", result), indent=2, ensure_ascii=False))


def cmd_permissions(args):
    host, token = _creds(args)
    result = _api(host, token, "GET", f"/{args.document}/access/{args.name}")
    data = result.get("data", {})
    defaults = data.get("fieldDefaults", {})
    fields = data.get("fields", {})
    doc_flags = {k: data.get(k) for k in ("isReadable", "isCreatable", "isUpdatable", "isDeletable")}

    print("Document-level flags:")
    for k, v in doc_flags.items():
        print(f"  {k}: {v}")
    print(f"\nField defaults:")
    for k, v in defaults.items():
        print(f"  {k}: {v}")
    print(f"\nField overrides ({len(fields)}):")
    for fname, perms in sorted(fields.items()):
        parts = []
        for op in ("CREATE", "READ", "UPDATE", "DELETE"):
            if op in perms:
                allow = perms[op].get("allow", "?")
                has_cond = "condition" in perms[op]
                parts.append(f"{op}={'allow' if allow else 'deny'}{'(cond)' if has_cond else ''}")
        print(f"  {fname}: {', '.join(parts)}")


def cmd_set_field(args):
    host, token = _creds(args)
    result = _api(host, token, "GET", f"/{args.document}/access/{args.name}")
    doc = result.get("data", {})
    fields = doc.setdefault("fields", {})
    field = fields.setdefault(args.field, {})
    for op, val in [("CREATE", args.create), ("READ", args.read), ("UPDATE", args.update), ("DELETE", args.delete)]:
        if val is not None:
            field[op] = {"allow": val.lower() == "true"}
    doc["fields"] = fields
    _api(host, token, "PUT", f"/{args.document}/access/{args.name}", doc)
    print(f"Field {args.field} permissions updated in {args.document}:access:{args.name}")


def cmd_set_flag(args):
    host, token = _creds(args)
    result = _api(host, token, "GET", f"/{args.document}/access/{args.name}")
    doc = result.get("data", {})
    for flag in ("isReadable", "isCreatable", "isUpdatable", "isDeletable"):
        val = getattr(args, flag, None)
        if val is not None:
            doc[flag] = val.lower() == "true"
    _api(host, token, "PUT", f"/{args.document}/access/{args.name}", doc)
    print(f"Flags updated for {args.document}:access:{args.name}")


def cmd_upsert(args):
    host, token = _creds(args)
    with open(args.file, "r", encoding="utf-8") as f: doc = json.load(f)
    _api(host, token, "PUT", f"/{args.document}/access/{args.name}", doc)
    print(f"Access {args.document}:access:{args.name} upserted")


def main():
    parser = argparse.ArgumentParser(description="Konecty Meta Access")
    parser.add_argument("--host", default=""); parser.add_argument("--token", default="")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fn in [("show", cmd_show), ("permissions", cmd_permissions)]:
        p = sub.add_parser(name); p.add_argument("document"); p.add_argument("name"); p.set_defaults(func=fn)
    p = sub.add_parser("set-field"); p.add_argument("document"); p.add_argument("name"); p.add_argument("field")
    p.add_argument("--create"); p.add_argument("--read"); p.add_argument("--update"); p.add_argument("--delete"); p.set_defaults(func=cmd_set_field)
    p = sub.add_parser("set-flag"); p.add_argument("document"); p.add_argument("name")
    p.add_argument("--isReadable"); p.add_argument("--isCreatable"); p.add_argument("--isUpdatable"); p.add_argument("--isDeletable"); p.set_defaults(func=cmd_set_flag)
    p = sub.add_parser("upsert"); p.add_argument("document"); p.add_argument("name"); p.add_argument("--file", required=True); p.set_defaults(func=cmd_upsert)
    args = parser.parse_args(); args.func(args)


if __name__ == "__main__": main()
