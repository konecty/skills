"""Unit tests for konecty_skills.mcp_config (T17).

All offline: urllib and subprocess are mocked; shutil.which is mocked for
CLI-presence branches. Covers MCPF-01 (URL validation + registration commands),
MCPF-02 (well-known probe diagnostics), MCPF-21 (no-claude-CLI fallback) and
the replace-not-duplicate idempotency rule.
"""
from __future__ import annotations

import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

_src = str(Path(__file__).parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from konecty_skills import mcp_config
from konecty_skills.mcp_config import (
    ADMIN_SERVER,
    USER_SERVER,
    UrlValidationError,
    build_add_admin_oauth,
    build_add_admin_token,
    build_add_user,
    build_list,
    build_remove,
    cli_available,
    format_command,
    list_servers,
    normalize_url,
    probe_well_known,
    register,
    run_command,
)


class TestNormalizeUrl(unittest.TestCase):
    """https-only + trailing-slash/path normalization (spec Edge Cases)."""

    def test_plain_https_unchanged(self):
        self.assertEqual(normalize_url("https://acme.konecty.com"), "https://acme.konecty.com")

    def test_strips_trailing_slash(self):
        self.assertEqual(normalize_url("https://acme.konecty.com/"), "https://acme.konecty.com")

    def test_strips_path(self):
        self.assertEqual(
            normalize_url("https://acme.konecty.com/some/path"), "https://acme.konecty.com"
        )

    def test_strips_query_and_fragment(self):
        self.assertEqual(
            normalize_url("https://acme.konecty.com/?a=1#frag"), "https://acme.konecty.com"
        )

    def test_preserves_port(self):
        self.assertEqual(
            normalize_url("https://acme.konecty.com:8443/"), "https://acme.konecty.com:8443"
        )

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(normalize_url("  https://acme.konecty.com  "), "https://acme.konecty.com")

    def test_rejects_http(self):
        with self.assertRaises(UrlValidationError):
            normalize_url("http://acme.konecty.com")

    def test_rejects_ftp(self):
        with self.assertRaises(UrlValidationError):
            normalize_url("ftp://acme.konecty.com")

    def test_rejects_missing_scheme(self):
        with self.assertRaises(UrlValidationError):
            normalize_url("acme.konecty.com")

    def test_rejects_empty(self):
        with self.assertRaises(UrlValidationError):
            normalize_url("")


def _fake_response(payload: bytes, status: int = 200):
    """Build a context-manager mock mimicking urlopen's response."""
    resp = MagicMock()
    resp.read.return_value = payload
    resp.status = status
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestProbeWellKnown(unittest.TestCase):
    """GET <url>/.well-known/oauth-protected-resource branches (MCPF-02)."""

    URL = "https://acme.konecty.com"

    def test_ok_when_resource_matches_mcp_url(self):
        body = json.dumps({"resource": f"{self.URL}/mcp"}).encode()
        with patch("urllib.request.urlopen", return_value=_fake_response(body)) as mock_open:
            result = probe_well_known(self.URL)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["resource"], f"{self.URL}/mcp")
        # Probe target must be the well-known path.
        req = mock_open.call_args[0][0]
        self.assertEqual(
            req.full_url, f"{self.URL}/.well-known/oauth-protected-resource"
        )

    def test_resource_mismatch_flags_audience_misconfiguration(self):
        body = json.dumps({"resource": "https://other.example/mcp"}).encode()
        with patch("urllib.request.urlopen", return_value=_fake_response(body)):
            result = probe_well_known(self.URL)
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["resource"], "https://other.example/mcp")

    def test_404_means_no_mcp(self):
        err = urllib.error.HTTPError(self.URL, 404, "Not Found", {}, io.BytesIO(b""))
        with patch("urllib.request.urlopen", side_effect=err):
            result = probe_well_known(self.URL)
        self.assertEqual(result["status"], "no_mcp")

    def test_http_500_means_unreachable(self):
        err = urllib.error.HTTPError(self.URL, 500, "Server Error", {}, io.BytesIO(b""))
        with patch("urllib.request.urlopen", side_effect=err):
            result = probe_well_known(self.URL)
        self.assertEqual(result["status"], "unreachable")

    def test_network_error_means_unreachable(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("timed out"),
        ):
            result = probe_well_known(self.URL)
        self.assertEqual(result["status"], "unreachable")

    def test_timeout_means_unreachable(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError("timeout")):
            result = probe_well_known(self.URL)
        self.assertEqual(result["status"], "unreachable")

    def test_bad_json_body(self):
        with patch("urllib.request.urlopen", return_value=_fake_response(b"<html>nope")):
            result = probe_well_known(self.URL)
        self.assertEqual(result["status"], "bad_json")


