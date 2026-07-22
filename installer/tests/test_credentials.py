"""Unit tests for konecty_skills.credentials (T7; trimmed to a URL cache in
T20/0.3.0 — the legacy manual-login/Bearer-header admin token flow was
removed, OAuth is the only auth path)."""
from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from konecty_skills.credentials import (
    current_env,
    validate_url,
    write_url_only,
)


class TestValidateUrl(unittest.TestCase):
    """validate_url must accept http/https with a netloc; reject everything else."""

    def test_accepts_https(self):
        self.assertTrue(validate_url("https://konecty.example.com"))

    def test_accepts_http_with_port(self):
        self.assertTrue(validate_url("http://localhost:3000"))

    def test_accepts_http_ip(self):
        self.assertTrue(validate_url("http://192.168.1.1"))

    def test_rejects_empty_string(self):
        self.assertFalse(validate_url(""))

    def test_rejects_ftp(self):
        self.assertFalse(validate_url("ftp://files.example.com"))

    def test_rejects_plain_string(self):
        self.assertFalse(validate_url("not a url"))

    def test_rejects_no_scheme(self):
        self.assertFalse(validate_url("example.com"))


class TestWriteUrlOnlyAndCurrentEnv(unittest.TestCase):
    """write_url_only and current_env integration over a tmp file."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.env_path = Path(self._td.name) / ".konecty" / ".env"

    def tearDown(self):
        self._td.cleanup()

    def test_creates_env_with_url(self):
        write_url_only("https://new.example.com", path=self.env_path)
        self.assertTrue(self.env_path.exists())
        env = current_env(path=self.env_path)
        self.assertEqual(env["url"], "https://new.example.com")

    def test_sets_file_mode_0o600(self):
        write_url_only("https://new.example.com", path=self.env_path)
        file_mode = stat.S_IMODE(os.stat(self.env_path).st_mode)
        self.assertEqual(file_mode, 0o600)

    def test_preserves_other_lines(self):
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        self.env_path.write_text("SOME_OTHER=val\n", encoding="utf-8")
        write_url_only("https://updated.example.com", path=self.env_path)
        content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("SOME_OTHER=val", content)
        env = current_env(path=self.env_path)
        self.assertEqual(env["url"], "https://updated.example.com")

    def test_replaces_existing_url_line(self):
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        self.env_path.write_text("KONECTY_URL=https://old.example.com\n", encoding="utf-8")
        write_url_only("https://new.example.com", path=self.env_path)
        content = self.env_path.read_text(encoding="utf-8")
        self.assertNotIn("old.example.com", content)
        self.assertIn("new.example.com", content)

    def test_current_env_missing_file(self):
        env = current_env(path=Path(self._td.name) / "nonexistent" / ".env")
        self.assertIsNone(env["url"])

    def test_current_env_reads_url(self):
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        self.env_path.write_text("KONECTY_URL=https://x.com\n", encoding="utf-8")
        env = current_env(path=self.env_path)
        self.assertEqual(env["url"], "https://x.com")


if __name__ == "__main__":
    unittest.main()
