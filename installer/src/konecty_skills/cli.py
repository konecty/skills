#!/usr/bin/env python3
"""konecty-skills CLI entry point.

Argparse dispatcher for the six lifecycle commands. Command bodies are wired in
later tasks (T10–T13); for now each handler is a stub that returns 0 so the
package builds and ``konecty-skills --help`` works.
"""
from __future__ import annotations

import argparse
import sys
from typing import Callable, Optional, Sequence

from . import __version__

DEFAULT_REF = "main"
ENGINES = ("claude", "agents", "cursor")
SCOPES = ("project", "global")


# --- command stubs (replaced by real wiring in T10–T13) --------------------

def _stub(name: str) -> int:
    print(f"konecty-skills: '{name}' is not implemented yet.", file=sys.stderr)
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    return _stub("install")


def cmd_configure(args: argparse.Namespace) -> int:
    return _stub("configure")


def cmd_status(args: argparse.Namespace) -> int:
    return _stub("status")


def cmd_update(args: argparse.Namespace) -> int:
    return _stub("update")


def cmd_doctor(args: argparse.Namespace) -> int:
    return _stub("doctor")


def cmd_uninstall(args: argparse.Namespace) -> int:
    return _stub("uninstall")


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
