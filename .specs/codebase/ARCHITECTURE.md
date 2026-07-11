# Architecture

**Pattern:** Domain-segmented skill monorepo — each skill is an isolated, composable unit with a single responsibility.

## High-Level Structure

```
Agent (Claude Code / Cursor)
        │
        ▼
   SKILL.md         ← loaded by agent harness (instructions + description triggers)
        │
        ▼
  Python script     ← invoked by agent via bash (stdlib only)
        │
        ▼
  Konecty REST API  ← HTTP requests via urllib
        │
        ▼
  ~/.konecty/.env   ← shared credential store (written by konecty-session)
```

## Skill Dependency Graph

```
konecty-session (OTP auth — must run first)
    │
    ├─→ konecty-modules      (discover modules & fields)
    ├─→ konecty-find         (search / filter / SQL)
    ├─→ konecty-create       (create records)
    ├─→ konecty-update       (update records, _updatedAt locking)
    ├─→ konecty-delete       (delete with preview + --confirm)
    ├─→ konecty-upload       (file attach / list / delete)
    │
    └─→ konecty-meta-* (admin tier — requires KONECTY_TOKEN with admin rights)
            ├─→ konecty-meta-read       (read-only for all meta types)
            ├─→ konecty-meta-document   (document schema CRUD)
            ├─→ konecty-meta-list       (list meta CRUD)
            ├─→ konecty-meta-view       (form view CRUD)
            ├─→ konecty-meta-access     (access profile CRUD)
            ├─→ konecty-meta-pivot      (pivot meta CRUD)
            ├─→ konecty-meta-hook       (hook code generation)
            ├─→ konecty-meta-namespace  (tenant config)
            ├─→ konecty-meta-doctor     (integrity validation)
            ├─→ konecty-meta-sync       (plan/apply IaC)
            └─→ konecty-meta-remove     (full module deletion)
```

## Identified Patterns

### Credential Bootstrap (Shared Store)
**Location:** All `scripts/*.py` files  
**Purpose:** Every skill reads shared credentials, avoiding per-skill config  
**Implementation:** Load from env vars → `~/.konecty/.env` → `~/.konecty/credentials` (ini)  
**Example:** `skills/konecty-modules/scripts/modules.py:_load_credentials()`

### Subcommand CLI (argparse)
**Location:** All `scripts/*.py` files  
**Purpose:** Expose multiple operations from a single script entry point  
**Implementation:** `argparse` with subparsers; each subcommand maps to a function  
**Example:** `konecty-find/scripts/find.py` → subcommands: `find`, `query`, `sql`

### Fetch-First Update (Optimistic Locking)
**Location:** `skills/konecty-update/`  
**Purpose:** Prevent overwriting concurrent changes via `_updatedAt` timestamp  
**Implementation:** Fetch record → extract `_updatedAt` → include in PUT payload  
**Example:** `skills/konecty-update/scripts/update.py`

### Preview-Then-Act Safety Guard
**Location:** `skills/konecty-delete/`, `skills/konecty-meta-remove/`  
**Purpose:** Prevent accidental destructive operations  
**Implementation:** Show full record/impact preview; require explicit `--confirm` flag  
**Example:** `skills/konecty-delete/SKILL.md` — "NEVER skip the preview step"

### IaC Plan/Apply (Metadata Sync)
**Location:** `skills/konecty-meta-sync/`  
**Purpose:** Terraform-style declarative metadata management (repo ↔ database)  
**Implementation:** `plan` computes diff, `apply` executes changes  
**Example:** `skills/konecty-meta-sync/scripts/sync.py` → subcommands: `plan`, `apply`

### Reference Documentation Split
**Location:** `skills/<name>/references/*.md`  
**Purpose:** Keep SKILL.md under ~300 lines; move dense reference material out  
**Implementation:** SKILL.md links to `references/` files; agent loads on-demand  
**Example:** `skills/konecty-find/references/filter-operators.md`

## Data Flow

### Authentication Flow
```
User → konecty-session
     → POST /api/auth/login-options (check OTP availability)
     → POST /api/auth/request-otp (email/WhatsApp OTP)
     → User enters OTP code
     → POST /api/auth/verify-otp (returns token)
     → Write KONECTY_URL + KONECTY_TOKEN to ~/.konecty/.env
```

### Record CRUD Flow
```
User → konecty-find/create/update/delete
     → Read ~/.konecty/.env (credentials)
     → GET/POST/PUT/DELETE /rest/data/:document
     → Parse JSON response (check success/errors)
     → Display results / confirm destructive action
```

### Metadata Management Flow
```
User → konecty-meta-* skill
     → Read ~/.konecty/.env (admin token required)
     → GET/POST/PUT/DELETE /api/admin/meta/:type
     → OR: konecty-meta-sync plan/apply (repo file ↔ API diff)
     → Parse MetaObjects collection response
```

## Code Organization

**Approach:** Feature-based (one folder per skill, self-contained)

**Module boundaries:**
- Each skill folder is fully self-contained — SKILL.md + scripts + references
- No shared utilities between skills (see CONCERNS.md — credential loading is duplicated)
- External skills in `.agents/skills/` are installed via CLI and tracked in `skills-lock.json`

**API tier separation:**
- User-level skills: `konecty-{modules,find,create,update,delete,upload}` → `/rest/`
- Admin-level skills: `konecty-meta-*` → `/api/admin/meta/`
- Auth: `konecty-session` → `/api/auth/`
