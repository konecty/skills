#!/usr/bin/env python3
"""
In-memory mock of the full Konecty HTTP surface used by konecty-data and
konecty-meta skill scripts.

Surfaces covered
----------------
/api/admin/meta/*           — original meta CRUD (document, list, view, access,
                              pivot, hook, namespace, doctor, reload)
/api/auth/*                 — login-options, request-otp, verify-otp
/rest/data/:document/*      — find (GET/POST), create (POST), update (PUT),
                              delete (DELETE)
/rest/query/json            — NDJSON cross-module query (used by find.py `query`,
                              update.py `_find_record`, delete.py `_fetch_one`,
                              create.py `lookup`)
/rest/query/sql             — NDJSON SQL query stub
/rest/query/explorer/modules — module list used by modules.py
/rest/file/upload/...       — multipart upload stub
/rest/file/delete/...       — file delete stub

Usage::

    from tests.e2e.mock_konecty import MockKonecty

    mk = MockKonecty()
    with mk.patch():
        # any code that calls urllib.request.urlopen is intercepted
        ...

    assert mk.has("Contact")               # meta store
    assert "cid001" in mk.records["Contact"]   # record store
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SEED_DIR = _REPO_ROOT / "e2e" / "fixtures" / "seed-metas"

# ---------------------------------------------------------------------------
# Valid types and hook names (mirrors konecty-meta scripts)
# ---------------------------------------------------------------------------

_VALID_TYPES = frozenset(
    ["document", "composite", "list", "view", "access", "pivot", "hook", "namespace"]
)

_VALID_HOOKS = frozenset(
    ["scriptBeforeValidation", "validationData", "validationScript", "scriptAfterSave"]
)

# Types whose _id is just <document> (no :<type>:<name> suffix)
_DOC_TYPES = frozenset(["document", "composite"])

# Base path the meta skills hit
_META_BASE = "/api/admin/meta"

# Sentinel _id that triggers a foreign-key error on DELETE
_FK_SENTINEL_ID = "__fk_error__"


# ---------------------------------------------------------------------------
# Minimal fake HTTP response (context-manager compatible)
# ---------------------------------------------------------------------------


class _FakeResponse:
    """Mimics the object returned by urllib.request.urlopen on 2xx."""

    def __init__(self, body: bytes, status: int = 200, content_type: str = "application/json") -> None:
        self._body = body
        self.status = status
        self.code = status
        self._content_type = content_type
        self.headers = _FakeHeaders(content_type)

    # Support both attribute and method access used by different callers.
    def getcode(self) -> int:
        return self.code

    def read(self) -> bytes:
        return self._body

    # Context-manager protocol
    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _FakeHeaders:
    """Minimal headers object that supports .get()."""

    def __init__(self, content_type: str = "application/json") -> None:
        self._ct = content_type

    def get(self, key: str, default: str = "") -> str:
        if key.lower() in ("content-type", "content_type"):
            return self._ct
        return default


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _json_response(data: Any, status: int = 200) -> _FakeResponse:
    return _FakeResponse(json.dumps(data, ensure_ascii=False).encode("utf-8"), status)


def _ndjson_response(lines: list[Any]) -> _FakeResponse:
    """Return NDJSON (application/x-ndjson) — one JSON object per line."""
    body = "\n".join(json.dumps(line, ensure_ascii=False) for line in lines).encode("utf-8")
    return _FakeResponse(body, 200, "application/x-ndjson")


def _ok(status: int = 200, **extra: Any) -> _FakeResponse:
    return _json_response({"success": True, **extra}, status)


def _err(status: int, *messages: str) -> urllib.error.HTTPError:
    body = json.dumps({"success": False, "errors": list(messages)}).encode("utf-8")
    return urllib.error.HTTPError(
        url="", code=status, msg=str(status), hdrs={}, fp=io.BytesIO(body)  # type: ignore[arg-type]
    )


def _meta_id(document: str, type_: str, name: str) -> str:
    """Compute canonical _id from path segments."""
    if type_ in _DOC_TYPES:
        return document
    return f"{document}:{type_}:{name}"


# ---------------------------------------------------------------------------
# JS-hook validation rules (mirror the real backend's checks)
# ---------------------------------------------------------------------------


def _validate_js_hook(hook_name: str, code: str) -> list[str]:
    """Return a list of error strings (empty = valid)."""
    errors: list[str] = []
    if not code or not code.strip():
        errors.append("Code must not be empty")
        return errors
    if "//" in code:
        errors.append("Single-line comments (//) are not allowed")
    if "/*" in code or "*/" in code:
        errors.append("Block comments (/* */) are not allowed")
    if hook_name in ("scriptBeforeValidation", "validationScript"):
        if "return" not in code:
            errors.append(f"{hook_name} must contain a 'return' statement")
    return errors


# ---------------------------------------------------------------------------
# Record store helpers
# ---------------------------------------------------------------------------

# Seed data: two Contact records
_SEED_RECORDS: dict[str, dict[str, dict]] = {
    "Contact": {
        "cid001": {
            "_id": "cid001",
            "code": 1,
            "name": "Alice Test",
            "status": "lead",
            "_updatedAt": {"$date": "2026-01-01T00:00:00.000Z"},
        },
        "cid002": {
            "_id": "cid002",
            "code": 2,
            "name": "Bob Test",
            "status": "client",
            "_updatedAt": {"$date": "2026-01-02T00:00:00.000Z"},
        },
    },
    "Activity": {},
}

# Counter for deterministic ID and code generation
_ID_COUNTER: dict[str, int] = {}


def _make_id(document: str) -> str:
    """Generate a deterministic record _id using a per-document counter."""
    counter = _ID_COUNTER.get(document, 0) + 1
    _ID_COUNTER[document] = counter
    return f"{document[:3].lower()}{counter:05d}"


def _make_code(records: dict[str, dict]) -> int:
    """Return max(code) + 1 across all records in a document store."""
    codes = [r.get("code", 0) for r in records.values() if isinstance(r.get("code"), int)]
    return max(codes, default=0) + 1


def _bump_updated_at(counter: list[int]) -> dict:
    """Return a new _updatedAt $date string, incremented by counter."""
    counter[0] += 1
    return {"$date": f"2026-06-{counter[0]:02d}T00:00:00.000Z"}


def _extract_date_string(raw: Any) -> str:
    """Unwrap a $date value to a plain string, handling nested dicts.

    Some scripts (e.g. update.py cmd_patch, delete.py _http_delete) wrap
    `_updatedAt` in ``{"$date": updated_at}`` without checking whether
    ``updated_at`` is already a ``{"$date": ...}`` dict. This helper
    extracts the innermost string so the optimistic-lock comparison works.
    """
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        inner = raw.get("$date", "")
        return _extract_date_string(inner)
    return ""


# Global update counter so bumped timestamps are unique
_UPDATE_COUNTER = [0]


def _match_filter(record: dict, fil: dict | None) -> bool:
    """
    Minimal filter evaluation.
    Supports {match:"and", conditions:[{term, operator:"equals", value}]}
    where term is "_id" or "code".
    """
    if not fil:
        return True
    conditions = fil.get("conditions", [])
    match = fil.get("match", "and")

    results = []
    for cond in conditions:
        term = cond.get("term", "")
        operator = cond.get("operator", "equals")
        value = cond.get("value")
        field_val = record.get(term)
        if operator == "equals":
            results.append(field_val == value)
        elif operator == "in":
            results.append(field_val in (value if isinstance(value, list) else [value]))
        else:
            # Unknown operator — treat as pass-through (include record)
            results.append(True)

    if not results:
        return True
    return all(results) if match == "and" else any(results)


def _project(record: dict, fields_str: str | None) -> dict:
    """Return a copy of record with only the requested fields (plus _id always)."""
    if not fields_str:
        return copy.deepcopy(record)
    wanted = {f.strip() for f in fields_str.split(",") if f.strip()}
    wanted.add("_id")
    return {k: v for k, v in record.items() if k in wanted}


# ---------------------------------------------------------------------------
# MockKonecty
# ---------------------------------------------------------------------------


class MockKonecty:
    """
    In-memory mock of the full Konecty HTTP surface used by konecty-data and
    konecty-meta skill scripts.

    Parameters
    ----------
    seed_dir:
        Directory containing ``*.json`` files to load into the meta store on
        construction.  Each file may be either a JSON **list** of MetaObjects
        or a single MetaObject dict.  Defaults to
        ``<repo-root>/e2e/fixtures/seed-metas/``.
    """

    def __init__(self, seed_dir: "str | Path | None" = None) -> None:
        # --- Meta store (keyed by meta _id) ---
        self._store: dict[str, dict] = {}
        sd = Path(seed_dir) if seed_dir is not None else _SEED_DIR
        if sd.is_dir():
            for json_file in sorted(sd.glob("*.json")):
                with json_file.open("r", encoding="utf-8") as fh:
                    payload = json.load(fh)
                items: list[dict] = payload if isinstance(payload, list) else [payload]
                for item in items:
                    meta_id = item.get("_id")
                    if meta_id:
                        self._store[meta_id] = copy.deepcopy(item)

        # --- Record store (keyed by document → _id → record) ---
        self.records: dict[str, dict[str, dict]] = copy.deepcopy(_SEED_RECORDS)

    # ------------------------------------------------------------------
    # Public helpers for test assertions
    # ------------------------------------------------------------------

    def has(self, meta_id: str) -> bool:
        """Return True if *meta_id* is present in the meta store."""
        return meta_id in self._store

    def get(self, meta_id: str) -> "dict | None":
        """Return a deep copy of the stored meta, or None."""
        item = self._store.get(meta_id)
        return copy.deepcopy(item) if item is not None else None

    # ------------------------------------------------------------------
    # Context-manager patch
    # ------------------------------------------------------------------

    @contextlib.contextmanager
    def patch(self):
        """Temporarily replace ``urllib.request.urlopen`` with self.urlopen."""
        original = urllib.request.urlopen
        urllib.request.urlopen = self.urlopen  # type: ignore[assignment]
        try:
            yield self
        finally:
            urllib.request.urlopen = original  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # urlopen entry point
    # ------------------------------------------------------------------

    def urlopen(self, req: Any, *args: Any, **kwargs: Any) -> Any:
        """
        Drop-in replacement for ``urllib.request.urlopen``.

        Parses method/path/body from *req*, routes to the appropriate handler,
        and returns a :class:`_FakeResponse` or raises
        :class:`urllib.error.HTTPError`.
        """
        full_url: str = req.full_url
        method: str = req.get_method().upper()

        parsed = urllib.parse.urlparse(full_url)
        raw_path: str = parsed.path
        query_string: str = parsed.query

        # --- Route by path prefix ---

        # /api/auth/...
        if raw_path.startswith("/api/auth/"):
            return self._route_auth(method, raw_path, req)

        # /api/admin/meta/...  (original meta handler)
        if _META_BASE in raw_path:
            return self._route_meta(method, raw_path, req)

        # /rest/data/...
        if raw_path.startswith("/rest/data/"):
            return self._route_data(method, raw_path, query_string, req)

        # /rest/query/...
        if raw_path.startswith("/rest/query/"):
            return self._route_query(method, raw_path, query_string, req)

        # /rest/file/...
        if raw_path.startswith("/rest/file/"):
            return self._route_file(method, raw_path, req)

        # /mcp  (User MCP — stateless Streamable HTTP, SSE responses)
        if raw_path == "/mcp":
            return self._route_mcp(method, req)

        raise _err(404, f"Path not routed by mock: {raw_path}")

    # ------------------------------------------------------------------
    # Body parser
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_body(req: Any) -> Any:
        """Attempt to JSON-parse the request body; return None if absent."""
        if req.data:
            try:
                return json.loads(req.data)
            except (json.JSONDecodeError, ValueError):
                raise _err(400, "Request body is not valid JSON")
        return None

    # ==================================================================
    # AUTH routes  /api/auth/...
    # ==================================================================

    def _route_auth(self, method: str, path: str, req: Any) -> _FakeResponse:
        """
        Handles:
          GET  /api/auth/login-options
          POST /api/auth/request-otp
          POST /api/auth/verify-otp
        """
        # /api/auth/login-options
        if path == "/api/auth/login-options" and method == "GET":
            return _json_response({
                "passwordEnabled": True,
                "emailOtpEnabled": True,
                "whatsAppOtpEnabled": False,
            })

        # /api/auth/request-otp
        if path == "/api/auth/request-otp" and method == "POST":
            return _json_response({"success": True, "message": "OTP sent (mock)"})

        # /api/auth/verify-otp
        if path == "/api/auth/verify-otp" and method == "POST":
            return _json_response({
                "success": True,
                "logged": True,
                "authId": "mock-token-123",
                "user": {"_id": "mock-user-id"},
            })

        raise _err(404, f"Auth path not found: {path}")

    # ==================================================================
    # META routes  /api/admin/meta/...
    # ==================================================================

    def _route_meta(self, method: str, raw_path: str, req: Any) -> _FakeResponse:
        base_idx = raw_path.find(_META_BASE)
        remainder = raw_path[base_idx + len(_META_BASE):]
        remainder = remainder.rstrip("/")
        if remainder:
            segments = [urllib.parse.unquote(s) for s in remainder.lstrip("/").split("/")]
        else:
            segments = []

        body = self._parse_body(req)
        return self._route(method, segments, body, raw_path)

    # ------------------------------------------------------------------
    # Router (original meta logic — preserved exactly, split for CC)
    # ------------------------------------------------------------------

    def _route(
        self,
        method: str,
        segments: list[str],
        body: Any,
        url: str,
    ) -> _FakeResponse:
        """Top-level meta dispatcher — detects path shape and delegates."""
        n = len(segments)

        # Special top-level POSTs with no document context
        special = self._route_meta_special(method, n, segments, body)
        if special is not None:
            return special

        # Root (no segments): GET lists all, anything else is 405
        if n == 0:
            if method == "GET":
                return self._handle_list_all()
            raise _err(405, f"Method {method} not allowed on /api/admin/meta")

        return self._route_meta_document(method, n, segments, body)

    def _route_meta_special(
        self,
        method: str,
        n: int,
        segments: list[str],
        body: Any,
    ) -> "_FakeResponse | None":
        """Handle special POST endpoints that don't follow the document pattern.

        Returns the response if the path matched, or None to fall through.
        """
        if method != "POST":
            return None

        # POST /api/admin/meta/doctor
        if n == 1 and segments[0] == "doctor":
            return self._handle_doctor(body)

        # POST /api/admin/meta/reload
        if n == 1 and segments[0] == "reload":
            return self._handle_reload()

        # POST /api/admin/meta/hook/validate
        if n == 2 and segments[0] == "hook" and segments[1] == "validate":
            return self._handle_hook_validate(body)

        return None

    def _route_meta_document(
        self,
        method: str,
        n: int,
        segments: list[str],
        body: Any,
    ) -> _FakeResponse:
        """Dispatch paths that start with /:document (n >= 1)."""
        document = segments[0]

        # GET /api/admin/meta/:document  (list all metas for document)
        if n == 1:
            if method == "GET":
                return self._handle_list_document(document)
            raise _err(405, f"Method {method} not allowed on /:document")

        type_ = segments[1]

        # Hook sub-routes: /:document/hook/:hookName
        if type_ == "hook":
            return self._route_meta_hook(method, document, n, segments, body)

        # Validate type before dispatching CRUD
        if type_ not in _VALID_TYPES:
            raise _err(400, f"Invalid type: {type_}")

        return self._route_meta_crud(method, document, type_, n, segments, body)

    def _route_meta_hook(
        self,
        method: str,
        document: str,
        n: int,
        segments: list[str],
        body: Any,
    ) -> _FakeResponse:
        """Handle /:document/hook/:hookName (GET, PUT, DELETE)."""
        if n < 3:
            raise _err(400, "Missing hook name")
        hook_name = segments[2]
        if method == "GET":
            return self._handle_hook_get(document, hook_name)
        if method == "PUT":
            return self._handle_hook_put(document, hook_name, body)
        if method == "DELETE":
            return self._handle_hook_delete(document, hook_name)
        raise _err(405, f"Method {method} not allowed on hook endpoint")

    def _route_meta_crud(
        self,
        method: str,
        document: str,
        type_: str,
        n: int,
        segments: list[str],
        body: Any,
    ) -> _FakeResponse:
        """Handle GET/PUT/DELETE for 2-segment (doc types) and 3-segment paths."""
        if n == 2:
            if type_ not in _DOC_TYPES:
                raise _err(400, f"Type '{type_}' requires a name segment; use /:document/:type/:name")
            name = document
            meta_id = document
            if method == "GET":
                return self._handle_get_meta(meta_id)
            if method == "PUT":
                return self._handle_put_meta(document, type_, name, meta_id, body)
            if method == "DELETE":
                return self._handle_delete_meta(meta_id)
            raise _err(405, f"Method {method} not allowed")

        if n == 3:
            name = segments[2]
            meta_id = _meta_id(document, type_, name)
            if method == "GET":
                return self._handle_get_meta(meta_id)
            if method == "PUT":
                return self._handle_put_meta(document, type_, name, meta_id, body)
            if method == "DELETE":
                return self._handle_delete_meta(meta_id)
            raise _err(405, f"Method {method} not allowed")

        raise _err(404, f"Unrecognised path with {n} segments")

    # ------------------------------------------------------------------
    # Meta handlers — read operations
    # ------------------------------------------------------------------

    def _handle_list_all(self) -> _FakeResponse:
        summaries = []
        for meta_id, meta in self._store.items():
            if meta.get("type") in _DOC_TYPES:
                summaries.append({
                    "_id": meta_id,
                    "name": meta.get("name", meta_id),
                    "type": meta.get("type"),
                    "label": meta.get("label"),
                })
        return _ok(data=summaries)

    def _handle_list_document(self, document: str) -> _FakeResponse:
        matches = [
            copy.deepcopy(m)
            for key, m in self._store.items()
            if key == document or key.startswith(f"{document}:")
        ]
        if not matches:
            raise _err(404, "Document not found")
        return _ok(data=matches)

    def _handle_get_meta(self, meta_id: str) -> _FakeResponse:
        item = self._store.get(meta_id)
        if item is None:
            raise _err(404, "Meta not found")
        return _ok(data=copy.deepcopy(item))

    # ------------------------------------------------------------------
    # Meta handlers — write operations
    # ------------------------------------------------------------------

    def _handle_put_meta(
        self,
        document: str,
        type_: str,
        name: str,
        meta_id: str,
        body: Any,
    ) -> _FakeResponse:
        if not isinstance(body, dict) or not body:
            raise _err(400, "Body must be a non-empty JSON object")

        existed = meta_id in self._store
        merged = copy.deepcopy(self._store.get(meta_id, {}))
        merged.update(body)
        merged["_id"] = meta_id
        merged["type"] = type_
        merged["name"] = name
        merged["document"] = document
        self._store[meta_id] = merged

        action = "updated" if existed else "created"
        status = 200 if existed else 201
        return _ok(status, action=action, _id=meta_id)

    def _handle_delete_meta(self, meta_id: str) -> _FakeResponse:
        if meta_id not in self._store:
            raise _err(404, "Meta not found")
        del self._store[meta_id]
        return _ok(action="deleted", _id=meta_id)

    # ------------------------------------------------------------------
    # Meta handlers — hook operations
    # ------------------------------------------------------------------

    def _handle_hook_get(self, document: str, hook_name: str) -> _FakeResponse:
        if hook_name not in _VALID_HOOKS:
            raise _err(400, f"Invalid hook name: {hook_name}")
        doc_meta = self._store.get(document)
        if doc_meta is None:
            raise _err(404, f"Document not found: {document}")
        value = doc_meta.get(hook_name)
        if value is None:
            raise _err(404, f"Hook {hook_name} not defined on {document}")
        return _ok(data={"hookName": hook_name, "value": value})

    def _handle_hook_put(self, document: str, hook_name: str, body: Any) -> _FakeResponse:
        if hook_name not in _VALID_HOOKS:
            raise _err(400, f"Invalid hook name: {hook_name}")
        doc_meta = self._store.get(document)
        if doc_meta is None:
            raise _err(404, f"Document not found: {document}")
        if not isinstance(body, dict) or not body:
            raise _err(400, "Body must be a non-empty JSON object")

        if hook_name == "validationData":
            value = body.get("value", body)
        else:
            code = body.get("code", "")
            errors = _validate_js_hook(hook_name, str(code))
            if errors:
                raise _err(400, *errors)
            value = code

        self._store[document][hook_name] = value
        return _ok(action="updated", hookName=hook_name)

    def _handle_hook_delete(self, document: str, hook_name: str) -> _FakeResponse:
        if hook_name not in _VALID_HOOKS:
            raise _err(400, f"Invalid hook name: {hook_name}")
        doc_meta = self._store.get(document)
        if doc_meta is None:
            raise _err(404, f"Document not found: {document}")
        doc_meta.pop(hook_name, None)
        return _ok(action="deleted", hookName=hook_name)

    # ------------------------------------------------------------------
    # Meta handlers — special POST endpoints
    # ------------------------------------------------------------------

    def _handle_hook_validate(self, body: Any) -> _FakeResponse:
        if not isinstance(body, dict):
            raise _err(400, "Body must be a JSON object")
        hook_name = body.get("hookName", "")
        if hook_name not in _VALID_HOOKS:
            raise _err(400, f"Invalid hook name: {hook_name}")

        doc_name = body.get("document")
        if doc_name is not None:
            if doc_name not in self._store:
                raise _err(404, f"Document not found: {doc_name}")

        if hook_name == "validationData":
            return _ok(valid=True, errors=[])

        code = body.get("code", "")
        errors = _validate_js_hook(hook_name, str(code))
        valid = len(errors) == 0
        return _ok(valid=valid, errors=errors)

    def _handle_doctor(self, body: Any) -> _FakeResponse:
        doc_filter: "str | None" = None
        if body is not None:
            if not isinstance(body, dict):
                raise _err(400, "Body must be a JSON object or empty")
            doc_filter = body.get("document")
            if doc_filter is not None and not isinstance(doc_filter, str):
                raise _err(400, "'document' must be a string")

        if doc_filter is not None:
            metas = [
                m
                for k, m in self._store.items()
                if k == doc_filter or k.startswith(f"{doc_filter}:")
            ]
        else:
            metas = list(self._store.values())

        total = len(metas)
        return _ok(
            summary={"total": total, "valid": total, "warnings": 0, "errors": 0},
            issues=[],
        )

    def _handle_reload(self) -> _FakeResponse:
        return _ok(action="reloaded")

    # ==================================================================
    # DATA routes  /rest/data/:document/...
    # ==================================================================

    def _route_data(self, method: str, path: str, query_string: str, req: Any) -> _FakeResponse:
        """
        Dispatch /rest/data/:document[/find | /<id>].

        Path shapes:
          GET  /rest/data/:document/find           — find (no filter)
          POST /rest/data/:document/find           — find (with filter)
          POST /rest/data/:document                — create
          PUT  /rest/data/:document                — update
          DELETE /rest/data/:document             — delete
        """
        # Strip leading /rest/data/
        tail = path[len("/rest/data/"):].strip("/")
        parts = tail.split("/", 1)
        document = parts[0]
        sub = parts[1] if len(parts) > 1 else ""

        body = self._parse_body(req)

        if sub == "find":
            return self._handle_data_find(document, method, body, query_string)

        if not sub:
            if method == "POST":
                return self._handle_data_create(document, body)
            if method == "PUT":
                return self._handle_data_update(document, body)
            if method == "DELETE":
                return self._handle_data_delete(document, body)

        raise _err(404, f"Data path not handled: {path}")

    def _handle_data_find(
        self,
        document: str,
        method: str,
        body: Any,
        query_string: str,
    ) -> _FakeResponse:
        """
        GET /rest/data/:document/find  — no filter, optional params in QS
        POST /rest/data/:document/find — body: {filter?, fields?, limit?, start?, sort?}

        Response: {"success": true, "data": [...], "total": N}
        """
        doc_records = self.records.get(document, {})

        fil = None
        fields_str = None
        limit = 50
        start = 0

        if method == "POST" and isinstance(body, dict):
            fil = body.get("filter")
            fields_str = body.get("fields")
            limit = body.get("limit", limit)
            start = body.get("start", start)
        elif method == "GET" and query_string:
            params = urllib.parse.parse_qs(query_string)
            fields_str = params.get("fields", [None])[0]
            try:
                limit = int(params.get("limit", [50])[0])
            except (ValueError, TypeError):
                limit = 50
            try:
                start = int(params.get("start", [0])[0])
            except (ValueError, TypeError):
                start = 0

        matched = [
            _project(r, fields_str)
            for r in doc_records.values()
            if _match_filter(r, fil)
        ]

        # Pagination
        total = len(matched)
        if limit == -1:
            page = matched[start:]
        else:
            page = matched[start: start + limit]

        return _json_response({"success": True, "data": page, "total": total})

    def _handle_data_create(self, document: str, body: Any) -> _FakeResponse:
        """
        POST /rest/data/:document
        Body: {<field>: <value>, ...}  (scripts send the payload directly, not wrapped in 'data')

        On success:  {"success": true, "data": [<created record>]}
        On sentinel: {"success": false, "errors": [{"message": "forced error"}]}
        """
        if not isinstance(body, dict):
            raise _err(400, "Body must be a JSON object")

        # Error sentinel
        if body.get("__force_error__"):
            return _json_response({"success": False, "errors": [{"message": "forced error"}]})

        doc_records = self.records.setdefault(document, {})
        new_id = _make_id(document)
        new_code = _make_code(doc_records)
        _UPDATE_COUNTER[0] += 1
        new_record: dict = {
            "_id": new_id,
            "code": new_code,
            "_updatedAt": {"$date": f"2026-06-{min(_UPDATE_COUNTER[0], 28):02d}T12:00:00.000Z"},
        }
        new_record.update({k: v for k, v in body.items() if k not in ("_id", "code", "_updatedAt")})
        doc_records[new_id] = new_record

        return _json_response({"success": True, "data": [copy.deepcopy(new_record)]})

    def _handle_data_update(self, document: str, body: Any) -> _FakeResponse:
        """
        PUT /rest/data/:document
        Body: {"ids": [{"_id": ..., "_updatedAt": {"$date": ...}}], "data": {...}}

        On success:       {"success": true, "data": [<updated record>]}
        On stale lock:    {"success": false, "errors": [{"message": "... new version ..."}]}
        """
        if not isinstance(body, dict):
            raise _err(400, "Body must be a JSON object")

        ids = body.get("ids", [])
        data = body.get("data", {})
        if not ids:
            raise _err(400, "ids must be a non-empty array")

        doc_records = self.records.get(document, {})
        updated: list[dict] = []

        for id_entry in ids:
            rid = id_entry.get("_id")
            client_ts_raw = id_entry.get("_updatedAt", {})
            # Normalise: accept string, {"$date": str}, or nested {"$date": {"$date": str}}
            client_ts = _extract_date_string(client_ts_raw)

            record = doc_records.get(rid)
            if record is None:
                return _json_response({
                    "success": False,
                    "errors": [{"message": f"Record not found: {rid}"}],
                })

            stored_ts = _extract_date_string(record.get("_updatedAt", {}))

            if client_ts and client_ts != stored_ts:
                return _json_response({
                    "success": False,
                    "errors": [{"message": "Record has a new version. Please fetch again before updating."}],
                })

            _UPDATE_COUNTER[0] += 1
            new_ts = {"$date": f"2026-06-{min(_UPDATE_COUNTER[0], 28):02d}T12:00:00.000Z"}
            record.update(data)
            record["_updatedAt"] = new_ts
            updated.append(copy.deepcopy(record))

        return _json_response({"success": True, "data": updated})

    def _handle_data_delete(self, document: str, body: Any) -> _FakeResponse:
        """
        DELETE /rest/data/:document
        Body: {"ids": [{"_id": ..., "_updatedAt": {"$date": ...}}]}

        On success:         {"success": true, "data": [<deleted id>, ...]}
        On FK sentinel:     {"success": false, "errors": [{"message": "... referenced by ..."}]}
        On stale lock:      {"success": false, "errors": [{"message": "... new version ..."}]}
        """
        if not isinstance(body, dict):
            raise _err(400, "Body must be a JSON object")

        ids = body.get("ids", [])
        if not ids:
            raise _err(400, "ids must be a non-empty array")

        doc_records = self.records.get(document, {})
        deleted_ids: list[str] = []

        for id_entry in ids:
            rid = id_entry.get("_id")

            # Foreign-key sentinel
            if rid == _FK_SENTINEL_ID:
                return _json_response({
                    "success": False,
                    "errors": [{"message": f"Cannot delete: record is referenced by another module"}],
                })

            client_ts_raw = id_entry.get("_updatedAt", {})
            # Normalise: accept string, {"$date": str}, or nested {"$date": {"$date": str}}
            client_ts = _extract_date_string(client_ts_raw)

            record = doc_records.get(rid)
            if record is None:
                return _json_response({
                    "success": False,
                    "errors": [{"message": f"Record not found: {rid}"}],
                })

            stored_ts = _extract_date_string(record.get("_updatedAt", {}))

            if client_ts and client_ts != stored_ts:
                return _json_response({
                    "success": False,
                    "errors": [{"message": "Record has a new version. Please fetch again before deleting."}],
                })

            del doc_records[rid]
            deleted_ids.append(rid)

        return _json_response({"success": True, "data": deleted_ids})

    # ==================================================================
    # QUERY routes  /rest/query/...
    # ==================================================================

    def _route_query(self, method: str, path: str, query_string: str, req: Any) -> _FakeResponse:
        """
        /rest/query/json            — NDJSON cross-module query
        /rest/query/sql             — NDJSON SQL stub
        /rest/query/explorer/modules — module list
        """
        if path == "/rest/query/explorer/modules":
            return self._handle_query_modules(query_string)

        body = self._parse_body(req)

        if path == "/rest/query/json" and method == "POST":
            return self._handle_query_json(body)

        if path == "/rest/query/sql" and method == "POST":
            return self._handle_query_sql(body)

        raise _err(404, f"Query path not handled: {path}")

    def _handle_query_json(self, body: Any) -> _FakeResponse:
        """
        POST /rest/query/json
        Body: {document, filter?, fields?, limit?, start?, includeMeta?, includeTotal?}

        Response: NDJSON — one record per line, plus optional
        {"_meta": {"success": true, "total": N}} line.

        Scripts parse: [r for r in lines if "_meta" not in r]
        meta_line: next((r for r in lines if "_meta" in r), None)
        """
        if not isinstance(body, dict):
            raise _err(400, "Body must be a JSON object")

        document = body.get("document", "")
        fil = body.get("filter")
        fields_str = body.get("fields")
        limit = body.get("limit", 1000)
        start = body.get("start", 0)
        include_meta = body.get("includeMeta", False)
        include_total = body.get("includeTotal", True)

        doc_records = self.records.get(document, {})
        matched = [
            _project(r, fields_str)
            for r in doc_records.values()
            if _match_filter(r, fil)
        ]
        total = len(matched)
        if limit == -1:
            page = matched[start:]
        else:
            page = matched[start: start + limit]

        lines: list[Any] = list(page)

        # Append _meta line when includeMeta=True or includeTotal is not False
        # (Scripts check: meta_line = next((r for r in result if "_meta" in r), None))
        if include_meta or include_total:
            meta_obj: dict = {"success": True}
            if include_total:
                meta_obj["total"] = total
            lines.append({"_meta": meta_obj})

        return _ndjson_response(lines)

    def _handle_query_sql(self, body: Any) -> _FakeResponse:
        """
        POST /rest/query/sql
        Body: {sql, includeMeta?, includeTotal?}

        Returns a stub NDJSON with two Contact rows and a _meta line.
        """
        if not isinstance(body, dict):
            raise _err(400, "Body must be a JSON object")

        include_total = body.get("includeTotal", True)

        rows = list(self.records.get("Contact", {}).values())[:2]
        lines: list[Any] = [copy.deepcopy(r) for r in rows]
        if include_total:
            lines.append({"_meta": {"success": True, "total": len(rows)}})
        return _ndjson_response(lines)

    def _handle_query_modules(self, query_string: str) -> _FakeResponse:
        """
        GET /rest/query/explorer/modules?lang=...

        modules.py calls: result.get("data", {}).get("modules", [])
        Each module dict: {document, label, fields: [...], reverseLookups: [...]}

        The script then accesses:
          m["document"], m["label"], m.get("fields", []), m.get("reverseLookups", [])
        And for each field:
          f["name"], f["type"], f["label"], f.get("document"), f.get("descriptionFields"),
          f.get("options")
        """
        modules = [
            {
                "document": "Contact",
                "label": "Contato",
                "fields": [
                    {"name": "_id",        "type": "text",       "label": "ID"},
                    {"name": "code",       "type": "autoNumber", "label": "Código"},
                    {"name": "name",       "type": "personName", "label": "Nome"},
                    {"name": "status",     "type": "picklist",   "label": "Situação",
                     "options": {"lead": "Lead", "client": "Cliente"}},
                    {"name": "picture",    "type": "file",       "label": "Imagem"},
                    {"name": "mainContact","type": "lookup",     "label": "Contato Principal",
                     "document": "Contact", "descriptionFields": ["code", "name.full"]},
                ],
                "reverseLookups": [
                    {"document": "Activity", "lookup": "contact", "label": "Atividades"},
                ],
            },
            {
                "document": "Activity",
                "label": "Atividade",
                "fields": [
                    {"name": "_id",      "type": "text",     "label": "ID"},
                    {"name": "code",     "type": "autoNumber","label": "Código"},
                    {"name": "subject",  "type": "text",     "label": "Assunto"},
                    {"name": "contact",  "type": "lookup",   "label": "Contato",
                     "document": "Contact", "descriptionFields": ["code", "name.full"]},
                ],
                "reverseLookups": [],
            },
            {
                "document": "Product",
                "label": "Produto",
                "fields": [
                    {"name": "_id",    "type": "text",       "label": "ID"},
                    {"name": "code",   "type": "autoNumber", "label": "Código"},
                    {"name": "name",   "type": "text",       "label": "Nome"},
                    {"name": "status", "type": "picklist",   "label": "Status",
                     "options": {"active": "Ativo", "inactive": "Inativo"}},
                ],
                "reverseLookups": [],
            },
        ]
        return _json_response({"success": True, "data": {"modules": modules}})

    # ==================================================================
    # FILE routes  /rest/file/...
    # ==================================================================

    def _route_file(self, method: str, path: str, req: Any) -> _FakeResponse:
        """
        POST /rest/file/upload/:namespace/:accessId/:document/:recordId/:fieldName
        DELETE /rest/file/delete/:namespace/:accessId/:document/:recordId/:fieldName/:fileName
        """
        if path.startswith("/rest/file/upload/") and method == "POST":
            return self._handle_file_upload(path)

        if path.startswith("/rest/file/delete/") and method == "DELETE":
            return self._handle_file_delete(path)

        raise _err(404, f"File path not handled: {path}")

    def _handle_file_upload(self, path: str) -> _FakeResponse:
        """
        POST /rest/file/upload/ns/access/:document/:recordId/:fieldName

        upload.py parses the response via _extract_stored_metadata:
          result.get("coreResponse") → {key, name, size, kind, etag, coreResponse: <record>}

        Returns:
          {"success": true, "coreResponse": {"key":..., "name":..., "size":..., "kind":...,
                                              "etag":..., "coreResponse": {<record snapshot>}}}
        """
        # Path: /rest/file/upload/<ns>/<access>/<doc>/<recordId>/<field>
        parts = path[len("/rest/file/upload/"):].split("/")
        # parts = [ns, access, document, recordId, fieldName]
        document = parts[2] if len(parts) > 2 else "Contact"
        record_id = parts[3] if len(parts) > 3 else "unknown"
        field_name = parts[4] if len(parts) > 4 else "picture"

        file_key = f"{document}/{record_id}/{field_name}/mock_upload_001.jpg"
        file_meta = {
            "key":  file_key,
            "name": "mock_upload_001.jpg",
            "size": 10240,
            "kind": "image/jpeg",
            "etag": "abc123mock",
        }
        # The inner coreResponse mirrors the full record snapshot
        record_snapshot = copy.deepcopy(
            self.records.get(document, {}).get(record_id, {"_id": record_id})
        )
        record_snapshot[field_name] = [file_meta]

        return _json_response({
            "success": True,
            "_id": record_id,
            "_updatedAt": self.records.get(document, {}).get(record_id, {}).get(
                "_updatedAt", {"$date": "2026-06-01T00:00:00.000Z"}
            ),
            "coreResponse": {
                **file_meta,
                "coreResponse": record_snapshot,
            },
        })

    def _handle_file_delete(self, path: str) -> _FakeResponse:
        """
        DELETE /rest/file/delete/ns/access/:document/:recordId/:fieldName/:fileName
        → {"success": true}
        """
        return _json_response({"success": True})

    # ==================================================================
    # MCP route  /mcp  (User MCP — stateless Streamable HTTP, SSE)
    # ==================================================================

    def _route_mcp(self, method: str, req: Any) -> _FakeResponse:
        """
        POST /mcp — JSON-RPC 2.0 ``tools/call``; SSE (``text/event-stream``) reply
        wrapping the tool ``result`` (``structuredContent`` + ``content``).

        Fault injection (drives the dispatcher's REST-fallback matrix): set
        ``mock_konecty.mcp_fault`` to one of:
          - ``403`` / ``404`` / ``429`` / ``500`` (int) → raises that HTTP status,
          - ``"urlerror"``  → raises ``urllib.error.URLError`` (connection failure),
          - ``"badsse"``    → returns a 200 with a malformed SSE body,
          - ``"toolerror"`` → returns a 200 SSE whose ``result.isError`` is true.
        GET/DELETE /mcp → 405.
        """
        if method != "POST":
            raise _err(405, f"Method {method} not allowed on /mcp")

        fault = getattr(self, "mcp_fault", None)
        if fault is not None:
            return self._mcp_apply_fault(fault)

        body = self._parse_body(req)
        if not isinstance(body, dict):
            raise _err(400, "MCP body must be a JSON object")

        params = body.get("params", {}) or {}
        name = params.get("name")
        arguments = params.get("arguments", {}) or {}

        if name == "records_find":
            result = self._mcp_records_find(arguments)
        elif name == "query_json":
            result = self._mcp_query_json(arguments)
        elif name == "query_sql":
            result = self._mcp_query_sql(arguments)
        else:
            result = {
                "content": [{"type": "text", "text": f"unknown tool: {name}"}],
                "isError": True,
            }
        return self._mcp_sse(result)

    @staticmethod
    def _mcp_apply_fault(fault: Any) -> _FakeResponse:
        """Translate a configured ``mcp_fault`` into the matching failure."""
        if fault == "urlerror":
            raise urllib.error.URLError("mock MCP connection refused")
        if fault == "badsse":
            return _FakeResponse(
                b"event: message\ndata: {broken json,,\n\n", 200, "text/event-stream"
            )
        if fault == "toolerror":
            result = {
                "content": [{"type": "text", "text": "VALIDATION_ERROR: bad filter"}],
                "isError": True,
            }
            return MockKonecty._mcp_sse(result)
        if isinstance(fault, int):
            raise _err(fault, f"mcp fault {fault}")
        raise _err(500, f"unknown mcp fault: {fault}")

    @staticmethod
    def _mcp_sse(result: dict) -> _FakeResponse:
        """Wrap a tool ``result`` in a single SSE frame carrying the JSON-RPC reply."""
        msg = {"jsonrpc": "2.0", "id": 1, "result": result}
        body = ("event: message\ndata: " + json.dumps(msg, ensure_ascii=False) + "\n\n").encode(
            "utf-8"
        )
        return _FakeResponse(body, 200, "text/event-stream")

    def _mcp_records_find(self, arguments: dict) -> dict:
        """records_find → structuredContent {records, total, pagination}."""
        document = arguments.get("document", "")
        fil = arguments.get("filter")
        fields_str = arguments.get("fields")
        limit = arguments.get("limit", 50)
        start = arguments.get("start", 0)

        doc_records = self.records.get(document, {})
        matched = [
            _project(r, fields_str)
            for r in doc_records.values()
            if _match_filter(r, fil)
        ]
        total = len(matched)
        if limit == -1:
            page = matched[start:]
        else:
            page = matched[start: start + limit]
        returned = len(page)
        has_more = (start + returned) < total if limit != -1 else False
        pagination = {
            "start": start,
            "limit": limit,
            "returned": returned,
            "total": total,
            "hasMore": has_more,
            "nextStart": (start + returned) if has_more else None,
        }
        structured = {"records": page, "total": total, "pagination": pagination}
        return {
            "content": [{"type": "text", "text": json.dumps(structured, ensure_ascii=False)}],
            "structuredContent": structured,
        }

    def _mcp_query_json(self, arguments: dict) -> dict:
        """query_json → structuredContent {records, meta, total}."""
        document = arguments.get("document", "")
        fil = arguments.get("filter")
        fields_str = arguments.get("fields")
        limit = arguments.get("limit", 1000)
        start = arguments.get("start", 0)

        doc_records = self.records.get(document, {})
        matched = [
            _project(r, fields_str)
            for r in doc_records.values()
            if _match_filter(r, fil)
        ]
        total = len(matched)
        if limit == -1:
            page = matched[start:]
        else:
            page = matched[start: start + limit]
        meta = {
            "document": document,
            "relations": arguments.get("relations", []),
            "warnings": [],
            "executionTimeMs": 1,
        }
        structured = {"records": page, "meta": meta, "total": total}
        return {
            "content": [{"type": "text", "text": json.dumps(structured, ensure_ascii=False)}],
            "structuredContent": structured,
        }

    def _mcp_query_sql(self, arguments: dict) -> dict:
        """query_sql → structuredContent {records, meta, total} (2-row Contact stub)."""
        rows = [copy.deepcopy(r) for r in list(self.records.get("Contact", {}).values())[:2]]
        total = len(rows)
        meta = {
            "document": "Contact",
            "relations": [],
            "warnings": [],
            "executionTimeMs": 1,
        }
        structured = {"records": rows, "meta": meta, "total": total}
        return {
            "content": [{"type": "text", "text": json.dumps(structured, ensure_ascii=False)}],
            "structuredContent": structured,
        }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    BASE_URL = "http://localhost:3000"
    META_BASE = f"{BASE_URL}/api/admin/meta"
    DATA_BASE = f"{BASE_URL}/rest/data"
    QUERY_BASE = f"{BASE_URL}/rest/query"
    AUTH_BASE = f"{BASE_URL}/api/auth"

    _HDR = {"Authorization": "test-token"}
    _HDR_JSON = {**_HDR, "Content-Type": "application/json"}

    def _read(resp: Any) -> Any:
        with resp as r:
            raw = r.read().decode("utf-8")
            ct = r.headers.get("Content-Type", "")
            if "ndjson" in ct:
                lines = [line for line in raw.strip().splitlines() if line.strip()]
                return [json.loads(line) for line in lines]
            return json.loads(raw)

    def _get(url: str) -> Any:
        return _read(urllib.request.urlopen(urllib.request.Request(url, method="GET", headers=_HDR)))

    def _post(url: str, body: Any) -> Any:
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method="POST", headers=_HDR_JSON)
        return _read(urllib.request.urlopen(req))

    def _put(url: str, body: Any) -> Any:
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method="PUT", headers=_HDR_JSON)
        return _read(urllib.request.urlopen(req))

    def _delete_with_body(url: str, body: Any) -> Any:
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method="DELETE", headers=_HDR_JSON)
        return _read(urllib.request.urlopen(req))

    def _delete(url: str) -> Any:
        return _read(urllib.request.urlopen(urllib.request.Request(url, method="DELETE", headers=_HDR)))

    print("=== MockKonecty self-test ===\n")
    mk = MockKonecty()

    with mk.patch():

        # ----------------------------------------------------------------
        # SECTION 1: Original meta tests (all 22 preserved)
        # ----------------------------------------------------------------

        # 1. GET list
        result = _get(META_BASE)
        assert result["success"] is True
        ids = {item["_id"] for item in result["data"]}
        assert "Contact" in ids and "Activity" in ids and "Product" in ids
        print(f"[PASS] GET /api/admin/meta — {len(result['data'])} document metas: {sorted(ids)}")

        # 2. GET Contact document meta
        result = _get(f"{META_BASE}/Contact/document/Contact")
        assert result["success"] is True
        assert result["data"]["_id"] == "Contact"
        print(f"[PASS] GET /api/admin/meta/Contact/document/Contact — _id={result['data']['_id']}")

        # 3. GET /:document — all Contact metas
        result = _get(f"{META_BASE}/Contact")
        assert result["success"] is True
        contact_ids = {m["_id"] for m in result["data"]}
        assert "Contact" in contact_ids
        assert "Contact:list:Default" in contact_ids
        assert "Contact:view:Default" in contact_ids
        print(f"[PASS] GET /api/admin/meta/Contact — {len(result['data'])} metas")

        # 4. PUT new list meta
        new_list = {"columns": {"code": {"name": "code", "visible": True, "sort": 0}}, "label": {"en": "Test"}}
        result = _put(f"{META_BASE}/Contact/list/Test", new_list)
        assert result["success"] is True and result["action"] == "created"
        print(f"[PASS] PUT /api/admin/meta/Contact/list/Test — action={result['action']}")

        # 5. Verify store mutation
        assert mk.has("Contact:list:Test")
        stored = mk.get("Contact:list:Test")
        assert stored["type"] == "list" and stored["document"] == "Contact"
        print(f"[PASS] mk.has/mk.get — Contact:list:Test present")

        # 6. Re-GET
        result = _get(f"{META_BASE}/Contact/list/Test")
        assert result["data"]["_id"] == "Contact:list:Test"
        print(f"[PASS] GET /api/admin/meta/Contact/list/Test confirmed after PUT")

        # 7. PUT again (update)
        result = _put(f"{META_BASE}/Contact/list/Test", {**new_list, "label": {"en": "Test Updated"}})
        assert result["action"] == "updated"
        print(f"[PASS] PUT /api/admin/meta/Contact/list/Test (update) — action={result['action']}")

        # 8. DELETE
        result = _delete(f"{META_BASE}/Contact/list/Test")
        assert result["action"] == "deleted" and not mk.has("Contact:list:Test")
        print(f"[PASS] DELETE /api/admin/meta/Contact/list/Test — deleted")

        # 9. doctor (all)
        result = _post(f"{META_BASE}/doctor", {})
        assert result["success"] and result["summary"]["total"] > 0
        print(f"[PASS] POST /api/admin/meta/doctor — total={result['summary']['total']}")

        # 10. doctor (Contact)
        result = _post(f"{META_BASE}/doctor", {"document": "Contact"})
        assert result["success"] and result["summary"]["total"] > 0
        print(f"[PASS] POST /api/admin/meta/doctor (Contact) — total={result['summary']['total']}")

        # 11. hook/validate — valid
        result = _post(f"{META_BASE}/hook/validate", {"hookName": "scriptAfterSave", "code": "var x = 1;"})
        assert result["valid"] is True
        print(f"[PASS] POST /api/admin/meta/hook/validate (valid) — valid=True")

        # 12. hook/validate — comment
        result = _post(f"{META_BASE}/hook/validate", {"hookName": "scriptAfterSave", "code": "var x = 1; // c"})
        assert result["valid"] is False
        print(f"[PASS] POST /api/admin/meta/hook/validate (comment) — valid=False")

        # 13. hook/validate — missing return
        result = _post(f"{META_BASE}/hook/validate", {"hookName": "scriptBeforeValidation", "code": "var x = 1;"})
        assert result["valid"] is False
        print(f"[PASS] POST /api/admin/meta/hook/validate (missing return) — valid=False")

        # 14. hook/validate — bad hookName
        try:
            _post(f"{META_BASE}/hook/validate", {"hookName": "badHook", "code": "return {};"})
            assert False, "Should have raised"
        except urllib.error.HTTPError as e:
            assert e.code == 400
            print(f"[PASS] POST /api/admin/meta/hook/validate (bad name) — 400")

        # 15. Namespace
        result = _get(f"{META_BASE}/Namespace")
        assert "Namespace" in {m["_id"] for m in result["data"]}
        print(f"[PASS] GET /api/admin/meta/Namespace")

        # 16. PUT hook onto Contact
        result = _put(f"{META_BASE}/Contact/hook/scriptAfterSave", {"code": "var rec = data[0];"})
        assert result["action"] == "updated"
        print(f"[PASS] PUT /api/admin/meta/Contact/hook/scriptAfterSave")

        # 17. GET hook
        result = _get(f"{META_BASE}/Contact/hook/scriptAfterSave")
        assert result["data"]["value"] == "var rec = data[0];"
        print(f"[PASS] GET /api/admin/meta/Contact/hook/scriptAfterSave")

        # 18. DELETE hook
        result = _delete(f"{META_BASE}/Contact/hook/scriptAfterSave")
        assert result["action"] == "deleted"
        print(f"[PASS] DELETE /api/admin/meta/Contact/hook/scriptAfterSave")

        # 19. reload
        result = _post(f"{META_BASE}/reload", {})
        assert result["action"] == "reloaded"
        print(f"[PASS] POST /api/admin/meta/reload")

        # 20. 404 on missing meta
        try:
            _get(f"{META_BASE}/Contact/list/NoSuchList")
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 404
            print(f"[PASS] GET missing meta — 404")

        # 21. 404 on missing document
        try:
            _get(f"{META_BASE}/NoSuchDocument")
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 404
            err_body = json.loads(e.read())
            assert err_body["errors"] == ["Document not found"]
            print(f"[PASS] GET missing document — 404")

        # 22. 400 on invalid type
        try:
            _get(f"{META_BASE}/Contact/bogustype/Foo")
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 400
            err_body = json.loads(e.read())
            assert "Invalid type" in err_body["errors"][0]
            print(f"[PASS] GET invalid type — 400")

        print()

        # ----------------------------------------------------------------
        # SECTION 2: Auth tests
        # ----------------------------------------------------------------

        result = _get(f"{AUTH_BASE}/login-options")
        assert result["emailOtpEnabled"] is True
        assert result["whatsAppOtpEnabled"] is False
        print(f"[PASS] GET /api/auth/login-options — emailOtpEnabled=True")

        result = _post(f"{AUTH_BASE}/request-otp", {"email": "test@example.com"})
        assert result["success"] is True
        print(f"[PASS] POST /api/auth/request-otp — success=True")

        result = _post(f"{AUTH_BASE}/verify-otp", {"email": "test@example.com", "otpCode": "123456"})
        assert result["success"] is True
        assert result["logged"] is True
        assert result["authId"] == "mock-token-123"
        print(f"[PASS] POST /api/auth/verify-otp — authId={result['authId']}")

        print()

        # ----------------------------------------------------------------
        # SECTION 3: Data — find (GET, no filter)
        # ----------------------------------------------------------------

        result = _get(f"{DATA_BASE}/Contact/find")
        assert result["success"] is True
        assert result["total"] == 2
        assert len(result["data"]) == 2
        ids_found = {r["_id"] for r in result["data"]}
        assert "cid001" in ids_found and "cid002" in ids_found
        print(f"[PASS] GET /rest/data/Contact/find — total={result['total']}, ids={sorted(ids_found)}")

        # ----------------------------------------------------------------
        # SECTION 4: Data — find (POST with filter by _id)
        # ----------------------------------------------------------------

        result = _post(f"{DATA_BASE}/Contact/find", {
            "filter": {"match": "and", "conditions": [{"term": "_id", "operator": "equals", "value": "cid001"}]},
            "fields": "_id,code,name",
        })
        assert result["success"] is True
        assert result["total"] == 1
        assert result["data"][0]["_id"] == "cid001"
        assert "name" in result["data"][0]
        assert "status" not in result["data"][0]   # projected out
        print(f"[PASS] POST /rest/data/Contact/find (filter+fields) — _id=cid001 projected")

        # ----------------------------------------------------------------
        # SECTION 5: Data — find (POST with filter by code)
        # ----------------------------------------------------------------

        result = _post(f"{DATA_BASE}/Contact/find", {
            "filter": {"match": "and", "conditions": [{"term": "code", "operator": "equals", "value": 2}]},
        })
        assert result["success"] is True
        assert result["data"][0]["_id"] == "cid002"
        print(f"[PASS] POST /rest/data/Contact/find (filter by code=2) — cid002")

        # ----------------------------------------------------------------
        # SECTION 6: Data — create
        # ----------------------------------------------------------------

        result = _post(f"{DATA_BASE}/Contact", {"name": "Carol New", "status": "lead"})
        assert result["success"] is True
        new_rec = result["data"][0]
        assert "_id" in new_rec and "code" in new_rec and "_updatedAt" in new_rec
        new_id = new_rec["_id"]
        new_ts = new_rec["_updatedAt"]["$date"]
        assert new_id in mk.records["Contact"]
        assert mk.records["Contact"][new_id]["name"] == "Carol New"
        print(f"[PASS] POST /rest/data/Contact (create) — _id={new_id}, code={new_rec['code']}")

        # ----------------------------------------------------------------
        # SECTION 7: Data — create error sentinel
        # ----------------------------------------------------------------

        result = _post(f"{DATA_BASE}/Contact", {"__force_error__": True})
        assert result["success"] is False
        assert result["errors"][0]["message"] == "forced error"
        print(f"[PASS] POST /rest/data/Contact (__force_error__) — success=False")

        # ----------------------------------------------------------------
        # SECTION 8: Data — update (success)
        # ----------------------------------------------------------------

        result = _put(f"{DATA_BASE}/Contact", {
            "ids": [{"_id": new_id, "_updatedAt": {"$date": new_ts}}],
            "data": {"status": "client"},
        })
        assert result["success"] is True
        assert result["data"][0]["status"] == "client"
        updated_ts = result["data"][0]["_updatedAt"]["$date"]
        assert updated_ts != new_ts   # timestamp bumped
        print(f"[PASS] PUT /rest/data/Contact (update) — status=client, _updatedAt bumped")

        # ----------------------------------------------------------------
        # SECTION 9: Data — update optimistic-lock error
        # ----------------------------------------------------------------

        result = _put(f"{DATA_BASE}/Contact", {
            "ids": [{"_id": new_id, "_updatedAt": {"$date": "2020-01-01T00:00:00.000Z"}}],
            "data": {"status": "inactive"},
        })
        assert result["success"] is False
        assert "new version" in result["errors"][0]["message"]
        print(f"[PASS] PUT /rest/data/Contact (stale lock) — success=False, 'new version'")

        # ----------------------------------------------------------------
        # SECTION 10: Data — delete (success)
        # ----------------------------------------------------------------

        current_ts = mk.records["Contact"][new_id]["_updatedAt"]["$date"]
        result = _delete_with_body(f"{DATA_BASE}/Contact", {
            "ids": [{"_id": new_id, "_updatedAt": {"$date": current_ts}}],
        })
        assert result["success"] is True
        assert new_id in result["data"]
        assert new_id not in mk.records["Contact"]
        print(f"[PASS] DELETE /rest/data/Contact — {new_id} deleted and gone from store")

        # ----------------------------------------------------------------
        # SECTION 11: Data — delete FK sentinel
        # ----------------------------------------------------------------

        result = _delete_with_body(f"{DATA_BASE}/Contact", {
            "ids": [{"_id": "__fk_error__", "_updatedAt": {"$date": "2026-01-01T00:00:00.000Z"}}],
        })
        assert result["success"] is False
        assert "referenced by" in result["errors"][0]["message"]
        print(f"[PASS] DELETE /rest/data/Contact (FK sentinel) — 'referenced by'")

        print()

        # ----------------------------------------------------------------
        # SECTION 12: Query — /rest/query/json
        # ----------------------------------------------------------------

        result = _post(f"{QUERY_BASE}/json", {
            "document": "Contact",
            "filter": {"match": "and", "conditions": [{"term": "_id", "operator": "equals", "value": "cid001"}]},
            "fields": "_id,code,_updatedAt",
            "limit": 10,
            "start": 0,
            "includeMeta": True,
        })
        assert isinstance(result, list)
        rows = [r for r in result if "_meta" not in r]
        meta_line = next((r for r in result if "_meta" in r), None)
        assert len(rows) == 1
        assert rows[0]["_id"] == "cid001"
        assert meta_line is not None
        assert meta_line["_meta"]["success"] is True
        assert meta_line["_meta"]["total"] == 1
        print(f"[PASS] POST /rest/query/json — rows={len(rows)}, meta={meta_line['_meta']}")

        # Query used by update.py _find_record / delete.py _fetch_one
        result = _post(f"{QUERY_BASE}/json", {
            "document": "Contact",
            "filter": {"match": "and", "conditions": [{"term": "code", "operator": "equals", "value": 1}]},
            "fields": "_id,_updatedAt,code",
            "limit": 2,
        })
        assert isinstance(result, list)
        rows = [r for r in result if "_meta" not in r]
        assert len(rows) == 1 and rows[0]["_id"] == "cid001"
        print(f"[PASS] POST /rest/query/json (filter by code=1) — cid001 found")

        # create.py lookup — by code as int
        result = _post(f"{QUERY_BASE}/json", {
            "document": "Contact",
            "filter": {"match": "and", "conditions": [{"term": "code", "operator": "equals", "value": 2}]},
            "fields": "_id,code,name",
            "limit": 5,
        })
        rows = [r for r in result if "_meta" not in r]
        assert rows[0]["_id"] == "cid002"
        print(f"[PASS] POST /rest/query/json (lookup by code=2) — cid002 found")

        # ----------------------------------------------------------------
        # SECTION 13: Query — /rest/query/sql
        # ----------------------------------------------------------------

        result = _post(f"{QUERY_BASE}/sql", {"sql": "SELECT * FROM Contact LIMIT 2"})
        assert isinstance(result, list)
        sql_rows = [r for r in result if "_meta" not in r]
        assert len(sql_rows) >= 1
        print(f"[PASS] POST /rest/query/sql — {len(sql_rows)} row(s)")

        # ----------------------------------------------------------------
        # SECTION 14: Query — /rest/query/explorer/modules
        # ----------------------------------------------------------------

        result = _get(f"{QUERY_BASE}/explorer/modules?lang=pt_BR")
        assert result["success"] is True
        modules = result["data"]["modules"]
        doc_names = {m["document"] for m in modules}
        assert "Contact" in doc_names and "Activity" in doc_names
        # Verify field shape expected by modules.py
        contact_mod = next(m for m in modules if m["document"] == "Contact")
        assert "fields" in contact_mod and "reverseLookups" in contact_mod
        first_field = contact_mod["fields"][0]
        assert all(k in first_field for k in ("name", "type", "label"))
        print(f"[PASS] GET /rest/query/explorer/modules — {len(modules)} modules, fields OK")

        print()

        # ----------------------------------------------------------------
        # SECTION 15: File upload (info path via meta + upload)
        # ----------------------------------------------------------------

        # upload.py cmd_info calls GET /api/admin/meta/:document/document/:document
        # which the meta handler serves; Contact meta has a "picture" field of type "file"
        result = _get(f"{META_BASE}/Contact/document/Contact")
        assert result["success"] is True
        fields = result["data"].get("fields", {})
        assert "picture" in fields
        assert fields["picture"]["type"] == "file"
        print(f"[PASS] GET /api/admin/meta/Contact/document/Contact — picture field is type=file")

        # Upload stub
        # We simulate a multipart POST by sending a regular Request (no real file needed for mock)
        boundary = "testboundary"
        fake_file_body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="test.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
            "FAKEJPEG"
            f"\r\n--{boundary}--\r\n"
        ).encode("utf-8")
        upload_req = urllib.request.Request(
            f"{BASE_URL}/rest/file/upload/ns/access/Contact/cid001/picture",
            data=fake_file_body,
            method="POST",
            headers={**_HDR, "Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        result = _read(urllib.request.urlopen(upload_req))
        assert result["success"] is True
        core = result.get("coreResponse", {})
        assert "key" in core and "name" in core
        print(f"[PASS] POST /rest/file/upload — success=True, key={core['key'][:30]}")

        # File delete stub
        result = _delete(f"{BASE_URL}/rest/file/delete/ns/access/Contact/cid001/picture/mock_upload_001.jpg")
        assert result["success"] is True
        print(f"[PASS] DELETE /rest/file/delete — success=True")

    print("\n=== All self-tests passed ===")
    sys.exit(0)
