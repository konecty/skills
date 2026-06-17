#!/usr/bin/env python3
"""konecty-skills CLI entry point.

Argparse dispatcher for the six lifecycle commands. Command bodies are wired in
later tasks (T10–T13); for now each handler is a stub that returns 0 so the
package builds and ``konecty-skills --help`` works.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import __version__

DEFAULT_REF = "main"
ENGINES = ("claude", "agents", "cursor")
SCOPES = ("project", "global")


# --- konecty home path seam (overridable via KONECTY_HOME env var) ----------

def _konecty_home() -> Path:
    return Path(os.environ.get("KONECTY_HOME", str(Path.home() / ".konecty")))


def _manifest_path() -> Path:
    return _konecty_home() / "manifest.json"


def _env_path() -> Path:
    return _konecty_home() / ".env"


# --- commands ---------------------------------------------------------------

def cmd_install(args: argparse.Namespace) -> int:
    from . import banner, credentials, engines, fetcher, installer, manifest, ui

    assume_yes: bool = args.yes

    # 1. Print banner (globe + wordmark).
    banner.print_full()

    # 2. Determine project root.
    root: Path = Path.cwd() if args.scope == "project" else Path.home()

    # 3. Determine engines.
    if args.engine:
        chosen: list[str] = list(args.engine)
    else:
        detected = engines.detect(root)
        if detected:
            chosen = detected
        else:
            chosen = ["claude"]
            ui.warn("No engine detected in current directory; falling back to claude.")

    # When not assume_yes, let user confirm/adjust the selection.
    if not assume_yes:
        chosen = ui.select(engines.SUPPORTED_ENGINES, preselected=chosen, assume_yes=False)

    # 4. Fetch skills.
    try:
        fetch = fetcher.fetch_skills(ref=args.ref)
    except fetcher.FetchError as exc:
        ui.err(f"Failed to fetch skills: {exc}")
        return 1

    # 5. Load manifest.
    m = manifest.load(_manifest_path())

    # 6. Install skills.
    installed_at = datetime.now(timezone.utc).isoformat()
    source = {
        "repo": "konecty/skills",
        "ref": fetch["ref"],
        "commit": fetch["commit"],
    }
    report = installer.install(
        Path(fetch["skills_root"]),
        root,
        chosen,
        args.scope,
        m,
        source,
        installed_at,
    )

    # 7. Merge entry blocks.
    for engine in chosen:
        ef = engines.entry_file(engine, root)
        if ef is not None:
            installer.merge_entry_block(ef)

    # 8. Save manifest.
    manifest.save(m, _manifest_path())

    # 9. Credentials step (wrapped so a failure here doesn't undo the install).
    cred_status = "skipped"
    try:
        env = credentials.current_env(_env_path())

        # Resolve URL.
        url: str | None = args.url
        if not url and not assume_yes:
            url = credentials.prompt_url(env["url"])
        elif not url and not env["url"]:
            ui.warn("No URL provided and no saved credentials; skipping credentials setup.")
            url = None

        if url:
            if assume_yes:
                credentials.write_url_only(url, _env_path())
                cred_status = "url_written"
            else:
                # Interactive: ask whether to run OTP.
                run_otp_now = ui.confirm("Run OTP login now?", True, assume_yes)
                if run_otp_now:
                    identifier = ui.ask("Email or phone")
                    auth_py = engines.dest_path(chosen[0], root, args.scope) / "konecty-data" / "scripts" / "auth.py"
                    otp_ok = credentials.run_otp(url, auth_py, identifier)
                    if otp_ok:
                        cred_status = "otp_complete"
                    else:
                        ui.warn("OTP login failed; writing URL only.")
                        credentials.write_url_only(url, _env_path())
                        cred_status = "url_written"
                else:
                    credentials.write_url_only(url, _env_path())
                    cred_status = "url_written"
    except Exception as exc:  # noqa: BLE001
        ui.warn(f"Credentials step failed ({exc}); skills were installed successfully.")
        cred_status = "error"

    # 10. Print summary.
    ui.ok(f"Engines  : {', '.join(report['engines'])}")
    ui.ok(f"Skills   : {', '.join(report['skills'])}")
    ui.ok(f"Dests    : {', '.join(report['dests'])}")
    ui.ok(f"Files    : {report['files_written']} written")
    ui.ok(f"Creds    : {cred_status}")

    return 0


def _root(args: argparse.Namespace) -> Path:
    """Resolve the installation root from args (mirrors cmd_install logic)."""
    return Path.cwd() if args.scope == "project" else Path.home()


def _probe_konecty(url: str, token: str) -> tuple[bool, str]:
    """Probe the Konecty server with a GET to /api/auth/login-options.

    Returns (reachable, detail).  All exceptions are caught so this is always
    safe to call — callers just inspect the boolean.
    """
    import urllib.parse
    import urllib.request
    import urllib.error

    probe_url = f"{url.rstrip('/')}/api/auth/login-options"

    # B310: guard scheme before calling urlopen.
    scheme = urllib.parse.urlparse(probe_url).scheme.lower()
    if scheme not in ("http", "https"):
        return False, f"unsupported URL scheme: {scheme!r}"

    try:
        req = urllib.request.Request(
            probe_url,
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310  # nosec B310 - scheme guarded above
            return True, f"HTTP {resp.status}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def cmd_configure(args: argparse.Namespace) -> int:
    from . import credentials, manifest, ui

    assume_yes: bool = args.yes

    # Read existing credentials.
    env = credentials.current_env(_env_path())

    # If credentials already exist and we're not force-confirming, ask.
    if (env["url"] or env["token"]) and not assume_yes:
        masked_token = (env["token"][:4] + "****") if env["token"] else "(not set)"
        ui.step(f"Current URL  : {env['url'] or '(not set)'}")
        ui.step(f"Current token: {masked_token}")
        if not ui.confirm("Overwrite existing credentials?", False, args.yes):
            return 0

    # Resolve URL.
    url: str | None = args.url
    if not url:
        if assume_yes:
            # No url provided in non-interactive mode — nothing to do.
            if env["url"]:
                url = env["url"]
            else:
                ui.warn("No URL provided; skipping credentials setup.")
                return 0
        else:
            url = credentials.prompt_url(env["url"])

    if assume_yes:
        credentials.write_url_only(url, _env_path())
        return 0

    # Interactive: offer OTP.
    run_otp_now = ui.confirm("Run OTP login now?", True, False)
    if run_otp_now:
        # Find auth.py from the manifest (first installation containing konecty-data).
        m = manifest.load(_manifest_path())
        auth_py: Path | None = None
        for inst_root_str, installation in m.get("installations", {}).items():
            for _key, skill_info in installation.get("skills", {}).items():
                dest_rel = skill_info.get("dest", "")
                if "konecty-data" in dest_rel:
                    candidate = Path(inst_root_str) / dest_rel / "scripts" / "auth.py"
                    if candidate.exists():
                        auth_py = candidate
                        break
            if auth_py:
                break

        if auth_py:
            identifier = ui.ask("Email or phone")
            otp_ok = credentials.run_otp(url, auth_py, identifier)
            if not otp_ok:
                ui.warn("OTP login failed; writing URL only.")
                credentials.write_url_only(url, _env_path())
        else:
            ui.warn("Install skills first to run OTP; writing URL only.")
            credentials.write_url_only(url, _env_path())
    else:
        credentials.write_url_only(url, _env_path())

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from . import credentials, manifest, ui

    m = manifest.load(_manifest_path())
    installs = m.get("installations", {})

    root_key = str(_root(args).resolve())
    if args.all:
        targets = list(installs.items())
    else:
        if root_key in installs:
            targets = [(root_key, installs[root_key])]
        else:
            ui.step(f"No installation found for {root_key}. Use --all to list all.")
            return 0

    env = credentials.current_env(_env_path())
    url_status = "set" if env["url"] else "missing"
    token_status = "set" if env["token"] else "missing"

    for inst_root, installation in targets:
        ui.step(f"Root    : {inst_root}")
        ui.step(f"Scope   : {installation.get('scope', '?')}")
        ui.step(f"Engines : {', '.join(installation.get('engines', []))}")
        source = installation.get("source", {})
        ui.step(f"Source  : ref={source.get('ref', '?')} commit={source.get('commit', '?')}")
        skill_keys = list(installation.get("skills", {}).keys())
        ui.step(f"Skills  : {', '.join(skill_keys) if skill_keys else '(none)'}")
        ui.step(f"Creds   : url={url_status}, token={token_status}")

    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from . import credentials, manifest, ui

    m = manifest.load(_manifest_path())
    installs = m.get("installations", {})

    root_key = str(_root(args).resolve())
    if args.all:
        targets = [(k, v) for k, v in installs.items()]
    else:
        if root_key in installs:
            targets = [(root_key, installs[root_key])]
        else:
            ui.step(f"No installation found for {root_key}. Use --all to list all.")
            return 0

    for inst_root, installation in targets:
        ui.step(f"Checking {inst_root} ...")
        conflicts = manifest.diff(installation, Path(inst_root))
        if conflicts:
            for c in conflicts:
                ui.warn(f"  {c['skill']}/{c['file']}: {c['reason']}")
        else:
            ui.ok("All files match manifest")

    # Credentials / connection check.
    env = credentials.current_env(_env_path())
    if env["url"] and env["token"]:
        reachable, detail = _probe_konecty(env["url"], env["token"])
        if reachable:
            ui.ok(f"Konecty connection: OK ({detail})")
        else:
            ui.warn(f"Konecty connection: FAILED ({detail})")
    else:
        ui.warn("No credentials configured")

    return 0


def cmd_update(args: argparse.Namespace) -> int:
    from . import fetcher, installer, manifest, ui

    root = _root(args)
    m = manifest.load(_manifest_path())
    root_key = str(root.resolve())

    if root_key not in m.get("installations", {}):
        ui.err(f"No installation found for {root_key}; run install first.")
        return 1

    try:
        fetch = fetcher.fetch_skills(ref=args.ref)
    except fetcher.FetchError as exc:
        ui.err(f"Failed to fetch skills: {exc}")
        return 1

    report = installer.update(
        Path(fetch["skills_root"]),
        root.resolve(),
        m,
        datetime.now(timezone.utc).isoformat(),
    )
    manifest.save(m, _manifest_path())

    ui.ok(f"Updated  : {report['updated']} files")
    ui.ok(f"Added    : {report['added']} new files")
    if report["preserved"]:
        for p in report["preserved"]:
            ui.warn(f"Preserved (locally modified): {p['skill']}/{p['file']}")

    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    from . import installer, manifest, ui

    root = _root(args)
    m = manifest.load(_manifest_path())
    root_key = str(root.resolve())

    if root_key not in m.get("installations", {}):
        ui.err(f"No installation found for {root_key}; nothing to uninstall.")
        return 1

    if not args.yes:
        if not ui.confirm("Remove installed Konecty skills?", False, args.yes):
            return 0

    confirm_modified = (
        (lambda skill, f: True)
        if args.yes
        else (lambda skill, f: ui.confirm(
            f"{skill}/{f} was modified locally. Remove anyway?", False, False
        ))
    )

    report = installer.uninstall(
        root.resolve(),
        m,
        purge=args.purge,
        confirm_modified=confirm_modified,
        credentials_path=_env_path(),
    )
    manifest.save(m, _manifest_path())

    ui.ok(f"Removed  : {report['removed']} files")
    if report["skipped"]:
        for s in report["skipped"]:
            ui.warn(f"Skipped (locally modified): {s['skill']}/{s['file']}")
    if report.get("purged"):
        ui.ok("Credentials file removed (--purge).")

    return 0


# --- parser ----------------------------------------------------------------

def _common_flags(p: argparse.ArgumentParser) -> None:
    """Flags shared by every subcommand (non-interactive operation, NFR5)."""
    p.add_argument("-y", "--yes", action="store_true", help="assume yes; run non-interactively")
    p.add_argument(
        "--engine", action="append", choices=ENGINES, default=None,
        help="target engine (repeatable); default = auto-detect",
    )
    p.add_argument("--scope", choices=SCOPES, default="project", help="install scope (default: project)")
    p.add_argument("--url", default=None, help="Konecty base URL")
    p.add_argument("--ref", default=DEFAULT_REF, help=f"git ref to install (default: {DEFAULT_REF})")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="konecty-skills",
        description="One-command installer for Konecty Agent Skills.",
    )
    parser.add_argument("--version", action="version", version=f"konecty-skills {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    handlers: dict[str, Callable[[argparse.Namespace], int]] = {
        "install": cmd_install,
        "configure": cmd_configure,
        "status": cmd_status,
        "update": cmd_update,
        "doctor": cmd_doctor,
        "uninstall": cmd_uninstall,
    }
    helps = {
        "install": "detect engines, copy skills, set up credentials, write manifest",
        "configure": "set up Konecty credentials only (~/.konecty/.env)",
        "status": "show installed skills, engines, and credential status",
        "update": "re-fetch skills with SHA-256 protection (keeps local edits)",
        "doctor": "validate installation and test the Konecty connection",
        "uninstall": "remove installed skills (credentials kept unless --purge)",
    }
    for name, handler in handlers.items():
        sp = sub.add_parser(name, help=helps[name])
        _common_flags(sp)
        if name == "status" or name == "doctor":
            sp.add_argument("--all", action="store_true", help="report every installation, not just the current dir")
        if name == "uninstall":
            sp.add_argument("--purge", action="store_true", help="also remove ~/.konecty credentials")
        sp.set_defaults(func=handler)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
