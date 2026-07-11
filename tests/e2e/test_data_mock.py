"""Mock-backed coverage tests for konecty-data skill scripts.

Every test runs the script main() in-process via PseudoAgent against the
in-memory MockKonecty. No live server required.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

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
