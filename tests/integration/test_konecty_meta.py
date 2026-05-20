"""
Integration tests for konecty-meta scripts.
Requires Konecty at http://localhost:3000 with credentials in ~/.konecty/.env.
"""
import argparse
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

_META_SCRIPTS = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../skills/konecty-meta/scripts")
)
sys.path.insert(0, _META_SCRIPTS)

import meta_read    # noqa: E402
import meta_doctor  # noqa: E402


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
# meta_read.py
# ---------------------------------------------------------------------------

class TestMetaReadList(unittest.TestCase):
    def _args(self, **kwargs) -> argparse.Namespace:
        defaults = dict(host=HOST, token=TOKEN, format="table")
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_list_table_includes_contact(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_read.cmd_list(self._args())
        self.assertIn("Contact", buf.getvalue())

    def test_list_table_includes_activity(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_read.cmd_list(self._args())
        self.assertIn("Activity", buf.getvalue())

    def test_list_json_returns_list(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_read.cmd_list(self._args(format="json"))
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_list_json_entries_have_id_and_type(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_read.cmd_list(self._args(format="json"))
        data = json.loads(buf.getvalue())
        first = data[0]
        self.assertIn("_id", first)
        self.assertIn("type", first)


class TestMetaReadGet(unittest.TestCase):
    def _args(self, document="Contact", meta_type=None, name=None) -> argparse.Namespace:
        return argparse.Namespace(
            host=HOST, token=TOKEN,
            document=document, type=meta_type, name=name,
        )

    def test_get_contact_returns_list(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_read.cmd_get(self._args())
        data = json.loads(buf.getvalue())
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_get_contact_has_document_meta(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_read.cmd_get(self._args())
        data = json.loads(buf.getvalue())
        types = {m.get("type") for m in data}
        self.assertIn("document", types)

    def test_get_contact_has_access_metas(self):
        # cmd_get without --name returns all metas for the document
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_read.cmd_get(self._args())
        data = json.loads(buf.getvalue())
        access_metas = [m for m in data if m.get("type") == "access"]
        self.assertGreater(len(access_metas), 0)

    def test_types_for_contact(self):
        args = argparse.Namespace(host=HOST, token=TOKEN, document="Contact")
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_read.cmd_types(args)
        output = buf.getvalue()
        self.assertIn("document", output)
        self.assertIn("access", output)


# ---------------------------------------------------------------------------
# meta_doctor.py
# ---------------------------------------------------------------------------

class TestMetaDoctor(unittest.TestCase):
    def _args(self, document=None, fmt="table") -> argparse.Namespace:
        return argparse.Namespace(host=HOST, token=TOKEN, document=document, format=fmt)

    def test_check_all_returns_summary(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_doctor.cmd_check(self._args())
        output = buf.getvalue()
        self.assertIn("Summary:", output)
        self.assertIn("total=", output)

    def test_check_all_json_has_summary_key(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_doctor.cmd_check(self._args(fmt="json"))
        data = json.loads(buf.getvalue())
        self.assertIn("summary", data)
        self.assertIn("issues", data)
        self.assertIsInstance(data["issues"], list)

    def test_check_summary_counts_are_integers(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_doctor.cmd_check(self._args(fmt="json"))
        data = json.loads(buf.getvalue())
        summary = data["summary"]
        for key in ("total", "valid", "warnings", "errors"):
            self.assertIn(key, summary)
            self.assertIsInstance(summary[key], int)

    def test_check_single_document(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_doctor.cmd_check(self._args(document="Contact"))
        output = buf.getvalue()
        self.assertIn("Summary:", output)

    def test_check_queues(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            meta_doctor.cmd_check_queues(self._args())
        # Either prints queue issues or "Queue configuration is consistent."
        output = buf.getvalue()
        self.assertIsNotNone(output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
