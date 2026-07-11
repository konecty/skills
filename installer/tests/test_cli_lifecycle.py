"""Unit tests for cmd_update and cmd_uninstall in cli.py (T13).

Isolation:
- KONECTY_HOME -> tmp directory (avoids ~/.konecty)
- os.chdir -> tmp project directory
- fetcher.fetch_skills patched -> returns a fake skills_root (no network)
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


def _make_fake_skills_root(base: Path, skill_md_content: bytes = b"# konecty-data\n") -> Path:
    """Create a minimal fake skills root with one skill dir."""
    skills_root = base / "fake_skills"
    skill_dir = skills_root / "konecty-data"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_bytes(skill_md_content)
    return skills_root


class TestCmdUpdate(unittest.TestCase):
    """Tests for the update subcommand."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="ks_test_update_")
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

    def _seed_installation(self, skill_md_content: bytes = b"# old content\n") -> Path:
        """Write a skill file on disk and a matching manifest entry."""
        skill_dest = self._project.resolve() / ".claude" / "skills" / "konecty-data"
        skill_dest.mkdir(parents=True, exist_ok=True)
        skill_md = skill_dest / "SKILL.md"
        skill_md.write_bytes(skill_md_content)
        recorded_hash = _sha256(skill_md_content)

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
                            "files": {"SKILL.md": recorded_hash},
                        }
                    },
                }
            },
        }
        (self._konecty_home / "manifest.json").write_text(json.dumps(manifest_data))
        return skill_dest

    # --- test (a): update rewrites unmodified file --------------------------

    def test_update_rewrites_file(self) -> None:
        """update patches an unmodified skill file and returns rc=0."""
        old_content = b"# old content\n"
        skill_dest = self._seed_installation(old_content)
        skill_md = skill_dest / "SKILL.md"

        # New content in the fetched skills_root.
        new_content = b"# new content from update\n"
        fake_skills = _make_fake_skills_root(Path(self._tmp), new_content)
        fetch_return = {
            "tmp_dir": str(fake_skills),
            "skills_root": str(fake_skills),
            "ref": "main",
            "commit": None,
        }

        buf = io.StringIO()
        with (
            patch("konecty_skills.fetcher.fetch_skills", return_value=fetch_return),
            patch("sys.stdout", buf),
        ):
            rc = main(["update", "--yes"])

        self.assertEqual(rc, 0)
        # The file on disk should now have new content.
        self.assertEqual(skill_md.read_bytes(), new_content)
        # Manifest should have been updated.
        manifest_data = json.loads((self._konecty_home / "manifest.json").read_text())
        new_hash = manifest_data["installations"][self._project_resolved]["skills"][
            "claude:konecty-data"
        ]["files"]["SKILL.md"]
        self.assertEqual(new_hash, _sha256(new_content))

    # --- test (b): update with no installation returns 1 --------------------

    def test_update_no_installation_returns_1(self) -> None:
        """update with no manifest entry for cwd returns rc=1."""
        # Empty manifest.
        (self._konecty_home / "manifest.json").write_text(
            json.dumps({"schema": 1, "installations": {}})
        )
        fake_skills = _make_fake_skills_root(Path(self._tmp))
        fetch_return = {
            "tmp_dir": str(fake_skills),
            "skills_root": str(fake_skills),
            "ref": "main",
            "commit": None,
        }
        with patch("konecty_skills.fetcher.fetch_skills", return_value=fetch_return):
            rc = main(["update", "--yes"])

        self.assertEqual(rc, 1)

    # --- test (c): FetchError returns 1 -------------------------------------

    def test_update_fetch_error_returns_1(self) -> None:
        """update returns rc=1 when fetch_skills raises FetchError."""
        self._seed_installation()

        from konecty_skills.fetcher import FetchError

        with patch("konecty_skills.fetcher.fetch_skills", side_effect=FetchError("down")):
            rc = main(["update", "--yes"])

        self.assertEqual(rc, 1)


class TestCmdUninstall(unittest.TestCase):
    """Tests for the uninstall subcommand."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="ks_test_uninstall_")
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

    def _seed_installation(self) -> Path:
        """Write skill files on disk and a matching manifest."""
        skill_dest = self._project.resolve() / ".claude" / "skills" / "konecty-data"
        skill_dest.mkdir(parents=True, exist_ok=True)
        content = b"# konecty-data\n"
        (skill_dest / "SKILL.md").write_bytes(content)
        recorded_hash = _sha256(content)

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
                            "files": {"SKILL.md": recorded_hash},
                        }
                    },
                }
            },
        }
        (self._konecty_home / "manifest.json").write_text(json.dumps(manifest_data))
        return skill_dest

    # --- test (a): uninstall --yes removes files and manifest entry ----------

    def test_uninstall_yes_removes_files_and_manifest_entry(self) -> None:
        """uninstall --yes removes tracked files and clears the manifest entry."""
        skill_dest = self._seed_installation()
        skill_md = skill_dest / "SKILL.md"
        self.assertTrue(skill_md.exists(), "pre-condition: skill file must exist")

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = main(["uninstall", "--yes"])

        self.assertEqual(rc, 0)
        # File must be gone.
        self.assertFalse(skill_md.exists(), "skill file should have been removed")
        # Manifest entry must be gone.
        manifest_data = json.loads((self._konecty_home / "manifest.json").read_text())
        self.assertNotIn(
            self._project_resolved,
            manifest_data.get("installations", {}),
            "manifest entry should have been removed",
        )

    # --- test (b): uninstall with no installation returns 1 -----------------

    def test_uninstall_no_installation_returns_1(self) -> None:
        """uninstall when nothing installed for cwd returns rc=1."""
        (self._konecty_home / "manifest.json").write_text(
            json.dumps({"schema": 1, "installations": {}})
        )
        rc = main(["uninstall", "--yes"])
        self.assertEqual(rc, 1)

    # --- test (c): uninstall declined returns 0 without removing -------------

    def test_uninstall_declined_keeps_files(self) -> None:
        """uninstall without --yes, user declines → rc=0 and files untouched."""
        skill_dest = self._seed_installation()
        skill_md = skill_dest / "SKILL.md"

        with patch("konecty_skills.ui.confirm", return_value=False):
            rc = main(["uninstall"])

        self.assertEqual(rc, 0)
        self.assertTrue(skill_md.exists(), "skill file must still exist after declining")

    # --- test (d): --purge also removes credentials -------------------------

    def test_uninstall_purge_removes_credentials(self) -> None:
        """uninstall --yes --purge removes the .env credentials file."""
        self._seed_installation()
        env_path = self._konecty_home / ".env"
        env_path.write_text("KONECTY_URL=https://h.example\n")

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = main(["uninstall", "--yes", "--purge"])

        self.assertEqual(rc, 0)
        self.assertFalse(env_path.exists(), ".env should have been removed with --purge")


if __name__ == "__main__":
    unittest.main()
