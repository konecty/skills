#!/usr/bin/env python3
"""
Konecty Upload: upload, list, and delete files in Konecty document fields.
Endpoint: POST /rest/file/upload/ns/access/:document/:recordId/:fieldName
Credentials from ~/.konecty/.env or ~/.konecty/credentials. Stdlib only.
"""
from __future__ import annotations

import argparse
import configparser
import json
import mimetypes
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

CREDENTIALS_DIR = os.path.expanduser("~/.konecty")
ENV_FILE = os.path.join(CREDENTIALS_DIR, ".env")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials")


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def _load_credentials() -> tuple[str, str]:
    url = os.environ.get("KONECTY_URL", "")
    token = os.environ.get("KONECTY_TOKEN", "")

    if os.path.isfile(ENV_FILE):
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("KONECTY_URL=") and not url:
                    url = line.split("=", 1)[1].strip()
                elif line.startswith("KONECTY_TOKEN=") and not token:
                    token = line.split("=", 1)[1].strip()

    if (not url or not token) and os.path.isfile(CREDENTIALS_FILE):
        config = configparser.ConfigParser()
        config.read(CREDENTIALS_FILE, encoding="utf-8")
        section = "default"
        if section in config:
            if not url:
                url = config[section].get("host", "")
            if not token:
                token = config[section].get("authid", "")

    if not url or not token:
        raise SystemExit(
            "Error: KONECTY_URL and KONECTY_TOKEN are required.\n"
            "Run the konecty-session skill first to authenticate."
        )

    return url.rstrip("/"), token


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _base_headers(token: str) -> dict[str, str]:
    return {"Authorization": token, "Accept": "application/json"}


def _do_request(req: urllib.request.Request) -> Any:
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
            msg = body.get("errors") or body.get("message") or str(body)
        except Exception:
            msg = e.reason
        raise SystemExit(f"HTTP {e.code}: {msg}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Connection error: {e.reason}")


def _http_get(host: str, token: str, path: str) -> Any:
    req = urllib.request.Request(
        f"{host}{path}",
        headers=_base_headers(token),
        method="GET",
    )
    return _do_request(req)


def _http_post_json(host: str, token: str, path: str, body: dict) -> Any:
    data = json.dumps(body).encode("utf-8")
    headers = {**_base_headers(token), "Content-Type": "application/json"}
    req = urllib.request.Request(f"{host}{path}", data=data, headers=headers, method="POST")
    return _do_request(req)


def _http_delete(host: str, token: str, path: str) -> Any:
    req = urllib.request.Request(
        f"{host}{path}",
        headers=_base_headers(token),
        method="DELETE",
    )
    return _do_request(req)


