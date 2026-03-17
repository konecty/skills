#!/usr/bin/env python3
"""Konecty Meta Doctor: validate metadata integrity. Stdlib only."""
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


def _api(host, token, path):
    url = f"{host}{API_PREFIX}{path}"
    req = urllib.request.Request(url, headers={"Authorization": token})
    try:
        with urllib.request.urlopen(req) as r: return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}"}


def _get_all_metas(host: str, token: str, document: str | None = None) -> list[dict]:
    if document:
        result = _api(host, token, f"/{document}")
        return result.get("data", [])
    result = _api(host, token, "/")
    docs = result.get("data", [])
    all_metas = []
    for doc in docs:
        doc_result = _api(host, token, f"/{doc['_id']}")
        all_metas.extend(doc_result.get("data", []))
    return all_metas


def _get_doc_meta(host: str, token: str, doc_name: str) -> dict | None:
    result = _api(host, token, f"/{doc_name}/document/{doc_name}")
    if result.get("success"):
        return result.get("data")
    return None


def _get_namespace(host: str, token: str) -> dict | None:
    result = _api(host, token, "/Namespace/namespace/Namespace")
    if result.get("success"):
        return result.get("data")
    return None


class Issue:
    def __init__(self, severity: str, meta_id: str, message: str):
        self.severity = severity
        self.meta_id = meta_id
        self.message = message

    def to_dict(self):
        return {"severity": self.severity, "meta_id": self.meta_id, "message": self.message}


def check_document(host: str, token: str, doc_name: str, doc_meta: dict, all_doc_names: set[str]) -> list[Issue]:
    issues: list[Issue] = []
    fields = doc_meta.get("fields", {})

    for fname, field in fields.items():
        ftype = field.get("type", "")
        if ftype in ("lookup", "filter", "composite") and field.get("document"):
            target = field["document"]
            if target not in all_doc_names:
                issues.append(Issue("error", doc_name, f"Field '{fname}' references non-existent document '{target}'"))

        if field.get("inheritedFields"):
            for inh in field["inheritedFields"]:
                target_doc = field.get("document", "")
                if target_doc and target_doc not in all_doc_names:
                    issues.append(Issue("error", doc_name, f"Field '{fname}' inheritedField references non-existent document '{target_doc}'"))

        if not field.get("label"):
            issues.append(Issue("warning", doc_name, f"Field '{fname}' has no label"))

    events = doc_meta.get("events", [])
    for i, event in enumerate(events):
        ev = event.get("event", {})
        if ev.get("type") == "queue":
            resource = ev.get("resource", "")
            if not resource:
                issues.append(Issue("error", doc_name, f"Event #{i} queue event has no resource"))

    return issues


def check_list_meta(host: str, token: str, meta: dict, doc_fields: set[str]) -> list[Issue]:
    issues: list[Issue] = []
    meta_id = meta.get("_id", "?")
    columns = meta.get("columns", {})
    for cname, col in columns.items():
        link = col.get("linkField", "")
        base_field = link.split(".")[0] if "." in link else link
        if base_field and base_field not in doc_fields and not base_field.startswith("_"):
            issues.append(Issue("warning", meta_id, f"Column '{cname}' linkField '{link}' not found in document fields"))
    return issues


def check_access_meta(meta: dict, doc_fields: set[str]) -> list[Issue]:
    issues: list[Issue] = []
    meta_id = meta.get("_id", "?")
    fields = meta.get("fields", {})
    for fname in fields:
        if fname not in doc_fields and not fname.startswith("_"):
            issues.append(Issue("warning", meta_id, f"Access field override '{fname}' not found in document fields"))
    return issues


