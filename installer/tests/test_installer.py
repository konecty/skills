"""Unit tests for konecty_skills.installer (T8 + T9)."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from konecty_skills.installer import (
    _BLOCK_BODY,
    _BLOCK_END,
    _BLOCK_START,
    install,
    merge_entry_block,
    uninstall,
    update,
)


def _make_skills_root(tmp: Path) -> Path:
    """Create a fake skills_root with konecty-data and konecty-meta."""
    skills_root = tmp / "skills"
    for skill in ("konecty-data", "konecty-meta"):
        skill_dir = skills_root / skill
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {skill}\n", encoding="utf-8")
        scripts = skill_dir / "scripts"
        scripts.mkdir()
        (scripts / "main.py").write_text(f"# {skill} main\n", encoding="utf-8")
    return skills_root


def _fresh_manifest() -> dict:
    return {"schema": 1, "installations": {}}


class TestInstallSingleEngine(unittest.TestCase):
    """Test 1: install copies skills into root/.claude/skills/ for a single engine."""

    def test_copies_skills_and_records_manifest(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            skills_root = _make_skills_root(tmp)
            root = tmp / "project"
            root.mkdir()
            manifest = _fresh_manifest()

            report = install(
                skills_root=skills_root,
                root=root,
                engines=["claude"],
                scope="project",
                manifest=manifest,
                source={"repo": "konecty/skills", "ref": "main", "commit": None},
                installed_at="2026-06-17T00:00:00Z",
            )

            # Files should exist on disk.
            for skill in ("konecty-data", "konecty-meta"):
                dest_skill = root / ".claude" / "skills" / skill
                self.assertTrue(dest_skill.is_dir(), f"{dest_skill} should exist")
                self.assertTrue((dest_skill / "SKILL.md").exists())
                self.assertTrue((dest_skill / "scripts" / "main.py").exists())

            # Manifest installation entry should be present.
            installation = manifest["installations"][str(root)]
            self.assertEqual(installation["scope"], "project")
            self.assertEqual(installation["engines"], ["claude"])

            # Composite keys should be present.
            skills = installation["skills"]
            self.assertIn("claude:konecty-data", skills)
            self.assertIn("claude:konecty-meta", skills)

            # Hashes should be correct sha256.
            entry = skills["claude:konecty-data"]
            self.assertEqual(entry["dest"], ".claude/skills/konecty-data")
            skill_file = root / ".claude" / "skills" / "konecty-data" / "SKILL.md"
            expected_hash = hashlib.sha256(skill_file.read_bytes()).hexdigest()
            self.assertEqual(entry["files"]["SKILL.md"], expected_hash)

            # Report checks.
            self.assertEqual(report["engines"], ["claude"])
            self.assertIn("konecty-data", report["skills"])
            self.assertIn("konecty-meta", report["skills"])
            self.assertGreater(report["files_written"], 0)


class TestInstallTwoEngines(unittest.TestCase):
    """Test 2: install with two engines writes both dests and records composite keys for each."""

    def test_two_engines_write_both_dests(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            skills_root = _make_skills_root(tmp)
            root = tmp / "project"
            root.mkdir()
            manifest = _fresh_manifest()

            report = install(
                skills_root=skills_root,
                root=root,
                engines=["claude", "agents"],
                scope="project",
                manifest=manifest,
                source={"repo": "konecty/skills", "ref": "main", "commit": None},
                installed_at="2026-06-17T00:00:00Z",
            )

            # Both engine dests should have both skills.
            for engine, engine_dir in (("claude", ".claude"), ("agents", ".agents")):
                for skill in ("konecty-data", "konecty-meta"):
                    dest_skill = root / engine_dir / "skills" / skill
                    self.assertTrue(dest_skill.is_dir(), f"{dest_skill} should exist")

            # Manifest should have 4 composite keys (2 engines × 2 skills).
            skills = manifest["installations"][str(root)]["skills"]
            self.assertIn("claude:konecty-data", skills)
            self.assertIn("claude:konecty-meta", skills)
            self.assertIn("agents:konecty-data", skills)
            self.assertIn("agents:konecty-meta", skills)

            # Report contains both engines.
            self.assertIn("claude", report["engines"])
            self.assertIn("agents", report["engines"])
            self.assertEqual(len(report["dests"]), 2)


class TestInstallReplaceExisting(unittest.TestCase):
    """Test 3: install replaces a pre-existing skill dir but leaves unrelated sibling files."""

    def test_replaces_skill_dir_leaves_sibling(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            skills_root = _make_skills_root(tmp)
            root = tmp / "project"
            root.mkdir()

            dest_dir = root / ".claude" / "skills"
            dest_dir.mkdir(parents=True)

            # Pre-existing skill dir with old content.
            old_skill = dest_dir / "konecty-data"
            old_skill.mkdir()
            (old_skill / "OLD_FILE.md").write_text("old content", encoding="utf-8")

            # Unrelated sibling file in dest — must NOT be touched.
            sibling = dest_dir / "some-other-skill"
            sibling.mkdir()
            (sibling / "README.md").write_text("unrelated", encoding="utf-8")

            manifest = _fresh_manifest()
            install(
                skills_root=skills_root,
                root=root,
                engines=["claude"],
                scope="project",
                manifest=manifest,
                source={},
                installed_at="2026-06-17T00:00:00Z",
            )

            # Old file inside the replaced skill dir should be gone.
            self.assertFalse((old_skill / "OLD_FILE.md").exists())
            # New SKILL.md should be present.
            self.assertTrue((old_skill / "SKILL.md").exists())
            # Unrelated sibling must be untouched.
            self.assertTrue((sibling / "README.md").exists())
            self.assertEqual((sibling / "README.md").read_text(encoding="utf-8"), "unrelated")


class TestMergeEntryBlockCreate(unittest.TestCase):
    """Test 4: merge_entry_block creates the file with markers when absent;
    appends preserving prior content when markers are absent."""

    def test_creates_file_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ef = tmp / "CLAUDE.md"
            self.assertFalse(ef.exists())

            merge_entry_block(ef)

            self.assertTrue(ef.exists())
            content = ef.read_text(encoding="utf-8")
            self.assertIn(_BLOCK_START, content)
            self.assertIn(_BLOCK_END, content)
            self.assertIn("konecty-data", content)
            self.assertIn("konecty-meta", content)

    def test_appends_preserving_prior_content(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ef = tmp / "AGENTS.md"
            prior = "# My Project\n\nSome existing content.\n"
            ef.write_text(prior, encoding="utf-8")

            merge_entry_block(ef)

            content = ef.read_text(encoding="utf-8")
            # Prior content intact at the start.
            self.assertTrue(content.startswith("# My Project"))
            self.assertIn("Some existing content.", content)
            # Block appended.
            self.assertIn(_BLOCK_START, content)
            self.assertIn(_BLOCK_END, content)
            # Markers appear after the prior content.
            self.assertGreater(content.index(_BLOCK_START), content.index("Some existing content."))


class TestMergeEntryBlockIdempotent(unittest.TestCase):
    """Test 5: merge_entry_block is idempotent and replaces only the block region."""

    def test_running_twice_yields_identical_bytes(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ef = tmp / "CLAUDE.md"
            prior = "# Header\n\nContent before.\n"
            ef.write_text(prior, encoding="utf-8")

            merge_entry_block(ef)
            first_run = ef.read_bytes()

            merge_entry_block(ef)
            second_run = ef.read_bytes()

            self.assertEqual(first_run, second_run)

    def test_replaces_only_block_region_leaves_surrounding_content(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ef = tmp / "CLAUDE.md"
            # File already has the block with some surrounding content.
            before = "# Header\n\nBefore block.\n"
            after = "\nAfter block.\n"
            initial = before + _BLOCK_BODY + after
            ef.write_text(initial, encoding="utf-8")

            merge_entry_block(ef)

            content = ef.read_text(encoding="utf-8")
            # Surrounding content preserved.
            self.assertIn("Before block.", content)
            self.assertIn("After block.", content)
            # Exactly one occurrence of each marker.
            self.assertEqual(content.count(_BLOCK_START), 1)
            self.assertEqual(content.count(_BLOCK_END), 1)
            # Block body is present.
            self.assertIn("konecty-data", content)
            self.assertIn("konecty-meta", content)

    def test_file_with_existing_block_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            ef = tmp / "AGENTS.md"

            # First: create from scratch.
            merge_entry_block(ef)
            after_first = ef.read_bytes()

            # Second: run again on a file that already has the block.
            merge_entry_block(ef)
            after_second = ef.read_bytes()

            self.assertEqual(after_first, after_second)


# ---------------------------------------------------------------------------
# T9 helpers
# ---------------------------------------------------------------------------

def _do_install(tmp: Path, skills_root: Path, root: Path) -> dict:
    """Run install() with a single 'claude' engine and return the manifest."""
    manifest = _fresh_manifest()
    install(
        skills_root=skills_root,
        root=root,
        engines=["claude"],
        scope="project",
        manifest=manifest,
        source={"repo": "konecty/skills", "ref": "main", "commit": None},
        installed_at="2026-06-17T00:00:00Z",
    )
    return manifest


# ---------------------------------------------------------------------------
# T9 Tests — update()
# ---------------------------------------------------------------------------

class TestUpdateOverwritesUnmodifiedFile(unittest.TestCase):
    """T9-T1: update() overwrites an unmodified file and refreshes the manifest hash."""

    def test_overwrites_unmodified_file_and_updates_hash(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            skills_root = _make_skills_root(tmp)
            root = tmp / "project"
            root.mkdir()

            manifest = _do_install(tmp, skills_root, root)

            # Write a NEW version of SKILL.md in skills_root (simulates upstream update).
            new_content = "# konecty-data v2\n"
            (skills_root / "konecty-data" / "SKILL.md").write_text(new_content, encoding="utf-8")

            result = update(
                skills_root=skills_root,
                root=root,
                manifest=manifest,
                installed_at="2026-06-18T00:00:00Z",
            )

            # File on disk should now have the new content.
            installed_skill_md = root / ".claude" / "skills" / "konecty-data" / "SKILL.md"
            self.assertEqual(installed_skill_md.read_text(encoding="utf-8"), new_content)

            # Manifest hash should be updated to match the new content.
            expected_hash = hashlib.sha256(new_content.encode()).hexdigest()
            recorded_hash = (
                manifest["installations"][str(root)]["skills"]["claude:konecty-data"]["files"]["SKILL.md"]
            )
            self.assertEqual(recorded_hash, expected_hash)

            # At least one file was updated; nothing in preserved.
            self.assertGreater(result["updated"], 0)
            self.assertEqual(result["preserved"], [])

            # installed_at was refreshed.
            self.assertEqual(
                manifest["installations"][str(root)]["installed_at"],
                "2026-06-18T00:00:00Z",
            )


class TestUpdatePreservesLocallyModifiedFile(unittest.TestCase):
    """T9-T2: update() skips locally modified files and reports them under 'preserved'."""

    def test_preserves_locally_modified_file(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            skills_root = _make_skills_root(tmp)
            root = tmp / "project"
            root.mkdir()

            manifest = _do_install(tmp, skills_root, root)

            # Simulate a local edit to the installed SKILL.md.
            installed_skill_md = root / ".claude" / "skills" / "konecty-data" / "SKILL.md"
            local_edit_content = "# locally edited\n"
            installed_skill_md.write_text(local_edit_content, encoding="utf-8")

            # Also update the upstream version so it differs from the pre-install original.
            (skills_root / "konecty-data" / "SKILL.md").write_text(
                "# upstream v2\n", encoding="utf-8"
            )

            result = update(
                skills_root=skills_root,
                root=root,
                manifest=manifest,
                installed_at="2026-06-18T00:00:00Z",
            )

            # The locally modified file must NOT be overwritten.
            self.assertEqual(installed_skill_md.read_text(encoding="utf-8"), local_edit_content)

            # It should appear in 'preserved'.
            self.assertTrue(
                any(p["skill"] == "claude:konecty-data" and p["file"] == "SKILL.md"
                    for p in result["preserved"]),
                f"Expected SKILL.md in preserved, got: {result['preserved']}",
            )


class TestUpdateAddsNewFile(unittest.TestCase):
    """T9-T3: update() copies a brand-new file from skills_root that wasn't previously recorded."""

    def test_adds_new_file_to_disk_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            skills_root = _make_skills_root(tmp)
            root = tmp / "project"
            root.mkdir()

            manifest = _do_install(tmp, skills_root, root)

            # Add a brand-new file to skills_root AFTER install.
            new_file_content = "# new reference\n"
            new_file_src = skills_root / "konecty-data" / "references" / "new.md"
            new_file_src.parent.mkdir(parents=True, exist_ok=True)
            new_file_src.write_text(new_file_content, encoding="utf-8")

            result = update(
                skills_root=skills_root,
                root=root,
                manifest=manifest,
                installed_at="2026-06-18T00:00:00Z",
            )

            # The new file should appear on disk.
            dest_new_file = root / ".claude" / "skills" / "konecty-data" / "references" / "new.md"
            self.assertTrue(dest_new_file.exists(), "New file should have been copied to dest")
            self.assertEqual(dest_new_file.read_text(encoding="utf-8"), new_file_content)

            # It should be recorded in the manifest.
            recorded = (
                manifest["installations"][str(root)]["skills"]["claude:konecty-data"]["files"]
            )
            self.assertIn("references/new.md", recorded)

            # result should report at least 1 added file.
            self.assertGreater(result["added"], 0)


