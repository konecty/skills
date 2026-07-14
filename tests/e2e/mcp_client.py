"""Minimal stateless MCP client for the e2e pseudo-agent (stdlib only).

Speaks JSON-RPC 2.0 over Streamable HTTP POST against Konecty's MCP servers
(``/mcp`` and ``/admin-mcp``). Konecty runs the transport in **stateless** mode
(``sessionIdGenerator: undefined`` — see ``src/mcp/shared/transport.ts`` in the
Konecty repo): a fresh server+transport pair is created per POST, GET/DELETE
return 405, and there is no ``Mcp-Session-Id`` handshake to carry.

The MCP SDK's Streamable HTTP transport requires the client to accept both
JSON and SSE (``Accept: application/json, text/event-stream``) and may answer
either as plain JSON or as an SSE body with a single ``message`` event — both
shapes are parsed here.

Auth: pass ``token`` to send ``Authorization: Bearer <token>`` (works for both
first-party ``authTokenId`` sessions and OAuth access tokens). The per-tool
``authTokenId`` argument path is exercised by passing it inside ``arguments``.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

PROTOCOL_VERSION = "2025-03-26"


class McpHttpError(Exception):
    """Non-2xx HTTP response from the MCP endpoint."""

    def __init__(self, status: int, body: str, headers: dict[str, str] | None = None):
        self.status = status
        self.body = body
        self.headers = headers or {}
        super().__init__(f"HTTP {status}: {body[:500]}")

    def json(self) -> Any:
        try:
            return json.loads(self.body)
        except (json.JSONDecodeError, ValueError):
            return None


class McpToolError(Exception):
    """JSON-RPC level error, or a tool result flagged ``isError``."""

    def __init__(self, message: str, code: int | None = None, data: Any = None):
        self.code = code
        self.data = data
        super().__init__(message)


@dataclass
class ToolResult:
    """Parsed ``tools/call`` result: both MCP response channels."""

    text: str
    structured: Any
    is_error: bool
    raw: dict = field(repr=False, default_factory=dict)


def _parse_sse(body: str) -> dict:
    """Extract the JSON-RPC message from an SSE body (single ``message`` event)."""
    for line in body.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:"):].strip())
    raise McpToolError(f"no data event in SSE body: {body[:300]!r}")


class McpClient:
    """One client per MCP endpoint URL (e.g. ``http://localhost:3200/mcp``)."""

    def __init__(self, url: str, token: str | None = None, timeout: float = 60.0):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._next_id = 0

    # ── transport ─────────────────────────────────────────────────────────
    def _post(self, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                content_type = resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            raise McpHttpError(exc.code, exc.read().decode("utf-8", "replace"), dict(exc.headers)) from exc

        if "text/event-stream" in content_type:
            return _parse_sse(body)
        return json.loads(body)

    def rpc(self, method: str, params: dict | None = None) -> Any:
        """Send one JSON-RPC request; return ``result`` or raise :class:`McpToolError`."""
        self._next_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            payload["params"] = params
        message = self._post(payload)
        if "error" in message:
            err = message["error"]
            raise McpToolError(err.get("message", "unknown error"), err.get("code"), err.get("data"))
        return message.get("result")

    def http_raw(self, method: str = "GET") -> tuple[int, str]:
        """Raw non-POST request — used to assert the 405 stateless contract."""
        req = urllib.request.Request(self.url, method=method)
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", "replace")

    # ── MCP surface ───────────────────────────────────────────────────────
    def initialize(self) -> dict:
        return self.rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "konecty-skills-e2e", "version": "1.0.0"},
            },
        )

    def tools_list(self) -> list[dict]:
        return self.rpc("tools/list").get("tools", [])

    def tool_names(self) -> set[str]:
        return {t["name"] for t in self.tools_list()}

    def call(self, name: str, arguments: dict | None = None, expect_error: bool = False) -> ToolResult:
        """``tools/call`` — returns both channels; raises unless ``expect_error``."""
        result = self.rpc("tools/call", {"name": name, "arguments": arguments or {}})
        content = result.get("content") or []
        text = "\n".join(part.get("text", "") for part in content if part.get("type") == "text")
        parsed = ToolResult(
            text=text,
            structured=result.get("structuredContent"),
            is_error=result.get("isError", False),
            raw=result,
        )
        if parsed.is_error and not expect_error:
            raise McpToolError(f"tool {name} failed: {text[:500]}")
        return parsed
