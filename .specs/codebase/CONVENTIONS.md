# Code Conventions

## Naming Conventions

**Skill folders:**  
`konecty-<function>` — lowercase, hyphens, unique  
Examples: `konecty-session`, `konecty-meta-hook`, `konecty-meta-sync`

**Python scripts:**  
Named after the skill's primary noun (not the full skill name)  
Examples: `login.py`, `modules.py`, `find.py`, `create.py`, `sync.py`

**SKILL.md frontmatter name:**  
Matches the folder name exactly  
Examples: `name: konecty-find`, `name: konecty-meta-document`

**Reference files:**  
Lowercase, hyphens, topic-named  
Examples: `filter-operators.md`, `hook-contracts.md`, `meta-schemas.md`, `field-types.md`

**Python functions:**  
`_snake_case` for internal helpers (prefixed `_` for private)  
Examples: `_load_credentials()`, `_request()`, `_parse_api_error()`  
Public entrypoints: `cmd_list()`, `cmd_find()`, `cmd_create()`

**CLI arguments:**  
`--kebab-case` for flags  
Examples: `--format`, `--limit`, `--confirm`, `--dry-run`

## SKILL.md Structure

Every production skill follows this template:

```markdown
---
name: konecty-<function>
description: <what> + Use when ... + Do NOT use for ...
---

# Skill Title

[1-3 sentence intro]

## Prerequisites
- konecty-session (active token)
- [Other dependencies]

## [API Endpoints / Hook Types / Subcommands]
[Table or bulleted list]

## Workflow
### Step N — [Action]
[Instructions + bash example]

## Examples
[Real trigger phrases + bash code]

## Key Concepts / Guards / Rules
[Bulleted constraints]

## Script Reference
[Link to scripts + what each subcommand does]
```

## Description Field Format (Trigger Engineering)

All skill descriptions follow a three-part pattern:

1. **What it does** — active verb + endpoint/operation  
2. **Use when** — exact trigger phrases, includes Portuguese equivalents for Konecty skills  
3. **Do NOT use for** — negative triggers to prevent overlap

Example (konecty-delete):
> "Deletes a single record in any Konecty module via DELETE /rest/data/:document. Enforces a mandatory safety workflow: preview the record first, then delete one at a time with an explicit --confirm flag. Use when the user wants to delete, remove, or erase a record in Konecty. NEVER delete multiple records in a single operation. NEVER skip the preview step. Requires an active konecty-session."

Keep under 1,024 characters. No XML angle brackets.

## Python Script Structure

```python
#!/usr/bin/env python3
"""Module-level docstring: purpose + API endpoint used."""

from __future__ import annotations
import argparse, json, os, sys, urllib.request, urllib.error

# Constants
ENV_FILE = os.path.expanduser("~/.konecty/.env")
CREDENTIALS_FILE = os.path.expanduser("~/.konecty/credentials")


def _load_credentials() -> tuple[str, str]:
    """Load KONECTY_URL and KONECTY_TOKEN from env/file."""
    ...


def _request(host: str, token: str, path: str, ...) -> dict:
    """HTTP helper — raises SystemExit on error."""
    ...


def cmd_<subcommand>(args: argparse.Namespace) -> None:
    url, token = _load_credentials()
    ...


def main() -> None:
    parser = argparse.ArgumentParser(description="...")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    sub = subparsers.add_parser("<subcommand>")
    sub.add_argument("--flag")
    
    args = parser.parse_args()
    if args.command == "<subcommand>":
        cmd_<subcommand>(args)


if __name__ == "__main__":
    main()
```

## Credential Loading Order

All scripts follow this exact order (no exceptions):

1. `KONECTY_URL` / `KONECTY_TOKEN` environment variables
2. `~/.konecty/.env` (key=value format, no quotes)
3. `~/.konecty/credentials` (ini `[default]` section: `host`, `authId`)

Fail fast with `raise SystemExit("message")` if credentials not found.

## Error Handling

**User-facing errors:**
```python
raise SystemExit("Human-readable message describing the problem")
```

**API errors (check response):**
```python
result = _request(...)
if not result.get("success"):
    errors = result.get("errors") or [{"message": result.get("message", "Unknown")}]
    raise SystemExit(errors[0]["message"])
```

**Network errors:**
```python
try:
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)
except urllib.error.HTTPError as e:
    body = json.loads(e.read())
    raise SystemExit(body.get("message", str(e)))
```

## Output Format

- **Data output:** stdout (parseable JSON or table)
- **Counts/metadata:** stderr (human-readable, not parseable)
- **Errors:** `SystemExit` (non-zero exit code, message to stderr)
- **Dry-run mode:** prefix output lines with `[DRY RUN]`

## Comments and Documentation

Comments are rare — used only for non-obvious constraints or workarounds.  
Reference material goes in `references/*.md`, not inline in scripts.  
Docstrings at module level only; no method-level docstrings in production skills.

## Changelog Discipline

Any structural change (new skill, template update, convention change) requires:
1. `docs/changelog/YYYY-MM-DD_<slug>.md` — new entry
2. `docs/changelog/README.md` — new row in index table

Changelog entries are written in Portuguese.  
Editing a SKILL.md's instruction content alone does NOT require a changelog entry.  
Architectural decisions go in `docs/adr/####-title.md` (format: `#### Accepted/Rejected/Deprecated`).
