"""T23 — user-MCP e2e suites: every flow konecty-data documents (MCPF-26).

Flows covered (skills/konecty-data references):
- auth.md            : OTP session flow (request → verify → per-tool authTokenId → logout)
- field-discovery.md : modules_list → modules_fields → field_picklist_options /
                       field_lookup_search → filter_build
- find.md            : records_find w/ validated filter + offset pagination;
                       query_json (groupBy + relations/aggregators); query_sql;
                       Mongo-style filter rejection
- create-update.md   : records_create; fetch-first records_update with _updatedAt
- delete.md          : records_delete_preview → records_delete (confirm)
- files.md           : file_upload / file_download / file_delete
- errors.md          : read-only mode (mcpUserWriteEnabled=false → insufficient_scope)

The OTP code is read from the seeded ``data.Message`` collection (the stack has
no mail server; DISABLE_SENDMAIL=true stores the rendered message with
``data.otpCode``).

Known upstream deviations pinned here (reported with konecty/Konecty#453 rollup):
- Optimistic-lock *conflict* rejection is currently disabled in Konecty
  (``src/imports/data/api/update.ts`` — check commented out), so a stale
  ``_updatedAt`` succeeds. The suite asserts the format requirement only.
- ``file_upload`` applies the file but misreports an error: ``fileUpload``
  returns the bare record on success while the MCP tool checks
  ``result.success !== true``.
"""

from __future__ import annotations

import time

import pytest

from conftest import E2E_URL, mongo_eval, requires_stack
from mcp_client import McpToolError

pytestmark = requires_stack

ADMIN_EMAIL = "support@konecty.com"


# ── setup validation ───────────────────────────────────────────────────────


def test_well_known_protected_resource_announces_mcp():
    import json
    import urllib.request

    with urllib.request.urlopen(f"{E2E_URL}/.well-known/oauth-protected-resource") as resp:
        assert resp.status == 200
        body = json.load(resp)
    assert body["resource"] == f"{E2E_URL}/mcp"
    assert "read" in body["scopes_supported"]


# ── auth.md: OTP session flow ──────────────────────────────────────────────


def _latest_otp_code() -> str:
    return mongo_eval(
        'print(db.getCollection("data.Message").find({"data.otpCode":{$exists:true}})'
        ".sort({_createdAt:-1}).limit(1).toArray()[0].data.otpCode)"
    ).splitlines()[-1].strip()


def test_otp_session_flow_with_per_tool_token(user_mcp):
    options = user_mcp.call("session_login_options")
    assert options.structured.get("options"), "no OTP options advertised"

    requested = user_mcp.call("session_request_otp_email", {"email": ADMIN_EMAIL})
    assert requested.structured["otpRequest"]["success"] is True

    code = _latest_otp_code()
    verified = user_mcp.call("session_verify_otp_email", {"email": ADMIN_EMAIL, "otpCode": code})
    auth_id = verified.structured["authId"]
    assert verified.structured["logged"] is True
    assert auth_id

    # per-tool authTokenId argument (docs/en/mcp.md preferred transport)
    from mcp_client import McpClient

    anon = McpClient(f"{E2E_URL}/mcp", token=user_mcp.token)  # header for HTTP guard
    listed = anon.call("modules_list", {"authTokenId": auth_id})
    assert any(m["document"] == "Contact" for m in listed.structured["modules"])

    logout = user_mcp.call("session_logout", {"authTokenId": auth_id})
    assert logout.structured.get("logout") is not None


# ── field-discovery.md ─────────────────────────────────────────────────────


def test_modules_discovery(user_mcp):
    modules = user_mcp.call("modules_list").structured["modules"]
    documents = {m["document"] for m in modules}
    assert {"Contact", "Opportunity", "User"} <= documents

    fields = user_mcp.call("modules_fields", {"document": "Contact"}).structured
    control = {f["name"] for f in fields["controlFields"]}
    assert {"_id", "_createdAt", "_updatedAt", "_user"} <= control


def test_field_picklist_options(user_mcp):
    result = user_mcp.call(
        "field_picklist_options", {"document": "Contact", "fieldName": "status"}
    ).structured
    keys = {opt["key"] for opt in result["options"]}
    assert {"lead", "client"} <= keys


def test_filter_build_validates_operator_by_type(user_mcp):
    built = user_mcp.call(
        "filter_build",
        {
            "match": "and",
            "conditions": [
                {"field": "status", "operator": "equals", "value": "lead", "fieldType": "picklist"}
            ],
        },
    ).structured
    assert built["filter"]["conditions"][0]["term"] == "status"

    bad = user_mcp.call(
        "filter_build",
        {
            "match": "and",
            "conditions": [
                {"field": "status", "operator": "greater_than", "value": "x", "fieldType": "picklist"}
            ],
        },
        expect_error=True,
    )
    assert bad.is_error, "picklist + greater_than must be rejected"


