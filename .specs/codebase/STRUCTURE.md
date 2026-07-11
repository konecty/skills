# Project Structure

**Root:** `/Users/silveira/dev/konecty/KonectySkills`

## Directory Tree

```
KonectySkills/
├── skills/                    # 18 production Konecty skills
│   ├── konecty-session/
│   ├── konecty-modules/
│   ├── konecty-find/
│   ├── konecty-create/
│   ├── konecty-update/
│   ├── konecty-delete/
│   ├── konecty-upload/
│   ├── konecty-meta-read/
│   ├── konecty-meta-document/
│   ├── konecty-meta-list/
│   ├── konecty-meta-view/
│   ├── konecty-meta-access/
│   ├── konecty-meta-pivot/
│   ├── konecty-meta-hook/
│   ├── konecty-meta-namespace/
│   ├── konecty-meta-doctor/
│   ├── konecty-meta-sync/
│   └── konecty-meta-remove/
├── .agents/skills/            # External skills installed via CLI
│   ├── skill-creator/
│   └── tlc-spec-driven/
├── template/
│   └── SKILL.md               # Minimal skill template
├── spec/
│   └── README.md              # Links to agentskills.io spec
├── docs/
│   ├── README.md              # Docs index
│   ├── development.md         # Contribution guide
│   ├── adr/                   # Architecture Decision Records (4)
│   └── changelog/             # Per-change entries (13) + README index
├── .specs/                    # SDD specs (created by tlc-spec-driven)
│   ├── project/               # Vision, roadmap, state
│   └── codebase/              # Brownfield analysis (this directory)
├── .claude/                   # Claude Code harness config
├── skills-lock.json           # External skills version lock
├── AGENTS.md / CLAUDE.md      # AI coding guidance
├── README.md                  # Public overview
└── .env.example               # Credential template
```

## Per-Skill Structure

Each production skill follows this layout:

```
skills/<skill-name>/
├── SKILL.md              # Main definition (frontmatter + instructions)
├── scripts/
│   └── <entrypoint>.py   # CLI script (stdlib-only)
└── references/
    ├── <topic>.md        # Reference docs (operators, schemas, patterns)
    └── ...
```

Exceptions:
- `konecty-session`: has `reference.md` at top-level (not in `references/`)
- Simple skills: may not have `references/` folder if no reference material needed

## Module Organization

### konecty-session
**Purpose:** Auth bootstrap — OTP login, writes shared credentials  
**Location:** `skills/konecty-session/`  
**Key files:** `SKILL.md`, `scripts/login.py`, `reference.md`

### konecty-* (CRUD)
**Purpose:** Record operations on Konecty modules  
**Location:** `skills/konecty-{modules,find,create,update,delete,upload}/`  
**Key files:** `SKILL.md`, `scripts/<name>.py`, `references/`

### konecty-meta-* (Admin)
**Purpose:** Metadata management (document schema, lists, views, access, hooks, sync)  
**Location:** `skills/konecty-meta-{read,document,list,view,access,pivot,hook,namespace,doctor,sync,remove}/`  
**Key files:** `SKILL.md`, `scripts/<name>.py`, `references/`

### External Skills
**Purpose:** Development workflow tooling  
**Location:** `.agents/skills/`  
**Key files:** `skill-creator/SKILL.md`, `tlc-spec-driven/SKILL.md`

## Where Things Live

**Authentication:**
- Auth logic: `skills/konecty-session/scripts/login.py`
- Credential store (runtime): `~/.konecty/.env`, `~/.konecty/credentials`
- Credential template: `.env.example`

**Business Logic:**
- Per-skill Python scripts: `skills/<name>/scripts/<name>.py`
- Shared credential loading: duplicated in each script (see CONCERNS.md)

**Documentation:**
- Architecture decisions: `docs/adr/`
- Change history: `docs/changelog/`
- Reference material: `skills/<name>/references/`
- AI agent guidance: `AGENTS.md`, `CLAUDE.md`

**Configuration:**
- External skill versions: `skills-lock.json`
- Claude Code harness: `.claude/settings.json`

## Special Directories

**.agents/skills/:**
**Purpose:** External skills installed via CLI (not authored in this repo)  
**Examples:** `skill-creator/SKILL.md`, `tlc-spec-driven/SKILL.md`

**.specs/:**
**Purpose:** SDD specs — project vision, codebase analysis, feature specs  
**Examples:** `codebase/STACK.md`, `project/PROJECT.md` (to be created)

**docs/adr/:**
**Purpose:** Architecture Decision Records  
**Examples:** `0001-formato-agent-skills.md`, `0004-konecty-meta-skills.md`

**template/:**
**Purpose:** Minimal SKILL.md scaffold for new skills  
**Examples:** `SKILL.md`