# ---------------------------------------------------------------------------
# T9 Tests — uninstall()
# ---------------------------------------------------------------------------

class TestUninstallRemovesTrackedFiles(unittest.TestCase):
    """T9-T4: uninstall() removes all unmodified tracked files and pops the manifest entry;
    an untracked sibling file survives."""

    def test_removes_tracked_leaves_untracked_sibling(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            skills_root = _make_skills_root(tmp)
            root = tmp / "project"
            root.mkdir()

            manifest = _do_install(tmp, skills_root, root)

            # Plant an untracked sibling file inside the skills dir.
            sibling = root / ".claude" / "skills" / "konecty-data" / "my_notes.txt"
            sibling.write_text("personal notes", encoding="utf-8")

            result = uninstall(root=root, manifest=manifest)

            # All tracked files should be gone.
            tracked_skill_md = root / ".claude" / "skills" / "konecty-data" / "SKILL.md"
            self.assertFalse(tracked_skill_md.exists(), "Tracked SKILL.md should have been removed")

            # Untracked sibling file must survive.
            self.assertTrue(sibling.exists(), "Untracked sibling must not be removed")

            # Installation entry should be gone from the manifest.
            self.assertNotIn(str(root), manifest["installations"])

            # Nothing was skipped.
            self.assertEqual(result["skipped"], [])
            self.assertGreater(result["removed"], 0)


class TestUninstallModifiedFileConfirmation(unittest.TestCase):
    """T9-T5: uninstall() on a locally-modified file calls confirm_modified;
    when it returns False the file is kept under 'skipped'.
    With purge=True and a tmp credentials_path the credentials file is removed."""

    def test_modified_file_kept_when_confirm_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            skills_root = _make_skills_root(tmp)
            root = tmp / "project"
            root.mkdir()

            manifest = _do_install(tmp, skills_root, root)

            # Locally modify one tracked file.
            modified_skill_md = root / ".claude" / "skills" / "konecty-data" / "SKILL.md"
            modified_skill_md.write_text("# user-modified\n", encoding="utf-8")

            # confirm_modified always returns False → keep the file.
            calls: list[tuple] = []
            def confirm_no(skill, file):
                calls.append((skill, file))
                return False

            result = uninstall(root=root, manifest=manifest, confirm_modified=confirm_no)

            # The modified file must still be on disk.
            self.assertTrue(modified_skill_md.exists(), "Modified file should be preserved")
            self.assertEqual(modified_skill_md.read_text(encoding="utf-8"), "# user-modified\n")

            # It should appear under skipped.
            self.assertTrue(
                any(s["file"] == "SKILL.md" for s in result["skipped"]),
                f"Expected SKILL.md in skipped, got: {result['skipped']}",
            )

            # confirm_modified was called at least once.
            self.assertGreater(len(calls), 0)

            # Installation entry is still popped.
            self.assertNotIn(str(root), manifest["installations"])

    def test_purge_removes_credentials_file(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            skills_root = _make_skills_root(tmp)
            root = tmp / "project"
            root.mkdir()

            # Create a fake credentials file.
            cred_path = tmp / "fake_creds" / ".env"
            cred_path.parent.mkdir(parents=True)
            cred_path.write_text("KONECTY_TOKEN=secret\n", encoding="utf-8")

            manifest = _do_install(tmp, skills_root, root)

            result = uninstall(
                root=root,
                manifest=manifest,
                purge=True,
                credentials_path=cred_path,
            )

            # Credentials file should be removed.
            self.assertFalse(cred_path.exists(), "Credentials file should be purged")
            self.assertTrue(result["purged"])


if __name__ == "__main__":
    unittest.main()