def _http_post_multipart(host: str, token: str, path: str, file_path: str) -> Any:
    """Upload a file using multipart/form-data (stdlib, no dependencies)."""
    filename = os.path.basename(file_path)
    mime_type, _ = mimetypes.guess_type(filename)
    mime_type = mime_type or "application/octet-stream"

    boundary = uuid.uuid4().hex

    with open(file_path, "rb") as fh:
        file_data = fh.read()

    # Build the multipart body manually
    part_header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n"
        f"\r\n"
    ).encode("utf-8")
    part_footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = part_header + file_data + part_footer

    headers = {
        **_base_headers(token),
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    req = urllib.request.Request(f"{host}{path}", data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            msg = err_body.get("errors") or err_body.get("message") or str(err_body)
        except Exception:
            msg = e.reason
        raise SystemExit(f"HTTP {e.code}: {msg}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Connection error: {e.reason}")


# ---------------------------------------------------------------------------
# Field metadata
# ---------------------------------------------------------------------------

def _get_field_meta(host: str, token: str, document: str, field_name: str) -> dict | None:
    """Fetch the field definition from the document's admin meta."""
    data = _http_get(host, token, f"/api/admin/meta/{document}/document/{document}")
    if not isinstance(data, dict) or not data.get("success"):
        return None
    fields = data.get("data", {}).get("fields", {})
    return fields.get(field_name)


def _wildcard_to_extensions(wildcard: str) -> list[str]:
    """Parse a Konecty wildcard regex pattern like '(jpg|jpeg|png)' into a list of extensions."""
    return re.findall(r"[a-zA-Z0-9]+", wildcard)


def _format_size(size_kb: float) -> str:
    if size_kb >= 1024:
        return f"{size_kb / 1024:.1f} MB"
    if size_kb < 1:
        return f"{int(size_kb * 1024)} B"
    return f"{size_kb:.1f} KB"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_info(args: argparse.Namespace, host: str, token: str) -> None:
    """Show file field constraints from metadata."""
    field = _get_field_meta(host, token, args.document, args.field)
    if field is None:
        raise SystemExit(
            f"Field '{args.field}' not found in document '{args.document}'.\n"
            "Run `konecty-modules fields <Document>` to list available fields."
        )
    if field.get("type") != "file":
        raise SystemExit(
            f"Field '{args.field}' has type '{field.get('type')}', not 'file'.\n"
            "This skill only manages file-type fields."
        )

    is_list = field.get("isList", False)
    wildcard = field.get("wildcard", "")
    max_size_kb = field.get("maxSize")
    max_items = field.get("maxItems")
    min_items = field.get("minItems", 0)

    print(f"Field: {args.document}.{args.field}")
    print("  type:     file")
    print(f"  isList:   {is_list} → accepts {'multiple files' if is_list else 'single file'}")

    if wildcard:
        exts = _wildcard_to_extensions(wildcard)
        print(f"  wildcard: {wildcard}")
        print(f"  accepted: {', '.join(f'.{e}' for e in exts)}")
    else:
        print("  accepted: all file types (no restriction)")

    if max_size_kb:
        print(f"  maxSize:  {max_size_kb} KB ({_format_size(max_size_kb)})")
    else:
        print("  maxSize:  no limit configured (server default: 1 GB)")

    if is_list:
        print(f"  maxItems: {max_items if max_items is not None else 'unlimited'}")
        print(f"  minItems: {min_items}")


def _print_file_list(label: str, files: list[dict]) -> None:
    """Print a formatted list of file objects."""
    count = len(files)
    print(f"{label} ({count} file{'s' if count != 1 else ''}):")
    for i, f in enumerate(files, 1):
        size_kb = (f.get("size") or 0) / 1024
        print(f"  {i}. {f.get('name')}  ({_format_size(size_kb)}, {f.get('kind', 'unknown type')})")
        if f.get("key"):
            print(f"     key: {f['key']}")


def _extract_files_from_record(record: dict, field: str) -> list[dict] | None:
    """Return file list from a record dict, or None if the field is absent."""
    if field not in record:
        return None
    raw = record[field]
    if raw is None:
        return []
    files = raw if isinstance(raw, list) else [raw]
    return [f for f in files if isinstance(f, dict) and f]


def cmd_list(args: argparse.Namespace, host: str, token: str) -> None:
    """List files currently stored in a field."""
    result = _http_post_json(
        host, token,
        f"/rest/data/{args.document}/find",
        {
            "filter": {
                "match": "and",
                "conditions": [{"term": "_id", "operator": "equals", "value": args.record_id}],
            },
            "fields": args.field,
            "limit": 1,
        },
    )

    if not isinstance(result, dict) or not result.get("success"):
        raise SystemExit(f"Error fetching record: {result.get('errors') if isinstance(result, dict) else result}")

    records = result.get("data", [])
    if not records:
        raise SystemExit(f"Record '{args.record_id}' not found in '{args.document}'.")

    files = _extract_files_from_record(records[0], args.field)

    if files is None:
        # Field was not returned by the API — likely excluded by the user's access profile
        print(
            f"Note: field '{args.field}' was not returned by the find API.\n"
            "This usually means the field is not included in the user's read access profile.\n"
            "Files may still exist — they just cannot be listed with this token.\n"
            "Use 'upload' to add a file; the response will show all current files in the field."
        )
        return

    if not files:
        print(f"No files in {args.document}/{args.record_id}/{args.field}")
        return

    _print_file_list(f"Files in {args.document}/{args.record_id}/{args.field}", files)


def _validate_upload_constraints(
    host: str, token: str, args: argparse.Namespace, ext: str, file_size_bytes: int
) -> None:
    """Validate the file against the field's type/wildcard/maxSize constraints."""
    field = _get_field_meta(host, token, args.document, args.field)
    if field is None:
        return

    if field.get("type") != "file":
        raise SystemExit(
            f"Field '{args.field}' has type '{field.get('type')}', not 'file'."
        )

    wildcard = field.get("wildcard", "")
    if wildcard:
        allowed = _wildcard_to_extensions(wildcard)
        if ext not in allowed:
            raise SystemExit(
                f"File type '.{ext}' is not accepted for '{args.document}.{args.field}'.\n"
                f"Accepted types: {', '.join(f'.{e}' for e in allowed)}\n"
                f"Wildcard pattern: {wildcard}"
            )

    max_size_kb = field.get("maxSize")
    if max_size_kb is not None and file_size_bytes > max_size_kb * 1024:
        raise SystemExit(
            f"File is too large: {file_size_bytes / 1024:.1f} KB\n"
            f"Maximum allowed for '{args.document}.{args.field}': "
            f"{max_size_kb} KB ({_format_size(max_size_kb)})"
        )


def _extract_stored_metadata(result: dict) -> dict:
    """Pull the stored-file metadata from the nested upload response.

    The response nests: result → coreResponse → coreResponse (full record).
    Prefer the inner coreResponse (hash-based name) over the outer response.
    """
    core1 = result.get("coreResponse") or {}
    core2 = core1.get("coreResponse") if isinstance(core1, dict) else {}
    return {
        "key": core1.get("key") or result.get("key") or "",
        "name": core1.get("name") or result.get("name") or "",
        "size": core1.get("size") or result.get("size") or 0,
        "kind": core1.get("kind") or result.get("kind") or "",
        "etag": core1.get("etag") or result.get("etag") or "",
        "core2": core2,
    }


def _print_upload_result(
    host: str, args: argparse.Namespace, filename: str, result: dict, stored: dict
) -> None:
    """Print the success summary, access URLs, and current field file list."""
    print("Upload successful!")
    print(f"  stored name: {stored['name']}  (original: {filename})")
    print(f"  size:  {_format_size(stored['size'] / 1024)}")
    print(f"  kind:  {stored['kind']}")
    print(f"  key:   {stored['key']}")
    if stored["etag"]:
        print(f"  etag:  {stored['etag']}")
    if result.get("_id"):
        print(f"  record _id:        {result['_id']}")
        print(f"  record _updatedAt: {result.get('_updatedAt')}")

    if stored["key"] or stored["name"]:
        # Download URL uses the key path (the actual stored file), not the display name
        key_basename = stored["key"].split("/")[-1] if stored["key"] else stored["name"]
        encoded_key_name = urllib.parse.quote(key_basename)
        print("\nAccess URLs:")
        print(f"  Download:  {host}/rest/file/{args.document}/{args.record_id}/{args.field}/{encoded_key_name}")
        if stored["kind"].startswith("image/"):
            print(f"  Thumbnail: {host}/rest/image/thumb/{stored['key']}")
            print(f"  Full:      {host}/rest/image/full/{stored['key']}")

    # Show the current state of the field (all files, not just the one just uploaded)
    core2 = stored["core2"]
    if isinstance(core2, dict):
        files = _extract_files_from_record(core2, args.field)
        if files is not None:
            print()
            _print_file_list(f"Current files in {args.document}/{args.record_id}/{args.field}", files)
            print("\nTo delete a file, use the 'name' shown above (not the key).")


def cmd_upload(args: argparse.Namespace, host: str, token: str) -> None:
    """Upload a local file to a Konecty document field."""
    file_path = args.file_path

    if not os.path.isfile(file_path):
        raise SystemExit(f"File not found: {file_path}")

    file_size_bytes = os.path.getsize(file_path)
    filename = os.path.basename(file_path)
    ext = os.path.splitext(filename)[1].lstrip(".").lower()

    # Validate against field constraints unless explicitly skipped
    if not args.skip_validation:
        _validate_upload_constraints(host, token, args, ext, file_size_bytes)

    print(f"Uploading: {filename} ({_format_size(file_size_bytes / 1024)})")
    print(f"  → {args.document}/{args.record_id}/{args.field}")

    path = f"/rest/file/upload/ns/access/{args.document}/{args.record_id}/{args.field}"
    result = _http_post_multipart(host, token, path, file_path)

    if not isinstance(result, dict) or not result.get("success"):
        errors = result.get("errors") if isinstance(result, dict) else result
        raise SystemExit(f"Upload failed: {errors}")

    stored = _extract_stored_metadata(result)
    _print_upload_result(host, args, filename, result, stored)


def cmd_delete(args: argparse.Namespace, host: str, token: str) -> None:
    """Delete a file from a Konecty document field."""
    if not args.confirm:
        print(f"About to delete: {args.file_name}")
        print(f"  from: {args.document}/{args.record_id}/{args.field}")
        print()
        print("Run with --confirm to actually delete.")
        return

    encoded_name = urllib.parse.quote(args.file_name)
    path = f"/rest/file/delete/ns/access/{args.document}/{args.record_id}/{args.field}/{encoded_name}"
    result = _http_delete(host, token, path)

    if not isinstance(result, dict) or not result.get("success"):
        errors = result.get("errors") if isinstance(result, dict) else result
        raise SystemExit(f"Delete failed: {errors}")

    print(f"Deleted: {args.file_name}")
    print(f"  from: {args.document}/{args.record_id}/{args.field}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage file uploads in Konecty document fields."
    )
    parser.add_argument("--host", default="", help="Override KONECTY_URL")
    parser.add_argument("--token", default="", help="Override KONECTY_TOKEN")

    sub = parser.add_subparsers(dest="command", required=True)

    # info
    p_info = sub.add_parser("info", help="Show file field constraints from metadata")
    p_info.add_argument("document", help="Document/module name, e.g. Contact")
    p_info.add_argument("field", help="Field name, e.g. picture")

    # list
    p_list = sub.add_parser("list", help="List files stored in a field")
    p_list.add_argument("document", help="Document name")
    p_list.add_argument("record_id", help="Record _id or numeric code")
    p_list.add_argument("field", help="Field name")

    # upload
    p_upload = sub.add_parser("upload", help="Upload a local file to a field")
    p_upload.add_argument("document", help="Document name, e.g. Contact")
    p_upload.add_argument("record_id", help="Record _id or numeric code")
    p_upload.add_argument("field", help="Field name, e.g. picture")
    p_upload.add_argument("file_path", help="Path to the local file to upload")
    p_upload.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip pre-upload field constraint validation (use if meta endpoint is unavailable)",
    )

    # delete
    p_delete = sub.add_parser("delete", help="Delete a file from a field")
    p_delete.add_argument("document", help="Document name")
    p_delete.add_argument("record_id", help="Record _id or numeric code")
    p_delete.add_argument("field", help="Field name")
    p_delete.add_argument("file_name", help="File name to delete (as shown by the list command)")
    p_delete.add_argument("--confirm", action="store_true", help="Actually perform the deletion")

    args = parser.parse_args()

    # Allow --host/--token to override only what's provided
    host_env, token_env = _load_credentials()
    host = args.host.rstrip("/") if args.host else host_env
    token = args.token if args.token else token_env

    dispatch = {
        "info": cmd_info,
        "list": cmd_list,
        "upload": cmd_upload,
        "delete": cmd_delete,
    }
    dispatch[args.command](args, host, token)


if __name__ == "__main__":
    main()
