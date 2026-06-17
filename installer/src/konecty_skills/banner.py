"""KONECTY truecolor ASCII banner."""
from __future__ import annotations

import os
import sys

# ANSI Shadow blocky font — one entry per letter, 6 rows each.
_LETTERS: dict[str, list[str]] = {
    "K": ["██╗  ██╗", "██║ ██╔╝", "█████╔╝ ", "██╔═██╗ ", "██║  ██╗", "╚═╝  ╚═╝"],
    "O": [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "N": ["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║", "╚═╝  ╚═══╝"],
    "E": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"],
    "C": [" ██████╗", "██╔════╝", "██║     ", "██║     ", "╚██████╗", " ╚═════╝"],
    "T": ["████████╗", "╚══██╔══╝", "   ██║   ", "   ██║   ", "   ██║   ", "   ╚═╝   "],
    "Y": ["██╗   ██╗", "╚██╗ ██╔╝", " ╚████╔╝ ", "  ╚██╔╝  ", "   ██║   ", "   ╚═╝   "],
}

# Globe rainbow — left-to-right around the logo sphere.
_COLORS: dict[str, tuple[int, int, int]] = {
    "K": (229, 72, 77),    # red
    "O": (242, 140, 58),   # orange
    "N": (245, 197, 24),   # yellow
    "E": (60, 184, 120),   # green
    "C": (41, 182, 216),   # teal
    "T": (45, 108, 183),   # blue
    "Y": (142, 68, 173),   # purple
}

_RESET = "\033[0m"
_GREY = "\033[38;2;120;130;140m"
_WORD = "KONECTY"


def _ansi(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"


def render(color: bool = True) -> str:
    """Return the full banner as a string.

    When *color* is True, truecolor ANSI escape codes are embedded.
    When *color* is False, plain text only — no escape codes.
    Both variants include all 7 KONECTY letterforms and the subtitle line.
    """
    rows = ["" for _ in range(6)]
    for ch in _WORD:
        glyph = _LETTERS[ch]
        if color:
            col = _ansi(*_COLORS[ch])
            for i in range(6):
                rows[i] += col + glyph[i] + "  "
        else:
            for i in range(6):
                rows[i] += glyph[i] + "  "

    lines: list[str] = [""]
    for row in rows:
        if color:
            lines.append("  " + row + _RESET)
        else:
            lines.append("  " + row)

    if color:
        subtitle = (
            f"  {_GREY}── BUSINESS PLATFORM ─────────  "
            f"Agent Skills for the Konecty low-code platform{_RESET}"
        )
    else:
        subtitle = (
            "  ── BUSINESS PLATFORM ─────────  "
            "Agent Skills for the Konecty low-code platform"
        )
    lines.append(subtitle)
    lines.append("")
    return "\n".join(lines)


def print_banner(stream=None) -> None:
    """Print the banner to *stream* (default: sys.stdout).

    Color is disabled when:
    - the stream has no ``isatty`` method or ``isatty()`` returns False, OR
    - the ``NO_COLOR`` environment variable is set to any value.
    """
    if stream is None:
        stream = sys.stdout

    no_color_env = "NO_COLOR" in os.environ
    try:
        tty = stream.isatty()
    except Exception:
        tty = False

    use_color = tty and not no_color_env
    stream.write(render(color=use_color))
