"""Install manifest: model, sha256 hashing, conflict detection. Implemented in T4."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

DEFAULT_MANIFEST_PATH: Path = Path.home() / ".konecty" / "manifest.json"

_EMPTY_MANIFEST: dict = {"schema": 1, "installations": {}}


def load(path: Path = DEFAULT_MANIFEST_PATH) -> dict:
    """Return the manifest dict; if file is missing return a fresh empty manifest."""
    path = Path(path)
    if not path.exists():
        return {"schema": 1, "installations": {}}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save(manifest: dict, path: Path = DEFAULT_MANIFEST_PATH) -> None:
    """Write manifest to *path*, creating the parent directory (mode 0o700) if needed."""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)


def hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of the bytes in *path*."""
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def diff(installation: dict, dest_root: Path) -> list[dict]:
    """Compare recorded hashes in *installation* against files on disk under *dest_root*.

    For every (skill, relative-file) pair recorded in installation["skills"], look up the
    file at ``dest_root / skill_dest / relpath`` and compare its SHA-256 to the stored hash.

    Returns a list of conflict dicts::

        {"skill": <skill_name>, "file": <relpath>, "reason": "modified" | "missing"}

    Files whose on-disk hash matches the recorded hash are not included.
    """
    dest_root = Path(dest_root)
    conflicts: list[dict] = []

    skills: dict = installation.get("skills", {})
    for skill_name, skill_info in skills.items():
        skill_dest: str = skill_info.get("dest", "")
        files: dict = skill_info.get("files", {})
        for relpath, recorded_hash in files.items():
            on_disk = dest_root / skill_dest / relpath
            if not on_disk.exists():
                conflicts.append({"skill": skill_name, "file": relpath, "reason": "missing"})
            else:
                actual_hash = hashlib.sha256(on_disk.read_bytes()).hexdigest()
                if actual_hash != recorded_hash:
                    conflicts.append({"skill": skill_name, "file": relpath, "reason": "modified"})

    return conflicts
