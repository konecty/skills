#!/usr/bin/env python3
"""Konecty Meta Namespace: manage global Namespace configuration. Stdlib only."""
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


def _get_namespace(host: str, token: str) -> dict:
    result = _api(host, token, "GET", "/Namespace/namespace/Namespace")
    return result.get("data", {})


def _put_namespace(host: str, token: str, doc: dict) -> dict:
    return _api(host, token, "PUT", "/Namespace/namespace/Namespace", doc)


def cmd_show(args):
    host, token = _creds(args)
    ns = _get_namespace(host, token)
    print(json.dumps(ns, indent=2, ensure_ascii=False))


def cmd_email_servers(args):
    host, token = _creds(args)
    ns = _get_namespace(host, token)
    servers = ns.get("emailServers", {})
    if not servers:
        print("No email servers configured.")
        return
    for name, cfg in sorted(servers.items()):
        host_val = cfg.get("host", cfg.get("service", "?"))
        port = cfg.get("port", "")
        user = cfg.get("auth", {}).get("user", "?")
        secure = cfg.get("secure", False)
        print(f"  {name}: {host_val}:{port} user={user} secure={secure}")


def cmd_set_email_server(args):
    host, token = _creds(args)
    ns = _get_namespace(host, token)
    servers = ns.setdefault("emailServers", {})
    server: dict[str, Any] = {"host": args.smtp_host, "port": args.port}
    if args.user and args.password:
        server["auth"] = {"user": args.user, "pass": args.password}
    if args.secure:
        server["secure"] = True
    servers[args.server_name] = server
    ns["emailServers"] = servers
    _put_namespace(host, token, ns)
    print(f"Email server {args.server_name} configured")


def cmd_queue_config(args):
    host, token = _creds(args)
    ns = _get_namespace(host, token)
    qc = ns.get("QueueConfig")
    if not qc:
        print("No QueueConfig configured.")
        return
    print(json.dumps(qc, indent=2, ensure_ascii=False))


def cmd_add_queue(args):
    host, token = _creds(args)
    ns = _get_namespace(host, token)
    qc = ns.setdefault("QueueConfig", {})
    resources = qc.setdefault("resources", {})
    resource = resources.get(args.resource)
    if not resource:
        print(f"Resource {args.resource} not found. Available: {list(resources.keys())}", file=sys.stderr)
        sys.exit(1)
    queues = resource.setdefault("queues", [])
    if any(q.get("name") == args.queue_name for q in queues):
        print(f"Queue {args.queue_name} already exists in {args.resource}.")
        return
    queues.append({"name": args.queue_name})
    _put_namespace(host, token, ns)
    print(f"Queue {args.queue_name} added to {args.resource}")


def cmd_set_webhook(args):
    host, token = _creds(args)
    ns = _get_namespace(host, token)
    if args.event not in ("onCreate", "onUpdate", "onDelete"):
        print(f"Invalid event: {args.event}. Use onCreate, onUpdate, or onDelete.", file=sys.stderr)
        sys.exit(1)
    ns[args.event] = args.url
    _put_namespace(host, token, ns)
    print(f"Webhook {args.event} set to {args.url}")


def cmd_upsert(args):
    host, token = _creds(args)
    with open(args.file, "r", encoding="utf-8") as f: doc = json.load(f)
    _put_namespace(host, token, doc)
    print("Namespace upserted")


def main():
    parser = argparse.ArgumentParser(description="Konecty Meta Namespace")
    parser.add_argument("--host", default=""); parser.add_argument("--token", default="")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("show").set_defaults(func=cmd_show)
    sub.add_parser("email-servers").set_defaults(func=cmd_email_servers)

    p = sub.add_parser("set-email-server"); p.add_argument("server_name")
    p.add_argument("--host", dest="smtp_host", required=True); p.add_argument("--port", type=int, required=True)
    p.add_argument("--user", default=""); p.add_argument("--pass", dest="password", default="")
    p.add_argument("--secure", action="store_true"); p.set_defaults(func=cmd_set_email_server)

    sub.add_parser("queue-config").set_defaults(func=cmd_queue_config)

    p = sub.add_parser("add-queue"); p.add_argument("resource"); p.add_argument("queue_name"); p.set_defaults(func=cmd_add_queue)

    p = sub.add_parser("set-webhook"); p.add_argument("event"); p.add_argument("url"); p.set_defaults(func=cmd_set_webhook)

    p = sub.add_parser("upsert"); p.add_argument("--file", required=True); p.set_defaults(func=cmd_upsert)

    args = parser.parse_args(); args.func(args)


if __name__ == "__main__": main()
