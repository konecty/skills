"""Unit tests for konecty_skills.fetcher — no network access."""
from __future__ import annotations

import gzip
import io
import tarfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from konecty_skills.fetcher import FetchError, fetch_skills


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tarball(*entries: tuple[str, bytes]) -> bytes:
    """Build an in-memory .tar.gz.

    *entries* is a sequence of (archive_path, content_bytes).
    Directories are created automatically for every file entry.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        # Track which dir entries have been added to avoid duplicates
        added_dirs: set[str] = set()

        for archive_path, content in entries:
            # Add parent directory entries so the tar is well-formed
            parts = archive_path.split("/")
            for depth in range(1, len(parts)):
                dir_name = "/".join(parts[:depth])
                if dir_name not in added_dirs:
                    dir_info = tarfile.TarInfo(name=dir_name)
                    dir_info.type = tarfile.DIRTYPE
                    dir_info.mode = 0o755
                    tf.addfile(dir_info)
                    added_dirs.add(dir_name)

            file_info = tarfile.TarInfo(name=archive_path)
            file_info.size = len(content)
            tf.addfile(file_info, io.BytesIO(content))

    return buf.getvalue()


def _make_standard_tarball() -> bytes:
    """Archive that mimics a real GitHub source tarball for ref 'main'."""
    return _make_tarball(
        ("skills-main/README.md", b"top-level readme"),
        ("skills-main/skills/konecty-data/SKILL.md", b"data skill"),
        ("skills-main/skills/konecty-data/scripts/auth.py", b"# auth"),
        ("skills-main/skills/konecty-meta/SKILL.md", b"meta skill"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFetchSkillsExtracts(unittest.TestCase):
    """T1 — correct files are extracted; unrelated entries are ignored."""

    def test_skill_dirs_present(self) -> None:
        tarball = _make_standard_tarball()
        with patch("konecty_skills.fetcher._download", return_value=tarball):
            result = fetch_skills(ref="main")

        root = Path(result["skills_root"])
        self.assertTrue((root / "konecty-data").is_dir(), "konecty-data missing")
        self.assertTrue((root / "konecty-meta").is_dir(), "konecty-meta missing")

    def test_nested_file_extracted(self) -> None:
        tarball = _make_standard_tarball()
        with patch("konecty_skills.fetcher._download", return_value=tarball):
            result = fetch_skills(ref="main")

        root = Path(result["skills_root"])
        nested = root / "konecty-data" / "scripts" / "auth.py"
        self.assertTrue(nested.exists(), "scripts/auth.py not extracted")
        self.assertEqual(nested.read_bytes(), b"# auth")

    def test_unrelated_readme_not_extracted(self) -> None:
        tarball = _make_standard_tarball()
        with patch("konecty_skills.fetcher._download", return_value=tarball):
            result = fetch_skills(ref="main")

        root = Path(result["skills_root"])
        # The top-level README.md must NOT appear anywhere under skills_root
        readme = root / "README.md"
        self.assertFalse(readme.exists(), "top-level README.md should not be extracted")

    def test_return_shape(self) -> None:
        tarball = _make_standard_tarball()
        with patch("konecty_skills.fetcher._download", return_value=tarball):
            result = fetch_skills(ref="main")

        self.assertIn("tmp_dir", result)
        self.assertIn("skills_root", result)
        self.assertEqual(result["ref"], "main")
        self.assertIsNone(result["commit"])


class TestFetchSkillsSkillsRootContent(unittest.TestCase):
    """T2 — skills_root actually contains both SKILL.md files."""

    def test_skill_md_files_exist(self) -> None:
        tarball = _make_standard_tarball()
        with patch("konecty_skills.fetcher._download", return_value=tarball):
            result = fetch_skills(ref="main")

        root = Path(result["skills_root"])
        data_skill = root / "konecty-data" / "SKILL.md"
        meta_skill = root / "konecty-meta" / "SKILL.md"

        self.assertTrue(data_skill.exists(), "konecty-data/SKILL.md missing")
        self.assertTrue(meta_skill.exists(), "konecty-meta/SKILL.md missing")

    def test_skill_md_content(self) -> None:
        tarball = _make_standard_tarball()
        with patch("konecty_skills.fetcher._download", return_value=tarball):
            result = fetch_skills(ref="main")

        root = Path(result["skills_root"])
        self.assertEqual((root / "konecty-data" / "SKILL.md").read_bytes(), b"data skill")
        self.assertEqual((root / "konecty-meta" / "SKILL.md").read_bytes(), b"meta skill")


class TestFetchSkillsTraversalRejected(unittest.TestCase):
    """T3 — path-traversal members raise FetchError."""

    def _make_traversal_tarball(self) -> bytes:
        """Tarball with a malicious member that tries to escape the temp dir."""
        return _make_tarball(
            # Legitimate member
            ("skills-main/skills/konecty-data/SKILL.md", b"ok"),
            # Traversal: resolves to ../../evil.sh relative to konecty-data
            ("skills-main/skills/konecty-data/../../../evil.sh", b"malicious"),
        )

    def test_traversal_raises_fetch_error(self) -> None:
        tarball = self._make_traversal_tarball()
        with patch("konecty_skills.fetcher._download", return_value=tarball):
            with self.assertRaises(FetchError):
                fetch_skills(ref="main")


class TestFetchSkillsNetworkErrors(unittest.TestCase):
    """T4 — urllib errors are wrapped in FetchError."""

    def test_http_error_raises_fetch_error(self) -> None:
        http_err = urllib.error.HTTPError(
            url="http://example.com",
            code=500,
            msg="Internal Server Error",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )
        with patch("konecty_skills.fetcher._download", side_effect=FetchError("http", http_err)):
            with self.assertRaises(FetchError):
                fetch_skills(ref="main")

    def test_url_error_raises_fetch_error(self) -> None:
        url_err = urllib.error.URLError(reason="Name or service not known")
        with patch("konecty_skills.fetcher._download", side_effect=FetchError("url", url_err)):
            with self.assertRaises(FetchError):
                fetch_skills(ref="main")

    def test_download_helper_wraps_http_error(self) -> None:
        """_download itself must raise FetchError, not a raw HTTPError."""
        from konecty_skills.fetcher import _download

        http_err = urllib.error.HTTPError(
            url="http://x.example.com",
            code=404,
            msg="Not Found",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            with self.assertRaises(FetchError):
                _download("http://x.example.com")

    def test_download_helper_wraps_url_error(self) -> None:
        """_download itself must raise FetchError, not a raw URLError."""
        from konecty_skills.fetcher import _download

        url_err = urllib.error.URLError(reason="connection refused")
        with patch("urllib.request.urlopen", side_effect=url_err):
            with self.assertRaises(FetchError):
                _download("http://x.example.com")


if __name__ == "__main__":
    unittest.main()