# ── create-update.md + find.md ─────────────────────────────────────────────


@pytest.fixture(scope="module")
def seed_contacts(user_mcp):
    """Three contacts created through the documented records_create flow."""
    created = []
    for index in range(3):
        result = user_mcp.call(
            "records_create",
            {
                "document": "Contact",
                "data": {"name": {"first": "E2E", "last": f"Suite{index}"}, "status": "lead"},
            },
        )
        created.append(result.structured["records"][0])
    return created


def test_records_create_returns_full_record(seed_contacts):
    record = seed_contacts[0]
    assert record["_id"] and record["_updatedAt"]
    assert record["status"] == "lead"
    assert record["name"]["full"].startswith("E2E")


def test_records_find_with_filter_and_pagination(user_mcp, seed_contacts):
    built = user_mcp.call(
        "filter_build",
        {
            "match": "and",
            "conditions": [{"field": "name.last", "operator": "starts_with", "value": "Suite"}],
        },
    ).structured["filter"]

    page1 = user_mcp.call(
        "records_find", {"document": "Contact", "filter": built, "limit": 2, "start": 0}
    ).structured
    assert page1["total"] >= 3
    assert page1["pagination"]["hasMore"] is True
    assert len(page1["records"]) == 2

    page2 = user_mcp.call(
        "records_find",
        {"document": "Contact", "filter": built, "limit": 2, "start": page1["pagination"]["nextStart"]},
    ).structured
    ids = {r["_id"] for r in page1["records"]} | {r["_id"] for r in page2["records"]}
    assert len(ids) >= 3, "pagination pages must not overlap"


def test_mongo_style_filter_is_rejected(user_mcp):
    result = user_mcp.call(
        "records_find", {"document": "Contact", "filter": {"status": "lead"}}, expect_error=True
    )
    assert result.is_error, "Mongo-style top-level map must be rejected"
    assert "filter" in result.text.lower()


def test_fetch_first_update_with_updated_at(user_mcp, seed_contacts):
    target = seed_contacts[1]
    fresh = user_mcp.call(
        "records_find_by_id", {"document": "Contact", "recordId": target["_id"]}
    ).structured["record"]

    updated = user_mcp.call(
        "records_update",
        {
            "document": "Contact",
            "ids": [{"_id": fresh["_id"], "_updatedAt": fresh["_updatedAt"]}],
            "data": {"status": "client"},
        },
    ).structured["records"][0]
    assert updated["status"] == "client"
    assert updated["_updatedAt"] != fresh["_updatedAt"]


def test_update_without_updated_at_is_rejected(user_mcp, seed_contacts):
    with pytest.raises(McpToolError):
        user_mcp.call(
            "records_update",
            {
                "document": "Contact",
                "ids": [{"_id": seed_contacts[1]["_id"]}],
                "data": {"status": "lead"},
            },
        )


def test_field_lookup_search_resolves_related_id(user_mcp, seed_contacts):
    result = user_mcp.call(
        "field_lookup_search",
        {"document": "Opportunity", "fieldName": "contact", "search": "E2E"},
    ).structured
    assert result["relatedDocument"] == "Contact"
    assert result["total"] >= 1


def test_query_json_relations_and_group_by(user_mcp, seed_contacts):
    contact = seed_contacts[0]
    user_mcp.call(
        "records_create",
        {
            "document": "Opportunity",
            "data": {"contact": {"_id": contact["_id"]}, "status": "new"},
        },
    )

    joined = user_mcp.call(
        "query_json",
        {
            "query": {
                "document": "Contact",
                "filter": {
                    "match": "and",
                    "conditions": [{"term": "_id", "operator": "equals", "value": contact["_id"]}],
                },
                "fields": "code,name,status",
                "relations": [
                    {
                        "document": "Opportunity",
                        "lookup": "contact",
                        "aggregators": {"opportunityCount": {"aggregator": "count"}},
                    }
                ],
            }
        },
    ).structured
    assert joined["records"][0]["opportunityCount"] >= 1

    grouped = user_mcp.call(
        "query_json",
        {
            "query": {
                "document": "Contact",
                "groupBy": ["status"],
                "aggregators": {"total": {"aggregator": "count"}},
            }
        },
    ).structured
    statuses = {r["status"]: r["total"] for r in grouped["records"]}
    assert statuses and sum(statuses.values()) >= 3


