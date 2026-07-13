"""Download and extract the skills tarball from GitHub. Implemented in T6."""
from __future__ import annotations

import io
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SKILL_DIRS = ("konecty-data", "konecty-meta", "konecty-setup", "konecty-dev")

_PUBLIC_URL = "https://github.com/konecty/skills/archive/refs/heads/{ref}.tar.gz"
_API_URL = "https://api.github.com/repos/konecty/skills/tarball/{ref}"


class FetchError(Exception):
    """Raised when the skills tarball cannot be downloaded or extracted."""


def _download(url: str, token: str | None = None) -> bytes:
    """Fetch *url* and return the raw response bytes.

    If *token* is provided it is sent as a Bearer Authorization header.
    Raises FetchError on any network or HTTP error, or if the URL scheme is
    not ``https`` (B310 guard against file:// and SSRF vectors).
    """
    # B310: only allow https; GitHub archive and API are always https.
    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme != "https":
        raise FetchError(f"Unsupported URL scheme {scheme!r}; only https is allowed.")

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["Accept"] = "application/vnd.github+json"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310  # nosec B310 - https-only guard above
            return resp.read()
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise FetchError(f"Download failed for {url}: {exc}") from exc


def fetch_skills(ref: str = "main", token: str | None = None) -> dict:
    """Download and extract the Konecty skill folders (SKILL_DIRS).

    Steps
    -----
    1. Try the public GitHub source-archive URL.
    2. On HTTP 401/404, retry the GitHub API tarball URL (requires *token*).
    3. Extract only ``*/skills/konecty-data/**`` and
       ``*/skills/konecty-meta/**`` into a fresh temp directory, stripping the
       top-level archive component **and** the leading ``skills/`` segment so
       the layout becomes ``<tmp>/konecty-data/…`` and ``<tmp>/konecty-meta/…``.
    4. Reject any member whose resolved destination escapes the temp dir.

    Returns
    -------
    dict with keys ``tmp_dir``, ``skills_root``, ``ref``, ``commit``.

    Raises
    ------
    FetchError
        On any network, HTTP, or tar error, or a path-traversal attempt.
    """
    # --- 1. Download --------------------------------------------------------
    public_url = _PUBLIC_URL.format(ref=ref)
    raw: bytes
    try:
        raw = _download(public_url)
    except FetchError as exc:
        # Unwrap to inspect the original HTTP status if available
        original = exc.__cause__
        if (
            token
            and isinstance(original, urllib.error.HTTPError)
            and original.code in (401, 404)
        ):
            api_url = _API_URL.format(ref=ref)
            try:
                raw = _download(api_url, token=token)
            except FetchError:
                raise
        else:
            raise

    # --- 2. Extract ---------------------------------------------------------
    tmp_dir = tempfile.mkdtemp(prefix="konecty-skills-")
    tmp_path = Path(tmp_dir)

    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
            for member in tf.getmembers():
                parts = Path(member.name).parts  # e.g. ('skills-main', 'skills', 'konecty-data', 'SKILL.md')

                # Must have at least: <top>/ skills/ <skill-dir>/ <file>
                # i.e. at minimum 4 parts for a file (3 for the directory itself)
                if len(parts) < 3:
                    continue  # top-level or too shallow

                # Strip the top-level archive dir (parts[0] = 'skills-main')
                # The next component must be 'skills'
                if parts[1] != "skills":
                    continue

                # The component after 'skills/' must be one of the skill dirs
                if parts[2] not in SKILL_DIRS:
                    continue

                # Build the relative destination path: konecty-data/<rest>
                rel_parts = parts[2:]  # ('konecty-data', 'SKILL.md', …)
                rel_path = Path(*rel_parts)

                dest = (tmp_path / rel_path).resolve()

                # --- SECURITY: path-traversal guard -------------------------
                try:
                    dest.relative_to(tmp_path.resolve())
                except ValueError:
                    raise FetchError(
                        f"Path traversal detected in archive member: {member.name!r}"
                    )

                # Extract
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    file_obj = tf.extractfile(member)
                    if file_obj is not None:
                        dest.write_bytes(file_obj.read())
                # Ignore symlinks and other exotic member types

    except tarfile.TarError as exc:
        raise FetchError(f"Failed to open/read archive: {exc}") from exc

    return {
        "tmp_dir": tmp_dir,
        "skills_root": tmp_dir,
        "ref": ref,
        "commit": None,
    }
