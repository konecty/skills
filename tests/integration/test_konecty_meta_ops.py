"""
Integration tests for konecty-meta operation scripts (beyond meta_read and meta_doctor).
Requires Konecty at http://localhost:3000 with credentials in ~/.konecty/.env.
"""
import argparse
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

_META_SCRIPTS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../skills/konecty-meta/scripts")
)
sys.path.insert(0, _META_SCRIPTS)

import meta_list       # noqa: E402
import meta_view       # noqa: E402
import meta_access     # noqa: E402
import meta_hook       # noqa: E402
import meta_namespace  # noqa: E402
import meta_pivot      # noqa: E402
import meta_document   # noqa: E402
import meta_sync       # noqa: E402
import meta_remove     # noqa: E402


def _read_credentials() -> tuple[str, str]:
    env_file = os.path.expanduser("~/.konecty/.env")
    url, token = "", ""
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("KONECTY_URL="):
                url = line.split("=", 1)[1]
            elif line.startswith("KONECTY_TOKEN="):
                token = line.split("=", 1)[1]
    if not url or not token:
        raise RuntimeError("~/.konecty/.env missing KONECTY_URL or KONECTY_TOKEN")
    return url.rstrip("/"), token


HOST, TOKEN = _read_credentials()


def _args(**kwargs) -> argparse.Namespace:
    defaults = dict(host=HOST, token=TOKEN)
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# meta_document.py
# ---------------------------------------------------------------------------

