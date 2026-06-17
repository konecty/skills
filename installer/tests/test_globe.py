import io
import unittest

from konecty_skills import globe


class TestGlobeRender(unittest.TestCase):
    def test_color_has_truecolor_escapes(self):
        art = globe.render(height=16, color=True)
        self.assertIn("\033[38;2;", art)

    def test_plain_has_no_escapes(self):
        art = globe.render(height=16, color=False)
        self.assertNotIn("\033[", art)

    def test_is_circular(self):
        # Corners must be blank (outside the unit circle); the middle row's
        # center must be filled.
        art = globe.render(height=16, color=False)
        lines = art.split("\n")
        self.assertEqual(lines[0][0], " ")
        self.assertEqual(lines[0][-1], " ")
        mid = lines[len(lines) // 2]
        self.assertNotEqual(mid[len(mid) // 2], " ")

    def test_row_count_matches_height(self):
        self.assertEqual(len(globe.render(height=20, color=False).split("\n")), 20)

    def test_print_globe_non_tty_omits_color(self):
        buf = io.StringIO()  # StringIO.isatty() is False
        globe.print_globe(height=12, stream=buf)
        self.assertNotIn("\033[", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
