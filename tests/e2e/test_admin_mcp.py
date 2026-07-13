"""T24 — admin-MCP e2e suites: every flow konecty-meta documents (MCPF-26).

Flows covered (skills/konecty-meta references):
- read.md      : meta_read (document-type metas)
- document.md  : meta_document_upsert (full-replace, read-modify-write)
- list.md / view.md / access.md / pivot.md : the respective meta_*_upsert
- hook.md      : meta_hook_validate (valid + rejected) → meta_hook_upsert
- namespace.md : meta_namespace_update patch semantics
- doctor.md    : meta_doctor_run
- sync.md      : meta_sync_plan → meta_sync_apply (repo fixtures under
                 e2e/fixtures/MetaObjects/E2ESync)
- guard errors : mcpAdminEnabled=false → 503; mcpRoleIds=[] → 403
                 mcp_access_denied (flags restored afterwards)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from conftest import REPO_ROOT, mongo_eval, requires_stack

pytestmark = requires_stack

FIXTURES = REPO_ROOT / "e2e" / "fixtures" / "MetaObjects" / "E2ESync"

DOC_ID = "E2EAdmin"
DOC_META = {
    "_id": DOC_ID,
    "type": "document",
    "name": DOC_ID,
    "label": {"en": "E2E Admin Test", "pt_BR": "Teste Admin E2E"},
    "plurals": {"en": "E2E Admin Tests", "pt_BR": "Testes Admin E2E"},
    "icon": "tag",
    "fields": {
        "code": {
            "name": "code",
            "type": "autoNumber",
            "label": {"en": "Code", "pt_BR": "Código"},
            "isUnique": True,
            "isSortable": True,
        },
        "title": {
            "name": "title",
            "type": "text",
            "label": {"en": "Title", "pt_BR": "Título"},
            "isRequired": True,
        },
    },
}


# ── read.md ────────────────────────────────────────────────────────────────


def test_meta_read_document(admin_mcp):
    meta = admin_mcp.call("meta_read", {"name": "Contact"}).structured["meta"]
    assert meta["_id"] == "Contact"
    assert meta["type"] == "document"
    assert "status" in meta["fields"]


# ── document.md: full-replace read-modify-write ───────────────────────────


def test_meta_document_upsert_full_replace_cycle(admin_mcp):
    created = admin_mcp.call("meta_document_upsert", {"id": DOC_ID, "document": DOC_META})
    assert created.structured["result"] is not None

    meta = admin_mcp.call("meta_read", {"name": DOC_ID}).structured["meta"]
    assert set(meta["fields"]) >= {"code", "title"}

    # read-modify-write: upserts are full-replace — send the COMPLETE meta
    modified = json.loads(json.dumps(meta))
    modified["fields"]["notes"] = {
        "name": "notes",
        "type": "text",
        "label": {"en": "Notes", "pt_BR": "Notas"},
    }
    admin_mcp.call("meta_document_upsert", {"id": DOC_ID, "document": modified})

    reread = admin_mcp.call("meta_read", {"name": DOC_ID}).structured["meta"]
    assert "notes" in reread["fields"], "added field must persist"
    assert "title" in reread["fields"], "full payload must preserve existing fields"


# ── list.md / view.md / access.md / pivot.md ──────────────────────────────


def test_meta_child_upserts(admin_mcp):
    list_meta = {
        "_id": f"{DOC_ID}:list:Default",
        "type": "list",
        "name": "Default",
        "document": DOC_ID,
        "label": {"en": "E2E Admin Test", "pt_BR": "Teste Admin E2E"},
        "plurals": {"en": "E2E Admin Tests", "pt_BR": "Testes Admin E2E"},
        "view": "Default",
        "rowsPerPage": {"default": 25, "options": [10, 25, 50, 100]},
        "refreshRate": {"default": 0, "options": [0, 30, 60, 300]},
        "columns": {"title": {"name": "title", "linkField": "title", "visible": True}},
        "sorters": [{"term": "code", "direction": "asc"}],
    }
    admin_mcp.call("meta_list_upsert", {"id": list_meta["_id"], "list": list_meta})

    view_meta = {
        "_id": f"{DOC_ID}:view:Default",
        "type": "view",
        "name": "Default",
        "document": DOC_ID,
        "label": {"en": "E2E Admin Test", "pt_BR": "Teste Admin E2E"},
        "plurals": {"en": "E2E Admin Tests", "pt_BR": "Testes Admin E2E"},
        "visuals": [
            {
                "type": "visualGroup",
                "style": {"title": {"en": "Main", "pt_BR": "Principal"}},
                "visuals": [{"type": "visualSymlink", "fieldName": "title"}],
            }
        ],
    }
    admin_mcp.call("meta_view_upsert", {"id": view_meta["_id"], "view": view_meta})

    access_meta = {
        "_id": f"{DOC_ID}:access:Default",
        "type": "access",
        "name": "Default",
        "document": DOC_ID,
        "label": {"en": "Default", "pt_BR": "Padrão"},
        "fields": {},
        "isUpdatable": True,
        "isCreatable": True,
        "isReadable": True,
        "isDeletable": True,
    }
    admin_mcp.call("meta_access_upsert", {"id": access_meta["_id"], "access": access_meta})

    pivot_meta = {
        "_id": f"{DOC_ID}:pivot:Default",
        "type": "pivot",
        "name": "Default",
        "document": DOC_ID,
        "label": {"en": "E2E Pivot", "pt_BR": "Pivot E2E"},
        "plurals": {"en": "E2E Pivots", "pt_BR": "Pivots E2E"},
        "rows": [{"field": "title"}],
        "values": [{"field": "code", "aggregator": "count"}],
    }
    admin_mcp.call("meta_pivot_upsert", {"id": pivot_meta["_id"], "pivot": pivot_meta})

    stored_ids = mongo_eval(
        f'db.getCollection("MetaObjects").find({{document:"{DOC_ID}"}},{{_id:1}})'
        ".toArray().forEach(d => print(d._id))"
    ).splitlines()
    assert {f"{DOC_ID}:list:Default", f"{DOC_ID}:view:Default", f"{DOC_ID}:access:Default", f"{DOC_ID}:pivot:Default"} <= set(stored_ids)


# ── hook.md: validate before upsert ───────────────────────────────────────


def test_meta_hook_validate_then_upsert(admin_mcp):
    good_script = 'if (!data.title) { errors.push("title is required"); }'
    validation = admin_mcp.call("meta_hook_validate", {"script": good_script}).structured
    assert validation["validation"]["valid"] is True

    bad = admin_mcp.call(
        "meta_hook_validate", {"script": 'const fs = require("fs");'}, expect_error=True
    )
    assert bad.is_error or bad.structured["validation"]["valid"] is False

    # hooks live as fields of the DOCUMENT meta (hook.md): upsert the full
    # document meta carrying the script — id is the document _id
    meta = admin_mcp.call("meta_read", {"name": DOC_ID}).structured["meta"]
    hook_payload = json.loads(json.dumps(meta))
    hook_payload["scriptBeforeValidation"] = good_script
    hook_payload["script"] = good_script  # validated by meta_hook_upsert
    result = admin_mcp.call("meta_hook_upsert", {"id": DOC_ID, "hook": hook_payload}).structured
    assert result["result"] is not None

    persisted = admin_mcp.call("meta_read", {"name": DOC_ID}).structured["meta"]
    assert persisted.get("scriptBeforeValidation") == good_script


def test_meta_hook_upsert_rejects_invalid_script(admin_mcp):
    rejected = admin_mcp.call(
        "meta_hook_upsert",
        {"id": f"{DOC_ID}:hook:bad", "hook": {"script": 'require("child_process")'}},
        expect_error=True,
    )
    assert rejected.is_error, "upsert must refuse scripts that fail validation"


# ── namespace.md: patch semantics ─────────────────────────────────────────


def test_meta_namespace_update_is_a_patch(admin_mcp):
    before = json.loads(
        mongo_eval(
            'print(JSON.stringify(db.getCollection("MetaObjects").findOne({type:"namespace"},'
            "{mcpUserEnabled:1,trackUserGeolocation:1})))"
        ).splitlines()[-1]
    )
    admin_mcp.call("meta_namespace_update", {"patch": {"trackUserGeolocation": False}})
    after = json.loads(
        mongo_eval(
            'print(JSON.stringify(db.getCollection("MetaObjects").findOne({type:"namespace"},'
            "{mcpUserEnabled:1,trackUserGeolocation:1})))"
        ).splitlines()[-1]
    )
    assert after["trackUserGeolocation"] is False
    assert after["mcpUserEnabled"] == before["mcpUserEnabled"], "patch must not clobber other flags"


# ── doctor.md ──────────────────────────────────────────────────────────────


def test_meta_doctor_run(admin_mcp):
    result = admin_mcp.call("meta_doctor_run").structured
    assert "issues" in result and "total" in result


# ── sync.md: plan → apply from repo fixtures ──────────────────────────────


def _sync_items() -> list[dict]:
    document = json.loads((FIXTURES / "document.json").read_text())
    hook_script = (FIXTURES / "hook" / "scriptBeforeValidation.js").read_text()
    document["scriptBeforeValidation"] = hook_script
    list_meta = json.loads((FIXTURES / "list" / "Default.json").read_text())
    access_meta = json.loads((FIXTURES / "access" / "Default.json").read_text())
    return [document, list_meta, access_meta]


def test_meta_sync_plan_then_apply(admin_mcp):
    items = _sync_items()

    plan = admin_mcp.call("meta_sync_plan", {"items": items}).structured["plan"]
    assert {p["_id"] for p in plan} == {i["_id"] for i in items}
    assert all(p["action"] in ("create", "update") for p in plan)

    refused = admin_mcp.call("meta_sync_apply", {"items": items}, expect_error=True)
    assert refused.is_error, "apply without autoApprove must be refused"

    applied = admin_mcp.call("meta_sync_apply", {"items": items, "autoApprove": True}).structured
    assert applied["total"] == len(items)

    stored = mongo_eval(
        'print(JSON.stringify(db.getCollection("MetaObjects").findOne({_id:"E2ESync"},{type:1,name:1})))'
    ).splitlines()[-1]
    assert json.loads(stored)["name"] == "E2ESync"


# ── guard errors (flags off → 503/403) ────────────────────────────────────


def _set_namespace(js_patch: str) -> None:
    mongo_eval(
        f'db.getCollection("MetaObjects").updateOne({{type:"namespace"}},{{$set:{js_patch}}})'
    )
    time.sleep(3)  # change-stream rebuild debounce


def test_admin_mcp_disabled_returns_503(admin_mcp):
    _set_namespace("{mcpAdminEnabled:false}")
    try:
        status, body = _raw_post(admin_mcp)
        assert status == 503, f"expected 503, got {status}: {body[:200]}"
        assert "disabled" in body.lower()
    finally:
        _set_namespace("{mcpAdminEnabled:true}")


def test_role_allowlist_empty_returns_403_mcp_access_denied(user_mcp):
    role_ids = mongo_eval(
        'print(JSON.stringify(db.getCollection("MetaObjects").findOne({type:"namespace"}).mcpRoleIds))'
    ).splitlines()[-1]
    _set_namespace("{mcpRoleIds:[]}")
    try:
        status, body = _raw_post(user_mcp)
        assert status == 403, f"expected 403, got {status}: {body[:200]}"
        assert "mcp_access_denied" in body
    finally:
        _set_namespace(f"{{mcpRoleIds:{role_ids}}}")


def _raw_post(client) -> tuple[int, str]:
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        client.url,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {client.token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
