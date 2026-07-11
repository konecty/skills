"""Unit tests for cmd_status and cmd_doctor in cli.py (T12).

Isolation:
- KONECTY_HOME -> tmp directory (avoids ~/.konecty)
- os.chdir -> tmp project directory
- _probe_konecty patched for doctor tests (no network)
- manifest.json seeded directly for each test
"""
from __future__ import annotations

import hashlib
import io
import json
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TestCmdStatus(unittest.TestCase):
    """Tests for the status subcommand."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="ks_test_status_")
        self._orig_cwd = os.getcwd()
        self._orig_konecty_home = os.environ.get("KONECTY_HOME")

        # Point KONECTY_HOME to a fresh tmp sub-directory.
        self._konecty_home = Path(self._tmp) / "konecty_home"
        self._konecty_home.mkdir(parents=True, exist_ok=True)
        os.environ["KONECTY_HOME"] = str(self._konecty_home)

        # Create project dir and chdir into it.
        self._project = Path(self._tmp) / "project"
        self._project.mkdir(parents=True, exist_ok=True)
        os.chdir(str(self._project))

        # Resolved project path (handles macOS /var -> /private/var symlink).
        self._project_resolved = str(self._project.resolve())

    def tearDown(self) -> None:
        os.chdir(self._orig_cwd)
        if self._orig_konecty_home is None:
            os.environ.pop("KONECTY_HOME", None)
        else:
            os.environ["KONECTY_HOME"] = self._orig_konecty_home
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _seed_manifest(self, extra_root: str | None = None) -> None:
        """Write a manifest.json with one (or two) installation entries."""
        installations = {
            self._project_resolved: {
                "installed_at": "2024-01-01T00:00:00+00:00",
                "source": {"repo": "konecty/skills", "ref": "main", "commit": None},
                "scope": "project",
                "engines": ["claude", "agents"],
                "skills": {
                    "claude:konecty-data": {
                        "dest": ".claude/skills/konecty-data",
                        "files": {"SKILL.md": "abc123"},
                    },
                    "claude:konecty-meta": {
                        "dest": ".claude/skills/konecty-meta",
                        "files": {"SKILL.md": "def456"},
                    },
                },
            }
        }
        if extra_root:
            installations[extra_root] = {
                "installed_at": "2024-02-01T00:00:00+00:00",
                "source": {"repo": "konecty/skills", "ref": "v1", "commit": None},
                "scope": "project",
                "engines": ["cursor"],
                "skills": {},
            }
        manifest_path = self._konecty_home / "manifest.json"
        manifest_path.write_text(json.dumps({"schema": 1, "installations": installations}))

    # --- test (a): status for cwd -------------------------------------------

    def test_status_current_dir(self) -> None:
        """status (no --all) reports engines and skills for the current dir."""
        self._seed_manifest()

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = main(["status"])

        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("claude", out)
        self.assertIn("agents", out)
        self.assertIn("konecty-data", out)

    # --- test (b): --all lists every installation ---------------------------

    def test_status_all(self) -> None:
        """status --all lists all installations including a second root."""
        other_root = str((Path(self._tmp) / "other").resolve())
        self._seed_manifest(extra_root=other_root)

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = main(["status", "--all"])

        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn(self._project_resolved, out)
        self.assertIn(other_root, out)

    # --- test (c): no installation for cwd -> helpful message ---------------

    def test_status_no_installation_message(self) -> None:
        """status when nothing installed for cwd shows a helpful message."""
        # Seed manifest but with a different root key.
        other_root = str((Path(self._tmp) / "other").resolve())
        self._seed_manifest(extra_root=other_root)
        # Remove the project entry so nothing matches cwd.
        manifest_path = self._konecty_home / "manifest.json"
        data = json.loads(manifest_path.read_text())
        del data["installations"][self._project_resolved]
        manifest_path.write_text(json.dumps(data))

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = main(["status"])

        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("No installation found", out)

    # --- test (d): credentials shown in status output -----------------------

    def test_status_shows_credential_presence(self) -> None:
        """status shows url/token set/missing from .env."""
        self._seed_manifest()
        env_path = self._konecty_home / ".env"
        env_path.write_text("KONECTY_URL=https://h.example\n")

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = main(["status"])

        self.assertEqual(rc, 0)
        out = buf.getvalue()
        # url is set, token is missing
        self.assertIn("url=set", out)
        self.assertIn("token=missing", out)


class TestCmdDoctor(unittest.TestCase):
    """Tests for the doctor subcommand."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="ks_test_doctor_")
        self._orig_cwd = os.getcwd()
        self._orig_konecty_home = os.environ.get("KONECTY_HOME")

        self._konecty_home = Path(self._tmp) / "konecty_home"
        self._konecty_home.mkdir(parents=True, exist_ok=True)
        os.environ["KONECTY_HOME"] = str(self._konecty_home)

        self._project = Path(self._tmp) / "project"
        self._project.mkdir(parents=True, exist_ok=True)
        os.chdir(str(self._project))

        self._project_resolved = str(self._project.resolve())

    def tearDown(self) -> None:
        os.chdir(self._orig_cwd)
        if self._orig_konecty_home is None:
            os.environ.pop("KONECTY_HOME", None)
        else:
            os.environ["KONECTY_HOME"] = self._orig_konecty_home
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_doctor_reports_modified_file(self) -> None:
        """doctor reports a modified file and an ok file; probe patched to return (True, 'ok')."""
        # Create two skill files on disk.
        skill_dir = self._project.resolve() / ".claude" / "skills" / "konecty-data"
        skill_dir.mkdir(parents=True, exist_ok=True)

        ok_file = skill_dir / "SKILL.md"
        ok_content = b"# konecty-data\n"
        ok_file.write_bytes(ok_content)
        ok_hash = _sha256(ok_content)

        mod_file = skill_dir / "scripts" / "auth.py"
        mod_file.parent.mkdir(parents=True, exist_ok=True)
        mod_file.write_bytes(b"# original\n")
        # Record a different hash so it looks modified.
        modified_hash = _sha256(b"# something completely different\n")

        manifest_data = {
            "schema": 1,
            "installations": {
                self._project_resolved: {
                    "installed_at": "2024-01-01T00:00:00+00:00",
                    "source": {"repo": "konecty/skills", "ref": "main", "commit": None},
                    "scope": "project",
                    "engines": ["claude"],
                    "skills": {
                        "claude:konecty-data": {
                            "dest": ".claude/skills/konecty-data",
                            "files": {
                                "SKILL.md": ok_hash,
                                "scripts/auth.py": modified_hash,
                            },
                        }
                    },
                }
            },
        }
        (self._konecty_home / "manifest.json").write_text(json.dumps(manifest_data))

        # Provide credentials so _probe_konecty is called.
        (self._konecty_home / ".env").write_text(
            "KONECTY_URL=https://h.example\nKONECTY_TOKEN=tok123\n"
        )

        buf = io.StringIO()
        with (
            patch("konecty_skills.cli._probe_konecty", return_value=(True, "ok")),
            patch("sys.stdout", buf),
        ):
            rc = main(["doctor"])

        self.assertEqual(rc, 0)
        out = buf.getvalue()
        # Should report the modified conflict.
        self.assertIn("scripts/auth.py", out)
        self.assertIn("modified", out)
        # Should confirm connection is OK.
        self.assertIn("ok", out.lower())

    def test_doctor_all_match(self) -> None:
        """doctor reports 'All files match' when hashes are correct."""
        skill_dir = self._project.resolve() / ".claude" / "skills" / "konecty-data"
        skill_dir.mkdir(parents=True, exist_ok=True)
        f = skill_dir / "SKILL.md"
        content = b"# konecty-data\n"
        f.write_bytes(content)
        correct_hash = _sha256(content)

        manifest_data = {
            "schema": 1,
            "installations": {
                self._project_resolved: {
                    "installed_at": "2024-01-01T00:00:00+00:00",
                    "source": {"repo": "konecty/skills", "ref": "main", "commit": None},
                    "scope": "project",
                    "engines": ["claude"],
                    "skills": {
                        "claude:konecty-data": {
                            "dest": ".claude/skills/konecty-data",
                            "files": {"SKILL.md": correct_hash},
                        }
                    },
                }
            },
        }
        (self._konecty_home / "manifest.json").write_text(json.dumps(manifest_data))
        # No credentials -> warn path.
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = main(["doctor"])

        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("All files match manifest", out)
        self.assertIn("No credentials configured", out)


