"""Streaming PASS/FAIL/SKIP reporter for the e2e harness.

Mirrors the company-brain ``e2e_check.py`` pattern: a single ``record()`` sink
that both prints a line immediately (streaming feedback) and accumulates a list
for a final summary. Cascading SKIP is supported by recording a step as SKIP
with a "<prior> failed" detail when a precondition did not hold.

This module is import-safe and has no third-party dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

_ICON = {PASS: "✅", FAIL: "❌", SKIP: "⏭️ "}


@dataclass
class Reporter:
    """Accumulates step results and prints them as they are recorded."""

    results: list[tuple[str, str, str]] = field(default_factory=list)
    echo: bool = True

    def record(self, step: str, status: str, detail: str = "") -> None:
        self.results.append((step, status, detail))
        if self.echo:
            tail = f" — {detail}" if detail else ""
            print(f"{_ICON.get(status, '  ')} {status}  {step}{tail}")

    # convenience wrappers ------------------------------------------------
    def ok(self, step: str, detail: str = "") -> None:
        self.record(step, PASS, detail)

    def fail(self, step: str, detail: str = "") -> None:
        self.record(step, FAIL, detail)

    def skip(self, step: str, detail: str = "") -> None:
        self.record(step, SKIP, detail)

    # summary -------------------------------------------------------------
    @property
    def passed(self) -> int:
        return sum(1 for _, s, _ in self.results if s == PASS)

    @property
    def failed(self) -> int:
        return sum(1 for _, s, _ in self.results if s == FAIL)

    @property
    def skipped(self) -> int:
        return sum(1 for _, s, _ in self.results if s == SKIP)

    def summary(self) -> str:
        return f"{self.passed} passed, {self.failed} failed, {self.skipped} skipped"

    def exit_code(self) -> int:
        """0 when no FAIL was recorded, 1 otherwise (SKIP never fails)."""
        return 1 if self.failed else 0
