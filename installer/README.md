# konecty-skills

One-command installer for the [Konecty](https://github.com/konecty/skills) Agent Skills
(`konecty-data`, `konecty-meta`). Detects your AI engine, copies the skills into the right
place, and sets up your Konecty credentials — without ever deleting or modifying your
existing files.

```bash
uvx --from git+https://github.com/konecty/skills konecty-skills install
```

## Commands

| Command | What it does |
|---------|--------------|
| `install` | Detect engines → select skills → download → copy → set up credentials (OTP) → write manifest |
| `configure` | Credentials only: write `~/.konecty/.env` (URL + OTP token) |
| `status` | What is installed, in which engines, and whether credentials are present |
| `update` | Re-fetch skills with SHA-256 protection (never overwrites local edits) |
| `doctor` | Validate installed files vs manifest and test the Konecty connection |
| `uninstall` | Remove the installed skills (credentials left intact unless `--purge`) |

Stdlib only — no third-party runtime dependencies.