class TestCommandBuilders(unittest.TestCase):
    """Argv lists must match the konecty-setup skill templates exactly."""

    URL = "https://acme.konecty.com"

    def test_build_add_user(self):
        self.assertEqual(
            build_add_user(self.URL),
            [
                "claude", "mcp", "add",
                "--transport", "http",
                "--scope", "user",
                "konecty", f"{self.URL}/mcp",
            ],
        )

    def test_build_add_admin_token(self):
        self.assertEqual(
            build_add_admin_token(self.URL, "tok123"),
            [
                "claude", "mcp", "add",
                "--transport", "http",
                "--scope", "user",
                "konecty-admin", f"{self.URL}/admin-mcp",
                "--header", "Authorization: Bearer tok123",
            ],
        )

    def test_build_add_admin_oauth(self):
        self.assertEqual(
            build_add_admin_oauth(self.URL, "claude-code", 8976),
            [
                "claude", "mcp", "add",
                "--transport", "http",
                "--scope", "user",
                "konecty-admin", f"{self.URL}/admin-mcp",
                "--client-id", "claude-code",
                "--callback-port", "8976",
            ],
        )

    def test_build_remove(self):
        self.assertEqual(
            build_remove("konecty"),
            ["claude", "mcp", "remove", "--scope", "user", "konecty"],
        )

    def test_build_list(self):
        self.assertEqual(build_list(), ["claude", "mcp", "list"])

    def test_server_name_constants(self):
        self.assertEqual(USER_SERVER, "konecty")
        self.assertEqual(ADMIN_SERVER, "konecty-admin")

    def test_format_command_quotes_args_with_spaces(self):
        """Printable form must match the skill template (double quotes)."""
        argv = build_add_admin_token(self.URL, "tok123")
        self.assertEqual(
            format_command(argv),
            "claude mcp add --transport http --scope user konecty-admin "
            f'{self.URL}/admin-mcp --header "Authorization: Bearer tok123"',
        )

    def test_format_command_no_quotes_when_unneeded(self):
        self.assertEqual(
            format_command(build_add_user(self.URL)),
            f"claude mcp add --transport http --scope user konecty {self.URL}/mcp",
        )


class TestCliDetection(unittest.TestCase):
    """shutil.which drives the present/absent branch (MCPF-21)."""

    def test_cli_present(self):
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            self.assertTrue(cli_available())

    def test_cli_absent(self):
        with patch("shutil.which", return_value=None):
            self.assertFalse(cli_available())


class TestRunCommand(unittest.TestCase):
    """run_command wraps subprocess.run and never raises."""

    def test_success(self):
        completed = MagicMock(returncode=0, stdout="added\n", stderr="")
        with patch("subprocess.run", return_value=completed) as mock_run:
            ok, detail = run_command(["claude", "mcp", "list"])
        self.assertTrue(ok)
        self.assertIn("added", detail)
        self.assertEqual(mock_run.call_args[0][0], ["claude", "mcp", "list"])

    def test_failure_returncode(self):
        completed = MagicMock(returncode=1, stdout="", stderr="boom\n")
        with patch("subprocess.run", return_value=completed):
            ok, detail = run_command(["claude", "mcp", "list"])
        self.assertFalse(ok)
        self.assertIn("boom", detail)

    def test_oserror_returns_false(self):
        with patch("subprocess.run", side_effect=OSError("not found")):
            ok, detail = run_command(["claude", "mcp", "list"])
        self.assertFalse(ok)
        self.assertIn("not found", detail)


class TestListServers(unittest.TestCase):
    """list_servers parses `claude mcp list` output into names."""

    def test_parses_names(self):
        out = (
            "Checking MCP server health...\n\n"
            "konecty: https://acme.konecty.com/mcp (HTTP) - ✓ Connected\n"
            "konecty-admin: https://acme.konecty.com/admin-mcp (HTTP) - ✗ Failed\n"
        )
        with patch.object(mcp_config, "run_command", return_value=(True, out)):
            names = list_servers()
        self.assertEqual(names, ["konecty", "konecty-admin"])

    def test_run_failure_returns_empty(self):
        with patch.object(mcp_config, "run_command", return_value=(False, "err")):
            self.assertEqual(list_servers(), [])


class TestRegister(unittest.TestCase):
    """register(): replace-not-duplicate + CLI-absent fallback (MCPF-21/23)."""

    URL = "https://acme.konecty.com"

    def test_cli_absent_returns_printable_commands(self):
        add_argv = build_add_user(self.URL)
        with patch.object(mcp_config, "cli_available", return_value=False):
            result = register("konecty", add_argv)
        self.assertFalse(result["executed"])
        self.assertEqual(
            result["commands"],
            [
                "claude mcp remove --scope user konecty",
                f"claude mcp add --transport http --scope user konecty {self.URL}/mcp",
            ],
        )

    def test_existing_entry_removed_before_add(self):
        """Re-run with a new URL replaces the entry — never duplicates."""
        add_argv = build_add_user(self.URL)
        calls: list[list[str]] = []

        def fake_run(argv):
            calls.append(argv)
            return True, "ok"

        with (
            patch.object(mcp_config, "cli_available", return_value=True),
            patch.object(mcp_config, "list_servers", return_value=["konecty"]),
            patch.object(mcp_config, "run_command", side_effect=fake_run),
        ):
            result = register("konecty", add_argv)

        self.assertTrue(result["executed"])
        self.assertTrue(result["ok"])
        self.assertEqual(calls[0], build_remove("konecty"))
        self.assertEqual(calls[1], add_argv)

    def test_fresh_entry_skips_remove(self):
        add_argv = build_add_user(self.URL)
        calls: list[list[str]] = []

        def fake_run(argv):
            calls.append(argv)
            return True, "ok"

        with (
            patch.object(mcp_config, "cli_available", return_value=True),
            patch.object(mcp_config, "list_servers", return_value=[]),
            patch.object(mcp_config, "run_command", side_effect=fake_run),
        ):
            result = register("konecty", add_argv)

        self.assertTrue(result["executed"])
        self.assertTrue(result["ok"])
        self.assertEqual(calls, [add_argv])

    def test_add_failure_reported(self):
        add_argv = build_add_user(self.URL)
        with (
            patch.object(mcp_config, "cli_available", return_value=True),
            patch.object(mcp_config, "list_servers", return_value=[]),
            patch.object(mcp_config, "run_command", return_value=(False, "add failed")),
        ):
            result = register("konecty", add_argv)
        self.assertTrue(result["executed"])
        self.assertFalse(result["ok"])
        self.assertIn("add failed", result["detail"])


if __name__ == "__main__":
    unittest.main()
