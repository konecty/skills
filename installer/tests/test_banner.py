"""Unit tests for konecty_skills.banner (T2)."""
from __future__ import annotations

import io
import os
import unittest

from konecty_skills.banner import full, print_banner, print_full, render


class TestFullBanner(unittest.TestCase):
    """full() stacks the globe above the wordmark."""

    def test_full_color_has_globe_and_wordmark(self) -> None:
        out = full(color=True)
        self.assertIn("\033[38;2;", out)          # globe truecolor cells
        self.assertIn("BUSINESS PLATFORM", out)    # wordmark subtitle
        # The globe block adds rows above the 6-row wordmark + subtitle.
        self.assertGreater(len(out.split("\n")), 16)

    def test_full_plain_has_no_escapes(self) -> None:
        out = full(color=False)
        self.assertNotIn("\033[", out)
        self.assertIn("BUSINESS PLATFORM", out)

    def test_print_full_non_tty_omits_color(self) -> None:
        buf = io.StringIO()  # isatty() is False
        print_full(stream=buf)
        self.assertNotIn("\033[", buf.getvalue())


class TestRenderColor(unittest.TestCase):
    """render(color=True) must embed truecolor ANSI escapes."""

    def test_contains_truecolor_escape(self) -> None:
        result = render(color=True)
        self.assertIn("\033[38;2;", result, "Expected truecolor escape in colored output")

    def test_contains_subtitle(self) -> None:
        result = render(color=True)
        self.assertIn("BUSINESS PLATFORM", result)


class TestRenderNoColor(unittest.TestCase):
    """render(color=False) must produce plain text with no ANSI codes."""

    def test_no_ansi_escapes(self) -> None:
        result = render(color=False)
        self.assertNotIn("\033[", result, "Expected no ANSI escapes in plain output")

    def test_contains_subtitle(self) -> None:
        result = render(color=False)
        self.assertIn("BUSINESS PLATFORM", result)

    def test_contains_all_letters(self) -> None:
        """Plain output should still contain at least one glyph row per letter."""
        result = render(color=False)
        # Each letter starts with block characters; spot-check a few
        self.assertIn("██╗  ██╗", result)   # K row 0
        self.assertIn("╚══════╝", result)   # E row 5


class TestPrintBannerNonTTY(unittest.TestCase):
    """print_banner must not emit ANSI codes to non-TTY streams."""

    def _make_non_tty(self) -> io.StringIO:
        """Return a StringIO whose isatty() returns False."""
        buf = io.StringIO()
        buf.isatty = lambda: False  # type: ignore[method-assign]
        return buf

    def test_non_tty_no_ansi(self) -> None:
        buf = self._make_non_tty()
        env_backup = os.environ.pop("NO_COLOR", None)
        try:
            print_banner(stream=buf)
        finally:
            if env_backup is not None:
                os.environ["NO_COLOR"] = env_backup

        output = buf.getvalue()
        self.assertNotIn("\033[", output, "Non-TTY stream should receive no ANSI codes")

    def test_non_tty_contains_subtitle(self) -> None:
        buf = self._make_non_tty()
        print_banner(stream=buf)
        self.assertIn("BUSINESS PLATFORM", buf.getvalue())

    def test_no_color_env_disables_color(self) -> None:
        """NO_COLOR env var must suppress ANSI even when stream.isatty() is True."""
        buf = io.StringIO()
        buf.isatty = lambda: True  # type: ignore[method-assign]
        old = os.environ.get("NO_COLOR")
        os.environ["NO_COLOR"] = "1"
        try:
            print_banner(stream=buf)
        finally:
            if old is None:
                del os.environ["NO_COLOR"]
            else:
                os.environ["NO_COLOR"] = old

        self.assertNotIn("\033[", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
