# External Integrations

## Konecty REST API

**Service:** Konecty low-code platform backend  
**Purpose:** Core platform — all user-data and metadata operations  
**Implementation:** `urllib.request` in each skill's Python script  
**Configuration:** `KONECTY_URL` in `~/.konecty/.env`  
**Authentication:** Bearer token (`KONECTY_TOKEN`) in `Authorization` header

### User-Level Endpoints

| Skill | Method | Endpoint | Purpose |
|---|---|---|---|
| konecty-modules | GET | `/rest/query/explorer/modules` | Discover available modules and fields |
| konecty-find | GET/POST | `/rest/data/:document/find` | Search/filter records |
| konecty-find | POST | `/rest/query/json` | Cross-module structured query |
| konecty-find | POST | `/rest/query/sql` | SQL-syntax query |
| konecty-create | POST | `/rest/data/:document` | Create new record |
| konecty-update | PUT | `/rest/data/:document` | Update record (requires `_updatedAt`) |
| konecty-delete | DELETE | `/rest/data/:document/:id` | Delete single record |
| konecty-upload | POST/GET/DELETE | `/rest/file/` | Upload, list, delete file attachments |

### Admin-Level Endpoints

| Skill | Method | Endpoint | Purpose |
|---|---|---|---|
| konecty-meta-read | GET | `/api/admin/meta/:type` | Read any MetaObject |
| konecty-meta-document | GET/POST/PUT/DELETE | `/api/admin/meta/document` | Document schema CRUD |
| konecty-meta-list | GET/POST/PUT/DELETE | `/api/admin/meta/list` | List meta CRUD |
| konecty-meta-view | GET/POST/PUT/DELETE | `/api/admin/meta/view` | Form view CRUD |
| konecty-meta-access | GET/POST/PUT/DELETE | `/api/admin/meta/access` | Access profile CRUD |
| konecty-meta-pivot | GET/POST/PUT/DELETE | `/api/admin/meta/pivot` | Pivot meta CRUD |
| konecty-meta-hook | GET/POST/PUT/DELETE | `/api/admin/meta/hook` | Hook code management |
| konecty-meta-hook | POST | `/api/admin/meta/hook/validate` | Hook code validation |
| konecty-meta-namespace | GET/PUT | `/api/admin/meta/namespace` | Tenant global config |
| konecty-meta-doctor | POST | `/api/admin/meta/doctor` | Metadata integrity check |
| konecty-meta-sync | GET/PUT | `/api/admin/meta/*` | Plan/apply repo↔DB sync |
| konecty-meta-remove | DELETE | `/api/admin/meta/*` | Full module metadata deletion |

### Authentication Endpoints

| Skill | Method | Endpoint | Purpose |
|---|---|---|---|
| konecty-session | GET | `/api/auth/login-options` | Check OTP availability |
| konecty-session | POST | `/api/auth/request-otp` | Send OTP (email or WhatsApp) |
| konecty-session | POST | `/api/auth/verify-otp` | Verify OTP, receive token |

## OTP Delivery

**Service:** Email or WhatsApp (configured per Konecty namespace)  
**Purpose:** Two-factor authentication delivery for `konecty-session`  
**Implementation:** Konecty backend handles delivery; skill only calls `/api/auth/request-otp`  
**Configuration:** Namespace-level setting (not in `.env`)

## Marketplace Publishing

### GitHub CLI (gh skill)
**Purpose:** Validate and publish skills against the agentskills.io spec  
**Implementation:** CLI tool (`gh skill publish`)  
**Authentication:** GitHub authentication (interactive `gh auth login`)  
**Key endpoints:** `--dry-run` for validation only, `--fix` for auto-repair

### skills.sh
**Purpose:** Telemetry-based discovery (skills appear organically when installed)  
**Implementation:** `npx @agentskill.sh/cli`  
**Authentication:** None required for publishing (public GitHub repo)  
**"Publishing":** Push a valid public repo; share `npx skills add owner/repo`

### OpenClaw (clawhub)
**Purpose:** Explicit skill marketplace with VirusTotal scanning  
**Implementation:** `clawhub skill publish ./skills/<name>`  
**Authentication:** Interactive `clawhub login`  
**Key flags:** `--slug`, `--version`, `--changelog`

### Hermes (NousResearch)
**Purpose:** Tap-based skill distribution (no central registry)  
**Implementation:** `hermes skills publish skills/<name> --to github --repo owner/repo`  
**Authentication:** GitHub authentication

## Security Scanning Services

### Snyk Agent Scan
**Purpose:** Detect prompt injection, credential leaks, malicious payloads in skills  
**Implementation:** `uvx snyk-agent-scan@latest`  
**Authentication:** `SNYK_TOKEN` env var (from `app.snyk.io/account`)  
**Scope:** Pre-publish only (manual)

### Socket
**Purpose:** Supply chain security for npm dependencies inside scripts  
**Implementation:** `socket scan create ./skills/<name>`, `socket ci`  
**Authentication:** Interactive `socket login`  
**Scope:** Pre-publish only (manual)

### Gen Agent Trust Hub
**Purpose:** Web-only trust audit (Safe / Low / High / Critical risk)  
**Implementation:** Web UI at `https://ai.gendigital.com/agent-trust-hub`  
**Authentication:** None (web form)

## Optional Integrations (Namespace-Configurable)

These are configured in the Konecty namespace via `konecty-meta-namespace` — not hardcoded in skills:

- **SMTP server** — email delivery for notifications
- **RabbitMQ** — message queue for background jobs
- **Webhook URLs** — global event hooks (onCreate, onUpdate, onDelete)
