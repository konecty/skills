"""Unit tests for the stdlib MCP-over-HTTP client (``mcp_client.py``).

Derived from spec ACs (P2: Stateless MCP protocol client) and the task
"Done when" clauses — NOT from the implementation. The module is loaded
in-process via PseudoAgent so coverage.py records every branch.

Layers under test:
  * ``parse_sse``            — SSE frame parsing + typed error on malformed data
  * typed error classes      — McpHttpError(.status), McpTransportError, McpToolError
  * ``call_tool``            — JSON-RPC envelope, both Accept types, Bearer header,
                               authTokenId argument, SSE + JSON extraction,
                               error branching (added in T2)
"""
from __future__ import annotations

import json

import pytest

from e2e.agent import PseudoAgent

pytestmark = pytest.mark.mock

_MOD = None


def mcp():
    """Load ``skills/konecty-data/scripts/mcp_client.py`` once (coverage-tracked)."""
    global _MOD
    if _MOD is None:
        _MOD = PseudoAgent()._load("konecty-data", "mcp_client")
    return _MOD


# ---------------------------------------------------------------------------
# SSE frame builders (mirror what Konecty's Streamable-HTTP transport emits)
# ---------------------------------------------------------------------------


def _sse_frame(payload: dict, event: str | None = "message") -> str:
    lines = []
    if event is not None:
        lines.append(f"event: {event}")
    lines.append("data: " + json.dumps(payload))
    return "\n".join(lines) + "\n\n"


def _rpc_result(result: dict, rpc_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


# ===========================================================================
# T1 — parse_sse
# ===========================================================================


class TestParseSSE:
    def test_single_frame(self):
        """A single well-formed SSE frame yields exactly one JSON-RPC message."""
        m = mcp()
        payload = _rpc_result({"structuredContent": {"records": [{"_id": "cid001"}], "total": 1}})
        body = _sse_frame(payload).encode("utf-8")

        msgs = m.parse_sse(body)

        assert isinstance(msgs, list)
        assert len(msgs) == 1
        assert msgs[0]["id"] == 1
        assert msgs[0]["result"]["structuredContent"]["total"] == 1

    def test_multi_frame_priming_then_result(self):
        """A priming frame followed by the result frame yields both, in order."""
        m = mcp()
        priming = {"jsonrpc": "2.0", "method": "notifications/message", "params": {"ping": True}}
        result = _rpc_result({"structuredContent": {"records": [], "total": 0}})
        body = (_sse_frame(priming) + _sse_frame(result)).encode("utf-8")

        msgs = m.parse_sse(body)

        assert len(msgs) == 2
        # The result-bearing message is the one with id==1.
        hit = next(x for x in msgs if x.get("id") == 1)
        assert "result" in hit

    def test_multi_data_lines_concatenated(self):
        """Several ``data:`` lines in one frame concatenate into one JSON payload."""
        m = mcp()
        obj = _rpc_result({"structuredContent": {"records": [{"_id": "x"}], "total": 1}})
        blob = json.dumps(obj)
        half = len(blob) // 2
        frame = "data: " + blob[:half] + "\n" + "data: " + blob[half:] + "\n\n"

        msgs = m.parse_sse(frame.encode("utf-8"))

        assert len(msgs) == 1
        assert msgs[0]["result"]["structuredContent"]["total"] == 1

    def test_empty_body_returns_empty_list(self):
        """A body with no ``data:`` payloads returns ``[]`` (no exception)."""
        m = mcp()
        assert m.parse_sse(b"") == []
        assert m.parse_sse(b": comment only\n\nevent: ping\n\n") == []

    def test_malformed_data_frame_raises_transport_error(self):
        """A present-but-invalid-JSON data frame raises McpTransportError cleanly."""
        m = mcp()
        body = b"event: message\ndata: {not valid json,,,\n\n"
        with pytest.raises(m.McpTransportError):
            m.parse_sse(body)

    def test_truncated_frame_raises_transport_error(self):
        """A truncated JSON payload (stream cut mid-object) raises McpTransportError."""
        m = mcp()
        body = b'data: {"jsonrpc":"2.0","id":1,"result":{"structuredCon'
        with pytest.raises(m.McpTransportError):
            m.parse_sse(body)


# ===========================================================================
# T1 — typed error classes
# ===========================================================================


class TestErrorClasses:
    def test_http_error_carries_status(self):
        m = mcp()
        err = m.McpHttpError(403, '{"error":"mcp_access_denied"}')
        assert err.status == 403
        assert "403" in str(err)
        assert isinstance(err, Exception)

    def test_tool_error_carries_code_message_details(self):
        m = mcp()
        err = m.McpToolError("VALIDATION_ERROR", "bad filter", {"field": "filter"})
        assert err.code == "VALIDATION_ERROR"
        assert err.message == "bad filter"
        assert err.details == {"field": "filter"}

    def test_transport_error_is_exception(self):
        m = mcp()
        err = m.McpTransportError("connection reset")
        assert isinstance(err, Exception)
        assert "connection reset" in str(err)
