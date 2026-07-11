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
