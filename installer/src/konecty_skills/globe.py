"""Konecty globe — a truecolor ASCII sphere homage to the brand logo.

The logo is a set of organic, interlocking "puzzle" blobs separated by white
channels, wrapped on a sphere. We reproduce that look with a spherical Voronoi:
seed points are spread over the sphere (Fibonacci lattice), each painted with a
brand color chosen from the logo's angular distribution (red left, orange/gold
top, green right, blue/purple bottom, magenta bottom-left, cyan core). Pixels
near a cell boundary become white channels; spherical shading sqrt(1-r^2) adds
volume. Run as a module to print it:

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
_WHITE = (244, 244, 246)

# Tuning: seed count controls blob size; channel width controls the white gaps.
_SEEDS = 30
_CHANNEL = 0.052
# Density ramp for the no-color fallback (used only for shaded cells).
_RAMP = "-=+*#%@"


def _palette(theta: float, r: float) -> tuple[int, int, int]:
    """Pick a brand color from a seed's angle (deg, clockwise from top) + radius."""
    if r < 0.32:  # central cyan core
        return _LBLUE
    if 0.32 <= r < 0.62 and 250 <= theta < 320:  # salmon-pink mid ring, center-left
        return _PINK
    if 0.32 <= r < 0.68 and 150 <= theta < 215:  # light-blue lobe reaching down
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


def _fib_sphere(n: int) -> list[tuple[float, float, float, tuple[int, int, int]]]:
    """Evenly-spread seed directions on the unit sphere, each with a brand color."""
    seeds = []
    golden = math.pi * (3 - math.sqrt(5))
    for k in range(n):
        z = 1 - 2 * (k + 0.5) / n
        rho = math.sqrt(max(0.0, 1 - z * z))
        t = golden * k
        sx, sy = rho * math.cos(t), rho * math.sin(t)
        theta = (math.degrees(math.atan2(sx, -sy)) + 360) % 360
        color = _palette(theta, math.hypot(sx, sy))
        seeds.append((sx, sy, z, color))
    return seeds


def render(height: int = 24, color: bool = True) -> str:
    """Return the globe as a multi-line string.

    Colored cells are truecolor blocks separated by white channels; with
    ``color=False`` cells become shaded density chars and channels become spaces.
    """
    width = height * 2  # terminal cells are ~2:1 tall:wide
    seeds = _fib_sphere(_SEEDS)
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
            z = math.sqrt(max(0.0, 1 - r * r))
            # Nearest two seeds by 3D dot product (cosine similarity).
            best = second = -2.0
            best_color = _WHITE
            for sx, sy, sz, scol in seeds:
                d = nx * sx + ny * sy + z * sz
                if d > best:
                    second, best, best_color = best, d, scol
                elif d > second:
                    second = d
            shade = 0.42 + 0.58 * z
            if r > 0.965:  # darken the rim
                shade *= 0.6
            is_channel = (best - second) < _CHANNEL
            if is_channel:
                cr, cg, cb = _WHITE
            else:
                cr, cg, cb = best_color
            if color:
                cells.append(
                    f"\033[38;2;{int(cr * shade)};{int(cg * shade)};{int(cb * shade)}m█"
                )
            elif is_channel:
                cells.append(" ")
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
