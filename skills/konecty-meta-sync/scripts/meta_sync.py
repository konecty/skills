#!/usr/bin/env python3
"""
Konecty Meta Sync: synchronize metadata between repo and database.
Terraform-style plan/apply workflow. Stdlib only.
"""
from __future__ import annotations

import argparse, json, os, sys, urllib.error, urllib.request
from pathlib import Path
from typing import Any

CREDENTIALS_DIR = os.path.expanduser("~/.konecty")
ENV_FILE = os.path.join(CREDENTIALS_DIR, ".env")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials")
API_PREFIX = "/api/admin/meta"

HOOK_FIELDS = {"scriptBeforeValidation": ".js", "validationScript": ".js", "scriptAfterSave": ".js", "validationData": ".json"}
META_SUBDIRS = {"list", "view", "access", "pivot", "card"}


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


def _creds(args):
    host, token = args.host or "", args.token or ""
    h, t = _load_credentials()
    host = host or h; token = token or t
    return host, token


def _api(host, token, method, path, body=None):
    url = f"{host}{API_PREFIX}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r: return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"}


def _read_repo_metas(repo_path: str) -> dict[str, Any]:
    """Read all metas from a repo directory. Returns {meta_id: meta_object}."""
    metas: dict[str, Any] = {}
    meta_dir = Path(repo_path) / "MetaObjects"
    if not meta_dir.exists():
        print(f"MetaObjects directory not found at {meta_dir}", file=sys.stderr)
        sys.exit(1)

    for doc_dir in sorted(meta_dir.iterdir()):
        if not doc_dir.is_dir():
            continue
        doc_name = doc_dir.name

        doc_file = doc_dir / "document.json"
        if doc_file.exists():
            with open(doc_file, "r", encoding="utf-8") as f:
                doc = json.load(f)
            if isinstance(doc, list):
                for item in doc:
                    metas[item.get("_id", doc_name)] = item
            else:
                hook_dir = doc_dir / "hook"
                if hook_dir.exists():
                    for hook_name, ext in HOOK_FIELDS.items():
                        hook_file = hook_dir / f"{hook_name}{ext}"
                        if hook_file.exists():
                            with open(hook_file, "r", encoding="utf-8") as f:
                                content = f.read()
                            if ext == ".json":
                                try:
                                    doc[hook_name] = json.loads(content)
                                except json.JSONDecodeError:
                                    doc[hook_name] = content
                            else:
                                doc[hook_name] = content

                metas[doc.get("_id", doc_name)] = doc

        for subdir_name in META_SUBDIRS:
            subdir = doc_dir / subdir_name
            if not subdir.exists():
                continue
            for meta_file in sorted(subdir.glob("*.json")):
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta_id = meta.get("_id", f"{doc_name}:{subdir_name}:{meta_file.stem}")
                metas[meta_id] = meta

    return metas


def _get_prod_meta(host: str, token: str, meta_id: str) -> dict | None:
    parts = meta_id.split(":")
    if len(parts) >= 3:
        doc, mtype, name = parts[0], parts[1], ":".join(parts[2:])
        result = _api(host, token, "GET", f"/{doc}/{mtype}/{name}")
    else:
        doc = meta_id
        result = _api(host, token, "GET", f"/{doc}/document/{doc}")
        if not result.get("success"):
            result = _api(host, token, "GET", f"/{doc}/namespace/{doc}")
    if result.get("success"):
        return result.get("data")
    return None


def _normalize(obj: Any) -> Any:
    """Normalize JSON for comparison: sort keys, strip None."""
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in sorted(obj.items()) if v is not None}
    if isinstance(obj, list):
        return [_normalize(i) for i in obj]
    return obj


def _compute_changes(repo_metas: dict, host: str, token: str) -> list[dict]:
    changes = []
    for meta_id, repo_meta in sorted(repo_metas.items()):
        prod_meta = _get_prod_meta(host, token, meta_id)
        repo_norm = json.dumps(_normalize(repo_meta), sort_keys=True)
        prod_norm = json.dumps(_normalize(prod_meta), sort_keys=True) if prod_meta else ""

        if prod_meta is None:
            changes.append({"action": "create", "meta_id": meta_id, "repo": repo_meta})
        elif repo_norm != prod_norm:
            changes.append({"action": "update", "meta_id": meta_id, "repo": repo_meta, "prod": prod_meta})
    return changes


def _apply_change(host: str, token: str, change: dict) -> bool:
    meta_id = change["meta_id"]
    meta = change["repo"]
    parts = meta_id.split(":")
    if len(parts) >= 3:
        doc, mtype, name = parts[0], parts[1], ":".join(parts[2:])
        result = _api(host, token, "PUT", f"/{doc}/{mtype}/{name}", meta)
    elif meta.get("type") == "namespace":
        result = _api(host, token, "PUT", "/Namespace/namespace/Namespace", meta)
    else:
        result = _api(host, token, "PUT", f"/{meta_id}/document/{meta_id}", meta)
    return result.get("success", False)


def cmd_plan(args):
    host, token = _creds(args)
    if args.direction_from == "repo" and args.direction_to == "prod":
        repo_metas = _read_repo_metas(args.repo)
        changes = _compute_changes(repo_metas, host, token)
    else:
        print("pull direction (prod → repo): use 'pull' command instead", file=sys.stderr)
        sys.exit(1)

    if not changes:
        print("No changes detected. Repo and production are in sync.")
        return

    creates = [c for c in changes if c["action"] == "create"]
    updates = [c for c in changes if c["action"] == "update"]

    print(f"\nPlan: {len(creates)} to create, {len(updates)} to update\n")
    for c in changes:
        icon = "+" if c["action"] == "create" else "~"
        print(f"  [{icon}] {c['meta_id']} ({c['action']})")


