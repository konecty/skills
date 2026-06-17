"""Konecty globe — a rasterized truecolor ASCII sphere homage to the brand logo.

Maps each terminal cell to a point on a unit sphere, colors it by the logo's
angular palette distribution (red left, orange/gold top, green right, blue/purple
bottom, magenta bottom-left, cyan core) and applies spherical shading sqrt(1-r^2)
for volume. Run as a module to print it:

    python3 -m konecty_skills.globe [height]
"""
from __future__ import annotations

import math
import os
import sys

# Brand palette (approx from the logo).
_RED = (216, 42, 46)
_ORANGE = (238, 96, 38)
_PINK = (232, 96, 112)
_GOLD = (247, 191, 32)
_GREEN = (58, 170, 90)
_TEAL = (41, 140, 172)
_LBLUE = (96, 176, 216)
_DBLUE = (40, 96, 150)
_PURPLE = (120, 82, 152)
_MAGENTA = (168, 42, 92)

# Density ramp for the no-color fallback (dark rim → lit center).
_RAMP = " .:-=+*#%@"


def _sector(theta: float, r: float) -> tuple[int, int, int]:
    """Pick a base color from angle (degrees, clockwise from top) and radius."""
    if r < 0.30:  # central cyan core
        return _LBLUE
    if 0.30 <= r < 0.60 and 250 <= theta < 320:  # salmon-pink mid ring, center-left
        return _PINK
    if 0.30 <= r < 0.66 and 150 <= theta < 215:  # light-blue lobe reaching down
        return _LBLUE
    if theta < 35:
        return _GOLD
    if theta < 120:
        return _GREEN
    if theta < 162:
        return _TEAL
    if theta < 196:
        return _DBLUE
    if theta < 236:
        return _PURPLE
    if theta < 276:
        return _MAGENTA
    if theta < 316:
        return _RED
    return _ORANGE


def render(height: int = 24, color: bool = True) -> str:
    """Return the globe as a multi-line string.

    When *color* is True, each cell is a truecolor block; otherwise a shaded
    density character (no ANSI escapes) is used.
    """
    width = height * 2  # terminal cells are ~2:1 tall:wide
    rows: list[str] = []
    for j in range(height):
        cells: list[str] = []
        for i in range(width):
            nx = (i / (width - 1)) * 2 - 1
            ny = (j / (height - 1)) * 2 - 1
            r = math.hypot(nx, ny)
            if r > 1.0:
                cells.append(" ")
                continue
            theta = (math.degrees(math.atan2(nx, -ny)) + 360) % 360
            nz = math.sqrt(max(0.0, 1 - r * r))
            shade = 0.40 + 0.60 * nz
            if r > 0.965:  # darken the rim
                shade *= 0.6
            if color:
                cr, cg, cb = _sector(theta, r)
                cells.append(
                    f"\033[38;2;{int(cr * shade)};{int(cg * shade)};{int(cb * shade)}m█"
                )
            else:
                cells.append(_RAMP[min(len(_RAMP) - 1, int(shade * (len(_RAMP) - 1)))])
        rows.append("".join(cells) + ("\033[0m" if color else ""))
    return "\n".join(rows)


def print_globe(height: int = 24, stream=None) -> None:
    """Print the globe, auto-disabling color on non-TTY or when NO_COLOR is set."""
    if stream is None:
        stream = sys.stdout
    no_color = "NO_COLOR" in os.environ
    try:
        tty = stream.isatty()
    except Exception:
        tty = False
    stream.write(render(height, color=tty and not no_color) + "\n")


if __name__ == "__main__":
    h = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    print_globe(h)
