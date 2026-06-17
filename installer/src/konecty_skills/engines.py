"""Engine detection and skills-path resolution. Implemented in T3."""
from __future__ import annotations

from pathlib import Path

# Canonical engine identifiers, in deterministic order used by detect().
SUPPORTED_ENGINES: list[str] = ["claude", "agents", "cursor"]

# Mapping: engine id → subdirectory name (under root for project scope).
_ENGINE_DIR: dict[str, str] = {
    "claude": ".claude",
    "agents": ".agents",
    "cursor": ".cursor",
}

# Detection signals: each engine maps to (dirs_to_check, files_to_check).
# A signal fires when ANY of the listed dirs OR files is present in root.
_DETECTION: dict[str, tuple[list[str], list[str]]] = {
    "claude":  ([".claude"], ["CLAUDE.md"]),
    "agents":  ([".agents"], ["AGENTS.md"]),
    "cursor":  ([".cursor"], []),
}


def detect(root: Path) -> list[str]:
    """Return engine ids whose detection signal is present under *root*.

    Detection order is always: claude, agents, cursor (i.e. the order of
    SUPPORTED_ENGINES), regardless of discovery order on disk.

    Returns an empty list when none of the signals are found.
    """
    found: list[str] = []
    for engine in SUPPORTED_ENGINES:
        dirs, files = _DETECTION[engine]
        if any((root / d).is_dir() for d in dirs):
            found.append(engine)
            continue
        if any((root / f).is_file() for f in files):
            found.append(engine)
    return found


def dest_path(engine: str, root: Path, scope: str) -> Path:
    """Resolve the skills destination directory for *engine*.

    scope="project"
        Returns ``root / .<engine-dir> / skills`` for all engines.

    scope="global"
        For "claude": returns ``~/.claude/skills`` (expanduser).
        For all other engines: global scope is not defined by their respective
        standards, so this falls back to the project path under *root*.
        Callers should warn the user when a non-claude engine is requested with
        global scope.

    Raises ValueError for unknown engine ids.
    """
    if engine not in _ENGINE_DIR:
        raise ValueError(
            f"Unknown engine {engine!r}. Supported engines: {SUPPORTED_ENGINES}"
        )

    if scope == "global":
        if engine == "claude":
            return Path.home() / ".claude" / "skills"
        # Graceful fallback: non-claude engines have no defined global path.
        return root / _ENGINE_DIR[engine] / "skills"

    # Default / scope="project"
    return root / _ENGINE_DIR[engine] / "skills"


def entry_file(engine: str, root: Path) -> Path | None:
    """Return the path to the engine's primary entry/config file, or None.

    claude  → <root>/CLAUDE.md
    agents  → <root>/AGENTS.md
    cursor  → None  (Cursor does not use a top-level markdown entry file)

    Raises ValueError for unknown engine ids.
    """
    if engine not in _ENGINE_DIR:
        raise ValueError(
            f"Unknown engine {engine!r}. Supported engines: {SUPPORTED_ENGINES}"
        )

    _entry_files: dict[str, str | None] = {
        "claude": "CLAUDE.md",
        "agents": "AGENTS.md",
        "cursor": None,
    }
    name = _entry_files[engine]
    return (root / name) if name is not None else None
