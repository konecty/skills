"""Copy skills, merge entry files, update/uninstall. Implemented in T8/T9."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from konecty_skills import engines as _engines
from konecty_skills.manifest import hash_file

# Exact markers for the managed block in entry files.
_BLOCK_START = "<!-- konecty-skills:start -->"
_BLOCK_END = "<!-- konecty-skills:end -->"

_BLOCK_BODY = """\
<!-- konecty-skills:start -->
## Konecty Skills

The `konecty-data`, `konecty-meta`, `konecty-setup` and `konecty-dev` skills are
installed and available. Data and metadata operations run through the Konecty MCP
servers (`konecty` / `konecty-admin`); use `konecty-setup` to (re)configure them.
<!-- konecty-skills:end -->"""


def install(
    skills_root: Path,
    root: Path,
    engines: list[str],
    scope: str,
    manifest: dict,
    source: dict,
    installed_at: str,
) -> dict:
    """Copy skills from *skills_root* into each engine's dest path and record in *manifest*.

    Parameters
    ----------
    skills_root:
        Directory that contains one sub-directory per skill
        (e.g. ``konecty-data/``, ``konecty-meta/``).
    root:
        Project root (used to resolve engine dest paths and to compute
        relative paths stored in the manifest).
    engines:
        List of engine ids (e.g. ``["claude", "agents"]``).
    scope:
        ``"project"`` or ``"global"``.
    manifest:
        The manifest dict (mutated in-place).
    source:
        Dict describing the install source (passed through into manifest).
    installed_at:
        ISO-8601 timestamp string.

    Returns
    -------
    dict
        ``{"engines": [...], "skills": [...], "dests": [...], "files_written": <int>}``
    """
    skills_root = Path(skills_root)
    root = Path(root)

    # Collect skill dirs present in skills_root.
    skill_dirs = sorted(
        p for p in skills_root.iterdir() if p.is_dir()
    )
    skill_names = [p.name for p in skill_dirs]

    skills_manifest: dict = {}
    dests: list[str] = []
    files_written = 0

    for engine in engines:
        dest = _engines.dest_path(engine, root, scope)
        dest.mkdir(parents=True, exist_ok=True)
        dests.append(str(dest))

        for skill_dir in skill_dirs:
            skill_name = skill_dir.name
            target = dest / skill_name

            # --- atomic replace via temp dir ---
            # Create temp dir as a sibling of dest so os.replace works
            # across the same filesystem.
            tmp_dir = dest / f"_tmp_{skill_name}_{os.getpid()}"
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)

            shutil.copytree(str(skill_dir), str(tmp_dir))

            if target.exists():
                # Remove old dir first so os.replace (which only works for
                # dirs on some platforms when dest is empty) is safe.
                # We use shutil.move instead, which handles non-empty dirs.
                shutil.rmtree(target)

            shutil.move(str(tmp_dir), str(target))

            # --- record files in manifest ---
            file_hashes: dict[str, str] = {}
            for fpath in sorted(target.rglob("*")):
                if fpath.is_file():
                    rel = fpath.relative_to(target).as_posix()
                    file_hashes[rel] = hash_file(fpath)
                    files_written += 1

            # dest relative to root, as posix str
            dest_rel = target.relative_to(root).as_posix()

            composite_key = f"{engine}:{skill_name}"
            skills_manifest[composite_key] = {
                "dest": dest_rel,
                "files": file_hashes,
            }

    # Update the manifest installation entry.
    installations = manifest.setdefault("installations", {})
    installations[str(root)] = {
        "installed_at": installed_at,
        "source": source,
        "scope": scope,
        "engines": list(engines),
        "skills": skills_manifest,
    }

    return {
        "engines": list(engines),
        "skills": skill_names,
        "dests": dests,
        "files_written": files_written,
    }


def update(
    skills_root: Path,
    root: Path,
    manifest: dict,
    installed_at: str,
) -> dict:
    """Update an existing installation by refreshing skill files from *skills_root*.

    Files that have been locally modified (on-disk hash differs from the recorded hash)
    are preserved unchanged and reported under "preserved".  Unmodified files are
    overwritten with the fresh version from *skills_root*.  New files that exist in
    *skills_root* but are not yet recorded are copied and added to the manifest.

    Parameters
    ----------
    skills_root:
        Directory containing one sub-directory per skill (the source of truth).
    root:
        Project root that was passed to ``install()``.
    manifest:
        The manifest dict (mutated in-place).
    installed_at:
        ISO-8601 timestamp for the refresh time.

    Returns
    -------
    dict
        ``{"updated": <int files overwritten>, "added": <int new files>,
           "preserved": [{"skill": ..., "file": ...}, ...]}``

    Raises
    ------
    KeyError
        If *root* is not present in ``manifest["installations"]``.
    ValueError
        If the entry exists but is not a dict.
    """
    skills_root = Path(skills_root)
    root = Path(root)

    installations: dict = manifest.get("installations", {})
    key = str(root)
    if key not in installations:
        raise KeyError(
            f"No installation found for root {root!r}. "
            "Run install() first."
        )

    installation = installations[key]
    if not isinstance(installation, dict):
        raise ValueError(
            f"Installation entry for {root!r} is not a dict: {installation!r}"
        )

    from konecty_skills.manifest import diff as _diff

    # Build a set of (composite_key, relpath) pairs that are locally modified.
    conflicts = _diff(installation, root)
    modified_set: set[tuple[str, str]] = {
        (c["skill"], c["file"])
        for c in conflicts
        if c["reason"] == "modified"
    }

    updated = 0
    added = 0
    preserved: list[dict] = []

    skills_manifest: dict = installation.setdefault("skills", {})

    for composite_key, skill_info in skills_manifest.items():
        # composite_key is "<engine>:<skill_name>"
        _, skill_name = composite_key.split(":", 1)
        dest_rel: str = skill_info["dest"]           # e.g. ".claude/skills/konecty-data"
        recorded_files: dict = skill_info.setdefault("files", {})

        source_skill_dir = skills_root / skill_name

        # --- update / preserve existing recorded files ---
        for relpath in list(recorded_files.keys()):
            if (composite_key, relpath) in modified_set:
                # Locally modified — preserve.
                preserved.append({"skill": composite_key, "file": relpath})
            else:
                src = source_skill_dir / relpath
                dst = root / dest_rel / relpath
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src), str(dst))
                    recorded_files[relpath] = hash_file(dst)
                    updated += 1

        # --- add new files present in skills_root but not yet recorded ---
        if source_skill_dir.is_dir():
            for src_file in sorted(source_skill_dir.rglob("*")):
                if not src_file.is_file():
                    continue
                rel = src_file.relative_to(source_skill_dir).as_posix()
                if rel not in recorded_files:
                    dst = root / dest_rel / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src_file), str(dst))
                    recorded_files[rel] = hash_file(dst)
                    added += 1

    installation["installed_at"] = installed_at
    return {"updated": updated, "added": added, "preserved": preserved}


def uninstall(
    root: Path,
    manifest: dict,
    purge: bool = False,
    confirm_modified=None,
    credentials_path: Path | None = None,
) -> dict:
    """Remove a previously installed set of skills and pop the manifest entry.

    For each recorded file:

    * If the file's on-disk hash matches the recorded hash (unmodified) → remove it.
    * If the hash differs (locally modified) → call ``confirm_modified(skill, file)``
      (a callable returning ``bool``).  If it returns ``False``, or if
      ``confirm_modified`` is ``None``, the file is kept and listed under "skipped".

    After removing files, any now-empty skill directories (and an empty parent
    ``skills/`` directory) are pruned.  Unrelated files are never touched.

    The installation entry is popped from ``manifest["installations"]`` regardless
    of whether some files were skipped.

    Parameters
    ----------
    root:
        Project root that was passed to ``install()``.
    manifest:
        The manifest dict (mutated in-place).
    purge:
        When ``True``, also remove the credentials file at *credentials_path*
        (if provided and the file exists).
    confirm_modified:
        Callable ``(skill: str, file: str) -> bool``.  Return ``True`` to remove
        a locally-modified file, ``False`` to keep it.  ``None`` → keep all
        modified files without prompting.
    credentials_path:
        Path to the credentials file that should be removed when ``purge=True``.
        When ``None`` nothing is removed even if ``purge=True`` (tests never hit
        the real home directory this way).

    Returns
    -------
    dict
        ``{"removed": <int>, "skipped": [{"skill": ..., "file": ...}], "purged": <bool>}``

    Raises
    ------
    KeyError
        If *root* is not present in ``manifest["installations"]``.
    """
    root = Path(root)

    installations: dict = manifest.get("installations", {})
    key = str(root)
    if key not in installations:
        raise KeyError(
            f"No installation found for root {root!r}. "
            "Nothing to uninstall."
        )

    installation = installations[key]

    import hashlib as _hashlib

    removed = 0
    skipped: list[dict] = []

    skills_manifest: dict = installation.get("skills", {})

    # Collect skill dest dirs so we can prune them afterwards.
    skill_dest_dirs: set[Path] = set()

    for composite_key, skill_info in skills_manifest.items():
        dest_rel: str = skill_info.get("dest", "")
        recorded_files: dict = skill_info.get("files", {})
        skill_dest = root / dest_rel
        skill_dest_dirs.add(skill_dest)

        for relpath, recorded_hash in recorded_files.items():
            on_disk = skill_dest / relpath
            if not on_disk.exists():
                # Already gone — count as removed.
                removed += 1
                continue

            # Check if locally modified.
            actual_hash = _hashlib.sha256(on_disk.read_bytes()).hexdigest()
            is_modified = actual_hash != recorded_hash

            if is_modified:
                should_remove = False
                if confirm_modified is not None:
                    should_remove = bool(confirm_modified(composite_key, relpath))
                if not should_remove:
                    skipped.append({"skill": composite_key, "file": relpath})
                    continue

            on_disk.unlink()
            removed += 1

    # Prune now-empty skill dirs and a possibly-empty parent skills/ dir.
    for skill_dir in skill_dest_dirs:
        _prune_empty_dir(skill_dir)
    # Also prune the common parent (skills/) if empty.
    parent_dirs: set[Path] = {d.parent for d in skill_dest_dirs}
    for parent in parent_dirs:
        _prune_empty_dir(parent)

    # Pop the installation entry.
    installations.pop(key)

    # Handle purge.
    purged = False
    if purge and credentials_path is not None:
        cred = Path(credentials_path)
        if cred.exists():
            cred.unlink()
            purged = True

    return {"removed": removed, "skipped": skipped, "purged": purged}


def _prune_empty_dir(path: Path) -> None:
    """Remove *path* if it is an existing empty directory; silently do nothing otherwise."""
    try:
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass


def merge_entry_block(entry_file: Path) -> None:
    """Idempotently insert/replace the managed konecty-skills block in *entry_file*.

    Rules
    -----
    * File absent → create it containing only the block.
    * File exists, no markers → append the block (preceded by a blank line),
      preserving all existing content.
    * File exists with markers → replace only the text between (and including)
      the markers; nothing outside is touched.
    * Running twice produces an identical file (idempotent).
    """
    entry_file = Path(entry_file)

    if not entry_file.exists():
        entry_file.parent.mkdir(parents=True, exist_ok=True)
        entry_file.write_text(_BLOCK_BODY + "\n", encoding="utf-8")
        return

    existing = entry_file.read_text(encoding="utf-8")

    if _BLOCK_START in existing and _BLOCK_END in existing:
        # Replace only the region between (and including) the markers.
        start_idx = existing.index(_BLOCK_START)
        end_idx = existing.index(_BLOCK_END) + len(_BLOCK_END)
        new_content = existing[:start_idx] + _BLOCK_BODY + existing[end_idx:]
        entry_file.write_text(new_content, encoding="utf-8")
    else:
        # Append the block, preceded by a blank line (unless file is empty).
        separator = "\n" if existing and not existing.endswith("\n\n") else ""
        if existing and not existing.endswith("\n"):
            separator = "\n" + separator
        entry_file.write_text(existing + separator + "\n" + _BLOCK_BODY + "\n", encoding="utf-8")
