"""Interactive UI layer (prompts + status lines). Implemented in T5."""
from __future__ import annotations

import sys


# ---------------------------------------------------------------------------
# Status line helpers
# ---------------------------------------------------------------------------

def step(msg: str) -> None:
    """Print a step/progress message to stdout."""
    print(f"› {msg}")


def ok(msg: str) -> None:
    """Print a success message to stdout."""
    print(f"✓ {msg}")


def warn(msg: str) -> None:
    """Print a warning message to stdout."""
    print(f"! {msg}")


def err(msg: str) -> None:
    """Print an error message to stderr."""
    print(f"✗ {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Interactive prompts
# ---------------------------------------------------------------------------

def confirm(prompt: str, default: bool, assume_yes: bool) -> bool:
    """Ask a yes/no question and return True for yes, False for no.

    If *assume_yes* is True, return *default* immediately without reading input.
    Empty input returns *default*; 'y'/'yes' → True; 'n'/'no' → False.
    Re-prompts on any other input.
    """
    if assume_yes:
        return default

    hint = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"{prompt} {hint}: ").strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("Please answer y or n.")


def select(items: list[str], preselected: list[str], assume_yes: bool) -> list[str]:
    """Present a numbered list and let the user toggle items.

    If *assume_yes* is True, return *preselected* immediately without reading
    input.

    Otherwise show each item with its index (1-based) and a marker for
    preselected items.  The user enters a comma-separated list of numbers to
    select (empty input keeps *preselected*).  Returns the chosen subset in
    the original *items* order.
    """
    if assume_yes:
        return list(preselected)

    print("Select items (comma-separated numbers, empty = keep current):")
    for i, item in enumerate(items, 1):
        marker = "*" if item in preselected else " "
        print(f"  {i}. [{marker}] {item}")

    raw = input("Selection: ").strip()
    if raw == "":
        return list(preselected)

    chosen: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            idx = int(token) - 1
        except ValueError:
            continue
        if 0 <= idx < len(items):
            chosen.append(items[idx])

    # Preserve original items order and deduplicate
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in chosen and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def ask(prompt: str, default: str | None = None) -> str:
    """Prompt for a string value.

    Empty input returns *default* (or "" if *default* is None).
    """
    hint = f" [{default}]" if default is not None else ""
    raw = input(f"{prompt}{hint}: ").strip()
    if raw == "":
        return default if default is not None else ""
    return raw