class TestProbeKonectySchemeGuard(unittest.TestCase):
    """B310 — _probe_konecty must reject unsupported URL schemes."""

    def test_unsupported_scheme_returns_false(self) -> None:
        """A file:// or other non-http/https URL must not reach urlopen."""
        from konecty_skills.cli import _probe_konecty

        ok, detail = _probe_konecty("file:///etc/passwd", "tok")
        self.assertFalse(ok)
        self.assertIn("scheme", detail.lower())

    def test_ftp_scheme_returns_false(self) -> None:
        """An ftp:// URL must return (False, ...) without network access."""
        from konecty_skills.cli import _probe_konecty

        ok, detail = _probe_konecty("ftp://example.com", "tok")
        self.assertFalse(ok)

    def test_https_scheme_is_allowed(self) -> None:
        """https:// passes the scheme check (network call patched out)."""
        from konecty_skills.cli import _probe_konecty
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            ok, _detail = _probe_konecty("https://example.com", "tok")
        # Should fail due to network error, not scheme error.
        self.assertFalse(ok)

    def test_http_scheme_is_allowed(self) -> None:
        """http:// passes the scheme check (network call patched out)."""
        from konecty_skills.cli import _probe_konecty
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            ok, _detail = _probe_konecty("http://localhost:3000", "tok")
        # Should fail due to network error, not scheme error.
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