def check_queue_consistency(host: str, token: str) -> list[Issue]:
    issues: list[Issue] = []
    ns = _get_namespace(host, token)
    if not ns:
        issues.append(Issue("error", "Namespace", "Could not load Namespace"))
        return issues

    qc = ns.get("QueueConfig", {})
    resources = qc.get("resources", {})
    resource_queues: dict[str, set[str]] = {}
    for rname, resource in resources.items():
        resource_queues[rname] = {q.get("name", "") for q in resource.get("queues", [])}

    docs_result = _api(host, token, "/")
    docs = docs_result.get("data", [])
    for doc in docs:
        doc_meta = _get_doc_meta(host, token, doc["_id"])
        if not doc_meta:
            continue
        events = doc_meta.get("events", [])
        for i, event in enumerate(events):
            ev = event.get("event", {})
            if ev.get("type") != "queue":
                continue
            resource = ev.get("resource", "")
            queues = ev.get("queue", [])
            if isinstance(queues, str):
                queues = [queues]
            if resource not in resources:
                issues.append(Issue("error", doc["_id"], f"Event #{i} references non-existent resource '{resource}'"))
                continue
            for q in queues:
                if q not in resource_queues.get(resource, set()):
                    issues.append(Issue("error", doc["_id"], f"Event #{i} references queue '{q}' not in resource '{resource}'"))

    konsistent = qc.get("konsistent")
    if konsistent and len(konsistent) == 2:
        rname, qname = konsistent
        if rname not in resources:
            issues.append(Issue("error", "Namespace", f"Konsistent references non-existent resource '{rname}'"))
        elif qname not in resource_queues.get(rname, set()):
            issues.append(Issue("warning", "Namespace", f"Konsistent queue '{qname}' not found in resource '{rname}' (auto-created at runtime)"))

    return issues


def cmd_check(args):
    host, token = _creds(args)
    all_issues: list[Issue] = []

    docs_result = _api(host, token, "/")
    docs = docs_result.get("data", [])
    all_doc_names = {d["_id"] for d in docs}

    target_docs = [d for d in docs if not args.document or d["_id"] == args.document]

    for doc in target_docs:
        doc_name = doc["_id"]
        doc_meta = _get_doc_meta(host, token, doc_name)
        if not doc_meta:
            all_issues.append(Issue("error", doc_name, "Could not load document meta"))
            continue

        all_issues.extend(check_document(host, token, doc_name, doc_meta, all_doc_names))

        doc_fields = set(doc_meta.get("fields", {}).keys())
        doc_fields.update(["_id", "_updatedAt", "_createdAt", "_user", "_createdBy", "_updatedBy"])

        metas_result = _api(host, token, f"/{doc_name}")
        for meta in metas_result.get("data", []):
            mtype = meta.get("type", "")
            if mtype == "list":
                full = _api(host, token, f"/{doc_name}/list/{meta.get('name', 'Default')}")
                if full.get("success"):
                    all_issues.extend(check_list_meta(host, token, full["data"], doc_fields))
            elif mtype == "access":
                full = _api(host, token, f"/{doc_name}/access/{meta.get('name', 'Default')}")
                if full.get("success"):
                    all_issues.extend(check_access_meta(full["data"], doc_fields))

    if args.format == "json":
        print(json.dumps([i.to_dict() for i in all_issues], indent=2))
    else:
        if not all_issues:
            print("No issues found.")
            return
        errors = [i for i in all_issues if i.severity == "error"]
        warnings = [i for i in all_issues if i.severity == "warning"]
        print(f"Found {len(errors)} error(s) and {len(warnings)} warning(s):\n")
        for issue in all_issues:
            icon = "ERROR" if issue.severity == "error" else "WARN"
            print(f"  [{icon}] {issue.meta_id}: {issue.message}")


def cmd_check_queues(args):
    host, token = _creds(args)
    issues = check_queue_consistency(host, token)

    if args.format == "json":
        print(json.dumps([i.to_dict() for i in issues], indent=2))
    else:
        if not issues:
            print("Queue configuration is consistent.")
            return
        for issue in issues:
            icon = "ERROR" if issue.severity == "error" else "WARN"
            print(f"  [{icon}] {issue.meta_id}: {issue.message}")


def main():
    parser = argparse.ArgumentParser(description="Konecty Meta Doctor")
    parser.add_argument("--host", default=""); parser.add_argument("--token", default="")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("check"); p.add_argument("--document"); p.add_argument("--format", choices=["table", "json"], default="table"); p.set_defaults(func=cmd_check)
    p = sub.add_parser("check-queues"); p.add_argument("--format", choices=["table", "json"], default="table"); p.set_defaults(func=cmd_check_queues)

    args = parser.parse_args(); args.func(args)


if __name__ == "__main__": main()
