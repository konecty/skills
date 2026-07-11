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

import contextlib
import json
import urllib.error
import urllib.request

import pytest

from e2e.agent import PseudoAgent
from e2e.mock_konecty import MockKonecty, _FakeResponse, _err

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


@contextlib.contextmanager
def _patched_urlopen(handler):
    """Temporarily replace ``urllib.request.urlopen`` with *handler*.

    ``handler(req)`` must return a response object (or raise). ``mcp_client``
    resolves ``urllib.request.urlopen`` at call time, so this intercepts it.
    """
    original = urllib.request.urlopen
    urllib.request.urlopen = handler  # type: ignore[assignment]
    try:
        yield
    finally:
        urllib.request.urlopen = original  # type: ignore[assignment]


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


# ===========================================================================
# T2 — call_tool
# ===========================================================================


class TestCallToolRequest:
    def test_request_envelope_headers_and_body(self):
        """Envelope carries both Accept types, Bearer header, and authTokenId arg."""
        m = mcp()
        captured = {}

        def handler(req, *a, **k):
            captured["req"] = req
            sse = _sse_frame(_rpc_result({"structuredContent": {"records": [], "total": 0}}))
            return _FakeResponse(sse.encode("utf-8"), 200, "text/event-stream")

        with _patched_urlopen(handler):
            m.call_tool("http://konecty.example", "tok-123", "records_find",
                        {"document": "Contact", "limit": 50})

        req = captured["req"]
        assert req.full_url == "http://konecty.example/mcp"
        assert req.get_method() == "POST"
        # Both Accept media types required (406 otherwise).
        accept = req.get_header("Accept")
        assert "application/json" in accept and "text/event-stream" in accept
        # Bearer auth header.
        assert req.get_header("Authorization") == "Bearer tok-123"
        # Content-Type must be application/json (415 otherwise).
        assert req.get_header("Content-type") == "application/json"

        sent = json.loads(req.data)
        assert sent["jsonrpc"] == "2.0"
        assert sent["id"] == 1
        assert sent["method"] == "tools/call"
        assert sent["params"]["name"] == "records_find"
        args = sent["params"]["arguments"]
        assert args["document"] == "Contact"
        assert args["limit"] == 50
        # Token echoed in the arguments (server prefers the arg).
        assert args["authTokenId"] == "tok-123"

    def test_trailing_slash_base_url_normalised(self):
        """A base_url with a trailing slash still targets exactly ``/mcp``."""
        m = mcp()
        captured = {}

        def handler(req, *a, **k):
            captured["req"] = req
            sse = _sse_frame(_rpc_result({"structuredContent": {"records": [], "total": 0}}))
            return _FakeResponse(sse.encode("utf-8"), 200, "text/event-stream")

        with _patched_urlopen(handler):
            m.call_tool("http://konecty.example/", "t", "records_find", {})

        assert captured["req"].full_url == "http://konecty.example/mcp"


class TestCallToolResponse:
    _RESULT = {
        "content": [{"type": "text", "text": "ok"}],
        "structuredContent": {
            "records": [{"_id": "cid001", "name": "Alice"}],
            "total": 1,
            "pagination": {"start": 0, "limit": 50, "returned": 1, "total": 1, "hasMore": False},
        },
    }

    def test_sse_result_extracted(self):
        """A 200 SSE reply yields the tool result object."""
        m = mcp()
        sse = _sse_frame(_rpc_result(self._RESULT))

        def handler(req, *a, **k):
            return _FakeResponse(sse.encode("utf-8"), 200, "text/event-stream")

        with _patched_urlopen(handler):
            result = m.call_tool("http://x", "t", "records_find", {"document": "Contact"})

        assert result["structuredContent"]["total"] == 1
        assert result["structuredContent"]["records"][0]["_id"] == "cid001"

    def test_json_result_extracted_defensively(self):
        """A 200 plain application/json reply yields the SAME result object."""
        m = mcp()
        body = json.dumps(_rpc_result(self._RESULT)).encode("utf-8")

        def handler(req, *a, **k):
            return _FakeResponse(body, 200, "application/json")

        with _patched_urlopen(handler):
            result = m.call_tool("http://x", "t", "records_find", {"document": "Contact"})

        assert result["structuredContent"]["records"][0]["_id"] == "cid001"

    def test_sse_and_json_yield_identical_result(self):
        """SSE-mode and JSON-mode extraction produce byte-identical results."""
        m = mcp()
        sse = _sse_frame(_rpc_result(self._RESULT)).encode("utf-8")
        js = json.dumps(_rpc_result(self._RESULT)).encode("utf-8")

        with _patched_urlopen(lambda req, *a, **k: _FakeResponse(sse, 200, "text/event-stream")):
            r_sse = m.call_tool("http://x", "t", "records_find", {})
        with _patched_urlopen(lambda req, *a, **k: _FakeResponse(js, 200, "application/json")):
            r_json = m.call_tool("http://x", "t", "records_find", {})

        assert r_sse == r_json


