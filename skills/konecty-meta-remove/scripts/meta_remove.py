#!/usr/bin/env python3
"""
Konecty Meta Remove: delete a full metadata module (MetaObjects) with interactive confirmation.
Stdlib only. See references/deletion-order.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

CREDENTIALS_DIR = os.path.expanduser("~/.konecty")
ENV_FILE = os.path.join(CREDENTIALS_DIR, ".env")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials")
API_PREFIX = "/api/admin/meta"

PRIMARY_TYPES = frozenset({"document", "composite"})
HOOK_NAMES = ("scriptBeforeValidation", "validationScript", "scriptAfterSave", "validationData")
# Delete child metas before access (often many); stable tie-break by _id
CHILD_TYPE_ORDER = {"list": 0, "view": 1, "pivot": 2, "card": 3, "access": 4, "namespace": 5}


def _unquote_env(val: str) -> str:
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        return val[1:-1]
    return val


def _load_credentials() -> tuple[str, str]:
    url, token = _unquote_env(os.environ.get("KONECTY_URL", "")), _unquote_env(os.environ.get("KONECTY_TOKEN", ""))
    if os.path.isfile(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("KONECTY_URL=") and not url:
                    url = _unquote_env(line.split("=", 1)[1])
                elif line.startswith("KONECTY_TOKEN=") and not token:
                    token = _unquote_env(line.split("=", 1)[1])
    if (not url or not token) and os.path.isfile(CREDENTIALS_FILE):
        import configparser

        config = configparser.ConfigParser()
        config.read(CREDENTIALS_FILE)
        if "default" in config:
            url = url or _unquote_env(config["default"].get("host", ""))
            token = token or _unquote_env(config["default"].get("authid", ""))
    return url.rstrip("/"), token


def _creds(args: argparse.Namespace) -> tuple[str, str]:
    host, token = _unquote_env(args.host or ""), _unquote_env(args.token or "")
    h, t = _load_credentials()
    return host or h, token or t


def _quote_path_seg(segment: str) -> str:
    return urllib.parse.quote(str(segment), safe="")


def _api(host: str, token: str, method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    url = f"{host}{API_PREFIX}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": token}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            if not raw.strip():
                return {"success": True}
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:500]}"}


def _is_primary(meta: dict[str, Any], module: str) -> bool:
    tid = meta.get("_id")
    typ = meta.get("type")
    return typ in PRIMARY_TYPES and tid == module


def _sort_child_metas(metas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(m: dict[str, Any]) -> tuple[int, str, str]:
        typ = str(m.get("type", ""))
        return (CHILD_TYPE_ORDER.get(typ, 99), typ, str(m.get("_id", "")))

    return sorted(metas, key=key)


def _fetch_module_metas(host: str, token: str, module: str) -> list[dict[str, Any]] | None:
    r = _api(host, token, "GET", f"/{_quote_path_seg(module)}")
    if not r.get("success"):
        err = str(r.get("error", "")).lower()
        if "http 404" in err or "document not found" in err or "meta not found" in err:
            return []
        return None
    data = r.get("data")
    if not isinstance(data, list):
        return None
    return data


def _fetch_full_primary(host: str, token: str, module: str, typ: str) -> dict[str, Any] | None:
    r = _api(host, token, "GET", f"/{_quote_path_seg(module)}/{_quote_path_seg(typ)}")
    if r.get("success") and isinstance(r.get("data"), dict):
        return r["data"]
    return None


def _hook_names_present(doc: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for name in HOOK_NAMES:
        if name in doc and doc[name] is not None:
            out.append(name)
    return out


def _delete_path_for_meta(meta: dict[str, Any], module: str) -> str | None:
    """Return API path (including leading slash) for DELETE, or None if unsupported."""
    tid = str(meta.get("_id", ""))
    typ = str(meta.get("type", ""))
    if typ in PRIMARY_TYPES and tid == module:
        return f"/{_quote_path_seg(module)}/{_quote_path_seg(typ)}"
    parts = tid.split(":")
    if len(parts) >= 3:
        doc, mtype, name = parts[0], parts[1], ":".join(parts[2:])
        return f"/{_quote_path_seg(doc)}/{_quote_path_seg(mtype)}/{_quote_path_seg(name)}"
    return None


@dataclass(frozen=True)
class QueueItem:
    kind: str  # "meta" | "hook"
    label: str
    path: str
    hook_name: str | None = None


def build_removal_queue(host: str, token: str, module: str, metas: list[dict[str, Any]]) -> tuple[list[QueueItem], str | None]:
    """
    Returns (queue, error_message).
    Order: child metas -> hooks on primary -> primary meta (last).
    """
    primaries = [m for m in metas if _is_primary(m, module)]
    children = [m for m in metas if not _is_primary(m, module)]

    if len(primaries) > 1:
        ids = [str(m.get("_id")) for m in primaries]
        return [], f"Multiple primary metas for module {module!r}: {ids}. Resolve manually."

    unsupported = [m for m in children if _delete_path_for_meta(m, module) is None]
    if unsupported:
        lines = ", ".join(str(m.get("_id")) for m in unsupported)
        return [], f"Unsupported or ambiguous meta _id (cannot derive DELETE path): {lines}"

    queue: list[QueueItem] = []
    for m in _sort_child_metas(children):
        p = _delete_path_for_meta(m, module)
        if p:
            queue.append(QueueItem("meta", str(m.get("_id")), p, None))

    primary = primaries[0] if primaries else None
    if primary:
        ptyp = str(primary.get("type", ""))
        full = _fetch_full_primary(host, token, module, ptyp)
        if full:
            for hn in _hook_names_present(full):
                queue.append(
                    QueueItem(
                        "hook",
                        f"{module} hook {hn}",
                        f"/{_quote_path_seg(module)}/hook/{_quote_path_seg(hn)}",
                        hn,
                    )
                )
        pp = _delete_path_for_meta(primary, module)
        if pp:
            queue.append(QueueItem("meta", str(primary.get("_id")), pp, None))

    return queue, None


def _count_by_type(metas: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for m in metas:
        t = str(m.get("type", "?"))
        counts[t] = counts.get(t, 0) + 1
    return counts


def cmd_plan(args: argparse.Namespace) -> None:
    host, token = _creds(args)
    module = args.document
    metas = _fetch_module_metas(host, token, module)
    if metas is None:
        r = _api(host, token, "GET", f"/{_quote_path_seg(module)}")
        print(r.get("error", "GET failed"), file=sys.stderr)
        sys.exit(1)
    if not metas:
        print(f"No metas returned for module {module!r}.")
        return

    counts = _count_by_type(metas)
    summary = ", ".join(f"{n} {t}" for t, n in sorted(counts.items()))
    print(f"\nModule {module!r}: {len(metas)} meta(s) — {summary}\n")

    for m in sorted(metas, key=lambda x: str(x.get("_id", ""))):
        print(f"  _id={m.get('_id')!s}  type={m.get('type')!s}  label={m.get('label')!s}")

    queue, err = build_removal_queue(host, token, module, metas)
    if err:
        print(f"\nError building queue: {err}", file=sys.stderr)
        sys.exit(1)

    print(f"\nDeletion queue ({len(queue)} step(s)), children and hooks before primary:\n")
    for i, item in enumerate(queue, 1):
        print(f"  {i:3}. [{item.kind}] {item.label}")
        print(f"       DELETE {API_PREFIX}{item.path}")

    print("\nRun `apply` only after reviewing impact on data and cross-document references.")


def _confirm(message: str) -> bool:
    if not sys.stdin.isatty():
        print("stdin is not a TTY; interactive confirmation is required.", file=sys.stderr)
        return False
    try:
        ans = input(f"{message} [y/N]: ").strip().lower()
    except EOFError:
        return False
    return ans == "y"


def _confirm_strong(message: str, token_phrase: str) -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        ans = input(f"{message}\nType {token_phrase!r} to proceed, anything else to abort: ").strip()
    except EOFError:
        return False
    return ans == token_phrase


def _execute_delete(host: str, token: str, path: str) -> tuple[bool, str]:
    r = _api(host, token, "DELETE", path)
    if r.get("success"):
        return True, "deleted"
    err = str(r.get("error", ""))
    if "HTTP 404" in err:
        return True, "already absent (404)"
    return False, err


def _is_primary_delete_step(item: QueueItem, module: str) -> bool:
    if item.kind != "meta":
        return False
    return item.path in (
        f"/{_quote_path_seg(module)}/document",
        f"/{_quote_path_seg(module)}/composite",
    )


def cmd_apply(args: argparse.Namespace) -> None:
    host, token = _creds(args)
    module = args.document
    yes_all = bool(getattr(args, "yes", False))
    if yes_all:
        print(
            "\n[--yes] Non-interactive: proceeding without per-step prompts (operator-requested only).\n",
            file=sys.stderr,
        )

    metas = _fetch_module_metas(host, token, module)
    if metas is None:
        r = _api(host, token, "GET", f"/{_quote_path_seg(module)}")
        print(r.get("error", "GET failed"), file=sys.stderr)
        sys.exit(1)

    queue, err = build_removal_queue(host, token, module, metas)
    if err:
        print(err, file=sys.stderr)
        sys.exit(1)
    if not queue:
        print("Nothing to delete.")
        return

    print(f"\n{len(queue)} deletion step(s) for module {module!r}.\n")
    skipped = 0
    deleted_any = False

    for item in queue:
        print(f"\n--- {item.kind.upper()}: {item.label}")
        print(f"    {API_PREFIX}{item.path}")

        if _is_primary_delete_step(item, module):
            live = _fetch_module_metas(host, token, module) or []
            children_left = [m for m in live if not _is_primary(m, module)]
            if children_left:
                ids = ", ".join(str(c.get("_id")) for c in children_left)
                print(f"    Child metas still present: {ids}")
                if yes_all:
                    print(
                        "    ERROR: refusing primary delete while children remain (fix or re-run plan).",
                        file=sys.stderr,
                    )
                    skipped += 1
                    continue
                if not _confirm_strong(
                    "Deleting the primary while children remain leaves orphan list/view/access metas.",
                    "DELETE PRIMARY ANYWAY",
                ):
                    print("    Skipped primary delete.")
                    skipped += 1
                    continue

        if not yes_all and not _confirm("Proceed with this DELETE?"):
            print("    Skipped.")
            skipped += 1
            continue
        ok, msg = _execute_delete(host, token, item.path)
        if ok:
            print(f"    OK — {msg}")
            deleted_any = True
        else:
            print(f"    FAIL — {msg}", file=sys.stderr)
            if yes_all:
                sys.exit(1)

    remaining = _fetch_module_metas(host, token, module)
    if remaining:
        primaries = [m for m in remaining if _is_primary(m, module)]
        children = [m for m in remaining if not _is_primary(m, module)]
        if children and not primaries:
            print(
                "\nWarning: inconsistent state — child metas exist but no primary document for this module.",
                file=sys.stderr,
            )
        if children and primaries:
            print(
                "\nWarning: non-primary metas still exist together with the primary document meta.",
                file=sys.stderr,
            )

    if deleted_any:
        print("\nReloading metadata...")
        rr = _api(host, token, "POST", "/reload")
        if rr.get("success") is not False:
            print("Reload requested.")
        else:
            print(f"Reload call returned: {rr}", file=sys.stderr)

    final = _fetch_module_metas(host, token, module)
    if final is None:
        print("\nModule GET failed after apply; verify manually.", file=sys.stderr)
    elif not final:
        print(f"\nModule {module!r} has no metas left (GET returned empty list).")
    else:
        print(f"\n{len(final)} meta(s) still returned for module {module!r}. Run `plan` again to review.")


def cmd_delete(args: argparse.Namespace) -> None:
    host, token = _creds(args)
    meta_id = args.meta_id.strip()
    parts = meta_id.split(":")

    if len(parts) == 2:
        print("meta-id with a single colon is ambiguous; use full _id (doc:type:name...).", file=sys.stderr)
        sys.exit(1)

    if len(parts) == 1:
        doc = parts[0]
        metas = _fetch_module_metas(host, token, doc)
        if metas is None:
            print("GET module failed.", file=sys.stderr)
            sys.exit(1)
        primary = next((m for m in metas if str(m.get("_id")) == doc and str(m.get("type")) in PRIMARY_TYPES), None)
        if primary is None:
            print(f"No primary document/composite with _id={doc!r} in module listing.", file=sys.stderr)
            sys.exit(1)
        path = _delete_path_for_meta(primary, doc)
    else:
        doc, mtype, name = parts[0], parts[1], ":".join(parts[2:])
        synthetic = {"_id": meta_id, "type": mtype, "document": doc}
        path = _delete_path_for_meta(synthetic, doc)

    if not path:
        print("Could not build DELETE path.", file=sys.stderr)
        sys.exit(1)

    print(f"\nDELETE {API_PREFIX}{path}\nmeta-id={meta_id!r}\n")
    if not _confirm("Proceed with this single DELETE?"):
        print("Aborted.")
        return
    ok, msg = _execute_delete(host, token, path)
    print(msg if ok else f"FAIL: {msg}", file=sys.stderr if not ok else sys.stdout)
    if ok:
        rr = _api(host, token, "POST", "/reload")
        if rr.get("success") is not False:
            print("Reload requested.")


def main() -> None:
    p = argparse.ArgumentParser(description="Remove Konecty metadata modules (interactive).")
    p.add_argument("--host", default="", help="Override KONECTY_URL")
    p.add_argument("--token", default="", help="Override KONECTY_TOKEN")
    sub = p.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="List metas and deletion queue")
    p_plan.add_argument("--document", required=True, help="Module / document _id (e.g. Contact)")
    p_plan.set_defaults(func=cmd_plan)

    p_apply = sub.add_parser("apply", help="Interactive delete for full module")
    p_apply.add_argument("--document", required=True, help="Module / document _id")
    p_apply.add_argument(
        "--yes",
        action="store_true",
        help="Non-interactive: skip prompts (use only when the operator explicitly requests it; aborts on first DELETE failure)",
    )
    p_apply.set_defaults(func=cmd_apply)

    p_del = sub.add_parser("delete", help="Delete one meta by _id")
    p_del.add_argument("--meta-id", required=True, help="Meta _id, e.g. Contact:list:Default or Contact")
    p_del.set_defaults(func=cmd_delete)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
