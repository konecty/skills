"""Unit tests for konecty_skills.manifest (T4)."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from konecty_skills.manifest import diff, hash_file, load, save


class TestLoadSave(unittest.TestCase):
    """Tests for load() and save()."""

    def test_load_missing_file_returns_empty_schema(self):
        """load() on a non-existent path returns the empty manifest structure."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does_not_exist.json"
            result = load(missing)
        self.assertEqual(result, {"schema": 1, "installations": {}})

    def test_save_and_load_roundtrip(self):
        """save() followed by load() on the same path reproduces the original dict."""
        manifest = {
            "schema": 1,
            "installations": {
                "/some/project": {
                    "installed_at": "2024-01-01T00:00:00Z",
                    "source": {"repo": "konecty/skills", "ref": "main", "commit": None},
                    "scope": "project",
                    "engines": ["claude"],
                    "skills": {
                        "konecty-data": {
                            "dest": ".claude/skills/konecty-data",
                            "files": {"SKILL.md": "abc123"},
                        }
                    },
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "subdir" / "manifest.json"
            save(manifest, path)
            loaded = load(path)

        self.assertEqual(loaded, manifest)

    def test_save_creates_parent_directory(self):
        """save() creates the parent directory when it does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "new_dir" / "manifest.json"
            self.assertFalse(path.parent.exists())
            save({"schema": 1, "installations": {}}, path)
            self.assertTrue(path.exists())

    def test_save_parent_directory_mode(self):
        """save() creates the parent directory with mode 0o700."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "private" / "manifest.json"
            save({"schema": 1, "installations": {}}, path)
            mode = path.parent.stat().st_mode & 0o777
            self.assertEqual(mode, 0o700)


class TestHashFile(unittest.TestCase):
    """Tests for hash_file()."""

    def test_hash_matches_hashlib_sha256(self):
        """hash_file() must equal hashlib.sha256 of the same bytes."""
        content = b"hello konecty\n"
        expected = hashlib.sha256(content).hexdigest()
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            fh.write(content)
            tmp_path = Path(fh.name)
        try:
            self.assertEqual(hash_file(tmp_path), expected)
        finally:
            tmp_path.unlink()

    def test_hash_is_stable(self):
        """Calling hash_file() twice on the same file returns the same digest."""
        content = b"stable content"
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            fh.write(content)
            tmp_path = Path(fh.name)
        try:
            self.assertEqual(hash_file(tmp_path), hash_file(tmp_path))
        finally:
            tmp_path.unlink()

    def test_different_content_different_hash(self):
        """Different file content produces a different hash."""
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            fh.write(b"content A")
            path_a = Path(fh.name)
        with tempfile.NamedTemporaryFile(delete=False) as fh:
            fh.write(b"content B")
            path_b = Path(fh.name)
        try:
            self.assertNotEqual(hash_file(path_a), hash_file(path_b))
        finally:
            path_a.unlink()
            path_b.unlink()


class TestDiff(unittest.TestCase):
    """Tests for diff()."""

    def _make_installation(self, dest: str, files: dict[str, str]) -> dict:
        return {
            "skills": {
                "konecty-data": {
                    "dest": dest,
                    "files": files,
                }
            }
        }

    def test_no_conflicts_when_files_match(self):
        """diff() returns [] when on-disk content matches all recorded hashes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / ".claude" / "skills" / "konecty-data"
            skill_dir.mkdir(parents=True)
            content = b"# SKILL.md content"
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_bytes(content)
            recorded_hash = hashlib.sha256(content).hexdigest()

            installation = self._make_installation(
                ".claude/skills/konecty-data",
                {"SKILL.md": recorded_hash},
            )
            result = diff(installation, root)

        self.assertEqual(result, [])

    def test_modified_conflict_when_content_changed(self):
        """diff() returns a 'modified' conflict when a file's content has changed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / ".claude" / "skills" / "konecty-data"
            skill_dir.mkdir(parents=True)
            original_content = b"original"
            modified_content = b"modified"
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_bytes(modified_content)
            recorded_hash = hashlib.sha256(original_content).hexdigest()

            installation = self._make_installation(
                ".claude/skills/konecty-data",
                {"SKILL.md": recorded_hash},
            )
            result = diff(installation, root)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["skill"], "konecty-data")
        self.assertEqual(result[0]["file"], "SKILL.md")
        self.assertEqual(result[0]["reason"], "modified")

    def test_missing_conflict_when_file_absent(self):
        """diff() returns a 'missing' conflict when a recorded file does not exist on disk."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Do NOT create the skill directory or file
            installation = self._make_installation(
                ".claude/skills/konecty-data",
                {"SKILL.md": "deadbeef" * 8},
            )
            result = diff(installation, root)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["skill"], "konecty-data")
        self.assertEqual(result[0]["file"], "SKILL.md")
        self.assertEqual(result[0]["reason"], "missing")

    def test_multiple_files_mixed_conflicts(self):
        """diff() correctly separates clean, modified, and missing files in one call."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / ".claude" / "skills" / "konecty-data"
            (skill_dir / "scripts").mkdir(parents=True)

            # clean file
            clean_content = b"clean"
            clean_hash = hashlib.sha256(clean_content).hexdigest()
            (skill_dir / "SKILL.md").write_bytes(clean_content)

            # modified file
            orig_content = b"original"
            mod_hash = hashlib.sha256(orig_content).hexdigest()
            (skill_dir / "scripts" / "auth.py").write_bytes(b"tampered")

            # missing file — not written to disk

            installation = self._make_installation(
                ".claude/skills/konecty-data",
                {
                    "SKILL.md": clean_hash,
                    "scripts/auth.py": mod_hash,
                    "references/field-discovery.md": "aabbccdd" * 8,
                },
            )
            result = diff(installation, root)

        reasons = {c["file"]: c["reason"] for c in result}
        self.assertNotIn("SKILL.md", reasons)
        self.assertEqual(reasons.get("scripts/auth.py"), "modified")
        self.assertEqual(reasons.get("references/field-discovery.md"), "missing")
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
