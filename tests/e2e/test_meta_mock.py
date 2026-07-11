"""Mock-backed coverage tests for konecty-meta skill scripts.

Every test runs the script main() in-process via PseudoAgent against the
in-memory MockKonecty. No live server required.
"""
from __future__ import annotations

import json
import sys
import unittest.mock
from pathlib import Path

import pytest

pytestmark = pytest.mark.mock

HOST = "http://mock.local"
TOKEN = "mock-token"

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_FIXTURES = str(REPO_ROOT / "e2e" / "fixtures")


# ---------------------------------------------------------------------------
# meta_read.py
# ---------------------------------------------------------------------------

class TestMetaRead:
    def test_list_table(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-meta", "meta_read", ["list"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert "Contact" in r.stdout

    def test_list_json(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-meta", "meta_read", ["list", "--format", "json"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert isinstance(data, list)
        ids = {d["_id"] for d in data}
        assert "Contact" in ids

    def test_get_document(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-meta", "meta_read", ["get", "Contact"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        # Returns list of all Contact metas
        data = json.loads(r.stdout)
        assert isinstance(data, list)

    def test_get_specific_meta(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_read",
                ["get", "Contact", "--type", "list", "--name", "Default"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert data["_id"] == "Contact:list:Default"

    def test_get_hook_value(self, agent, mock_konecty):
        """Get a hook value - must first PUT one"""
        with mock_konecty.patch():
            # Set up a hook
            mock_konecty._store["Contact"]["scriptAfterSave"] = "var x = 1;"
            r = agent.run(
                "konecty-meta", "meta_read",
                ["hook", "Contact", "scriptAfterSave"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "var x" in r.stdout

    def test_get_hook_json_value(self, agent, mock_konecty):
        """validationData hook returns JSON - exercises the json branch"""
        with mock_konecty.patch():
            mock_konecty._store["Contact"]["validationData"] = {"original": {"document": "Contact"}}
            r = agent.run(
                "konecty-meta", "meta_read",
                ["hook", "Contact", "validationData"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_types(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-meta", "meta_read", ["types", "Contact"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert "access" in r.stdout or "list" in r.stdout


# ---------------------------------------------------------------------------
# meta_document.py
# ---------------------------------------------------------------------------

class TestMetaDocument:
    def test_show(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-meta", "meta_document", ["show", "Contact"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert "fields" in data

    def test_fields_table(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-meta", "meta_document", ["fields", "Contact"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert "picture" in r.stdout

    def test_fields_json(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_document",
                ["fields", "Contact", "--format", "json"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        fields = json.loads(r.stdout)
        assert "picture" in fields

    def test_add_field(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_document",
                ["add-field", "Contact", "testField", "--type", "text",
                 "--label-en", "Test Field", "--label-pt", "Campo Teste"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "testField" in r.stdout

    def test_add_field_required(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_document",
                ["add-field", "Contact", "requiredField", "--type", "text", "--required"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_add_field_already_exists(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_document",
                ["add-field", "Contact", "picture", "--type", "file"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1
        assert "already exists" in r.stderr

    def test_update_field(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_document",
                ["update-field", "Contact", "picture", "--set", "maxSize=1024"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_update_field_nested(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_document",
                ["update-field", "Contact", "picture", "--set", "label.en=Photo", "isSortable=true"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_update_field_not_found(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_document",
                ["update-field", "Contact", "nonexistentXyz", "--set", "maxSize=100"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_remove_field(self, agent, mock_konecty):
        # Add then remove
        with mock_konecty.patch():
            agent.run(
                "konecty-meta", "meta_document",
                ["add-field", "Contact", "tempField", "--type", "text"],
                host=HOST, token=TOKEN,
            )
            r = agent.run(
                "konecty-meta", "meta_document",
                ["remove-field", "Contact", "tempField"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_remove_field_not_found(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_document",
                ["remove-field", "Contact", "nosuchfieldXYZ"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_upsert(self, agent, mock_konecty, tmp_path):
        doc = {"_id": "Contact", "type": "document", "name": "Contact", "fields": {}}
        f = tmp_path / "doc.json"
        f.write_text(json.dumps(doc))
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_document",
                ["upsert", "Contact", "--file", str(f)],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_events_empty(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-meta", "meta_document", ["events", "Contact"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        # Contact.json has no events key → "No events defined"
        assert "No events" in r.stdout


# ---------------------------------------------------------------------------
# meta_list.py
# ---------------------------------------------------------------------------

class TestMetaList:
    def test_show(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_list",
                ["show", "Contact", "Default"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert data["_id"] == "Contact:list:Default"

    def test_columns(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_list",
                ["columns", "Contact", "Default"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "code" in r.stdout

    def test_add_column(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_list",
                ["add-column", "Contact", "Default", "newCol", "--sort", "99"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "newCol" in r.stdout

    def test_add_column_duplicate(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_list",
                ["add-column", "Contact", "Default", "code"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_remove_column(self, agent, mock_konecty):
        with mock_konecty.patch():
            # First add
            agent.run(
                "konecty-meta", "meta_list",
                ["add-column", "Contact", "Default", "colToRemove"],
                host=HOST, token=TOKEN,
            )
            r = agent.run(
                "konecty-meta", "meta_list",
                ["remove-column", "Contact", "Default", "colToRemove"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_remove_column_not_found(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_list",
                ["remove-column", "Contact", "Default", "nosuchcolXYZ"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_upsert(self, agent, mock_konecty, tmp_path):
        doc = {"_id": "Contact:list:Default", "type": "list", "name": "Default", "document": "Contact", "columns": {}}
        f = tmp_path / "list.json"
        f.write_text(json.dumps(doc))
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_list",
                ["upsert", "Contact", "Default", "--file", str(f)],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr


# ---------------------------------------------------------------------------
# meta_view.py
# ---------------------------------------------------------------------------

class TestMetaView:
    def test_show(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_view",
                ["show", "Contact", "Default"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert data["_id"] == "Contact:view:Default"

    def test_visuals(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_view",
                ["visuals", "Contact", "Default"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        # Contact:view:Default has visuals - should output something
        assert len(r.stdout.strip()) > 0

    def test_upsert(self, agent, mock_konecty, tmp_path):
        doc = {"_id": "Contact:view:Default", "type": "view", "name": "Default", "document": "Contact", "visuals": []}
        f = tmp_path / "view.json"
        f.write_text(json.dumps(doc))
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_view",
                ["upsert", "Contact", "Default", "--file", str(f)],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_visuals_with_reverse_lookup(self, agent, mock_konecty):
        """Exercise the reverseLookup branch in _flatten_visuals"""
        with mock_konecty.patch():
            # Contact:view:Default already has reverseLookup entries
            r = agent.run(
                "konecty-meta", "meta_view",
                ["visuals", "Contact", "Default"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        # The view has reverseLookup visuals
        assert "reverseLookup" in r.stdout or "Activity" in r.stdout


# ---------------------------------------------------------------------------
# meta_access.py
# ---------------------------------------------------------------------------

class TestMetaAccess:
    def test_show(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_access",
                ["show", "Contact", "Default"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert data["_id"] == "Contact:access:Default"

    def test_permissions(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_access",
                ["permissions", "Contact", "Default"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "isReadable" in r.stdout

    def test_set_field(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_access",
                ["set-field", "Contact", "Default", "name",
                 "--read", "true", "--update", "true"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_set_flag(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_access",
                ["set-flag", "Contact", "Default",
                 "--isReadable", "true", "--isDeletable", "false"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_upsert(self, agent, mock_konecty, tmp_path):
        doc = {
            "_id": "Contact:access:Default",
            "type": "access",
            "name": "Default",
            "document": "Contact",
            "isReadable": True,
            "isCreatable": True,
            "isUpdatable": True,
            "isDeletable": False,
            "fieldDefaults": {},
            "fields": {},
        }
        f = tmp_path / "access.json"
        f.write_text(json.dumps(doc))
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_access",
                ["upsert", "Contact", "Default", "--file", str(f)],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr


# ---------------------------------------------------------------------------
# meta_pivot.py
# ---------------------------------------------------------------------------

class TestMetaPivot:
    def test_show(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_pivot",
                ["show", "Contact", "Default"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert data["_id"] == "Contact:pivot:Default"

    def test_upsert(self, agent, mock_konecty, tmp_path):
        doc = {"_id": "Contact:pivot:Default", "type": "pivot", "name": "Default", "document": "Contact"}
        f = tmp_path / "pivot.json"
        f.write_text(json.dumps(doc))
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_pivot",
                ["upsert", "Contact", "Default", "--file", str(f)],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr


# ---------------------------------------------------------------------------
# meta_hook.py
# ---------------------------------------------------------------------------

class TestMetaHook:
    def test_list_no_hooks(self, agent, mock_konecty):
        """Contact document has no hooks initially → 'No hooks defined'"""
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["list", "Contact"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "No hooks" in r.stdout

    def test_list_with_hooks(self, agent, mock_konecty):
        """After adding a hook, list shows it"""
        with mock_konecty.patch():
            mock_konecty._store["Contact"]["scriptAfterSave"] = "var x = 1;"
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["list", "Contact"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "scriptAfterSave" in r.stdout

    def test_show_hook(self, agent, mock_konecty):
        with mock_konecty.patch():
            mock_konecty._store["Contact"]["scriptAfterSave"] = "var x = 1;"
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["show", "Contact", "scriptAfterSave"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "var x" in r.stdout

    def test_show_invalid_hook(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["show", "Contact", "invalidHookName"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_upsert_hook_with_code(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["upsert", "Contact", "scriptAfterSave", "--code", "var rec = data[0];"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "updated" in r.stdout

    def test_upsert_hook_with_file(self, agent, mock_konecty, tmp_path):
        hookfile = tmp_path / "hook.js"
        hookfile.write_text("var rec = data[0];")
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["upsert", "Contact", "scriptAfterSave", "--file", str(hookfile)],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_upsert_hook_validation_data(self, agent, mock_konecty, tmp_path):
        hookfile = tmp_path / "hook.json"
        hookfile.write_text(json.dumps({"original": {"document": "Contact", "fields": "_id"}}))
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["upsert", "Contact", "validationData", "--file", str(hookfile)],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_upsert_hook_invalid_validation_data_json(self, agent, mock_konecty, tmp_path):
        hookfile = tmp_path / "hook.js"
        hookfile.write_text("not json content")
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["upsert", "Contact", "validationData", "--file", str(hookfile)],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_upsert_hook_no_source(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["upsert", "Contact", "scriptAfterSave"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_upsert_hook_invalid_name(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["upsert", "Contact", "badHookName", "--code", "var x = 1;"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_upsert_hook_backend_rejects(self, agent, mock_konecty, tmp_path):
        """Hook with comment → backend validation fails → upsert exits 1"""
        hookfile = tmp_path / "hook.js"
        hookfile.write_text("var x = 1; // this has a comment")
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["upsert", "Contact", "scriptAfterSave", "--file", str(hookfile)],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1
        assert "rejected" in r.stderr.lower() or "comment" in r.stderr.lower()

    def test_delete_hook(self, agent, mock_konecty):
        with mock_konecty.patch():
            mock_konecty._store["Contact"]["scriptAfterSave"] = "var x = 1;"
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["delete", "Contact", "scriptAfterSave"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_delete_invalid_hook(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["delete", "Contact", "badHookName"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_scaffold_valid(self, agent, mock_konecty):
        for hook_name in ["scriptBeforeValidation", "validationData", "validationScript", "scriptAfterSave"]:
            with mock_konecty.patch():
                r = agent.run(
                    "konecty-meta", "meta_hook",
                    ["scaffold", hook_name],
                    host=HOST, token=TOKEN,
                )
            assert r.ok, f"scaffold {hook_name} failed: {r.stderr}"
            assert len(r.stdout.strip()) > 0

    def test_scaffold_invalid(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["scaffold", "badHookName"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_validate_valid_hook(self, agent, mock_konecty, tmp_path):
        hookfile = tmp_path / "hook.js"
        hookfile.write_text("var rec = data[0];")
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["validate", "scriptAfterSave", "--file", str(hookfile)],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "OK" in r.stdout

    def test_validate_invalid_hook_name(self, agent, mock_konecty, tmp_path):
        hookfile = tmp_path / "hook.js"
        hookfile.write_text("var x = 1;")
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["validate", "badHookName", "--file", str(hookfile)],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_validate_rejected_hook(self, agent, mock_konecty, tmp_path):
        """Hook with comment → validation reports errors"""
        hookfile = tmp_path / "hook.js"
        hookfile.write_text("var x = 1; // comment")
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["validate", "scriptAfterSave", "--file", str(hookfile)],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_validate_with_document(self, agent, mock_konecty, tmp_path):
        hookfile = tmp_path / "hook.js"
        hookfile.write_text("var rec = data[0];")
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_hook",
                ["validate", "scriptAfterSave", "--file", str(hookfile), "--document", "Contact"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr


# ---------------------------------------------------------------------------
# meta_namespace.py
# ---------------------------------------------------------------------------

class TestMetaNamespace:
    def test_show(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-meta", "meta_namespace", ["show"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        # Should print JSON
        data = json.loads(r.stdout)
        assert isinstance(data, dict)

    def test_email_servers_empty(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-meta", "meta_namespace", ["email-servers"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        # Namespace.json has emailServers:{} → "No email servers"
        assert "No email servers" in r.stdout

    def test_email_servers_with_data(self, agent, mock_konecty):
        """Add email server data directly to mock store then check"""
        with mock_konecty.patch():
            mock_konecty._store["Namespace"]["emailServers"] = {
                "smtp1": {"host": "smtp.example.com", "port": 587, "auth": {"user": "u@e.com"}, "secure": False}
            }
            r = agent.run("konecty-meta", "meta_namespace", ["email-servers"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert "smtp1" in r.stdout or "smtp.example.com" in r.stdout

    def test_queue_config_empty(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-meta", "meta_namespace", ["queue-config"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert "No QueueConfig" in r.stdout

    def test_set_webhook_valid(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_namespace",
                ["set-webhook", "onCreate", "https://example.com/hook"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_set_webhook_invalid_event(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_namespace",
                ["set-webhook", "onBadEvent", "https://example.com/hook"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_set_email_server(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_namespace",
                ["set-email-server", "mysmtp",
                 "--host", "smtp.test.com",
                 "--port", "587",
                 "--user", "test@test.com",
                 "--pass", "secret",
                 "--secure"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_add_queue_resource_not_found(self, agent, mock_konecty):
        """Resource not found → exits 1"""
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_namespace",
                ["add-queue", "nonexistentResource", "myQueue"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_upsert_namespace(self, agent, mock_konecty, tmp_path):
        ns = {"_id": "Namespace", "type": "namespace", "name": "konecty", "active": True}
        f = tmp_path / "ns.json"
        f.write_text(json.dumps(ns))
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_namespace",
                ["upsert", "--file", str(f)],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr


# ---------------------------------------------------------------------------
# meta_doctor.py
# ---------------------------------------------------------------------------

class TestMetaDoctor:
    def test_check_all_table(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-meta", "meta_doctor", ["check"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert "Summary" in r.stdout
        assert "No issues" in r.stdout

    def test_check_document(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_doctor",
                ["check", "--document", "Contact"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "Summary" in r.stdout

    def test_check_json(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_doctor",
                ["check", "--format", "json"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert "summary" in data

    def test_check_queues_table(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run("konecty-meta", "meta_doctor", ["check-queues"], host=HOST, token=TOKEN)
        assert r.ok, r.stderr
        assert "consistent" in r.stdout or "Queue" in r.stdout

    def test_check_queues_json(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_doctor",
                ["check-queues", "--format", "json"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        data = json.loads(r.stdout)
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# meta_sync.py
# ---------------------------------------------------------------------------

class TestMetaSync:
    def test_plan(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_sync",
                ["plan", "--from", "repo", "--to", "prod", "--repo", E2E_FIXTURES],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        # E2ESync is not in mock store → should show as "create"
        assert "E2ESync" in r.stdout or "create" in r.stdout

    def test_plan_wrong_direction(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_sync",
                ["plan", "--from", "prod", "--to", "repo", "--repo", E2E_FIXTURES],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_diff(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_sync",
                ["diff", "--repo", E2E_FIXTURES, "--meta-id", "E2ESync"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_diff_meta_not_in_repo(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_sync",
                ["diff", "--repo", E2E_FIXTURES, "--meta-id", "NoSuchMeta"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_apply_auto_approve(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_sync",
                ["apply",
                 "--from", "repo", "--to", "prod",
                 "--repo", E2E_FIXTURES,
                 "--auto-approve",
                 "--skip-hook-validation"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_apply_wrong_direction(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_sync",
                ["apply", "--from", "prod", "--to", "repo", "--repo", E2E_FIXTURES,
                 "--auto-approve"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_pull_document(self, agent, mock_konecty, tmp_path):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_sync",
                ["pull", "--repo", str(tmp_path), "--document", "Contact"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert (tmp_path / "MetaObjects" / "Contact" / "document.json").exists()

    def test_pull_missing_document_or_all(self, agent, mock_konecty, tmp_path):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_sync",
                ["pull", "--repo", str(tmp_path)],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1


# ---------------------------------------------------------------------------
# meta_remove.py
# ---------------------------------------------------------------------------

class TestMetaRemove:
    def test_plan_contact(self, agent, mock_konecty):
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_remove",
                ["plan", "--document", "Contact"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "Contact" in r.stdout
        assert "Deletion queue" in r.stdout

    def test_plan_not_found(self, agent, mock_konecty):
        """Module not found → empty list → prints 'No metas returned'"""
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_remove",
                ["plan", "--document", "NoSuchModuleXYZ"],
                host=HOST, token=TOKEN,
            )
        # _fetch_module_metas returns [] on 404 → prints "No metas returned"
        assert r.ok, r.stderr
        assert "No metas" in r.stdout

    def test_apply_yes_activity(self, agent, mock_konecty):
        """Delete Activity module (only has document meta) non-interactively"""
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_remove",
                ["apply", "--document", "Activity", "--yes"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "deleted" in r.stdout.lower() or "step" in r.stdout.lower()

    def test_apply_nothing_to_delete(self, agent, mock_konecty):
        """Module with no metas → 'Nothing to delete'"""
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_remove",
                ["apply", "--document", "NoSuchModuleXYZ", "--yes"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr
        assert "Nothing to delete" in r.stdout

    def test_delete_meta_by_id_child(self, agent, mock_konecty, monkeypatch):
        """Delete a child meta (Contact:list:Default) with patched input"""
        monkeypatch.setattr("builtins.input", lambda prompt="": "y")
        monkeypatch.setattr("sys.stdin", unittest.mock.MagicMock(isatty=lambda: True))
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_remove",
                ["delete", "--meta-id", "Contact:list:Default"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_delete_meta_by_id_two_colon_ambiguous(self, agent, mock_konecty):
        """meta-id with single colon is ambiguous → exits 1"""
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_remove",
                ["delete", "--meta-id", "Contact:list"],
                host=HOST, token=TOKEN,
            )
        assert r.code == 1

    def test_delete_meta_primary_by_id(self, agent, mock_konecty, monkeypatch):
        """Delete primary document via meta-id = just doc name"""
        monkeypatch.setattr("builtins.input", lambda prompt="": "y")
        monkeypatch.setattr("sys.stdin", unittest.mock.MagicMock(isatty=lambda: True))
        # Create a throwaway document
        with mock_konecty.patch():
            mock_konecty._store["TempDoc"] = {
                "_id": "TempDoc",
                "type": "document",
                "name": "TempDoc",
                "fields": {},
            }
            r = agent.run(
                "konecty-meta", "meta_remove",
                ["delete", "--meta-id", "TempDoc"],
                host=HOST, token=TOKEN,
            )
        assert r.ok, r.stderr

    def test_apply_interactive_aborted(self, agent, mock_konecty, monkeypatch):
        """Interactive apply with 'n' answer → 'Skipped' or similar"""
        monkeypatch.setattr("builtins.input", lambda prompt="": "n")
        monkeypatch.setattr("sys.stdin", unittest.mock.MagicMock(isatty=lambda: True))
        with mock_konecty.patch():
            r = agent.run(
                "konecty-meta", "meta_remove",
                ["apply", "--document", "Contact"],
                host=HOST, token=TOKEN,
            )
        # Since each step prompt returns "n", all items are skipped
        assert r.ok, r.stderr
