"""Unit tests for konecty_skills.ui — T5."""
from __future__ import annotations

import io
import sys
import unittest
from unittest.mock import patch

from konecty_skills import ui


class TestConfirmAssumeYes(unittest.TestCase):
    """confirm(assume_yes=True) returns default without calling input."""

    def _raise(self, _prompt: str) -> str:  # noqa: PLR6301
        raise AssertionError("input() must not be called when assume_yes=True")

    def test_assume_yes_returns_true_default(self) -> None:
        with patch("builtins.input", side_effect=self._raise):
            result = ui.confirm("Continue?", default=True, assume_yes=True)
        self.assertTrue(result)

    def test_assume_yes_returns_false_default(self) -> None:
        with patch("builtins.input", side_effect=self._raise):
            result = ui.confirm("Continue?", default=False, assume_yes=True)
        self.assertFalse(result)


class TestConfirmInteractive(unittest.TestCase):
    """confirm interactive: empty → default; 'y' → True; 'n' → False."""

    def test_empty_returns_default_true(self) -> None:
        with patch("builtins.input", return_value=""):
            result = ui.confirm("OK?", default=True, assume_yes=False)
        self.assertTrue(result)

    def test_empty_returns_default_false(self) -> None:
        with patch("builtins.input", return_value=""):
            result = ui.confirm("OK?", default=False, assume_yes=False)
        self.assertFalse(result)

    def test_y_returns_true(self) -> None:
        with patch("builtins.input", return_value="y"):
            result = ui.confirm("OK?", default=False, assume_yes=False)
        self.assertTrue(result)

    def test_yes_returns_true(self) -> None:
        with patch("builtins.input", return_value="YES"):
            result = ui.confirm("OK?", default=False, assume_yes=False)
        self.assertTrue(result)

    def test_n_returns_false(self) -> None:
        with patch("builtins.input", return_value="n"):
            result = ui.confirm("OK?", default=True, assume_yes=False)
        self.assertFalse(result)

    def test_no_returns_false(self) -> None:
        with patch("builtins.input", return_value="No"):
            result = ui.confirm("OK?", default=True, assume_yes=False)
        self.assertFalse(result)

    def test_invalid_then_valid_reraises(self) -> None:
        """Invalid input triggers a re-prompt; then a valid answer is accepted."""
        responses = iter(["maybe", "y"])
        with patch("builtins.input", side_effect=lambda _: next(responses)):
            result = ui.confirm("OK?", default=False, assume_yes=False)
        self.assertTrue(result)


class TestSelectAssumeYes(unittest.TestCase):
    """select(assume_yes=True) returns preselected without input."""

    def _raise(self, _prompt: str) -> str:  # noqa: PLR6301
        raise AssertionError("input() must not be called when assume_yes=True")

    def test_returns_preselected(self) -> None:
        items = ["alpha", "beta", "gamma"]
        preselected = ["beta"]
        with patch("builtins.input", side_effect=self._raise):
            result = ui.select(items, preselected, assume_yes=True)
        self.assertEqual(result, ["beta"])

    def test_returns_copy_not_same_object(self) -> None:
        preselected = ["alpha"]
        with patch("builtins.input", side_effect=self._raise):
            result = ui.select(["alpha", "beta"], preselected, assume_yes=True)
        self.assertIsNot(result, preselected)


class TestSelectInteractive(unittest.TestCase):
    """select interactive: '1,3' selects items[0] and items[2]."""

    def test_numbered_selection(self) -> None:
        items = ["alpha", "beta", "gamma", "delta"]
        with patch("builtins.input", return_value="1,3"):
            result = ui.select(items, [], assume_yes=False)
        self.assertEqual(result, ["alpha", "gamma"])

    def test_empty_keeps_preselected(self) -> None:
        items = ["alpha", "beta", "gamma"]
        preselected = ["beta"]
        with patch("builtins.input", return_value=""):
            result = ui.select(items, preselected, assume_yes=False)
        self.assertEqual(result, ["beta"])

    def test_order_follows_items_not_input(self) -> None:
        """Items are returned in items[] order, not input order."""
        items = ["alpha", "beta", "gamma"]
        with patch("builtins.input", return_value="3,1"):
            result = ui.select(items, [], assume_yes=False)
        self.assertEqual(result, ["alpha", "gamma"])

    def test_out_of_range_ignored(self) -> None:
        items = ["alpha", "beta"]
        with patch("builtins.input", return_value="1,99"):
            result = ui.select(items, [], assume_yes=False)
        self.assertEqual(result, ["alpha"])


class TestAsk(unittest.TestCase):
    """ask returns default on empty input and the typed value otherwise."""

    def test_empty_returns_default(self) -> None:
        with patch("builtins.input", return_value=""):
            result = ui.ask("Name?", default="Alice")
        self.assertEqual(result, "Alice")

    def test_empty_no_default_returns_empty_string(self) -> None:
        with patch("builtins.input", return_value=""):
            result = ui.ask("Name?")
        self.assertEqual(result, "")

    def test_typed_value_returned(self) -> None:
        with patch("builtins.input", return_value="Bob"):
            result = ui.ask("Name?", default="Alice")
        self.assertEqual(result, "Bob")

    def test_typed_value_no_default(self) -> None:
        with patch("builtins.input", return_value="hello"):
            result = ui.ask("Say something?")
        self.assertEqual(result, "hello")


class TestStatusHelpers(unittest.TestCase):
    """Status line helpers print to stdout/stderr with distinct prefixes."""

    def _capture_stdout(self, fn, *args):  # noqa: ANN001, ANN202
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            fn(*args)
        return buf.getvalue()

    def _capture_stderr(self, fn, *args):  # noqa: ANN001, ANN202
        buf = io.StringIO()
        with patch("sys.stderr", buf):
            fn(*args)
        return buf.getvalue()

    def test_step_prefix(self) -> None:
        out = self._capture_stdout(ui.step, "doing it")
        self.assertIn("doing it", out)
        self.assertIn("›", out)

    def test_ok_prefix(self) -> None:
        out = self._capture_stdout(ui.ok, "done")
        self.assertIn("done", out)
        self.assertIn("✓", out)

    def test_warn_prefix(self) -> None:
        out = self._capture_stdout(ui.warn, "careful")
        self.assertIn("careful", out)
        self.assertIn("!", out)

    def test_err_goes_to_stderr(self) -> None:
        out_buf = io.StringIO()
        err_buf = io.StringIO()
        with patch("sys.stdout", out_buf), patch("sys.stderr", err_buf):
            ui.err("boom")
        self.assertIn("boom", err_buf.getvalue())
        self.assertEqual(out_buf.getvalue(), "")

    def test_err_prefix(self) -> None:
        out = self._capture_stderr(ui.err, "boom")
        self.assertIn("✗", out)


if __name__ == "__main__":
    unittest.main()
