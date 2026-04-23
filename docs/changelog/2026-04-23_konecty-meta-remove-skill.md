# Changelog: konecty-meta-remove skill

## Date

2026-04-23

## Summary

- Added skill **`konecty-meta-remove`** under `skills/konecty-meta-remove/`.
- Removes a **full metadata module** via `/api/admin/meta` (`GET` to plan, ordered `DELETE` for lists/views/access/pivot/card/namespace, hooks on the document, then primary document/composite), with **interactive confirmation** only (no `--auto-approve`).
- Script: `skills/konecty-meta-remove/scripts/meta_remove.py` (stdlib). Reference: `references/deletion-order.md`.
- Documented as the **11th** Konecty meta skill in ADR-0004.

## Rationale

Retiring a document module (e.g. moving preferences onto `User`) requires deleting **all** related MetaObjects safely, mirroring the confirmation style of `foxter-metas` `apply.js` while using the same HTTP admin API as `konecty-meta-sync`.
