"""Unit tests for engines.py (T3)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from konecty_skills.engines import (
    SUPPORTED_ENGINES,
    dest_path,
    detect,
    entry_file,
)


class TestDetectClaude(unittest.TestCase):
    """detect() — Claude engine signals."""

    def test_detect_claude_via_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            result = detect(root)
            self.assertIn("claude", result)

    def test_detect_claude_via_file_only(self) -> None:
        """CLAUDE.md alone (no .claude/ dir) must trigger claude detection."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CLAUDE.md").write_text("# test")
            result = detect(root)
            self.assertIn("claude", result)

    def test_detect_claude_not_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = detect(root)
            self.assertNotIn("claude", result)


class TestDetectMultipleEngines(unittest.TestCase):
    """detect() — agents, cursor, multiple signals, empty dir."""

    def test_detect_agents_via_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("# agents")
            result = detect(root)
            self.assertIn("agents", result)

    def test_detect_cursor_via_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cursor").mkdir()
            result = detect(root)
            self.assertIn("cursor", result)

    def test_detect_multiple_signals_returns_deterministic_order(self) -> None:
        """When all signals are present the order must be claude, agents, cursor."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / "AGENTS.md").write_text("")
            (root / ".cursor").mkdir()
            result = detect(root)
            self.assertEqual(result, ["claude", "agents", "cursor"])

    def test_detect_empty_directory_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(detect(root), [])

    def test_detect_agents_via_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".agents").mkdir()
            result = detect(root)
            self.assertIn("agents", result)


class TestDestPath(unittest.TestCase):
    """dest_path() — correct paths for project and global scope."""

    def test_project_scope_claude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = dest_path("claude", root, "project")
            self.assertEqual(result, root / ".claude" / "skills")

    def test_project_scope_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = dest_path("agents", root, "project")
            self.assertEqual(result, root / ".agents" / "skills")

    def test_project_scope_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = dest_path("cursor", root, "project")
            self.assertEqual(result, root / ".cursor" / "skills")

    def test_global_scope_claude_returns_home_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = dest_path("claude", root, "global")
            expected = Path.home() / ".claude" / "skills"
            self.assertEqual(result, expected)
            # Must end with .claude/skills regardless of machine
            self.assertTrue(str(result).endswith(".claude/skills"))

    def test_global_scope_agents_falls_back_to_project_path(self) -> None:
        """Non-claude engines have no global path; fall back to project scope."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = dest_path("agents", root, "global")
            self.assertEqual(result, root / ".agents" / "skills")

    def test_unknown_engine_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                dest_path("vscode", root, "project")


class TestEntryFile(unittest.TestCase):
    """entry_file() — correct paths and None for cursor; ValueError on unknown."""

    def test_entry_file_claude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = entry_file("claude", root)
            self.assertIsNotNone(result)
            self.assertEqual(result, root / "CLAUDE.md")

    def test_entry_file_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = entry_file("agents", root)
            self.assertIsNotNone(result)
            self.assertEqual(result, root / "AGENTS.md")

    def test_entry_file_cursor_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = entry_file("cursor", root)
            self.assertIsNone(result)

    def test_entry_file_unknown_engine_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                entry_file("windsurf", root)


class TestSupportedEnginesConstant(unittest.TestCase):
    """SUPPORTED_ENGINES constant sanity checks."""

    def test_supported_engines_contains_all_three(self) -> None:
        self.assertEqual(SUPPORTED_ENGINES, ["claude", "agents", "cursor"])

    def test_detect_order_matches_supported_engines_order(self) -> None:
        """Partial matches must appear in SUPPORTED_ENGINES order."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cursor").mkdir()
            (root / "CLAUDE.md").write_text("")
            result = detect(root)
            # claude must come before cursor
            self.assertLess(result.index("claude"), result.index("cursor"))


if __name__ == "__main__":
    unittest.main()
