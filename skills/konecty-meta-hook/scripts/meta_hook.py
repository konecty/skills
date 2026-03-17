#!/usr/bin/env python3
"""Konecty Meta Hook: manage hook code for documents. Stdlib only."""
from __future__ import annotations

import argparse, json, os, sys, urllib.error, urllib.request
from typing import Any

CREDENTIALS_DIR = os.path.expanduser("~/.konecty")
ENV_FILE = os.path.join(CREDENTIALS_DIR, ".env")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials")
API_PREFIX = "/api/admin/meta"

VALID_HOOKS = ["scriptBeforeValidation", "validationData", "validationScript", "scriptAfterSave"]

SCAFFOLDS = {
    "scriptBeforeValidation": """var ret = {};
var original = extraData.original;
var req = extraData.request;

// TODO: Add computed field logic here

return ret;
""",
    "validationData": """{
  "original": {
    "document": "DOCUMENT_NAME",
    "fields": "_id",
    "filter": {
      "match": "and",
      "conditions": [
        { "term": "_id", "operator": "equals", "value": "$this._id" }
      ]
    }
  }
}
""",
    "validationScript": """// extraData contains results from validationData queries

// TODO: Add validation logic here

return { success: true };
""",
    "scriptAfterSave": """// data may be an array for batch operations
// Models provides direct MongoDB collection access
// extraData.original contains pre-save state

if (data && data.length > 0) {
  var record = data[0];
  var original = extraData.original ? extraData.original[0] : null;

  // TODO: Add post-save logic here
}
""",
}


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
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r: return json.loads(r.read().decode())
    except urllib.error.HTTPError as e: print(f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}", file=sys.stderr); sys.exit(1)


def cmd_list(args):
    host, token = _creds(args)
    result = _api(host, token, "GET", f"/{args.document}/document/{args.document}")
    data = result.get("data", {})
    found = False
    for hook in VALID_HOOKS:
        val = data.get(hook)
        if val is not None:
            if isinstance(val, str):
                lines = val.count("\n") + 1
                print(f"  {hook}: JS ({lines} lines)")
            else:
                print(f"  {hook}: JSON")
            found = True
    if not found:
        print(f"No hooks defined for {args.document}")


def cmd_show(args):
    host, token = _creds(args)
    if args.hook_name not in VALID_HOOKS:
        print(f"Invalid hook: {args.hook_name}. Valid: {', '.join(VALID_HOOKS)}", file=sys.stderr)
        sys.exit(1)
    result = _api(host, token, "GET", f"/{args.document}/hook/{args.hook_name}")
    value = result.get("data", {}).get("value", "")
    if isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False))


def cmd_upsert(args):
    host, token = _creds(args)
    if args.hook_name not in VALID_HOOKS:
        print(f"Invalid hook: {args.hook_name}. Valid: {', '.join(VALID_HOOKS)}", file=sys.stderr)
        sys.exit(1)

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    elif args.code:
        content = args.code
    else:
        print("Either --file or --code is required.", file=sys.stderr)
        sys.exit(1)

    if args.hook_name == "validationData":
        try:
            body = {"value": json.loads(content)}
        except json.JSONDecodeError:
            print("validationData must be valid JSON.", file=sys.stderr)
            sys.exit(1)
    else:
        body = {"code": content}

    _api(host, token, "PUT", f"/{args.document}/hook/{args.hook_name}", body)
    print(f"Hook {args.hook_name} updated for {args.document}")


def cmd_delete(args):
    host, token = _creds(args)
    if args.hook_name not in VALID_HOOKS:
        print(f"Invalid hook: {args.hook_name}. Valid: {', '.join(VALID_HOOKS)}", file=sys.stderr)
        sys.exit(1)
    _api(host, token, "DELETE", f"/{args.document}/hook/{args.hook_name}")
    print(f"Hook {args.hook_name} deleted from {args.document}")


def cmd_scaffold(args):
    if args.hook_name not in VALID_HOOKS:
        print(f"Invalid hook: {args.hook_name}. Valid: {', '.join(VALID_HOOKS)}", file=sys.stderr)
        sys.exit(1)
    print(SCAFFOLDS[args.hook_name])


def cmd_validate(args):
    if args.hook_name not in VALID_HOOKS:
        print(f"Invalid hook: {args.hook_name}. Valid: {', '.join(VALID_HOOKS)}", file=sys.stderr)
        sys.exit(1)

    with open(args.file, "r", encoding="utf-8") as f:
        content = f.read()

    errors: list[str] = []

    if args.hook_name == "validationData":
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON: {e}")
    else:
        if "require(" in content:
            errors.append("require() is not available in hooks (VM sandbox)")
        if "import " in content and "from " in content:
            errors.append("ES module imports are not available in hooks (VM sandbox)")

        if args.hook_name == "scriptBeforeValidation":
            if "return " not in content:
                errors.append("scriptBeforeValidation should return an object (missing return statement)")
        elif args.hook_name == "validationScript":
            if "success" not in content:
                errors.append("validationScript should return { success: boolean } (missing 'success' in code)")
        elif args.hook_name == "scriptAfterSave":
            if "emails.push" in content:
                errors.append("emails.push() is not available in scriptAfterSave (use scriptBeforeValidation)")

    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("OK: No issues found")


def main():
    parser = argparse.ArgumentParser(description="Konecty Meta Hook")
    parser.add_argument("--host", default=""); parser.add_argument("--token", default="")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list"); p.add_argument("document"); p.set_defaults(func=cmd_list)
    p = sub.add_parser("show"); p.add_argument("document"); p.add_argument("hook_name"); p.set_defaults(func=cmd_show)

    p = sub.add_parser("upsert"); p.add_argument("document"); p.add_argument("hook_name")
    p.add_argument("--file"); p.add_argument("--code"); p.set_defaults(func=cmd_upsert)

    p = sub.add_parser("delete"); p.add_argument("document"); p.add_argument("hook_name"); p.set_defaults(func=cmd_delete)
    p = sub.add_parser("scaffold"); p.add_argument("hook_name"); p.set_defaults(func=cmd_scaffold)

    p = sub.add_parser("validate"); p.add_argument("hook_name"); p.add_argument("--file", required=True); p.set_defaults(func=cmd_validate)

    args = parser.parse_args(); args.func(args)


if __name__ == "__main__": main()