def cmd_apply(args):
    host, token = _creds(args)
    if args.direction_from != "repo" or args.direction_to != "prod":
        print("apply only supports --from repo --to prod", file=sys.stderr)
        sys.exit(1)

    repo_metas = _read_repo_metas(args.repo)
    changes = _compute_changes(repo_metas, host, token)

    if args.only:
        changes = [c for c in changes if c["meta_id"] in args.only]

    if not changes:
        print("No changes to apply.")
        return

    print(f"\n{len(changes)} change(s) to apply:\n")
    for c in changes:
        icon = "+" if c["action"] == "create" else "~"
        print(f"  [{icon}] {c['meta_id']} ({c['action']})")

    if not args.auto_approve:
        print()
        answer = input("Apply all changes? [y/N/select] ").strip().lower()
        if answer == "select":
            selected = []
            for c in changes:
                a = input(f"  Apply {c['meta_id']}? [y/N] ").strip().lower()
                if a == "y":
                    selected.append(c)
            changes = selected
        elif answer != "y":
            print("Aborted.")
            return

    applied = 0
    for c in changes:
        ok = _apply_change(host, token, c)
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {c['meta_id']}")
        if ok:
            applied += 1

    print(f"\nApplied {applied}/{len(changes)} changes.")

    if applied > 0:
        print("Reloading metadata...")
        _api(host, token, "POST", "/reload")
        print("Done.")


def cmd_diff(args):
    host, token = _creds(args)
    repo_metas = _read_repo_metas(args.repo)
    meta_id = args.meta_id

    if meta_id not in repo_metas:
        print(f"Meta {meta_id} not found in repo", file=sys.stderr)
        sys.exit(1)

    repo_meta = repo_metas[meta_id]
    prod_meta = _get_prod_meta(host, token, meta_id)

    repo_str = json.dumps(_normalize(repo_meta), indent=2, sort_keys=True, ensure_ascii=False)
    prod_str = json.dumps(_normalize(prod_meta), indent=2, sort_keys=True, ensure_ascii=False) if prod_meta else "(not in production)"

    import difflib
    diff = difflib.unified_diff(
        prod_str.splitlines(keepends=True),
        repo_str.splitlines(keepends=True),
        fromfile=f"prod:{meta_id}",
        tofile=f"repo:{meta_id}",
    )
    result = "".join(diff)
    if result:
        print(result)
    else:
        print(f"{meta_id}: no differences")


def cmd_pull(args):
    host, token = _creds(args)
    repo_path = Path(args.repo) / "MetaObjects"
    repo_path.mkdir(parents=True, exist_ok=True)

    if args.document:
        documents = [args.document]
    elif args.all:
        result = _api(host, token, "GET", "/")
        documents = [d["_id"] for d in result.get("data", [])]
    else:
        print("Specify --document or --all", file=sys.stderr)
        sys.exit(1)

    for doc_name in documents:
        doc_dir = repo_path / doc_name
        doc_dir.mkdir(exist_ok=True)

        doc_meta = _get_prod_meta(host, token, doc_name)
        if not doc_meta:
            continue

        hooks_to_extract: dict[str, Any] = {}
        for hook_name in HOOK_FIELDS:
            if hook_name in doc_meta:
                hooks_to_extract[hook_name] = doc_meta.pop(hook_name)

        with open(doc_dir / "document.json", "w", encoding="utf-8") as f:
            json.dump(doc_meta, f, indent="\t", ensure_ascii=False)
        print(f"  Pulled {doc_name}/document.json")

        if hooks_to_extract:
            hook_dir = doc_dir / "hook"
            hook_dir.mkdir(exist_ok=True)
            for hook_name, value in hooks_to_extract.items():
                ext = HOOK_FIELDS[hook_name]
                with open(hook_dir / f"{hook_name}{ext}", "w", encoding="utf-8") as f:
                    if ext == ".json":
                        json.dump(value, f, indent="\t", ensure_ascii=False)
                    else:
                        f.write(value)
                print(f"  Pulled {doc_name}/hook/{hook_name}{ext}")

        metas_result = _api(host, token, "GET", f"/{doc_name}")
        for meta in metas_result.get("data", []):
            mtype = meta.get("type", "")
            mname = meta.get("name", "Default")
            if mtype in META_SUBDIRS:
                full = _api(host, token, "GET", f"/{doc_name}/{mtype}/{mname}")
                if full.get("success"):
                    sub_dir = doc_dir / mtype
                    sub_dir.mkdir(exist_ok=True)
                    with open(sub_dir / f"{mname}.json", "w", encoding="utf-8") as f:
                        json.dump(full["data"], f, indent="\t", ensure_ascii=False)
                    print(f"  Pulled {doc_name}/{mtype}/{mname}.json")


def main():
    parser = argparse.ArgumentParser(description="Konecty Meta Sync")
    parser.add_argument("--host", default=""); parser.add_argument("--token", default="")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan")
    p.add_argument("--from", dest="direction_from", required=True, choices=["repo", "prod"])
    p.add_argument("--to", dest="direction_to", required=True, choices=["repo", "prod"])
    p.add_argument("--repo", required=True)
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("apply")
    p.add_argument("--from", dest="direction_from", required=True, choices=["repo", "prod"])
    p.add_argument("--to", dest="direction_to", required=True, choices=["repo", "prod"])
    p.add_argument("--repo", required=True)
    p.add_argument("--auto-approve", action="store_true")
    p.add_argument("--only", nargs="*")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("diff")
    p.add_argument("--repo", required=True)
    p.add_argument("--meta-id", required=True)
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("pull")
    p.add_argument("--repo", required=True)
    p.add_argument("--document")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_pull)

    args = parser.parse_args(); args.func(args)


if __name__ == "__main__": main()
