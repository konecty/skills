"""Unit tests for konecty_skills.credentials (T7)."""
from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from konecty_skills.credentials import (
    current_env,
    run_otp,
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


class TestRunOtpSuccess(unittest.TestCase):
    """run_otp returns True when both subprocess calls succeed."""

    def _make_ok(self):
        m = MagicMock()
        m.returncode = 0
        return m

    @patch("builtins.input", return_value="123456")
    @patch("subprocess.run")
    def test_returns_true_on_success_email(self, mock_run, _mock_input):
        mock_run.return_value = self._make_ok()
        result = run_otp("https://host", Path("/fake/auth.py"), "user@example.com")
        self.assertTrue(result)
        self.assertEqual(mock_run.call_count, 2)
        # First call: request-otp with --email
        first_cmd = mock_run.call_args_list[0][0][0]
        self.assertIn("request-otp", first_cmd)
        self.assertIn("--email", first_cmd)
        self.assertIn("user@example.com", first_cmd)

    @patch("builtins.input", return_value="654321")
    @patch("subprocess.run")
    def test_returns_true_on_success_phone(self, mock_run, _mock_input):
        mock_run.return_value = self._make_ok()
        result = run_otp("https://host", Path("/fake/auth.py"), "+5511999999999")
        self.assertTrue(result)
        # First call must use --phone, not --email
        first_cmd = mock_run.call_args_list[0][0][0]
        self.assertIn("--phone", first_cmd)
        self.assertNotIn("--email", first_cmd)

    @patch("builtins.input", return_value="111111")
    @patch("subprocess.run")
    def test_verify_otp_includes_code(self, mock_run, _mock_input):
        mock_run.return_value = self._make_ok()
        run_otp("https://host", Path("/fake/auth.py"), "a@b.com")
        second_cmd = mock_run.call_args_list[1][0][0]
        self.assertIn("verify-otp", second_cmd)
        self.assertIn("--otp", second_cmd)
        self.assertIn("111111", second_cmd)


class TestRunOtpFailure(unittest.TestCase):
    """run_otp returns False on first-call failure and does not make the second call."""

    @patch("builtins.input", return_value="000000")
    @patch("subprocess.run")
    def test_first_call_nonzero_skips_verify(self, mock_run, _mock_input):
        bad = MagicMock()
        bad.returncode = 1
        mock_run.return_value = bad
        result = run_otp("https://host", Path("/fake/auth.py"), "user@example.com")
        self.assertFalse(result)
        # verify-otp must NOT have been called
        self.assertEqual(mock_run.call_count, 1)

    @patch("builtins.input", return_value="000000")
    @patch("subprocess.run")
    def test_second_call_nonzero_returns_false(self, mock_run, _mock_input):
        ok = MagicMock()
        ok.returncode = 0
        bad = MagicMock()
        bad.returncode = 1
        mock_run.side_effect = [ok, bad]
        result = run_otp("https://host", Path("/fake/auth.py"), "user@example.com")
        self.assertFalse(result)
        self.assertEqual(mock_run.call_count, 2)


class TestRunOtpOSError(unittest.TestCase):
    """run_otp must catch OSError and return False without propagating."""

    @patch("builtins.input", return_value="000000")
    @patch("subprocess.run", side_effect=OSError("no such file"))
    def test_oserror_returns_false(self, _mock_run, _mock_input):
        result = run_otp("https://host", Path("/nonexistent/auth.py"), "x@example.com")
        self.assertFalse(result)

    @patch("builtins.input", return_value="000000")
    @patch("subprocess.run", side_effect=subprocess.SubprocessError("fail"))
    def test_subprocess_error_returns_false(self, _mock_run, _mock_input):
        result = run_otp("https://host", Path("/fake/auth.py"), "x@example.com")
        self.assertFalse(result)


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

    def test_preserves_existing_token_line(self):
        # Pre-write a KONECTY_TOKEN line.
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        self.env_path.write_text(
            "KONECTY_TOKEN=abc123\nSOME_OTHER=val\n", encoding="utf-8"
        )
        write_url_only("https://updated.example.com", path=self.env_path)
        env = current_env(path=self.env_path)
        self.assertEqual(env["url"], "https://updated.example.com")
        self.assertEqual(env["token"], "abc123")

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
        self.assertIsNone(env["token"])

    def test_current_env_both_values(self):
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        self.env_path.write_text(
            "KONECTY_URL=https://x.com\nKONECTY_TOKEN=tok99\n", encoding="utf-8"
        )
        env = current_env(path=self.env_path)
        self.assertEqual(env["url"], "https://x.com")
        self.assertEqual(env["token"], "tok99")


if __name__ == "__main__":
    unittest.main()
