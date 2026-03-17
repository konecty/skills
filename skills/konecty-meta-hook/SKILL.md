---
name: konecty-meta-hook
description: "Generate and manage Konecty hook code: scriptBeforeValidation, validationData, validationScript, scriptAfterSave. Use when the user wants to create, read, update, or delete hooks, generate hook code from requirements, scaffold hook templates, or validate hook correctness. Requires admin credentials."
---

# Konecty Meta Hook

Generate and manage hook code for Konecty documents.

## Prerequisites

Requires **admin** credentials from **konecty-session**. User must have `admin: true`.

## Hook Types

| Hook | File type | When it runs | Available variables | Returns |
|------|-----------|-------------|--------------------|---------| 
| `scriptBeforeValidation` | JS | Before validation | `data, emails, user, console, extraData` | Object merged into `data` |
| `validationData` | JSON | Before validationScript | N/A (config) | Feeds `extraData` |
| `validationScript` | JS | After validationData | `data, user, console, extraData` | `{ success, reason? }` |
| `scriptAfterSave` | JS | After record saved | `data, user, console, Models, extraData` | None |

## Workflow

### 1. List hooks for a document

```bash
python3 scripts/meta_hook.py list Contact
```

### 2. Show a specific hook

```bash
python3 scripts/meta_hook.py show Contact scriptBeforeValidation
python3 scripts/meta_hook.py show Product validationData
```

### 3. Update a hook (from file)

```bash
python3 scripts/meta_hook.py upsert Contact scriptBeforeValidation --file hook.js
python3 scripts/meta_hook.py upsert Product validationData --file validationData.json
```

### 4. Update a hook (inline code)

```bash
python3 scripts/meta_hook.py upsert Contact validationScript --code 'return { success: true };'
```

### 5. Delete a hook

```bash
python3 scripts/meta_hook.py delete Contact scriptAfterSave
```

### 6. Scaffold a hook template

```bash
python3 scripts/meta_hook.py scaffold scriptBeforeValidation
python3 scripts/meta_hook.py scaffold validationData
python3 scripts/meta_hook.py scaffold validationScript
python3 scripts/meta_hook.py scaffold scriptAfterSave
```

### 7. Validate a hook (backend dry-run)

```bash
python3 scripts/meta_hook.py validate scriptBeforeValidation --file hook.js
python3 scripts/meta_hook.py validate scriptBeforeValidation --file hook.js --document Contact
```

This command calls `POST /api/admin/meta/hook/validate` and uses the same backend validations used by apply/doctor.

## Code generation guidelines

When generating hook code, follow these rules:

1. **scriptBeforeValidation**: Always `var ret = {};` at top, always `return ret;` at bottom
2. **validationScript**: Always return `{ success: true }` on the happy path
3. **scriptAfterSave**: Data may be an array for batch operations
4. **validationData**: Pure JSON, use `$this.<field>` for dynamic filters
5. **emails.push()** only works in `scriptBeforeValidation`
6. No `require()` or `import` — hooks run in a VM sandbox
7. No inline comments in JS hook source (`//` or `/* */`)
8. `scriptBeforeValidation` and `validationScript` must include explicit `return`
9. Only `scriptAfterSave` supports `await`
10. Use try/catch for complex logic to prevent hook failures from blocking saves
11. Do NOT post to RabbitMQ queues from hooks — use `document.events` instead

## References

- [references/hook-contracts.md](references/hook-contracts.md) — detailed contracts for all 4 hooks
- [references/hook-patterns.md](references/hook-patterns.md) — common implementation patterns with real examples

## Script reference

See [scripts/meta_hook.py](scripts/meta_hook.py). Stdlib only.
