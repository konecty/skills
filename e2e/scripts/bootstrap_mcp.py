#!/usr/bin/env python3
"""Bootstrap the MCP namespace flags on the e2e Konecty stack.

After first boot Konecty seeds its metadata (including the Namespace document
in ``MetaObjects``) and creates the first ``admin`` user with a random role id.
MCP access is deny-by-default (``mcpRoleIds`` empty ⇒ 403 ``mcp_access_denied``),
so the harness must enable the flags before any suite runs:

- ``mcpUserEnabled: true``    — user MCP at ``/mcp``
- ``mcpAdminEnabled: true``   — admin MCP at ``/admin-mcp``
- ``mcpRoleIds: [<admin role _id>]`` — read live from the seeded admin user
- ``mcpUserWriteEnabled: true`` — write tools allowed (suites toggle it off in
  a dedicated read-only-mode case and restore it)

The update goes straight into mongo via ``docker exec <mongo> mongosh``;
Konecty watches ``MetaObjects`` with a change stream and rebuilds references
(~1s debounce), so no restart is needed.

Usage::

    python e2e/scripts/bootstrap_mcp.py                 # defaults
    python e2e/scripts/bootstrap_mcp.py --db e2e --container konecty-e2e-mongodb
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

_JS = r"""
const admin = db.getCollection('users').findOne({ username: 'admin' });
if (!admin || !admin.role || !admin.role._id) {
    print(JSON.stringify({ error: 'admin user or role not found' }));
} else {
    const res = db.getCollection('MetaObjects').updateOne(
        { type: 'namespace' },
        { $set: {
            mcpUserEnabled: true,
            mcpAdminEnabled: true,
            mcpRoleIds: [admin.role._id],
            mcpUserWriteEnabled: true,
        } }
    );
    const ns = db.getCollection('MetaObjects').findOne(
        { type: 'namespace' },
        { mcpUserEnabled: 1, mcpAdminEnabled: 1, mcpRoleIds: 1, mcpUserWriteEnabled: 1 }
    );
    print(JSON.stringify({ matched: res.matchedCount, adminRoleId: admin.role._id, namespace: ns }));
}
"""


def run_mongosh(container: str, db: str, js: str) -> dict:
    result = subprocess.run(
        ["docker", "exec", container, "mongosh", db, "--quiet", "--eval", js],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.exit(f"mongosh failed: {result.stderr.strip() or result.stdout.strip()}")
    # last JSON line is ours (mongosh may print connection noise first)
    for line in reversed(result.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    sys.exit(f"no JSON output from mongosh: {result.stdout!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="konecty-e2e-mongodb")
    parser.add_argument("--db", default="e2e")
    parser.add_argument("--retries", type=int, default=30, help="retries waiting for the seeded admin user")
    args = parser.parse_args()

    payload: dict = {}
    for attempt in range(args.retries):
        payload = run_mongosh(args.container, args.db, _JS)
        if "error" not in payload:
            break
        time.sleep(2)
    if "error" in payload:
        sys.exit(f"bootstrap failed after {args.retries} retries: {payload['error']}")

    if payload.get("matched") != 1:
        sys.exit(f"namespace document not found in MetaObjects: {payload}")

    ns = payload["namespace"]
    flags = {k: ns.get(k) for k in ("mcpUserEnabled", "mcpAdminEnabled", "mcpRoleIds", "mcpUserWriteEnabled")}
    print(f"MCP namespace flags set: {json.dumps(flags)}")
    # give the MetaObjects change-stream debounce (~1s) time to rebuild
    time.sleep(3)


if __name__ == "__main__":
    main()
