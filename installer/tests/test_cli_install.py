"""Unit tests for cmd_install in cli.py (T10, reworked in T18 for MCP-first).

Isolation strategy:
- KONECTY_HOME env var → tmp directory (avoids touching ~/.konecty)
- os.chdir → tmp project directory (avoids cwd side-effects)
- fetcher.fetch_skills patched → returns a fake skills_root (no network)
- mcp_config.probe_well_known / register patched → no network, no claude CLI
- credentials.otp_login patched → no subprocess/network
- banner.print_full patched → silences output noise
"""
from __future__ import annotations

import io
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

from konecty_skills import fetcher, mcp_config
from konecty_skills.cli import main

ALL_SKILLS = ("konecty-data", "konecty-meta", "konecty-setup", "konecty-dev")


def _make_skills_root(base: Path) -> Path:
    """Create a minimal fake skills root with all four skill dirs."""
    skills_root = base / "fake_skills"
    for skill in ALL_SKILLS:
        (skills_root / skill).mkdir(parents=True)
        (skills_root / skill / "SKILL.md").write_text(f"# {skill}\n")
    return skills_root


def _probe_ok(url: str, timeout: int = 10) -> dict:
    return {"status": "ok", "resource": f"{url}/mcp", "detail": "well-known OK"}


class TestCmdInstall(unittest.TestCase):
    """Tests for the install subcommand (MCP-first flow)."""

    # --- lifecycle ----------------------------------------------------------

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="ks_test_")
        self._orig_cwd = os.getcwd()
        self._orig_konecty_home = os.environ.get("KONECTY_HOME")
        self._skills_root = _make_skills_root(Path(self._tmp))

    def tearDown(self) -> None:
        os.chdir(self._orig_cwd)
        if self._orig_konecty_home is None:
            os.environ.pop("KONECTY_HOME", None)
        else:
            os.environ["KONECTY_HOME"] = self._orig_konecty_home
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    # --- helpers ------------------------------------------------------------

    def _setup_project_dir(self) -> Path:
        project = Path(self._tmp) / "project"
        project.mkdir(parents=True, exist_ok=True)
        (project / ".claude").mkdir(exist_ok=True)
        os.chdir(str(project))
        return project

    def _setup_empty_dir(self) -> Path:
        project = Path(self._tmp) / "empty_project"
        project.mkdir(parents=True, exist_ok=True)
        os.chdir(str(project))
        return project

    def _set_konecty_home(self) -> Path:
        home = Path(self._tmp) / "konecty_home"
        home.mkdir(parents=True, exist_ok=True)
        os.environ["KONECTY_HOME"] = str(home)
        return home

    def _make_fetch_return(self):
        return {
            "tmp_dir": str(self._skills_root),
            "skills_root": str(self._skills_root),
            "ref": "main",
            "commit": None,
        }

    def _patches(self, register_return=None, probe=_probe_ok):
        """Common patch set: no network, no claude CLI, silent banner."""
        if register_return is None:
            register_return = {"executed": True, "ok": True, "detail": "added"}
        return (
            patch("konecty_skills.fetcher.fetch_skills", return_value=self._make_fetch_return()),
            patch("konecty_skills.mcp_config.probe_well_known", side_effect=probe),
            patch("konecty_skills.mcp_config.register", return_value=register_return),
            patch("konecty_skills.banner.print_full"),
        )

    # --- happy path (MCPF-20): validate → register → copy 4 skills -----------

    def test_install_happy_path_registers_mcp_and_copies_four_skills(self) -> None:
        project = self._setup_project_dir()
        konecty_home = self._set_konecty_home()

        p_fetch, p_probe, p_register, p_banner = self._patches()
        with p_fetch, p_probe, p_register as mock_register, p_banner:
            rc = main([
                "install", "--yes",
                "--engine", "claude", "--scope", "project",
                "--url", "https://h.example",
            ])

        self.assertEqual(rc, 0)

        # All four skills copied (incl. konecty-setup).
        for skill in ALL_SKILLS:
            skill_md = project / ".claude" / "skills" / skill / "SKILL.md"
            self.assertTrue(skill_md.exists(), f"expected {skill_md} to exist")

        # User MCP registered with the exact template argv.
        mock_register.assert_called_once_with(
            "konecty", mcp_config.build_add_user("https://h.example")
        )

        # Manifest must record the installation.
        import json
        manifest_path = konecty_home / "manifest.json"
        self.assertTrue(manifest_path.exists(), "manifest.json not created")
        with manifest_path.open() as fh:
            data = json.load(fh)
        self.assertIn(str(project.resolve()), data.get("installations", {}))

    # --- URL validation branches (MCPF-01 / Edge Cases) ----------------------

    def test_install_rejects_http_url(self) -> None:
        project = self._setup_project_dir()
        self._set_konecty_home()

        p_fetch, p_probe, p_register, p_banner = self._patches()
        with p_fetch, p_probe, p_register as mock_register, p_banner:
            rc = main([
                "install", "--yes", "--engine", "claude",
                "--url", "http://h.example",
            ])

        self.assertEqual(rc, 1, "http:// URL must abort the install")
        mock_register.assert_not_called()
        self.assertFalse((project / ".claude" / "skills").exists(),
                         "nothing must be installed on URL rejection")

    def test_install_normalizes_trailing_slash_and_path(self) -> None:
        self._setup_project_dir()
        self._set_konecty_home()

        p_fetch, p_probe, p_register, p_banner = self._patches()
        with p_fetch, p_probe, p_register as mock_register, p_banner:
            rc = main([
                "install", "--yes", "--engine", "claude",
                "--url", "https://h.example/some/path/",
            ])

        self.assertEqual(rc, 0)
        mock_register.assert_called_once_with(
            "konecty", mcp_config.build_add_user("https://h.example")
        )

    def test_install_no_url_yes_mode_skips_mcp_but_installs(self) -> None:
        project = self._setup_project_dir()
        self._set_konecty_home()

        p_fetch, p_probe, p_register, p_banner = self._patches()
        buf = io.StringIO()
        with p_fetch, p_probe, p_register as mock_register, p_banner, patch("sys.stdout", buf):
            rc = main(["install", "--yes", "--engine", "claude"])

        self.assertEqual(rc, 0)
        mock_register.assert_not_called()
        self.assertIn("skipping MCP registration", buf.getvalue())
        self.assertTrue(
            (project / ".claude" / "skills" / "konecty-data" / "SKILL.md").exists()
        )

    # --- probe branches (MCPF-02) --------------------------------------------

    def test_install_no_mcp_server_aborts_with_pin_message(self) -> None:
        project = self._setup_project_dir()
        self._set_konecty_home()

        def probe_404(url, timeout=10):
            return {"status": "no_mcp", "resource": None, "detail": "HTTP 404"}

        p_fetch, p_probe, p_register, p_banner = self._patches(probe=probe_404)
        err = io.StringIO()
        with p_fetch, p_probe, p_register as mock_register, p_banner, patch("sys.stderr", err):
            rc = main([
                "install", "--yes", "--engine", "claude",
                "--url", "https://old.example",
            ])

        self.assertEqual(rc, 1)
        mock_register.assert_not_called()
        self.assertIn("does not expose MCP", err.getvalue())
        self.assertFalse((project / ".claude" / "skills").exists())

    def test_install_unreachable_url_aborts(self) -> None:
        self._setup_project_dir()
        self._set_konecty_home()

        def probe_down(url, timeout=10):
            return {"status": "unreachable", "resource": None, "detail": "timed out"}

        p_fetch, p_probe, p_register, p_banner = self._patches(probe=probe_down)
        with p_fetch, p_probe, p_register as mock_register, p_banner:
            rc = main([
                "install", "--yes", "--engine", "claude",
                "--url", "https://down.example",
            ])

        self.assertEqual(rc, 1)
        mock_register.assert_not_called()

    def test_install_audience_mismatch_warns_but_proceeds(self) -> None:
        self._setup_project_dir()
        self._set_konecty_home()

        def probe_mismatch(url, timeout=10):
            return {
                "status": "mismatch",
                "resource": "https://other.example/mcp",
                "detail": "audience misconfiguration (PLATFORM_MCP_RESOURCE_URL)",
            }

        p_fetch, p_probe, p_register, p_banner = self._patches(probe=probe_mismatch)
        buf = io.StringIO()
        with p_fetch, p_probe, p_register as mock_register, p_banner, patch("sys.stdout", buf):
            rc = main([
                "install", "--yes", "--engine", "claude",
                "--url", "https://h.example",
            ])

        self.assertEqual(rc, 0, "mismatch is a warning, not a failure")
        mock_register.assert_called_once()
        self.assertIn("audience misconfiguration", buf.getvalue())

    # --- claude CLI absent (MCPF-21) ------------------------------------------

    def test_install_cli_absent_prints_commands_and_succeeds(self) -> None:
        self._setup_project_dir()
        self._set_konecty_home()

        fallback = {
            "executed": False,
            "commands": [
                "claude mcp remove --scope user konecty",
                "claude mcp add --transport http --scope user konecty https://h.example/mcp",
            ],
        }
        p_fetch, p_probe, p_register, p_banner = self._patches(register_return=fallback)
        buf = io.StringIO()
        with p_fetch, p_probe, p_register, p_banner, patch("sys.stdout", buf):
            rc = main([
                "install", "--yes", "--engine", "claude",
                "--url", "https://h.example",
            ])

        self.assertEqual(rc, 0, "missing claude CLI must never fail the install")
        out = buf.getvalue()
        self.assertIn("claude CLI not found", out)
        self.assertIn(
            "claude mcp add --transport http --scope user konecty https://h.example/mcp", out
        )

    # --- idempotency (MCPF-23) -------------------------------------------------

    def test_install_rerun_is_idempotent_and_preserves_user_files(self) -> None:
        project = self._setup_project_dir()
        self._set_konecty_home()

        # A pre-existing user file that must survive both runs untouched.
        user_file = project / ".claude" / "skills" / "my-own-skill" / "SKILL.md"
        user_file.parent.mkdir(parents=True)
        user_file.write_text("# mine, do not touch\n")

        for _run in range(2):
            p_fetch, p_probe, p_register, p_banner = self._patches()
            with p_fetch, p_probe, p_register as mock_register, p_banner:
                rc = main([
                    "install", "--yes", "--engine", "claude",
                    "--url", "https://h.example",
                ])
            self.assertEqual(rc, 0)
            # register() (replace-not-duplicate internally) called exactly once per run.
            mock_register.assert_called_once_with(
                "konecty", mcp_config.build_add_user("https://h.example")
            )

        self.assertEqual(user_file.read_text(), "# mine, do not touch\n",
                         "pre-existing user files must never be modified")

    # --- admin path: OAuth is the default (AC1) --------------------------------

    def test_install_interactive_admin_defaults_to_oauth(self) -> None:
        self._setup_project_dir()
        konecty_home = self._set_konecty_home()

        p_fetch, p_probe, p_register, p_banner = self._patches()
        with (
            p_fetch, p_probe, p_register as mock_register, p_banner,
            patch("konecty_skills.ui.select", return_value=["claude"]),
            patch("konecty_skills.ui.confirm", return_value=True),
            # URL, then client_id, then callback port (defaults accepted).
            patch("konecty_skills.ui.ask",
                  side_effect=["https://h.example", "claude-code-admin", "19819"]),
            patch("konecty_skills.credentials.otp_login") as mock_otp,
        ):
            rc = main(["install", "--engine", "claude", "--scope", "project"])

        self.assertEqual(rc, 0)
        # OTP path must never run when OAuth is the (default) choice.
        mock_otp.assert_not_called()

        # Both servers registered: user first, then admin via the OAuth builder.
        calls = mock_register.call_args_list
        self.assertEqual(calls[0][0][0], "konecty")
        self.assertEqual(calls[1][0][0], "konecty-admin")
        self.assertEqual(
            calls[1][0][1],
            mcp_config.build_add_admin_oauth("https://h.example", "claude-code-admin", 19819),
        )

        # OAuth path stores no bearer token on disk.
        self.assertFalse((konecty_home / ".env").exists(),
                         "OAuth admin path must not write a token file")

    def test_install_admin_oauth_uses_prompted_client_id_and_port(self) -> None:
        self._setup_project_dir()
        self._set_konecty_home()

        p_fetch, p_probe, p_register, p_banner = self._patches()
        with (
            p_fetch, p_probe, p_register as mock_register, p_banner,
            patch("konecty_skills.ui.select", return_value=["claude"]),
            patch("konecty_skills.ui.confirm", return_value=True),
            patch("konecty_skills.ui.ask",
                  side_effect=["https://h.example", "my-client", "40000"]),
        ):
            rc = main(["install", "--engine", "claude", "--scope", "project"])

        self.assertEqual(rc, 0)
        calls = mock_register.call_args_list
        self.assertEqual(
            calls[1][0][1],
            mcp_config.build_add_admin_oauth("https://h.example", "my-client", 40000),
        )

    def test_install_admin_oauth_cli_absent_prints_oauth_command(self) -> None:
        """MCPF-21 parity: with no claude CLI, the printable OAuth add is shown."""
        self._setup_project_dir()
        self._set_konecty_home()

        # No register mock here: let register() build the real printable commands
        # off cli_available()=False so the OAuth argv is exercised end to end.
        buf = io.StringIO()
        with (
            patch("konecty_skills.fetcher.fetch_skills", return_value=self._make_fetch_return()),
            patch("konecty_skills.mcp_config.probe_well_known", side_effect=_probe_ok),
            patch("konecty_skills.mcp_config.cli_available", return_value=False),
            patch("konecty_skills.banner.print_full"),
            patch("konecty_skills.ui.select", return_value=["claude"]),
            patch("konecty_skills.ui.confirm", return_value=True),
            patch("konecty_skills.ui.ask",
                  side_effect=["https://h.example", "claude-code-admin", "19819"]),
            patch("sys.stdout", buf),
        ):
            rc = main(["install", "--engine", "claude", "--scope", "project"])

        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("claude CLI not found", out)
        self.assertIn(
            mcp_config.format_command(
                mcp_config.build_add_admin_oauth("https://h.example", "claude-code-admin", 19819)
            ),
            out,
        )

    # --- admin path: OTP fallback (AC2) — selected via --admin-auth otp ----------

    def test_install_admin_auth_otp_registers_admin_server(self) -> None:
        self._setup_project_dir()
        konecty_home = self._set_konecty_home()

        p_fetch, p_probe, p_register, p_banner = self._patches()
        with (
            p_fetch, p_probe, p_register as mock_register, p_banner,
            patch("konecty_skills.ui.select", return_value=["claude"]),
            patch("konecty_skills.ui.confirm", return_value=True),
            patch("konecty_skills.ui.ask", side_effect=["https://h.example", "admin@h.example"]),
            patch("konecty_skills.credentials.otp_login", return_value="tok-admin-1") as mock_otp,
        ):
            rc = main(["install", "--admin-auth", "otp",
                       "--engine", "claude", "--scope", "project"])

        self.assertEqual(rc, 0)
        mock_otp.assert_called_once_with("https://h.example", "admin@h.example")

        # Both servers registered: user first, then admin with the Bearer header.
        calls = mock_register.call_args_list
        self.assertEqual(calls[0][0][0], "konecty")
        self.assertEqual(calls[1][0][0], "konecty-admin")
        self.assertEqual(
            calls[1][0][1],
            mcp_config.build_add_admin_token("https://h.example", "tok-admin-1"),
        )

        # Interim admin token stored in ~/.konecty/.env.
        env_text = (konecty_home / ".env").read_text()
        self.assertIn("KONECTY_URL=https://h.example", env_text)
        self.assertIn("KONECTY_TOKEN=tok-admin-1", env_text)

    def test_install_admin_auth_otp_failure_skips_admin_registration(self) -> None:
        self._setup_project_dir()
        konecty_home = self._set_konecty_home()

        p_fetch, p_probe, p_register, p_banner = self._patches()
        buf = io.StringIO()
        with (
            p_fetch, p_probe, p_register as mock_register, p_banner,
            patch("konecty_skills.ui.select", return_value=["claude"]),
            patch("konecty_skills.ui.confirm", return_value=True),
            patch("konecty_skills.ui.ask", side_effect=["https://h.example", "admin@h.example"]),
            patch("konecty_skills.credentials.otp_login", return_value=None),
            patch("sys.stdout", buf),
        ):
            rc = main(["install", "--admin-auth", "otp",
                       "--engine", "claude", "--scope", "project"])

        self.assertEqual(rc, 0)
        # Only the user server was registered.
        self.assertEqual(mock_register.call_count, 1)
        self.assertIn("Admin OTP login failed", buf.getvalue())
        self.assertFalse((konecty_home / ".env").exists(),
                         "no token must be stored on OTP failure")

    def test_install_yes_skips_admin_prompt_entirely(self) -> None:
        """--yes preserves current behavior: no admin registration at all."""
        self._setup_project_dir()
        konecty_home = self._set_konecty_home()

        p_fetch, p_probe, p_register, p_banner = self._patches()
        with (
            p_fetch, p_probe, p_register as mock_register, p_banner,
            patch("konecty_skills.credentials.otp_login") as mock_otp,
        ):
            rc = main(["install", "--yes", "--engine", "claude",
                       "--scope", "project", "--url", "https://h.example"])

        self.assertEqual(rc, 0)
        # Only the user server; admin step is interactive-only.
        mock_register.assert_called_once_with(
            "konecty", mcp_config.build_add_user("https://h.example")
        )
        mock_otp.assert_not_called()
        self.assertFalse((konecty_home / ".env").exists())

    # --- engine fallback ---------------------------------------------------------

    def test_install_no_engine_fallback(self) -> None:
        self._setup_empty_dir()
        self._set_konecty_home()

        p_fetch, p_probe, p_register, p_banner = self._patches()
        with p_fetch, p_probe, p_register, p_banner:
            rc = main(["install", "--yes", "--url", "https://fallback.example"])

        self.assertEqual(rc, 0)
        cwd = Path(os.getcwd())
        skill_md = cwd / ".claude" / "skills" / "konecty-data" / "SKILL.md"
        self.assertTrue(skill_md.exists())

    # --- FetchError returns 1 -----------------------------------------------------

    def test_install_fetch_error_returns_1(self) -> None:
        project = self._setup_project_dir()
        self._set_konecty_home()

        from konecty_skills.fetcher import FetchError

        p_fetch, p_probe, p_register, p_banner = self._patches()
        with (
            patch("konecty_skills.fetcher.fetch_skills", side_effect=FetchError("network down")),
            p_probe, p_register, p_banner,
        ):
            rc = main([
                "install", "--yes", "--engine", "claude",
                "--scope", "project", "--url", "https://h.example",
            ])

        self.assertEqual(rc, 1)
        self.assertFalse((project / ".claude" / "skills").exists())


class TestFetcherSkillList(unittest.TestCase):
    """The installer must ship all four skills (MCPF-20)."""

    def test_skill_dirs_contains_four_skills(self) -> None:
        self.assertEqual(
            fetcher.SKILL_DIRS,
            ("konecty-data", "konecty-meta", "konecty-setup", "konecty-dev"),
        )


if __name__ == "__main__":
    unittest.main()
