"""
Integration tests for konecty-data scripts.
Requires Konecty at http://localhost:3000 with credentials in ~/.konecty/.env.
"""
import argparse
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

_DATA_SCRIPTS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../skills/konecty-data/scripts")
)
sys.path.insert(0, _DATA_SCRIPTS)

import modules as modules_mod  # noqa: E402
import find as find_mod         # noqa: E402
import create as create_mod     # noqa: E402
import update as update_mod     # noqa: E402
import delete as delete_mod     # noqa: E402


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


# ---------------------------------------------------------------------------
# modules.py
# ---------------------------------------------------------------------------

class TestModules(unittest.TestCase):
    def test_list_includes_contact(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            modules_mod.cmd_list(HOST, TOKEN, "pt_BR")
        self.assertIn("Contact", buf.getvalue())

    def test_list_includes_activity(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            modules_mod.cmd_list(HOST, TOKEN, "en")
        self.assertIn("Activity", buf.getvalue())

    def test_fields_contact_has_name(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            modules_mod.cmd_fields(HOST, TOKEN, "pt_BR", "Contact")
        self.assertIn("name", buf.getvalue())

    def test_fields_contact_has_status(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            modules_mod.cmd_fields(HOST, TOKEN, "pt_BR", "Contact")
        self.assertIn("status", buf.getvalue())

    def test_search_atividade_returns_activity(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            modules_mod.cmd_search(HOST, TOKEN, "pt_BR", "Atividade")
        self.assertIn("Activity", buf.getvalue())


# ---------------------------------------------------------------------------
# find.py
# ---------------------------------------------------------------------------

class TestFind(unittest.TestCase):
    def _find_args(self, **kwargs) -> argparse.Namespace:
        defaults = dict(
            document="Contact",
            filter=None,
            fields=None,
            sort=None,
            limit=2,
            start=0,
            post=False,
            output="json",
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_find_returns_list_with_ids(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            find_mod.cmd_find(HOST, TOKEN, self._find_args())
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertIn("_id", data[0])

    def test_find_with_status_filter(self):
        fil = '{"match":"and","conditions":[{"term":"status","operator":"equals","value":"Ativo"}]}'
        buf = io.StringIO()
        with redirect_stdout(buf):
            find_mod.cmd_find(HOST, TOKEN, self._find_args(filter=fil, limit=1))
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_find_field_projection(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            find_mod.cmd_find(HOST, TOKEN, self._find_args(fields="name,status", limit=1))
        data = json.loads(buf.getvalue())
        self.assertIn("name", data[0])

    def test_find_ndjson_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            find_mod.cmd_find(HOST, TOKEN, self._find_args(output="ndjson", limit=2))
        lines = [l for l in buf.getvalue().strip().splitlines() if l]
        self.assertEqual(len(lines), 2)
        record = json.loads(lines[0])
        self.assertIn("_id", record)

    def test_sql_query(self):
        args = argparse.Namespace(
            sql="SELECT _id, name FROM Contact LIMIT 2",
            include_meta=False,
            include_total=True,
            output="json",
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            find_mod.cmd_sql(HOST, TOKEN, args)
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_cross_module_query(self):
        args = argparse.Namespace(
            document="Contact",
            filter=None,
            fields="name",
            sort=None,
            limit=2,
            start=0,
            relations=None,
            include_meta=False,
            include_total=True,
            output="json",
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            find_mod.cmd_query(HOST, TOKEN, args)
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, list)


# ---------------------------------------------------------------------------
# create / update / delete — full CRUD lifecycle
# ---------------------------------------------------------------------------

class TestCRUDLifecycle(unittest.TestCase):
    """Create → Fetch → Patch → Preview → Delete."""

    _record_id: str | None = None

    @classmethod
    def setUpClass(cls) -> None:
        args = argparse.Namespace(
            document="Contact",
            data=(
                '{"name":{"first":"Teste","last":"Coverage-Integration"},'
                '"status":"Ativo","type":["Cliente"]}'
            ),
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            create_mod.cmd_create(HOST, TOKEN, args)
        record = json.loads(buf.getvalue())
        cls._record_id = record["_id"]

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._record_id:
            args = argparse.Namespace(
                document="Contact", term=cls._record_id, confirm=True
            )
            delete_mod.cmd_delete(HOST, TOKEN, args)

    def test_01_record_created_has_id(self):
        self.assertIsNotNone(self._record_id)
        self.assertGreater(len(self._record_id), 0)

    def test_02_fetch_returns_updated_at(self):
        args = argparse.Namespace(
            document="Contact", term=self._record_id, fields=""
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            update_mod.cmd_fetch(HOST, TOKEN, args)
        output = buf.getvalue()
        self.assertIn(self._record_id, output)
        self.assertIn("_updatedAt", output)

    def test_03_patch_updates_last_name(self):
        args = argparse.Namespace(
            document="Contact",
            term=self._record_id,
            data='{"name":{"first":"Teste","last":"Coverage-Updated"}}',
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            update_mod.cmd_patch(HOST, TOKEN, args)
        record = json.loads(buf.getvalue())
        self.assertEqual(record["name"]["last"], "Coverage-Updated")

    def test_04_update_explicit_ids(self):
        fetch_args = argparse.Namespace(
            document="Contact", term=self._record_id, fields=""
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            update_mod.cmd_fetch(HOST, TOKEN, fetch_args)
        # cmd_fetch format: '_updatedAt: "2026-..."'
        lines = [l for l in buf.getvalue().splitlines() if "_updatedAt" in l]
        updated_at = lines[0].split('"')[1]

        ids_payload = json.dumps([{"_id": self._record_id, "_updatedAt": updated_at}])
        update_args = argparse.Namespace(
            document="Contact",
            ids=ids_payload,
            data='{"priority":"Alta"}',
        )
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            update_mod.cmd_update(HOST, TOKEN, update_args)
        record = json.loads(buf2.getvalue())
        self.assertEqual(record.get("priority"), "Alta")

    def test_05_preview_shows_record(self):
        args = argparse.Namespace(
            document="Contact", term=self._record_id
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            delete_mod.cmd_preview(HOST, TOKEN, args)
        output = buf.getvalue()
        self.assertIn(self._record_id, output)
        self.assertIn("Contact", output)

    def test_06_delete_and_confirm(self):
        args = argparse.Namespace(
            document="Contact", term=self._record_id, confirm=True
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            delete_mod.cmd_delete(HOST, TOKEN, args)
        self.assertIn("Deleted successfully", buf.getvalue())
        self.__class__._record_id = None


if __name__ == "__main__":
    unittest.main(verbosity=2)
