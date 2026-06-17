"""Unit tests for cmd_configure in cli.py (T11).

Isolation:
- KONECTY_HOME -> tmp directory (avoids ~/.konecty)
- os.chdir -> tmp project directory
- credentials.run_otp patched -> no real subprocess
- ui.confirm patched where needed
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from konecty_skills.cli import main


class TestCmdConfigure(unittest.TestCase):
    """Tests for the configure subcommand."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="ks_test_cfg_")
        self._orig_cwd = os.getcwd()
        self._orig_konecty_home = os.environ.get("KONECTY_HOME")

        # Point KONECTY_HOME to a fresh tmp sub-directory.
        self._konecty_home = Path(self._tmp) / "konecty_home"
        self._konecty_home.mkdir(parents=True, exist_ok=True)
        os.environ["KONECTY_HOME"] = str(self._konecty_home)

        # chdir into a clean project directory.
        project = Path(self._tmp) / "project"
        project.mkdir(parents=True, exist_ok=True)
        os.chdir(str(project))

    def tearDown(self) -> None:
        os.chdir(self._orig_cwd)
        if self._orig_konecty_home is None:
            os.environ.pop("KONECTY_HOME", None)
        else:
            os.environ["KONECTY_HOME"] = self._orig_konecty_home
        shutil.rmtree(self._tmp, ignore_errors=True)

    # --- test (a): --yes --url writes KONECTY_URL to <KONECTY_HOME>/.env ----

    def test_configure_yes_url_writes_env(self) -> None:
        """configure --yes --url https://h.example writes KONECTY_URL and rc=0."""
        rc = main(["configure", "--yes", "--url", "https://h.example"])

        self.assertEqual(rc, 0, "expected return code 0")

        env_path = self._konecty_home / ".env"
        self.assertTrue(env_path.exists(), ".env was not created")
        env_text = env_path.read_text()
        self.assertIn("KONECTY_URL=https://h.example", env_text)

    # --- test (b): existing .env + interactive confirm=False → no overwrite --

    def test_configure_existing_credentials_decline_overwrite(self) -> None:
        """With existing url+token, declining the overwrite prompt returns 0 without changing .env."""
        env_path = self._konecty_home / ".env"
        env_path.write_text("KONECTY_URL=https://original.example\nKONECTY_TOKEN=tok123\n")

        # Patch ui.confirm to always return False (user declines overwrite).
        with patch("konecty_skills.ui.confirm", return_value=False) as mock_confirm:
            rc = main(["configure", "--url", "https://new.example"])

        self.assertEqual(rc, 0, "expected return code 0 when user declines")

        # .env must NOT have been overwritten.
        env_text = env_path.read_text()
        self.assertIn("KONECTY_URL=https://original.example", env_text)
        self.assertNotIn("https://new.example", env_text)

        # confirm must have been called once (the overwrite prompt).
        mock_confirm.assert_called_once()

    # --- test (c): no existing credentials, --yes with no --url → warn, rc 0 -

    def test_configure_yes_no_url_no_existing_warns(self) -> None:
        """configure --yes with no --url and no existing URL warns and returns 0."""
        rc = main(["configure", "--yes"])
        self.assertEqual(rc, 0)

        # .env should not exist (nothing written).
        env_path = self._konecty_home / ".env"
        self.assertFalse(env_path.exists())

    # --- test (d): existing url only (no token), --yes --url overwrites ------

    def test_configure_yes_overwrites_existing_url(self) -> None:
        """configure --yes --url replaces an existing URL-only .env."""
        env_path = self._konecty_home / ".env"
        env_path.write_text("KONECTY_URL=https://old.example\n")

        rc = main(["configure", "--yes", "--url", "https://new.example"])

        self.assertEqual(rc, 0)
        env_text = env_path.read_text()
        self.assertIn("KONECTY_URL=https://new.example", env_text)
        self.assertNotIn("https://old.example", env_text)


if __name__ == "__main__":
    unittest.main()
