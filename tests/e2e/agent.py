"""Pseudo-agent that drives the Konecty skills exactly as an AI agent would.

Two execution modes:

- :meth:`PseudoAgent.run` — imports the target script and calls its ``main()``
  **in-process**, after setting ``sys.argv`` and the credential env vars. Because
  the call happens inside the test process, ``coverage.py`` records every line of
  argparse + dispatch + the ``cmd_*`` handlers. This is the mode that drives the
  coverage gate. The skill scripts read credentials from ``KONECTY_URL`` /
  ``KONECTY_TOKEN`` (highest precedence) and parse ``sys.argv[1:]``.

- :meth:`PseudoAgent.smoke` — runs the script via ``subprocess`` (real CLI
  entrypoint). Proves the command works end-to-end as a process and is the right
  tool for clean-environment security checks (no credentials, isolated ``HOME``).

The scripts converge on a single HTTP call site (``urllib.request.urlopen``), so
a test can monkeypatch that one symbol to mock responses (used for konecty-meta,
whose ``/api/admin/meta/*`` API is not yet in a published image — see
``.specs/project/STATE.md`` D6–D8).
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

# Default credentials injected into in-process runs; set by conftest once the
# live stack is up. Mocked (meta) runs don't care about the values.
_DEFAULT_HOST = ""
_DEFAULT_TOKEN = ""


def set_default_creds(host: str, token: str) -> None:
    global _DEFAULT_HOST, _DEFAULT_TOKEN
    _DEFAULT_HOST, _DEFAULT_TOKEN = host, token


@dataclass
class Result:
    """Outcome of a skill invocation."""

    code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.code == 0


def script_path(skill: str, script: str) -> Path:
    """Absolute path to ``skills/<skill>/scripts/<script>.py``."""
    return SKILLS_DIR / skill / "scripts" / f"{script}.py"


class PseudoAgent:
    """Drives skill scripts in-process (coverage) or via subprocess (smoke)."""

    def __init__(self, host: str | None = None, token: str | None = None) -> None:
        self.host = host
        self.token = token
        self._modules: dict[tuple[str, str], object] = {}

    # ------------------------------------------------------------------ #
    # module loading
    # ------------------------------------------------------------------ #
    def _load(self, skill: str, script: str):
        """Import a script under a unique module name (so the byte-identical
        ``auth.py`` / ``modules.py`` copies in both skills don't collide and are
        tracked separately by coverage)."""
        key = (skill, script)
        if key in self._modules:
            return self._modules[key]
        path = script_path(skill, script)
        if not path.exists():
            raise FileNotFoundError(f"no such skill script: {path}")
        mod_name = f"e2e_{skill.replace('-', '_')}_{script}"
        spec = importlib.util.spec_from_file_location(mod_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
        self._modules[key] = module
        return module

    # ------------------------------------------------------------------ #
    # in-process run (coverage path)
    # ------------------------------------------------------------------ #
    def run(
        self,
        skill: str,
        script: str,
        argv: list[str],
        *,
        host: str | None = None,
        token: str | None = None,
    ) -> Result:
        """Call ``<script>.main()`` in-process with ``argv`` and credentials."""
        module = self._load(skill, script)
        eff_host = host if host is not None else (self.host or _DEFAULT_HOST)
        eff_token = token if token is not None else (self.token or _DEFAULT_TOKEN)

        prev_argv = sys.argv
        prev_env = {k: os.environ.get(k) for k in ("KONECTY_URL", "KONECTY_TOKEN")}
        os.environ["KONECTY_URL"] = eff_host
        os.environ["KONECTY_TOKEN"] = eff_token
        sys.argv = [f"{script}.py", *[str(a) for a in argv]]

        out, err = io.StringIO(), io.StringIO()
        code = 0
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    module.main()
                except SystemExit as exc:
                    code = _exit_code(exc, err)
        finally:
            sys.argv = prev_argv
            for k, v in prev_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return Result(code, out.getvalue(), err.getvalue())

    # ------------------------------------------------------------------ #
    # subprocess run (smoke / clean-env path)
    # ------------------------------------------------------------------ #
    def smoke(
        self,
        skill: str,
        script: str,
        argv: list[str],
        *,
        creds: bool = True,
        env: dict[str, str] | None = None,
        home: str | None = None,
        timeout: int = 60,
    ) -> Result:
        """Run the script as a real subprocess (the actual CLI entrypoint).

        ``creds=False`` strips ``KONECTY_*`` and points ``HOME`` at an (empty)
        directory so the credential fast-fail path can be exercised with a truly
        clean environment.
        """
        path = script_path(skill, script)
        proc_env = dict(os.environ)
        if env:
            proc_env.update(env)
        if creds:
            proc_env["KONECTY_URL"] = self.host or _DEFAULT_HOST
            proc_env["KONECTY_TOKEN"] = self.token or _DEFAULT_TOKEN
        else:
            proc_env.pop("KONECTY_URL", None)
            proc_env.pop("KONECTY_TOKEN", None)
            if home is not None:
                proc_env["HOME"] = home
        proc = subprocess.run(
            [sys.executable, str(path), *[str(a) for a in argv]],
            capture_output=True,
            text=True,
            env=proc_env,
            timeout=timeout,
        )
        return Result(proc.returncode, proc.stdout, proc.stderr)


def _exit_code(exc: SystemExit, err: io.StringIO) -> int:
    """Normalise a ``SystemExit`` to an int, echoing a string code to stderr.

    Scripts use ``sys.exit("message")`` for errors; Python would normally print
    that string to stderr and exit 1. We replicate that so the captured stderr
    carries the message and the numeric code is 1.
    """
    val = exc.code
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    err.write(str(val) + "\n")
    return 1