class TestCallToolErrors:
    def test_jsonrpc_error_raises_tool_error(self):
        """A 200 reply carrying a JSON-RPC ``error`` raises McpToolError (no fallback)."""
        m = mcp()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32602, "message": "invalid document", "data": {"document": "Contato"}},
        }
        sse = _sse_frame(payload).encode("utf-8")

        with _patched_urlopen(lambda req, *a, **k: _FakeResponse(sse, 200, "text/event-stream")):
            with pytest.raises(m.McpToolError) as ei:
                m.call_tool("http://x", "t", "records_find", {"document": "Contato"})
        assert ei.value.code == -32602
        assert "invalid document" in ei.value.message

    def test_result_iserror_raises_tool_error(self):
        """A 200 reply whose ``result.isError`` is true raises McpToolError."""
        m = mcp()
        result = {
            "content": [{"type": "text", "text": "VALIDATION_ERROR: bad filter"}],
            "isError": True,
        }
        sse = _sse_frame(_rpc_result(result)).encode("utf-8")

        with _patched_urlopen(lambda req, *a, **k: _FakeResponse(sse, 200, "text/event-stream")):
            with pytest.raises(m.McpToolError) as ei:
                m.call_tool("http://x", "t", "records_find", {})
        assert "VALIDATION_ERROR" in str(ei.value)

    def test_non_2xx_raises_http_error_with_status(self):
        """A non-2xx HTTP response raises McpHttpError carrying ``.status``."""
        m = mcp()

        def handler(req, *a, **k):
            raise _err(403, "mcp_access_denied")

        with _patched_urlopen(handler):
            with pytest.raises(m.McpHttpError) as ei:
                m.call_tool("http://x", "t", "records_find", {})
        assert ei.value.status == 403

    def test_url_error_raises_transport_error(self):
        """A connection/DNS failure (URLError) raises McpTransportError."""
        m = mcp()

        def handler(req, *a, **k):
            raise urllib.error.URLError("Name or service not known")

        with _patched_urlopen(handler):
            with pytest.raises(m.McpTransportError):
                m.call_tool("http://x", "t", "records_find", {})

    def test_timeout_raises_transport_error(self):
        """A read timeout (TimeoutError) raises McpTransportError."""
        m = mcp()

        def handler(req, *a, **k):
            raise TimeoutError("timed out")

        with _patched_urlopen(handler):
            with pytest.raises(m.McpTransportError):
                m.call_tool("http://x", "t", "records_find", {})

    def test_malformed_sse_raises_transport_error(self):
        """A 200 reply with a malformed SSE body raises McpTransportError → fallback."""
        m = mcp()
        bad = b"event: message\ndata: {broken json,,\n\n"

        with _patched_urlopen(lambda req, *a, **k: _FakeResponse(bad, 200, "text/event-stream")):
            with pytest.raises(m.McpTransportError):
                m.call_tool("http://x", "t", "records_find", {})


# ===========================================================================
# T3 — MockKonecty /mcp route smoke tests (client + mock integration)
# ===========================================================================


class TestMockMcpRoute:
    def test_records_find_sse_route(self):
        """POST /mcp records_find over the mock returns filtered structuredContent."""
        m = mcp()
        mk = MockKonecty()
        fil = {"match": "and", "conditions": [{"term": "_id", "operator": "equals", "value": "cid001"}]}
        with mk.patch():
            result = m.call_tool("http://mock.local", "t", "records_find",
                                 {"document": "Contact", "filter": fil})
        sc = result["structuredContent"]
        assert sc["total"] == 1
        assert sc["records"][0]["_id"] == "cid001"
        assert "pagination" in sc

    def test_query_json_sse_route(self):
        """POST /mcp query_json returns structuredContent {records, meta, total}."""
        m = mcp()
        mk = MockKonecty()
        with mk.patch():
            result = m.call_tool("http://mock.local", "t", "query_json", {"document": "Contact"})
        sc = result["structuredContent"]
        assert sc["total"] == 2
        assert sc["meta"]["document"] == "Contact"
        assert len(sc["records"]) == 2

    def test_query_sql_sse_route(self):
        """POST /mcp query_sql returns the 2-row Contact stub with meta."""
        m = mcp()
        mk = MockKonecty()
        with mk.patch():
            result = m.call_tool("http://mock.local", "t", "query_sql",
                                 {"sql": "SELECT * FROM Contact"})
        sc = result["structuredContent"]
        assert len(sc["records"]) == 2
        assert "meta" in sc

    @pytest.mark.parametrize("status", [403, 404, 429, 500])
    def test_fault_status_raises_http_error(self, status):
        """mcp_fault = <status> makes the route raise that HTTP status → McpHttpError."""
        m = mcp()
        mk = MockKonecty()
        mk.mcp_fault = status
        with mk.patch():
            with pytest.raises(m.McpHttpError) as ei:
                m.call_tool("http://mock.local", "t", "records_find", {"document": "Contact"})
        assert ei.value.status == status

    def test_fault_urlerror_raises_transport_error(self):
        m = mcp()
        mk = MockKonecty()
        mk.mcp_fault = "urlerror"
        with mk.patch():
            with pytest.raises(m.McpTransportError):
                m.call_tool("http://mock.local", "t", "records_find", {"document": "Contact"})

    def test_fault_badsse_raises_transport_error(self):
        m = mcp()
        mk = MockKonecty()
        mk.mcp_fault = "badsse"
        with mk.patch():
            with pytest.raises(m.McpTransportError):
                m.call_tool("http://mock.local", "t", "records_find", {"document": "Contact"})

    def test_fault_toolerror_raises_tool_error(self):
        m = mcp()
        mk = MockKonecty()
        mk.mcp_fault = "toolerror"
        with mk.patch():
            with pytest.raises(m.McpToolError):
                m.call_tool("http://mock.local", "t", "records_find", {"document": "Contact"})

    @pytest.mark.parametrize("method", ["GET", "DELETE"])
    def test_non_post_methods_405(self, method):
        """GET/DELETE /mcp → 405 (McpHttpError on the client side)."""
        mk = MockKonecty()
        with mk.patch():
            req = urllib.request.Request("http://mock.local/mcp", method=method)
            with pytest.raises(urllib.error.HTTPError) as ei:
                urllib.request.urlopen(req)
        assert ei.value.code == 405
