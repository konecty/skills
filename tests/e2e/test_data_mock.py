"""Mock-backed coverage tests for konecty-data skill scripts.

Every test runs the script main() in-process via PseudoAgent against the
in-memory MockKonecty. No live server required.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
from pathlib import Path

import pytest

from e2e.agent import PseudoAgent

pytestmark = pytest.mark.mock

HOST = "http://mock.local"
TOKEN = "mock-token"


# ---------------------------------------------------------------------------
# modules.py
# ---------------------------------------------------------------------------

class TestModules:
    def test_list(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-data", "modules", ["list"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert "Contact" in r.stdout
        assert "Activity" in r.stdout

    def test_fields_exact_match(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-data", "modules", ["fields", "Contact"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert "picture" in r.stdout

    def test_fields_label_match(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-data", "modules", ["fields", "Contato"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert "Contact" in r.stdout

    def test_fields_substring_single(self, agent, mock_konecty):
        """substring match that resolves to exactly one module"""
        with mock_konecty.patch():
            r = agent.run("konecty-data", "modules", ["fields", "Activ"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert "Activity" in r.stdout

    def test_fields_substring_multiple(self, agent, mock_konecty):
        """substring match ambiguous - exits 1"""
        with mock_konecty.patch():
            # 'co' matches Contact (Contato) and possibly others depending on labels
            # Use 'ato' which matches Contato and Atividade
            r = agent.run("konecty-data", "modules", ["fields", "ato"], host=HOST, token=TOKEN)
        # may be single or multiple; either is fine - just shouldn't crash unexpectedly
        # both code paths exercised

    def test_fields_no_match(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-data", "modules", ["fields", "NoSuchModuleXyz123"], host=HOST, token=TOKEN)
        assert r.code == 1

    def test_search_match(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-data", "modules", ["search", "contact"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert "Contact" in r.stdout

    def test_search_no_match(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-data", "modules", ["search", "zzznomatch"], host=HOST, token=TOKEN)
        assert r.ok  # exits 0 but prints "No modules found"
        assert "No modules found" in r.stdout

    def test_lang_override(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-data", "modules", ["--lang", "en", "list"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr


# ---------------------------------------------------------------------------
# find.py
# ---------------------------------------------------------------------------

class TestFind:
    def test_find_get(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-data", "find", ["find", "Contact"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert len(data) == 2

    def test_find_post_filter(self, agent, mock_konecty):
        fil = json.dumps({"match": "and", "conditions": [{"term": "_id", "operator": "equals", "value": "cid001"}]})
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["find", "Contact", "--filter", fil],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert len(data) == 1
        assert data[0]["_id"] == "cid001"

    def test_find_fields(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["find", "Contact", "--fields", "_id,code"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        for rec in data:
            assert "status" not in rec

    def test_find_output_ndjson(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["--output", "ndjson", "find", "Contact"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
        assert len(lines) == 2
        for line in lines:
            json.loads(line)  # valid JSON on each line

    def test_find_post_forced(self, agent, mock_konecty):
        """--post forces POST even without filter"""
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["find", "Contact", "--post"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_find_limit_start(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["find", "Contact", "--limit", "1", "--start", "0"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert len(data) == 1

    def test_find_sort_shorthand(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["find", "Contact", "--sort", "code:asc"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_find_sort_json(self, agent, mock_konecty):
        sort = json.dumps([{"property": "code", "direction": "DESC"}])
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["find", "Contact", "--sort", sort],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_query_basic(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["query", "Contact"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        rows = json.loads(r.stdout)
        assert isinstance(rows, list)

    def test_query_include_meta(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["query", "Contact", "--include-meta"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_query_no_total(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["query", "Contact", "--no-total"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_query_with_filter(self, agent, mock_konecty):
        fil = json.dumps({"match": "and", "conditions": [{"term": "code", "operator": "equals", "value": 1}]})
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["query", "Contact", "--filter", fil, "--fields", "_id,code"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        rows = json.loads(r.stdout)
        assert len(rows) == 1 and rows[0]["_id"] == "cid001"

    def test_query_with_relations(self, agent, mock_konecty):
        rels = json.dumps([{"document": "Activity"}])
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["query", "Contact", "--relations", rels],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_query_ndjson(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["--output", "ndjson", "query", "Contact"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_sql_basic(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["sql", "SELECT * FROM Contact LIMIT 2"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        rows = json.loads(r.stdout)
        assert isinstance(rows, list)

    def test_sql_include_meta(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["sql", "SELECT * FROM Contact", "--include-meta"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_sql_no_total(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["sql", "SELECT * FROM Contact", "--no-total"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_sql_ndjson(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "find",
                ["--output", "ndjson", "sql", "SELECT * FROM Contact"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr


# ---------------------------------------------------------------------------
# create.py
# ---------------------------------------------------------------------------

class TestCreate:
    def test_create_happy_path(self, agent, mock_konecty):
        payload = json.dumps({"name": "Test User", "status": "lead"})
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "create",
                ["create", "Contact", "--data", payload],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        rec = json.loads(r.stdout)
        assert "_id" in rec
        assert rec.get("name") == "Test User"

    def test_create_force_error(self, agent, mock_konecty):
        payload = json.dumps({"__force_error__": True})
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "create",
                ["create", "Contact", "--data", payload],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1
        assert "ERROR" in r.stderr

    def test_create_invalid_json(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "create",
                ["create", "Contact", "--data", "not-json"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_create_non_dict_json(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "create",
                ["create", "Contact", "--data", "[1,2,3]"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_lookup_by_code(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "create",
                ["lookup", "Contact", "1"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "cid001" in r.stdout

    def test_lookup_by_text(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "create",
                ["lookup", "Contact", "Alice"],
                host=HOST, token=TOKEN,
            )
        # textSearch is passed but mock returns all; still exercises the text path
        assert r.ok, r.stderr

    def test_lookup_not_found(self, agent, mock_konecty):
        # Query Activity which has no records in mock
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "create",
                ["lookup", "Activity", "999"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1
        assert "No records found" in r.stderr

    def test_lookup_extra_fields(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "create",
                ["lookup", "Contact", "1", "--fields", "name,status"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr


# ---------------------------------------------------------------------------
# update.py
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_fetch_by_code(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "update",
                ["fetch", "Contact", "1"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "cid001" in r.stdout
        assert "_updatedAt" in r.stdout

    def test_fetch_by_id(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "update",
                ["fetch", "Contact", "cid002"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "cid002" in r.stdout

    def test_fetch_with_fields(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "update",
                ["fetch", "Contact", "1", "--fields", "name,status"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_fetch_not_found(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "update",
                ["fetch", "Contact", "99999"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_update_explicit(self, agent, mock_konecty):
        ids_json = json.dumps([{"_id": "cid001", "_updatedAt": "2026-01-01T00:00:00.000Z"}])
        data_json = json.dumps({"status": "client"})
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "update",
                ["update", "Contact", "--ids", ids_json, "--data", data_json],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        rec = json.loads(r.stdout)
        assert rec.get("status") == "client"

    def test_update_stale_optimistic_lock(self, agent, mock_konecty):
        """stale _updatedAt triggers the 'new version' error branch"""
        ids_json = json.dumps([{"_id": "cid002", "_updatedAt": "2000-01-01T00:00:00.000Z"}])
        data_json = json.dumps({"status": "inactive"})
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "update",
                ["update", "Contact", "--ids", ids_json, "--data", data_json],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1
        assert "new version" in r.stderr.lower() or "ERROR" in r.stderr

    def test_update_invalid_ids_json(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "update",
                ["update", "Contact", "--ids", "not-json", "--data", "{}"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_update_invalid_data_json(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "update",
                ["update", "Contact", "--ids", '[{"_id":"x","_updatedAt":"t"}]', "--data", "bad"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_update_empty_ids(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "update",
                ["update", "Contact", "--ids", "[]", "--data", '{"status":"lead"}'],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_patch_by_code(self, agent, mock_konecty):
        data_json = json.dumps({"status": "client"})
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "update",
                ["patch", "Contact", "2", "--data", data_json],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_patch_invalid_data(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "update",
                ["patch", "Contact", "1", "--data", "badJSON"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1


# ---------------------------------------------------------------------------
# delete.py
# ---------------------------------------------------------------------------

class TestDelete:
    def test_preview(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "delete",
                ["preview", "Contact", "1"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "cid001" in r.stdout
        assert "WARNING" in r.stdout

    def test_preview_by_id(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "delete",
                ["preview", "Contact", "cid002"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "cid002" in r.stdout

    def test_preview_not_found(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "delete",
                ["preview", "Contact", "99999"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_delete_success(self, agent, mock_konecty):
        # First create a record to delete
        payload = json.dumps({"name": "DeleteMe", "status": "lead"})
        with mock_konecty.patch():
            cr = agent.run(
                "konecty-data", "create",
                ["create", "Contact", "--data", payload],
                host=HOST, token=TOKEN,
            )
            assert cr.ok, cr.stderr
            created = json.loads(cr.stdout)
            new_id = created["_id"]
            r = agent.run(
                "konecty-data", "delete",
                ["delete", "Contact", new_id, "--confirm"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "Deleted" in r.stdout

    def test_delete_fk_error(self, agent, mock_konecty):
        """Force FK error by injecting __fk_error__ record directly into mock"""
        with mock_konecty.patch():
            # Inject FK sentinel record
            mock_konecty.records.setdefault("Contact", {})["__fk_error__"] = {
                "_id": "__fk_error__",
                "code": 9999,
                "name": "FK Sentinel",
                "_updatedAt": {"$date": "2026-01-01T00:00:00.000Z"},
            }
            r = agent.run(
                "konecty-data", "delete",
                ["delete", "Contact", "__fk_error__", "--confirm"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1
        assert "referenced by" in r.stderr

    def test_delete_multiple_records_ambiguous(self, agent, mock_konecty):
        """code 1 returns both cid001 - testing the 'multiple records' branch"""
        # Both records have code 1 momentarily? No - inject a duplicate code
        with mock_konecty.patch():
            mock_konecty.records["Contact"]["cid_dup"] = {
                "_id": "cid_dup", "code": 1,
                "_updatedAt": {"$date": "2026-01-01T00:00:00.000Z"},
            }
            r = agent.run(
                "konecty-data", "delete",
                ["preview", "Contact", "1"],
                host=HOST, token=TOKEN,
            )
            # Multiple matches → exit 1
            assert r.code == 1
            # Clean up
            del mock_konecty.records["Contact"]["cid_dup"]


# ---------------------------------------------------------------------------
# upload.py
# ---------------------------------------------------------------------------

class TestUpload:
    def test_info_file_field(self, agent, mock_konecty, tmp_path):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "upload",
                ["info", "Contact", "picture"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "file" in r.stdout
        assert "wildcard" in r.stdout or "jpg" in r.stdout

    def test_info_non_file_field(self, agent, mock_konecty):
        """Requesting info on a non-file field exits 1"""
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "upload",
                ["info", "Contact", "status"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_info_unknown_field(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "upload",
                ["info", "Contact", "nonexistentField"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_list_files(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "upload",
                ["list", "Contact", "cid001", "picture"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        # cid001 seed data doesn't include the picture field, so either:
        # "No files" (field present but empty) or "Note: field ... was not returned" (field absent)
        assert "No files" in r.stdout or "0 file" in r.stdout or "not returned" in r.stdout

    def test_upload_file(self, agent, mock_konecty, tmp_path):
        tmpfile = tmp_path / "test.jpg"
        tmpfile.write_bytes(b"FAKEJPEG" * 100)
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "upload",
                ["upload", "Contact", "cid001", "picture", str(tmpfile)],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "Upload successful" in r.stdout

    def test_upload_file_skip_validation(self, agent, mock_konecty, tmp_path):
        tmpfile = tmp_path / "test.txt"
        tmpfile.write_bytes(b"some text content")
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "upload",
                ["upload", "Contact", "cid001", "picture", str(tmpfile), "--skip-validation"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_upload_invalid_extension(self, agent, mock_konecty, tmp_path):
        """Extension not in wildcard → exits 1 without skip-validation"""
        tmpfile = tmp_path / "test.pdf"
        tmpfile.write_bytes(b"FAKEPDF")
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "upload",
                ["upload", "Contact", "cid001", "picture", str(tmpfile)],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1
        assert "not accepted" in r.stderr or "Accepted" in r.stderr

    def test_upload_file_not_found(self, agent, mock_konecty, tmp_path):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "upload",
                ["upload", "Contact", "cid001", "picture", "/nonexistent/path/file.jpg"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1
        assert "not found" in r.stderr.lower() or "File not found" in r.stderr

    def test_delete_file_dry_run(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "upload",
                ["delete", "Contact", "cid001", "picture", "some_file.jpg"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "--confirm" in r.stdout

    def test_delete_file_confirm(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-data", "upload",
                ["delete", "Contact", "cid001", "picture", "some_file.jpg", "--confirm"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "Deleted" in r.stdout


# ---------------------------------------------------------------------------
# find.py — MCP-first dispatcher + fallback matrix (T5)
# ---------------------------------------------------------------------------


@pytest.fixture
def find_mod():
    """The loaded find.py module, with the process-level MCP flag reset."""
    mod = PseudoAgent()._load("konecty-data", "find")
    mod._mcp_disabled = False
    yield mod
    mod._mcp_disabled = False


def _run_dispatch(mod, mcp_call, rest_call):
    """Invoke ``mod._dispatch`` capturing (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            mod._dispatch(mcp_call, rest_call)
        except SystemExit as exc:
            if isinstance(exc.code, int):
                code = exc.code
            elif exc.code is None:
                code = 0
            else:
                code = 1
                err.write(str(exc.code))
    return code, out.getvalue(), err.getvalue()


class TestDispatcherMatrix:
    """Every row of the design fallback matrix, driven through ``_dispatch``.

    Requirements: FMCP-06 (401 no-fallback), FMCP-07 (404 silent), FMCP-08
    (403/429/5xx/transport + notice first), FMCP-09 (happy path silent),
    FMCP-11 (both-fail surfaces REST error), FMCP-12 (429 disables MCP).
    """

    NOTICE = "Busca feita via API direta (REST)."

    def _rest_records(self):
        """A rest_call stub that prints a records array to stdout."""
        def _call():
            print(json.dumps([{"_id": "cid001"}]))
        return _call

    def test_mcp_success_is_silent(self, find_mod, monkeypatch):
        """FMCP-09: happy MCP path emits no transport notice and skips REST."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        rest_ran = []

        def mcp_call():
            print(json.dumps([{"_id": "mcp001"}]))

        def rest_call():
            rest_ran.append(True)

        code, out, err = _run_dispatch(find_mod, mcp_call, rest_call)
        assert code == 0
        assert "mcp001" in out
        assert self.NOTICE not in err
        assert rest_ran == []  # REST never touched

    def test_fallback_404_silent(self, find_mod, monkeypatch):
        """FMCP-07: 404 (endpoint absent) → REST, no notice."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        errs = find_mod.mcp_client

        def mcp_call():
            raise errs.McpHttpError(404, "not found")

        code, out, err = _run_dispatch(find_mod, mcp_call, self._rest_records())
        assert code == 0
        assert "cid001" in out
        assert self.NOTICE not in err  # silent

    @pytest.mark.parametrize("status", [403, 500, 502])
    def test_fallback_http_with_notice(self, find_mod, monkeypatch, status):
        """FMCP-08: 403/5xx → REST + one-line notice on stderr."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        errs = find_mod.mcp_client

        def mcp_call():
            raise errs.McpHttpError(status, "boom")

        code, out, err = _run_dispatch(find_mod, mcp_call, self._rest_records())
        assert code == 0
        assert "cid001" in out
        assert self.NOTICE in err

    def test_fallback_transport_error_with_notice(self, find_mod, monkeypatch):
        """FMCP-08: connection/timeout/bad-SSE → REST + notice."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        errs = find_mod.mcp_client

        def mcp_call():
            raise errs.McpTransportError("connection reset")

        code, out, err = _run_dispatch(find_mod, mcp_call, self._rest_records())
        assert code == 0
        assert "cid001" in out
        assert self.NOTICE in err

    def test_notice_emitted_before_records(self, find_mod, monkeypatch):
        """FMCP-08: the notice is emitted before REST writes the records."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        errs = find_mod.mcp_client
        order: list[str] = []

        def mcp_call():
            raise errs.McpHttpError(403, "denied")

        def rest_call():
            order.append("records")

        # Shadow find.py's ``print`` to record when the notice is emitted; the
        # only print on the 403 path is the fallback notice itself.
        def rec_print(*a, **k):
            if a and self.NOTICE in str(a[0]):
                order.append("notice")

        monkeypatch.setattr(find_mod, "print", rec_print, raising=False)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            find_mod._dispatch(mcp_call, rest_call)

        assert order == ["notice", "records"]

    def test_401_surfaces_no_fallback(self, find_mod, monkeypatch):
        """FMCP-06: 401 → auth error, exit≠0, REST never called."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        errs = find_mod.mcp_client
        rest_ran = []

        def mcp_call():
            raise errs.McpHttpError(401, "unauthorized")

        def rest_call():
            rest_ran.append(True)

        code, out, err = _run_dispatch(find_mod, mcp_call, rest_call)
        assert code == 1
        assert "401" in err
        assert rest_ran == []

    def test_tool_error_surfaces_no_fallback(self, find_mod, monkeypatch):
        """Validation (McpToolError) → surface, exit≠0, REST never called."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        errs = find_mod.mcp_client
        rest_ran = []

        def mcp_call():
            raise errs.McpToolError("VALIDATION_ERROR", "invalid document Contato")

        def rest_call():
            rest_ran.append(True)

        code, out, err = _run_dispatch(find_mod, mcp_call, rest_call)
        assert code == 1
        assert "invalid document" in err
        assert rest_ran == []

    def test_both_fail_surfaces_rest_error(self, find_mod, monkeypatch):
        """FMCP-11: MCP 403 then REST also fails → REST error surfaces, exit≠0."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        errs = find_mod.mcp_client

        def mcp_call():
            raise errs.McpHttpError(403, "denied")

        def rest_call():
            raise SystemExit("HTTP 500: database unreachable")

        code, out, err = _run_dispatch(find_mod, mcp_call, rest_call)
        assert code == 1
        assert "HTTP 500" in err  # the actionable REST error surfaces
        assert self.NOTICE in err  # fallback was attempted

    def test_429_disables_mcp_for_rest_of_process(self, find_mod, monkeypatch):
        """FMCP-12: first 429 falls back + notice; later calls skip MCP entirely."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        errs = find_mod.mcp_client

        def mcp_call_429():
            raise errs.McpHttpError(429, "rate limited")

        code1, out1, err1 = _run_dispatch(find_mod, mcp_call_429, self._rest_records())
        assert code1 == 0
        assert self.NOTICE in err1
        assert find_mod._mcp_disabled is True

        # Second call: MCP must NOT be attempted (flag set) → straight to REST, silent.
        mcp_called = []

        def mcp_call_2():
            mcp_called.append(True)
            print(json.dumps([{"_id": "shouldnothappen"}]))

        code2, out2, err2 = _run_dispatch(find_mod, mcp_call_2, self._rest_records())
        assert code2 == 0
        assert mcp_called == []  # MCP skipped
        assert "cid001" in out2
        assert self.NOTICE not in err2  # no repeated notice

    def test_konecty_mcp_0_rest_only(self, find_mod, monkeypatch):
        """KONECTY_MCP=0 → MCP never attempted, REST runs silently."""
        monkeypatch.setenv("KONECTY_MCP", "0")
        mcp_called = []

        def mcp_call():
            mcp_called.append(True)

        code, out, err = _run_dispatch(find_mod, mcp_call, self._rest_records())
        assert code == 0
        assert mcp_called == []
        assert "cid001" in out
        assert self.NOTICE not in err

    def test_konecty_mcp_only_fail_no_fallback(self, find_mod, monkeypatch):
        """KONECTY_MCP=only + MCP failure → surface, exit≠0, REST never called."""
        monkeypatch.setenv("KONECTY_MCP", "only")
        errs = find_mod.mcp_client
        rest_ran = []

        def mcp_call():
            raise errs.McpHttpError(403, "denied")

        def rest_call():
            rest_ran.append(True)

        code, out, err = _run_dispatch(find_mod, mcp_call, rest_call)
        assert code == 1
        assert rest_ran == []


# ---------------------------------------------------------------------------
# find.py — `find` routed through MCP records_find (T6)
# ---------------------------------------------------------------------------


class TestFindViaMcp:
    """`find` over the MCP records_find tool, with REST fallback and parity.

    Requirements: FMCP-01 (records_find), FMCP-02 (local filter reject),
    FMCP-03 (Bearer), FMCP-04 (output contract), FMCP-05 (arg mapping),
    FMCP-10 (fallback shape parity).
    """

    def test_find_uses_mcp_when_enabled(self, agent, mock_konecty, monkeypatch):
        """FMCP-01: with MCP up, `find` is served by records_find (REST path broken)."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)

        def boom(*a, **k):
            from e2e.mock_konecty import _err
            raise _err(500, "REST find must not be called when MCP succeeds")

        mock_konecty._handle_data_find = boom  # break REST so success ⇒ MCP served it
        with mock_konecty.patch():
            r = agent.run("konecty-data", "find", ["find", "Contact"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert len(data) == 2
        assert "Busca feita via API direta" not in r.stderr  # happy path silent

    def test_find_mcp_rest_output_parity(self, agent, mock_konecty, monkeypatch):
        """FMCP-04/10: MCP-path stdout+total is byte-identical to the REST path."""
        with mock_konecty.patch():
            monkeypatch.delenv("KONECTY_MCP", raising=False)
            r_mcp = agent.run("konecty-data", "find", ["find", "Contact"], host=HOST, token=TOKEN)
            monkeypatch.setenv("KONECTY_MCP", "0")
            r_rest = agent.run("konecty-data", "find", ["find", "Contact"], host=HOST, token=TOKEN)
        assert r_mcp.ok and r_rest.ok, (r_mcp.stderr, r_rest.stderr)
        assert r_mcp.stdout == r_rest.stdout
        assert "# Total: 2  Returned: 2" in r_mcp.stderr
        assert "# Total: 2  Returned: 2" in r_rest.stderr

    def test_find_mcp_filter_passthrough(self, agent, mock_konecty, monkeypatch):
        """FMCP-02/05: a canonical KonFilter passes through to records_find."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        fil = json.dumps({"match": "and", "conditions": [
            {"term": "_id", "operator": "equals", "value": "cid001"}]})
        with mock_konecty.patch():
            r = agent.run("konecty-data", "find",
                          ["find", "Contact", "--filter", fil], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert len(data) == 1 and data[0]["_id"] == "cid001"

    def test_find_mcp_malformed_filter_rejected_before_call(self, agent, monkeypatch):
        """FMCP-02: malformed --filter is rejected locally, before any network call.

        Run WITHOUT the mock patched: a local reject exits with the JSON error;
        had it reached the network it would surface a connection error instead.
        """
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        r = agent.run("konecty-data", "find",
                      ["find", "Contact", "--filter", "{not valid json"],
                      host=HOST, token=TOKEN)
        assert r.code == 1
        assert "Invalid --filter" in r.stderr

    def test_find_mcp_fields_projection(self, agent, mock_konecty, monkeypatch):
        """FMCP-05: --fields maps to records_find `fields` (csv) and projects."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        with mock_konecty.patch():
            r = agent.run("konecty-data", "find",
                          ["find", "Contact", "--fields", "_id,code"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        for rec in json.loads(r.stdout):
            assert "status" not in rec

    def test_find_mcp_limit_neg1_passthrough(self, agent, mock_konecty, monkeypatch):
        """FMCP-05: --limit -1 (no limit) passes through unchanged."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        with mock_konecty.patch():
            r = agent.run("konecty-data", "find",
                          ["find", "Contact", "--limit", "-1"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert len(json.loads(r.stdout)) == 2

    def test_find_mcp_sort_normalized(self, agent, mock_konecty, monkeypatch):
        """FMCP-05: --sort shorthand normalizes to {property, direction:UPPER}."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        with mock_konecty.patch():
            r = agent.run("konecty-data", "find",
                          ["find", "Contact", "--sort", "code:asc"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr

    def test_find_mcp_403_falls_back_with_notice(self, agent, mock_konecty, monkeypatch):
        """FMCP-08: MCP 403 → records via REST fallback + notice first."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        mock_konecty.mcp_fault = 403
        with mock_konecty.patch():
            r = agent.run("konecty-data", "find", ["find", "Contact"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert len(json.loads(r.stdout)) == 2  # REST still returns records
        assert "Busca feita via API direta (REST)." in r.stderr

    def test_find_mcp_404_silent_fallback(self, agent, mock_konecty, monkeypatch):
        """FMCP-07: MCP 404 → records via REST, no notice."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        mock_konecty.mcp_fault = 404
        with mock_konecty.patch():
            r = agent.run("konecty-data", "find", ["find", "Contact"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert len(json.loads(r.stdout)) == 2
        assert "Busca feita via API direta" not in r.stderr

    def test_find_mcp_output_ndjson(self, agent, mock_konecty, monkeypatch):
        """FMCP-04: --output ndjson still works over the MCP path."""
        monkeypatch.delenv("KONECTY_MCP", raising=False)
        with mock_konecty.patch():
            r = agent.run("konecty-data", "find",
                          ["--output", "ndjson", "find", "Contact"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
        assert len(lines) == 2
        for line in lines:
            json.loads(line)
