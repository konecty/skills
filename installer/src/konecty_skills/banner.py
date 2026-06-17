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


def _use_color(stream) -> bool:
    no_color_env = "NO_COLOR" in os.environ
    try:
        tty = stream.isatty()
    except Exception:
        tty = False
    return tty and not no_color_env


def full(color: bool = True, globe_height: int = 13) -> str:
    """Return the combined banner: the brand globe centered above the wordmark."""
    from . import globe  # local import keeps banner usable without the globe

    glines = globe.render(globe_height, color=color).split("\n")
    pad = " " * 26  # center the globe (~2*height wide) over the wordmark block
    globe_block = "\n".join(pad + ln for ln in glines)
    return globe_block + "\n" + render(color=color)


def print_full(stream=None) -> None:
    """Print the combined globe + wordmark banner (used by `install`)."""
    if stream is None:
        stream = sys.stdout
    stream.write(full(color=_use_color(stream)) + "\n")
