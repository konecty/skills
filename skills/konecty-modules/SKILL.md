---
name: konecty-modules
description: Lists Konecty modules the current session has read access to, and retrieves fields and types for a specific module. Use when the user asks what modules or documents are available in Konecty, wants to know the fields/types of a module, needs to find the internal name of a module (e.g. "contatos", "clientes", "Oportunidade"), or wants to understand what data is accessible. Requires an active session from the konecty-session skill (KONECTY_URL and KONECTY_TOKEN in ~/.konecty/.env).
---

# Konecty Modules

Lists accessible Konecty modules and their fields/types for the current session.

## Prerequisites

Requires credentials from **konecty-session**: `KONECTY_URL` and `KONECTY_TOKEN` in `~/.konecty/.env`.
If not present or expired, ask the user to run `konecty-session` first.

## API

All requests require `Authorization: <KONECTY_TOKEN>` header.

| Endpoint | Description |
|----------|-------------|
| `GET /rest/query/explorer/modules?lang=pt_BR` | All modules accessible to the current user, with fields and types |

**Module object** (`lang` controls field/module labels):
```json
{
  "document": "Contact",
  "label": "Contato",
  "fields": [
    { "name": "name", "type": "text", "label": "Nome" },
    { "name": "status", "type": "picklist", "label": "Status", "options": { "active": "Ativo" } },
    { "name": "queue", "type": "lookup", "label": "Fila", "document": "Queue", "descriptionFields": ["name"] }
  ],
  "reverseLookups": [
    { "document": "Activity", "lookup": "contact", "label": "Atividade" }
  ]
}
```

**Field types:** `text`, `number`, `boolean`, `date`, `dateTime`, `lookup`, `inheritLookup`, `picklist`, `address`, `file`, `url`, `email`, `phone`, `money`, `percentage`, `richText`, `autoNumber`, `filter`.

## Workflow

### 1. Load credentials

```bash
source ~/.konecty/.env  # exports KONECTY_URL and KONECTY_TOKEN
```

Or use the script (auto-loads from `~/.konecty/.env`).

### 2. List modules

```bash
python3 scripts/modules.py list
python3 scripts/modules.py list --lang en
```

Output: table of `document` (internal name), `label`, field count.

### 3. Find a module and show its fields

```bash
python3 scripts/modules.py fields "contato"
python3 scripts/modules.py fields "Contact"
python3 scripts/modules.py fields "oport"   # fuzzy match
```

Matching priority: exact `document` name → exact `label` → fuzzy (difflib SequenceMatcher on document + label). Prints all fields with name, type, and label.

### 4. Search modules by keyword

```bash
python3 scripts/modules.py search "atividade"
```

Filters modules whose `document` or `label` contains the keyword (case-insensitive).

## Fuzzy matching for agents

When the user refers to a module by an approximate name or in Portuguese, use `python3 scripts/modules.py fields "<user term>"` — the script ranks by similarity and picks the best match. If no confident match, it prints the top candidates so you can ask the user to confirm.

## Script reference

See [scripts/modules.py](scripts/modules.py). Stdlib only (`urllib`, `json`, `difflib`, `configparser`).

All subcommands accept:
- `--host` — overrides `KONECTY_URL`
- `--token` — overrides `KONECTY_TOKEN`
- `--lang` — language for labels (default: `pt_BR`)
