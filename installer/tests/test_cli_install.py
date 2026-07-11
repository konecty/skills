"""Unit tests for cmd_install in cli.py (T10).

Isolation strategy:
- KONECTY_HOME env var → tmp directory (avoids touching ~/.konecty)
- os.chdir → tmp project directory (avoids cwd side-effects)
- fetcher.fetch_skills patched → returns a fake skills_root (no network)
- credentials.run_otp patched → avoids real subprocess
- banner.print_banner patched → silences output noise
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure the package is importable when run via the gate command.
_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from konecty_skills.cli import main


def _make_skills_root(base: Path) -> Path:
    """Create a minimal fake skills root with the two skill dirs."""
    skills_root = base / "fake_skills"
    (skills_root / "konecty-data" / "scripts").mkdir(parents=True)
    (skills_root / "konecty-data" / "SKILL.md").write_text("# konecty-data\n")
    (skills_root / "konecty-data" / "scripts" / "auth.py").write_text("# auth\n")
    (skills_root / "konecty-meta").mkdir(parents=True)
    (skills_root / "konecty-meta" / "SKILL.md").write_text("# konecty-meta\n")
    return skills_root


class TestCmdInstall(unittest.TestCase):
    """Tests for the install subcommand."""

    # --- lifecycle ----------------------------------------------------------

    def setUp(self) -> None:
        # Create a fresh tmp directory for every test.
        self._tmp = tempfile.mkdtemp(prefix="ks_test_")
        self._orig_cwd = os.getcwd()
        self._orig_konecty_home = os.environ.get("KONECTY_HOME")

        # Build fake skills_root inside tmp.
        self._skills_root = _make_skills_root(Path(self._tmp))

    def tearDown(self) -> None:
        os.chdir(self._orig_cwd)
        if self._orig_konecty_home is None:
            os.environ.pop("KONECTY_HOME", None)
        else:
            os.environ["KONECTY_HOME"] = self._orig_konecty_home
        # Clean up tmp directory.
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    # --- helpers ------------------------------------------------------------

    def _setup_project_dir(self) -> Path:
        """Create a project dir with .claude/ signal and chdir into it."""
        project = Path(self._tmp) / "project"
        project.mkdir(parents=True, exist_ok=True)
        (project / ".claude").mkdir()
        os.chdir(str(project))
        return project

    def _setup_empty_dir(self) -> Path:
        """Create an empty project dir (no engine signals) and chdir into it."""
        project = Path(self._tmp) / "empty_project"
        project.mkdir(parents=True, exist_ok=True)
        os.chdir(str(project))
        return project

    def _set_konecty_home(self) -> Path:
        """Point KONECTY_HOME to a fresh tmp sub-directory; return that path."""
        home = Path(self._tmp) / "konecty_home"
        home.mkdir(parents=True, exist_ok=True)
        os.environ["KONECTY_HOME"] = str(home)
        return home

    def _make_fetch_return(self):
        """Build the dict that a patched fetch_skills should return."""
        return {
            "tmp_dir": str(self._skills_root),
            "skills_root": str(self._skills_root),
            "ref": "main",
            "commit": None,
        }

    # --- test 1 : happy path ------------------------------------------------

    def test_install_happy_path(self) -> None:
        """install --yes --engine claude --scope project --url <u> returns 0
        and copies the skill files + writes the manifest + writes .env."""
        project = self._setup_project_dir()
        konecty_home = self._set_konecty_home()

        with (
            patch("konecty_skills.fetcher.fetch_skills", return_value=self._make_fetch_return()),
            patch("konecty_skills.credentials.run_otp", return_value=True),
            patch("konecty_skills.banner.print_full"),
        ):
            rc = main([
                "install",
                "--yes",
                "--engine", "claude",
                "--scope", "project",
                "--url", "https://h.example",
            ])

        self.assertEqual(rc, 0, "expected return code 0")

        # Skill file must exist under <cwd>/.claude/skills/konecty-data/
        skill_md = project / ".claude" / "skills" / "konecty-data" / "SKILL.md"
        self.assertTrue(skill_md.exists(), f"expected {skill_md} to exist")

        # Manifest must record the installation.
        import json
        manifest_path = konecty_home / "manifest.json"
        self.assertTrue(manifest_path.exists(), "manifest.json not created")
        with manifest_path.open() as fh:
            data = json.load(fh)
        installations = data.get("installations", {})
        # On macOS, /var/folders is a symlink to /private/var/folders;
        # Path.cwd() after chdir resolves the symlink, so use resolve() here.
        self.assertIn(str(project.resolve()), installations, "manifest missing installation entry for cwd")

        # .env must contain the URL.
        env_path = konecty_home / ".env"
        self.assertTrue(env_path.exists(), ".env not created")
        env_text = env_path.read_text()
        self.assertIn("KONECTY_URL=https://h.example", env_text)

    # --- test 2 : fallback to claude when no engine detected ----------------

    def test_install_no_engine_fallback(self) -> None:
        """When no engine flag and no signals, falls back to claude and installs."""
        self._setup_empty_dir()
        self._set_konecty_home()

        with (
            patch("konecty_skills.fetcher.fetch_skills", return_value=self._make_fetch_return()),
            patch("konecty_skills.credentials.run_otp", return_value=True),
            patch("konecty_skills.banner.print_full"),
        ):
            rc = main([
                "install",
                "--yes",
                "--url", "https://fallback.example",
            ])

        self.assertEqual(rc, 0, "expected return code 0 even with fallback engine")

        # Claude skills directory should have been created.
        cwd = Path(os.getcwd())
        skill_md = cwd / ".claude" / "skills" / "konecty-data" / "SKILL.md"
        self.assertTrue(skill_md.exists(), f"expected {skill_md} to exist after fallback install")

    # --- test 3 : FetchError returns 1 without installing -------------------

    def test_install_fetch_error_returns_1(self) -> None:
        """When fetch_skills raises FetchError, main returns 1 and no skills dir is created."""
        project = self._setup_project_dir()
        self._set_konecty_home()

        from konecty_skills.fetcher import FetchError

        with (
            patch("konecty_skills.fetcher.fetch_skills", side_effect=FetchError("network down")),
            patch("konecty_skills.banner.print_full"),
        ):
            rc = main([
                "install",
                "--yes",
                "--engine", "claude",
                "--scope", "project",
                "--url", "https://h.example",
            ])

        self.assertEqual(rc, 1, "expected return code 1 on FetchError")

        # Skills directory must NOT have been created.
        skills_dir = project / ".claude" / "skills"
        self.assertFalse(
            skills_dir.exists(),
            f"skills dir {skills_dir} should not exist after FetchError",
        )


if __name__ == "__main__":
    unittest.main()
