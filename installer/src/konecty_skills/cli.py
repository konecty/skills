#!/usr/bin/env python3
"""konecty-skills CLI entry point.

Argparse dispatcher for the six lifecycle commands (MCP-first): ``install``
validates the company URL, registers the ``konecty``/``konecty-admin`` MCP
servers in Claude Code, and copies the four skills; ``configure`` handles the
interim admin token; ``doctor`` checks URL/well-known/audience/registration.
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

def _report_registration(result: dict, name: str) -> str:
    """Print the outcome of an mcp_config.register() call; return a status word."""
    from . import ui

    if not result["executed"]:
        ui.warn("claude CLI not found — run these commands manually:")
        for cmd in result["commands"]:
            ui.step(cmd)
        return "printed"
    if result["ok"]:
        ui.ok(f"MCP server '{name}' registered")
        return "registered"
    ui.warn(f"Failed to register MCP server '{name}': {result['detail']}")
    return "failed"


def cmd_install(args: argparse.Namespace) -> int:
    from . import banner, credentials, engines, fetcher, installer, manifest, mcp_config, ui

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

    # 4. Company URL → validate → probe (MCPF-20; nothing half-configured).
    raw_url: str | None = args.url
    if not raw_url and not assume_yes:
        raw_url = ui.ask("Konecty company URL (https://...)")

    mcp_url: str | None = None
    if raw_url:
        try:
            mcp_url = mcp_config.normalize_url(raw_url)
        except mcp_config.UrlValidationError as exc:
            ui.err(str(exc))
            return 1
    else:
        ui.warn("No URL provided; skipping MCP registration.")

    mcp_status = "skipped"
    if mcp_url:
        probe = mcp_config.probe_well_known(mcp_url)
        if probe["status"] == "no_mcp":
            ui.err(
                "This Konecty does not expose MCP — ask for a server upgrade, "
                "or pin the last script-based release of this package."
            )
            return 1
        if probe["status"] == "unreachable":
            ui.err(f"Konecty URL is unreachable: {probe['detail']}")
            return 1
        if probe["status"] in ("mismatch", "bad_json"):
            ui.warn(probe["detail"])
        if probe.get("issuer_warning"):
            ui.warn(probe["issuer_warning"])

        # 5. Register the user MCP server (replace, never duplicate).
        result = mcp_config.register(
            mcp_config.USER_SERVER, mcp_config.build_add_user(mcp_url)
        )
        mcp_status = _report_registration(result, mcp_config.USER_SERVER)

        # 6. Optional admin path (interim: OTP → Bearer authTokenId header).
        if not assume_yes and ui.confirm(
            "Set up admin MCP access (requires a Konecty admin user)?", False, False
        ):
            identifier = ui.ask("Admin email or phone (E.164)")
            admin_token = credentials.otp_login(mcp_url, identifier)
            if admin_token:
                credentials.write_env(mcp_url, admin_token, _env_path())
                admin_result = mcp_config.register(
                    mcp_config.ADMIN_SERVER,
                    mcp_config.build_add_admin_token(mcp_url, admin_token),
                )
                _report_registration(admin_result, mcp_config.ADMIN_SERVER)
            else:
                ui.warn("Admin OTP login failed; skipping konecty-admin registration.")

    # 7. Fetch skills.
    try:
        fetch = fetcher.fetch_skills(ref=args.ref)
    except fetcher.FetchError as exc:
        ui.err(f"Failed to fetch skills: {exc}")
        return 1

    # 8. Load manifest.
    m = manifest.load(_manifest_path())

    # 9. Install skills.
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

    # 10. Merge entry blocks.
    for engine in chosen:
        ef = engines.entry_file(engine, root)
        if ef is not None:
            installer.merge_entry_block(ef)

    # 11. Save manifest.
    manifest.save(m, _manifest_path())

    # 12. Print summary.
    ui.ok(f"Engines  : {', '.join(report['engines'])}")
    ui.ok(f"Skills   : {', '.join(report['skills'])}")
    ui.ok(f"Dests    : {', '.join(report['dests'])}")
    ui.ok(f"Files    : {report['files_written']} written")
    ui.ok(f"MCP      : {mcp_status}")

    return 0


def _root(args: argparse.Namespace) -> Path:
    """Resolve the installation root from args (mirrors cmd_install logic)."""
    return Path.cwd() if args.scope == "project" else Path.home()


def _select_installations(args: argparse.Namespace, installs: dict) -> list[tuple[str, dict]]:
    """Installations that status/doctor report on: all, or just the current root.

    Prints a hint and returns an empty list when the current root has none.
    """
    from . import ui

    if args.all:
        return list(installs.items())
    root_key = str(_root(args).resolve())
    if root_key in installs:
        return [(root_key, installs[root_key])]
    ui.step(f"No installation found for {root_key}. Use --all to list all.")
    return []


def _probe_konecty(url: str, token: str) -> tuple[bool, str]:
    """Probe the Konecty server with a GET to /api/auth/login-options.

    Returns (reachable, detail).  All exceptions are caught so this is always
    safe to call — callers just inspect the boolean.
    """
    import urllib.parse
    import urllib.request
    import urllib.error

    from . import mcp_config

    probe_url = f"{url.rstrip('/')}/api/auth/login-options"

    # B310: guard scheme before calling urlopen.
    scheme = urllib.parse.urlparse(probe_url).scheme.lower()
    if scheme not in ("http", "https"):
        return False, f"unsupported URL scheme: {scheme!r}"

    try:
        req = urllib.request.Request(
            probe_url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": mcp_config.USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310  # nosec B310 - scheme guarded above
            return True, f"HTTP {resp.status}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def cmd_configure(args: argparse.Namespace) -> int:
    """Interim admin-token setup: URL → OTP → ~/.konecty/.env + konecty-admin entry."""
    from . import credentials, mcp_config, ui

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

    # Interactive: offer the admin OTP login (interim konecty-admin auth).
    run_otp_now = ui.confirm("Run the admin OTP login now?", True, False)
    if run_otp_now:
        identifier = ui.ask("Admin email or phone (E.164)")
        token = credentials.otp_login(url, identifier)
        if token:
            credentials.write_env(url, token, _env_path())
            result = mcp_config.register(
                mcp_config.ADMIN_SERVER,
                mcp_config.build_add_admin_token(url, token),
            )
            _report_registration(result, mcp_config.ADMIN_SERVER)
        else:
            ui.warn("OTP login failed; writing URL only.")
            credentials.write_url_only(url, _env_path())
    else:
        credentials.write_url_only(url, _env_path())

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from . import credentials, manifest, mcp_config, ui

    m = manifest.load(_manifest_path())
    targets = _select_installations(args, m.get("installations", {}))
    if not targets and not args.all:
        return 0

    env = credentials.current_env(_env_path())
    url_status = "set" if env["url"] else "missing"
    token_status = "set" if env["token"] else "missing"

    # MCP registration status (user-scope, shared by every installation).
    if mcp_config.cli_available():
        servers = mcp_config.list_servers()
        registered = [
            n for n in (mcp_config.USER_SERVER, mcp_config.ADMIN_SERVER) if n in servers
        ]
        mcp_status = ", ".join(registered) if registered else "(none registered)"
    else:
        mcp_status = "claude CLI not found"

    for inst_root, installation in targets:
        ui.step(f"Root    : {inst_root}")
        ui.step(f"Scope   : {installation.get('scope', '?')}")
        ui.step(f"Engines : {', '.join(installation.get('engines', []))}")
        source = installation.get("source", {})
        ui.step(f"Source  : ref={source.get('ref', '?')} commit={source.get('commit', '?')}")
        skill_keys = list(installation.get("skills", {}).keys())
        ui.step(f"Skills  : {', '.join(skill_keys) if skill_keys else '(none)'}")
        ui.step(f"MCP     : {mcp_status}")
        ui.step(f"Creds   : url={url_status}, token={token_status} (interim admin token store)")

    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    from . import credentials, manifest, mcp_config, ui

    m = manifest.load(_manifest_path())
    targets = _select_installations(args, m.get("installations", {}))
    if not targets and not args.all:
        return 0

    for inst_root, installation in targets:
        ui.step(f"Checking {inst_root} ...")
        conflicts = manifest.diff(installation, Path(inst_root))
        if conflicts:
            for c in conflicts:
                ui.warn(f"  {c['skill']}/{c['file']}: {c['reason']}")
        else:
            ui.ok("All files match manifest")

    env = credentials.current_env(_env_path())

    # --- Check 1: URL reachable + well-known + audience (MCPF-22, Risk #1) ---
    base: str | None = None
    if env["url"]:
        try:
            base = mcp_config.normalize_url(env["url"])
        except mcp_config.UrlValidationError as exc:
            ui.warn(f"Configured Konecty URL is invalid: {exc}")
    else:
        ui.warn(
            "No Konecty URL configured (~/.konecty/.env) — "
            "run install or the konecty-setup skill."
        )

    if base:
        probe = mcp_config.probe_well_known(base)
        if probe["status"] == "ok":
            ui.ok("MCP well-known endpoint: OK")
        elif probe["status"] == "no_mcp":
            ui.warn(
                "MCP well-known endpoint returned 404 — this Konecty does not "
                "expose MCP; upgrade the server or pin the last script-based "
                "release of this package."
            )
        elif probe["status"] == "mismatch":
            ui.warn(
                f"Audience mismatch: well-known resource is {probe['resource']!r} "
                f"but the MCP URL is {base + '/mcp'!r} — align "
                "PLATFORM_MCP_RESOURCE_URL on the server."
            )
        elif probe["status"] == "bad_json":
            ui.warn(f"MCP well-known endpoint returned invalid JSON: {probe['detail']}")
        else:
            ui.warn(
                f"Konecty URL unreachable: {probe['detail']} — "
                "check the URL (and VPN, if applicable)."
            )
        if probe.get("issuer_warning"):
            ui.warn(f"OAuth issuer problem: {probe['issuer_warning']}")

    # --- Check 2: MCP servers registered in Claude Code (MCPF-22) -------------
    if mcp_config.cli_available():
        servers = mcp_config.list_servers()
        if mcp_config.USER_SERVER in servers:
            ui.ok(f"MCP server '{mcp_config.USER_SERVER}' registered")
        else:
            ui.warn(
                f"MCP server '{mcp_config.USER_SERVER}' not registered — "
                "re-run install or ask the konecty-setup skill to register it."
            )
        if mcp_config.ADMIN_SERVER in servers:
            ui.ok(f"MCP server '{mcp_config.ADMIN_SERVER}' registered")
        else:
            ui.step(
                f"MCP server '{mcp_config.ADMIN_SERVER}' not registered "
                "(optional — only needed for metadata administration)."
            )
    else:
        ui.warn(
            "claude CLI not found — cannot verify MCP registration; "
            "run the claude mcp commands manually (see konecty-setup)."
        )

    # --- Check 3: interim admin token validity (when configured) --------------
    if env["url"] and env["token"]:
        reachable, detail = _probe_konecty(env["url"], env["token"])
        if reachable:
            ui.ok(f"Admin token check: OK ({detail})")
        else:
            ui.warn(
                f"Admin token check failed ({detail}) — re-run the OTP login "
                "(konecty-setup 'fix auth') and re-register the "
                "konecty-admin entry."
            )

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
    from . import installer, manifest, mcp_config, ui

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

    # --purge also removes the user-scope MCP entries created by install.
    if args.purge:
        if mcp_config.cli_available():
            servers = mcp_config.list_servers()
            for name in (mcp_config.USER_SERVER, mcp_config.ADMIN_SERVER):
                if name in servers:
                    ok, _detail = mcp_config.run_command(mcp_config.build_remove(name))
                    if ok:
                        ui.ok(f"MCP server '{name}' removed")
                    else:
                        ui.warn(f"Failed to remove MCP server '{name}'")
        else:
            ui.warn("claude CLI not found — remove MCP entries manually:")
            for name in (mcp_config.USER_SERVER, mcp_config.ADMIN_SERVER):
                ui.step(mcp_config.format_command(mcp_config.build_remove(name)))

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
        "install": "validate the company URL, register the Konecty MCP servers, copy the skills",
        "configure": "interim admin token only: OTP login + konecty-admin MCP entry",
        "status": "show installed skills, MCP registration, and admin-token status",
        "update": "re-fetch skills with SHA-256 protection (keeps local edits)",
        "doctor": "check URL, MCP well-known/audience, MCP registration, and admin token",
        "uninstall": "remove installed skills (--purge also removes credentials + MCP entries)",
    }
    for name, handler in handlers.items():
        sp = sub.add_parser(name, help=helps[name])
        _common_flags(sp)
        if name == "status" or name == "doctor":
            sp.add_argument("--all", action="store_true", help="report every installation, not just the current dir")
        if name == "uninstall":
            sp.add_argument(
                "--purge", action="store_true",
                help="also remove ~/.konecty credentials and the konecty MCP entries",
            )
        sp.set_defaults(func=handler)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