def test_query_sql_on_explicit_request(user_mcp, seed_contacts):
    result = user_mcp.call(
        "query_sql", {"sql": 'SELECT code, status FROM "Contact" LIMIT 5'}
    ).structured
    assert result["records"], "SQL query returned no records"


# ── files.md ───────────────────────────────────────────────────────────────


def test_file_upload_download_delete(user_mcp, seed_contacts):
    record_id = seed_contacts[2]["_id"]
    file_meta = {"name": "e2e.txt", "key": "e2e.txt", "size": 4, "kind": "text/plain"}

    # Upstream bug (pinned): upload APPLIES the file but the tool misreports an
    # error — fileUpload returns the bare record on success while the MCP tool
    # checks result.success !== true.
    upload = user_mcp.call(
        "file_upload",
        {"document": "Contact", "recordId": record_id, "fieldName": "picture", "file": file_meta},
        expect_error=True,
    )
    assert upload.is_error, "remove this pin once konecty fixes the file_upload success contract"

    fresh = user_mcp.call(
        "records_find_by_id", {"document": "Contact", "recordId": record_id}
    ).structured["record"]
    names = [f["name"] for f in fresh.get("picture") or []]
    assert "e2e.txt" in names, "file metadata must be attached to the record"

    download = user_mcp.call(
        "file_download",
        {"document": "Contact", "recordId": record_id, "fieldName": "picture", "fileName": "e2e.txt"},
    ).structured
    assert download["fileUrl"].endswith("e2e.txt")

    user_mcp.call(
        "file_delete",
        {
            "document": "Contact",
            "recordId": record_id,
            "fieldName": "picture",
            "fileName": "e2e.txt",
            "confirm": True,
        },
        expect_error=True,  # same success-contract bug family as file_upload
    )
    fresh = user_mcp.call(
        "records_find_by_id", {"document": "Contact", "recordId": record_id}
    ).structured["record"]
    names = [f["name"] for f in fresh.get("picture") or []]
    assert "e2e.txt" not in names, "file metadata must be removed from the record"


# ── delete.md ──────────────────────────────────────────────────────────────


def test_delete_preview_then_confirmed_delete(user_mcp):
    record = user_mcp.call(
        "records_create",
        {"document": "Contact", "data": {"name": {"first": "E2E", "last": "ToDelete"}, "status": "lead"}},
    ).structured["records"][0]

    preview = user_mcp.call(
        "records_delete_preview", {"document": "Contact", "recordId": record["_id"]}
    ).structured
    assert preview["preview"], "preview must show the record before deletion"

    # fetch-first: delete DOES enforce the optimistic lock — use the live
    # _updatedAt (creation hooks may bump it after records_create returns)
    fresh = user_mcp.call(
        "records_find_by_id", {"document": "Contact", "recordId": record["_id"]}
    ).structured["record"]

    deleted = user_mcp.call(
        "records_delete",
        {
            "document": "Contact",
            "confirm": True,
            # delete's lock check reads _updatedAt.$date (data.js:1066) — the
            # plain-string form is accepted by the schema but always fails the
            # version diff, so the {$date: ...} envelope is the working shape
            "ids": [{"_id": fresh["_id"], "_updatedAt": {"$date": fresh["_updatedAt"]}}],
        },
    ).structured
    assert deleted["deleted"], "delete must confirm the removal"

    with pytest.raises(McpToolError):
        user_mcp.call("records_find_by_id", {"document": "Contact", "recordId": record["_id"]})


# ── errors.md: read-only mode ──────────────────────────────────────────────


def test_read_only_mode_blocks_writes_with_insufficient_scope(user_mcp, admin_mcp):
    """mcpUserWriteEnabled=false strips write even from first-party sessions."""
    admin_mcp.call("meta_namespace_update", {"patch": {"mcpUserWriteEnabled": False}})
    time.sleep(3)  # MetaObjects change-stream rebuild debounce (~1s)
    try:
        with pytest.raises(McpToolError) as excinfo:
            user_mcp.call(
                "records_create",
                {"document": "Contact", "data": {"name": {"first": "RO", "last": "Blocked"}}},
            )
        message = str(excinfo.value).lower()
        assert "write scope required" in message or "insufficient_scope" in message

        # read tools keep working in read-only mode
        found = user_mcp.call("records_find", {"document": "Contact", "limit": 1}).structured
        assert found["records"] is not None
    finally:
        admin_mcp.call("meta_namespace_update", {"patch": {"mcpUserWriteEnabled": True}})
        time.sleep(3)
