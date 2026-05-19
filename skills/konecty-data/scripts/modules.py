#!/usr/bin/env python3
"""
Konecty Modules: list accessible modules, show fields, search.
Credentials loaded from ~/.konecty/.env (KONECTY_URL + KONECTY_TOKEN).
Stdlib only: urllib, json, difflib, configparser.
"""
from __future__ import annotations

import argparse
import configparser
import difflib
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

CREDENTIALS_DIR = os.path.expanduser("~/.konecty")
ENV_FILE = os.path.join(CREDENTIALS_DIR, ".env")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials")
FUZZY_THRESHOLD = 0.4


def _load_credentials() -> tuple[str, str]:
    """Load KONECTY_URL and KONECTY_TOKEN from ~/.konecty/.env, then env vars, then credentials ini."""
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


def _request(host: str, token: str, path: str) -> Any:
    url = f"{host}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": token,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
            msg = body.get("errors") or body.get("message") or str(body)
        except Exception:
            msg = e.reason
        raise SystemExit(f"HTTP {e.code}: {msg}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Connection error: {e.reason}")


def _get_modules(host: str, token: str, lang: str) -> list[dict]:
    result = _request(host, token, f"/rest/query/explorer/modules?lang={lang}")
    if not result.get("success"):
        errors = result.get("errors", [{"message": "Unknown error"}])
        raise SystemExit("API error: " + "; ".join(e.get("message", str(e)) for e in errors))
    return result.get("data", {}).get("modules", [])


def _fuzzy_find(modules: list[dict], query: str) -> tuple[dict | None, list[dict]]:
    """Return (best_match, candidates) — best_match is None if ambiguous."""
    q = query.lower().strip()

    # 1. exact match on document name (case-insensitive)
    for m in modules:
        if m["document"].lower() == q:
            return m, [m]

    # 2. exact match on label (case-insensitive)
    for m in modules:
        if m["label"].lower() == q:
            return m, [m]

    # 3. substring match on document or label
    substr_matches = [m for m in modules if q in m["document"].lower() or q in m["label"].lower()]
    if len(substr_matches) == 1:
        return substr_matches[0], substr_matches
    if len(substr_matches) > 1:
        return None, substr_matches

    # 4. fuzzy match via difflib on combined key
    keys = [f"{m['document'].lower()} {m['label'].lower()}" for m in modules]
    scores = [(difflib.SequenceMatcher(None, q, k).ratio(), i) for i, k in enumerate(keys)]
    scores.sort(reverse=True)
    top = [(s, i) for s, i in scores if s >= FUZZY_THRESHOLD]
    if not top:
        return None, []
    if top[0][0] >= 0.75:
        return modules[top[0][1]], [modules[top[0][1]]]
    candidates = [modules[i] for _, i in top[:5]]
    return None, candidates


def cmd_list(host: str, token: str, lang: str) -> None:
    modules = _get_modules(host, token, lang)
    if not modules:
        print("No accessible modules found.")
        return
    col_w = max(len(m["document"]) for m in modules)
    label_w = max(len(m["label"]) for m in modules)
    print(f"{'Document':<{col_w}}  {'Label':<{label_w}}  Fields  Lookups")
    print("-" * (col_w + label_w + 20))
    for m in sorted(modules, key=lambda x: x["label"].lower()):
        fields = len(m.get("fields", []))
        rev = len(m.get("reverseLookups", []))
        print(f"{m['document']:<{col_w}}  {m['label']:<{label_w}}  {fields:>6}  {rev:>7}")
    print(f"\nTotal: {len(modules)} modules")


def cmd_fields(host: str, token: str, lang: str, query: str) -> None:
    modules = _get_modules(host, token, lang)
    best, candidates = _fuzzy_find(modules, query)

    if best is None and not candidates:
        print(f"No module found matching '{query}'.")
        sys.exit(1)

    if best is None:
        print(f"Multiple modules match '{query}'. Candidates:")
        for c in candidates:
            print(f"  {c['document']}  ({c['label']})")
        print("\nRe-run with the exact document name.")
        sys.exit(1)

    m = best
    fields = m.get("fields", [])
    rev = m.get("reverseLookups", [])

    print(f"\nModule: {m['document']}  ({m['label']})")
    print(f"Fields: {len(fields)}   Reverse lookups: {len(rev)}\n")

    if fields:
        nw = max(len(f["name"]) for f in fields)
        tw = max(len(f["type"]) for f in fields)
        lw = max(len(f["label"]) for f in fields)
        print(f"  {'Name':<{nw}}  {'Type':<{tw}}  {'Label':<{lw}}  Extra")
        print("  " + "-" * (nw + tw + lw + 16))
        for f in fields:
            extra = ""
            if f.get("document"):
                extra = f"→ {f['document']}"
                if f.get("descriptionFields"):
                    extra += f" ({', '.join(f['descriptionFields'])})"
            elif f.get("options"):
                opts = list(f["options"].keys())
                extra = "options: " + ", ".join(opts[:5]) + ("…" if len(opts) > 5 else "")
            print(f"  {f['name']:<{nw}}  {f['type']:<{tw}}  {f['label']:<{lw}}  {extra}")

    if rev:
        print(f"\nReverse lookups (modules that reference {m['document']}):")
        for r in rev:
            print(f"  {r['document']}.{r['lookup']}  ({r['label']})")


def cmd_search(host: str, token: str, lang: str, keyword: str) -> None:
    modules = _get_modules(host, token, lang)
    kw = keyword.lower()
    results = [m for m in modules if kw in m["document"].lower() or kw in m["label"].lower()]
    if not results:
        print(f"No modules found matching '{keyword}'.")
        return
    print(f"Modules matching '{keyword}':")
    for m in sorted(results, key=lambda x: x["label"].lower()):
        print(f"  {m['document']}  ({m['label']})  — {len(m.get('fields', []))} fields")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Konecty module explorer. Credentials from ~/.konecty/.env."
    )
    parser.add_argument("--host", default="", help="Override KONECTY_URL")
    parser.add_argument("--token", default="", help="Override KONECTY_TOKEN")
    parser.add_argument("--lang", default="pt_BR", help="Label language (default: pt_BR)")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all accessible modules")

    p_fields = sub.add_parser("fields", help="Show fields for a module (fuzzy name match)")
    p_fields.add_argument("module", help="Module name or label (fuzzy matched)")

    p_search = sub.add_parser("search", help="Filter modules by keyword")
    p_search.add_argument("keyword", help="Keyword to search in module name/label")

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

    if args.command == "list":
        cmd_list(host, token, args.lang)
    elif args.command == "fields":
        cmd_fields(host, token, args.lang, args.module)
    elif args.command == "search":
        cmd_search(host, token, args.lang, args.keyword)


if __name__ == "__main__":
    main()