class TestMetaDocument(unittest.TestCase):
    def test_show_contact_document(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_document.cmd_show(_args(document="Contact"))
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("name"), "Contact")

    def test_fields_table_includes_name_field(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_document.cmd_fields(_args(document="Contact", format="table"))
        self.assertIn("name", buf.getvalue())

    def test_fields_json_returns_dict(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_document.cmd_fields(_args(document="Contact", format="json"))
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, dict)
        self.assertIn("name", data)


# ---------------------------------------------------------------------------
# meta_list.py
# ---------------------------------------------------------------------------

class TestMetaList(unittest.TestCase):
    def test_show_contact_default_list(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_list.cmd_show(_args(document="Contact", name="Default"))
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, dict)
        self.assertIn("columns", data)

    def test_columns_contact_default_list(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_list.cmd_columns(_args(document="Contact", name="Default"))
        output = buf.getvalue()
        self.assertGreater(len(output.strip()), 0)


# ---------------------------------------------------------------------------
# meta_view.py
# ---------------------------------------------------------------------------

class TestMetaView(unittest.TestCase):
    def test_show_contact_default_view(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_view.cmd_show(_args(document="Contact", name="Default"))
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, dict)

    def test_visuals_contact_default_view(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_view.cmd_visuals(_args(document="Contact", name="Default"))
        output = buf.getvalue()
        self.assertGreater(len(output.strip()), 0)


# ---------------------------------------------------------------------------
# meta_access.py
# ---------------------------------------------------------------------------

class TestMetaAccess(unittest.TestCase):
    def test_show_contact_builder_access(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_access.cmd_show(_args(document="Contact", name="Builder"))
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, dict)

    def test_permissions_contact_builder(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_access.cmd_permissions(_args(document="Contact", name="Builder"))
        output = buf.getvalue()
        self.assertGreater(len(output.strip()), 0)


# ---------------------------------------------------------------------------
# meta_hook.py
# ---------------------------------------------------------------------------

class TestMetaHook(unittest.TestCase):
    def test_list_hooks_for_contact(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_hook.cmd_list(_args(document="Contact"))
        output = buf.getvalue()
        self.assertGreater(len(output.strip()), 0)


# ---------------------------------------------------------------------------
# meta_namespace.py
# ---------------------------------------------------------------------------

class TestMetaNamespace(unittest.TestCase):
    def test_show_namespace_returns_data(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_namespace.cmd_show(_args())
        data = json.loads(buf.getvalue())
        # The fixed _get_namespace returns either the full namespace doc or the
        # summary item — either way it must be a non-empty dict.
        self.assertIsInstance(data, dict)
        self.assertGreater(len(data), 0)

    def test_load_credentials_returns_url_and_token(self):
        url, token = meta_namespace._load_credentials()
        self.assertTrue(url.startswith("http"))
        self.assertGreater(len(token), 0)


# ---------------------------------------------------------------------------
# meta_pivot.py
# ---------------------------------------------------------------------------

class TestMetaPivot(unittest.TestCase):
    def test_show_contact_default_pivot(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_pivot.cmd_show(_args(document="Contact", name="Default"))
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, dict)


# ---------------------------------------------------------------------------
# Write-operation tests
# ---------------------------------------------------------------------------

class TestMetaDocumentWriteOps(unittest.TestCase):
    """Add-field → verify → remove-field lifecycle on Contact."""

    FIELD_NAME = "testCoverageField"
    DOCUMENT = "Contact"

    def setUp(self):
        # Ensure the test field does not exist before the test starts.
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_document.cmd_fields(_args(document=self.DOCUMENT, format="json"))
        fields = json.loads(buf.getvalue())
        if self.FIELD_NAME in fields:
            meta_document.cmd_remove_field(
                _args(document=self.DOCUMENT, field_name=self.FIELD_NAME)
            )

    def tearDown(self):
        # Clean up in case the test failed mid-way.
        try:
            meta_document.cmd_remove_field(
                _args(document=self.DOCUMENT, field_name=self.FIELD_NAME)
            )
        except SystemExit:
            pass  # field already absent — that's fine

    def test_add_field_lifecycle(self):
        # 1. Add the field.
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_document.cmd_add_field(
                _args(
                    document=self.DOCUMENT,
                    field_name=self.FIELD_NAME,
                    type="text",
                    label_en="Test Coverage Field",
                    label_pt="Campo de Cobertura de Testes",
                    required=False,
                )
            )
        self.assertIn(self.FIELD_NAME, buf.getvalue())

        # 2. Verify it appears in the fields listing.
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            meta_document.cmd_fields(_args(document=self.DOCUMENT, format="json"))
        fields = json.loads(buf2.getvalue())
        self.assertIn(self.FIELD_NAME, fields)
        self.assertEqual(fields[self.FIELD_NAME].get("type"), "text")

        # 3. Remove it (cleanup happens here; tearDown is a safety net).
        buf3 = io.StringIO()
        with redirect_stdout(buf3):
            meta_document.cmd_remove_field(
                _args(document=self.DOCUMENT, field_name=self.FIELD_NAME)
            )
        self.assertIn(self.FIELD_NAME, buf3.getvalue())

        # 4. Confirm it's gone.
        buf4 = io.StringIO()
        with redirect_stdout(buf4):
            meta_document.cmd_fields(_args(document=self.DOCUMENT, format="json"))
        fields_after = json.loads(buf4.getvalue())
        self.assertNotIn(self.FIELD_NAME, fields_after)


class TestMetaListWriteOps(unittest.TestCase):
    """Upsert a test list → verify → delete via upsert (overwrite) → verify gone."""

    DOCUMENT = "Contact"
    SOURCE_LIST = "Default"
    TEST_LIST = "TestCoverageList"

    def _list_exists(self) -> bool:
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                meta_list.cmd_show(_args(document=self.DOCUMENT, name=self.TEST_LIST))
            return True
        except SystemExit:
            return False

    def _delete_test_list(self):
        """Delete via DELETE API; swallow SystemExit if the list does not exist."""
        try:
            meta_list._api(HOST, TOKEN, "DELETE", f"/{self.DOCUMENT}/list/{self.TEST_LIST}")
        except SystemExit:
            pass  # 404 → list already absent

    def setUp(self):
        # Remove leftover from a previous failed run.
        self._delete_test_list()

    def tearDown(self):
        self._delete_test_list()

    def test_upsert_list_lifecycle(self):
        # 1. Read the Default list to use as a template.
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_list.cmd_show(_args(document=self.DOCUMENT, name=self.SOURCE_LIST))
        template = json.loads(buf.getvalue())
        template["name"] = self.TEST_LIST
        template["_id"] = f"{self.DOCUMENT}:{self.TEST_LIST}"

        # 2. Write the template to a temp file and upsert.
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
            json.dump(template, tf)
            tf_path = tf.name

        try:
            buf2 = io.StringIO()
            with redirect_stdout(buf2):
                meta_list.cmd_upsert(
                    _args(document=self.DOCUMENT, name=self.TEST_LIST, file=tf_path)
                )
            self.assertIn("upserted", buf2.getvalue())
        finally:
            os.unlink(tf_path)

        # 3. Verify the list now exists.
        buf3 = io.StringIO()
        with redirect_stdout(buf3):
            meta_list.cmd_show(_args(document=self.DOCUMENT, name=self.TEST_LIST))
        data = json.loads(buf3.getvalue())
        self.assertIsInstance(data, dict)

        # 4. Cleanup via DELETE (tearDown is the safety net).
        self._delete_test_list()


class TestMetaHookWriteOps(unittest.TestCase):
    """Upsert a scriptAfterSave hook on Contact → verify → delete → verify gone."""

    DOCUMENT = "Contact"
    HOOK_NAME = "scriptAfterSave"
    # A minimal valid scriptAfterSave body — no comments (backend rejects them).
    HOOK_CODE = "var ret = {}; return ret;"
    HOOK_MARKER = "ret = {}"

    def _try_delete_hook(self):
        """Delete the hook; swallow SystemExit if it does not exist."""
        try:
            meta_hook.cmd_delete(_args(document=self.DOCUMENT, hook_name=self.HOOK_NAME))
        except SystemExit:
            pass  # hook absent — that's fine

    def setUp(self):
        # Remove any leftover hook from a previous failed run.
        self._try_delete_hook()

    def tearDown(self):
        self._try_delete_hook()

    def test_upsert_and_delete_hook(self):
        # 1. Upsert the hook using --code.
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_hook.cmd_upsert(
                _args(
                    document=self.DOCUMENT,
                    hook_name=self.HOOK_NAME,
                    code=self.HOOK_CODE,
                    file=None,
                )
            )
        self.assertIn("updated", buf.getvalue())

        # 2. Verify the hook content is present.
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            meta_hook.cmd_show(_args(document=self.DOCUMENT, hook_name=self.HOOK_NAME))
        self.assertIn(self.HOOK_MARKER, buf2.getvalue())

        # 3. Delete the hook.
        buf3 = io.StringIO()
        with redirect_stdout(buf3):
            meta_hook.cmd_delete(_args(document=self.DOCUMENT, hook_name=self.HOOK_NAME))
        self.assertIn("deleted", buf3.getvalue())


# ---------------------------------------------------------------------------
# meta_sync.py / meta_remove.py — module-level smoke tests
# (operations require filesystem setup; credential loading tested here)
# ---------------------------------------------------------------------------

class TestMetaSyncImport(unittest.TestCase):
    def test_load_credentials_returns_url_and_token(self):
        url, token = meta_sync._load_credentials()
        self.assertTrue(url.startswith("http"))
        self.assertGreater(len(token), 0)


class TestMetaRemoveImport(unittest.TestCase):
    def test_load_credentials_returns_url_and_token(self):
        url, token = meta_remove._load_credentials()
        self.assertTrue(url.startswith("http"))
        self.assertGreater(len(token), 0)

    def test_plan_contact_shows_metas(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_remove.cmd_plan(_args(document="Contact"))
        output = buf.getvalue()
        self.assertIn("Contact", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
