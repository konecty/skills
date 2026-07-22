"""T22 smoke suite: the stdlib MCP client against Konecty's stateless transport.

Asserts the transport contract (initialize handshake, stateless POST-only,
405 on GET/DELETE) and that ``tools/list`` on both servers exposes exactly the
tool sets documented in Konecty ``docs/en/mcp.md`` (the contract the skills
reference by name).
"""

from __future__ import annotations

import pytest

from conftest import requires_stack

pytestmark = requires_stack

# docs/en/mcp.md — User MCP tool classification
USER_TOOLS = {
    # modules + field helpers
    "modules_list",
    "modules_fields",
    "field_picklist_options",
    "field_lookup_search",
    "filter_build",
    # records
    "records_find",
    "records_find_by_id",
    "records_create",
    "records_update",
    "records_delete_preview",
    "records_delete",
    # query
    "query_json",
    "query_sql",
    "query_pivot",
    "query_graph",
    # files
    "file_upload",
    "file_download",
    "file_delete",
    # render-only widgets
    "render_records_widget",
    "render_record_widget",
    "render_record_card",
    "render_pivot_widget",
    "render_graph_widget",
    "render_file_widget",
}

# docs/en/mcp.md — Admin MCP tools
ADMIN_TOOLS = {
    "meta_read",
    "meta_document_upsert",
    "meta_list_upsert",
    "meta_view_upsert",
    "meta_access_upsert",
    "meta_hook_validate",
    "meta_hook_upsert",
    "meta_namespace_update",
    "meta_pivot_upsert",
    "meta_delete",
    "meta_doctor_run",
    "meta_sync_plan",
    "meta_sync_apply",
}


def test_initialize_handshake_user_mcp(user_mcp):
    result = user_mcp.initialize()
    assert result["serverInfo"]["name"] == "konecty-user-mcp"
    assert result["protocolVersion"]


def test_initialize_handshake_admin_mcp(admin_mcp):
    result = admin_mcp.initialize()
    assert result["serverInfo"]["name"] == "konecty-admin-mcp"


def test_user_mcp_exposes_documented_tools(user_mcp):
    names = user_mcp.tool_names()
    missing = USER_TOOLS - names
    assert not missing, f"user MCP missing documented tools: {sorted(missing)}"


def test_admin_mcp_exposes_documented_tools(admin_mcp):
    names = admin_mcp.tool_names()
    missing = ADMIN_TOOLS - names
    assert not missing, f"admin MCP missing documented tools: {sorted(missing)}"


def test_stateless_no_session_needed_between_posts(user_mcp):
    """Konecty MCP is stateless: a tools/call POST works without a prior
    initialize on the same connection/session."""
    from mcp_client import McpClient

    fresh = McpClient(user_mcp.url, token=user_mcp.token)
    result = fresh.call("filter_build", {
        "match": "and",
        "conditions": [{"field": "status", "operator": "equals", "value": "Ativo"}],
    })
    assert result.structured is not None


def test_get_and_delete_return_405(user_mcp, admin_mcp):
    for client in (user_mcp, admin_mcp):
        for method in ("GET", "DELETE"):
            status, body = client.http_raw(method)
            assert status == 405, f"{method} {client.url} -> {status}: {body[:200]}"


def test_unauthenticated_post_gets_401_with_www_authenticate(anon_user_mcp):
    from mcp_client import McpHttpError

    with pytest.raises(McpHttpError) as excinfo:
        anon_user_mcp.rpc("tools/list")
    assert excinfo.value.status == 401
    www = {k.lower(): v for k, v in excinfo.value.headers.items()}.get("www-authenticate", "")
    assert "resource_metadata" in www
