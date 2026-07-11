#!/usr/bin/env python3
"""
Minimal stdlib MCP-over-HTTP client for the Konecty User MCP server.

The server runs the Streamable-HTTP transport **statelessly** (a fresh
``McpServer`` per POST) with SSE responses (no ``enableJsonResponse``). This
client therefore:

  * POSTs a JSON-RPC 2.0 ``tools/call`` directly (no ``initialize`` handshake),
  * sends ``Accept: application/json, text/event-stream`` (both required),
  * parses the ``text/event-stream`` reply (SSE) — with a defensive plain-JSON
    fallback so a future JSON-mode server still works,
  * raises typed errors so the caller can branch surface-vs-fallback:
      - ``McpHttpError`` (non-2xx HTTP; carries ``.status``),
      - ``McpTransportError`` (connection/timeout/DNS/malformed-SSE),
      - ``McpToolError`` (HTTP 200 but JSON-RPC ``error`` or ``result.isError``).

Stdlib only: ``json``, ``urllib``.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

MCP_PROTOCOL_VERSION = "2025-06-18"


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class McpError(Exception):
    """Base class for all MCP client errors."""


class McpHttpError(McpError):
    """Non-2xx HTTP response from ``POST /mcp`` (carries ``.status``)."""

    def __init__(self, status: int, body: str = "") -> None:
        self.status = status
        self.body = body
        super().__init__(f"MCP HTTP {status}: {body}")


class McpTransportError(McpError):
    """Connection error, timeout, DNS failure, or malformed/truncated SSE."""


class McpToolError(McpError):
    """HTTP 200 but a JSON-RPC ``error`` object or ``result.isError`` is set."""

    def __init__(self, code: Any, message: str, details: Any = None) -> None:
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"MCP tool error {code}: {message}")


# ---------------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------------


def parse_sse(body: bytes) -> list[dict]:
    """Parse an SSE ``text/event-stream`` body into JSON-RPC messages.

    Frames are separated by a blank line (``\\n\\n``). Within a frame, every
    ``data:`` line is collected (a single logical payload may span several
    ``data:`` lines) and concatenated; other fields (``event:``/``id:``) are
    ignored. Each frame's data payload is JSON-parsed into one message.

    Returns the list of parsed JSON-RPC messages (``[]`` when the body carries
    no ``data:`` payloads). Raises :class:`McpTransportError` when a data frame
    is present but its payload is not valid JSON (malformed/truncated stream).
    """
    if isinstance(body, (bytes, bytearray)):
        text = bytes(body).decode("utf-8", errors="replace")
    else:
        text = str(body)

    # Normalise line endings so \r\n and \r frame separators still split.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    messages: list[dict] = []
    for frame in text.split("\n\n"):
        data_parts: list[str] = []
        for line in frame.split("\n"):
            if line.startswith("data:"):
                chunk = line[len("data:"):]
                # SSE: strip a single leading space after the colon, if present.
                if chunk.startswith(" "):
                    chunk = chunk[1:]
                data_parts.append(chunk)

        if not data_parts:
            continue
        payload = "".join(data_parts)
        if not payload.strip():
            continue
        try:
            messages.append(json.loads(payload))
        except (json.JSONDecodeError, ValueError) as exc:
            raise McpTransportError(f"malformed SSE data frame: {exc}")

    return messages


# ---------------------------------------------------------------------------
# tools/call over stateless Streamable HTTP
# ---------------------------------------------------------------------------


def _messages_from_body(raw: bytes, content_type: str) -> list[dict]:
    """Turn a raw response body into JSON-RPC messages.

    SSE (``text/event-stream``) is the Konecty default. A plain ``application/
    json`` body is also accepted (defensive, for a future JSON-mode server); an
    absent/ambiguous content-type is probed as JSON first, then SSE.
    """
    ct = (content_type or "").lower()
    if "text/event-stream" in ct:
        return parse_sse(raw)

    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Not plain JSON — fall back to SSE parsing (which raises on garbage).
        return parse_sse(raw)
    return parsed if isinstance(parsed, list) else [parsed]


def _first_text(result: dict) -> str:
    """Extract the first ``content[].text`` block from a tool result, if any."""
    content = result.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return str(block.get("text", ""))
    return ""


def _result_from_messages(messages: list) -> dict:
    """Locate the JSON-RPC reply (id==1) and return its tool ``result``.

    Raises :class:`McpToolError` on a JSON-RPC ``error`` or ``result.isError``;
    :class:`McpTransportError` when no reply message is present.
    """
    hit = None
    for msg in messages:
        if isinstance(msg, dict) and msg.get("id") == 1 and ("result" in msg or "error" in msg):
            hit = msg
            break
    if hit is None:
        for msg in messages:
            if isinstance(msg, dict) and ("result" in msg or "error" in msg):
                hit = msg
                break
    if hit is None:
        raise McpTransportError("no JSON-RPC response message found in reply")

    if "error" in hit:
        err = hit.get("error") or {}
        raise McpToolError(
            err.get("code"), err.get("message", "unknown MCP error"), err.get("data")
        )

    result = hit.get("result")
    if isinstance(result, dict) and result.get("isError"):
        raise McpToolError("TOOL_ERROR", _first_text(result) or "tool returned isError", result)
    return result if isinstance(result, dict) else {}


def call_tool(
    base_url: str,
    token: str,
    name: str,
    arguments: dict | None = None,
    *,
    timeout: int = 30,
) -> dict:
    """Call an MCP tool over ``POST {base_url}/mcp`` and return its ``result``.

    Sends a bare JSON-RPC 2.0 ``tools/call`` (no ``initialize`` handshake) with
    ``Accept: application/json, text/event-stream`` (both required), a Bearer
    header, and ``authTokenId`` in the tool arguments (server prefers the arg).

    Raises :class:`McpHttpError` (non-2xx, carries ``.status``),
    :class:`McpTransportError` (connection/timeout/DNS/malformed-SSE), or
    :class:`McpToolError` (JSON-RPC ``error`` / ``result.isError``).
    """
    url = base_url.rstrip("/") + "/mcp"
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": {**(arguments or {}), "authTokenId": token},
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        raise McpHttpError(exc.code, err_body)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise McpTransportError(f"transport failure: {exc}")

    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    messages = _messages_from_body(raw, content_type)
    return _result_from_messages(messages)
