# Field Discovery — pointer

Field/module discovery is a **user-MCP** concern and lives in the **konecty-data**
skill: the sequence `modules_list` → `modules_fields` →
`field_picklist_options` / `field_lookup_search` (on the `konecty` server), plus the
control-fields and operator-by-type tables.

See [konecty-data/references/field-discovery.md](../../konecty-data/references/field-discovery.md).

## Metadata-side note

For **schema truth** while administering metadata, prefer `meta_read` on the
`konecty-admin` server ([read.md](read.md)): it returns the raw document meta —
full field definitions, picklist option maps, lookup targets, `inheritedFields`,
hooks — unfiltered by the calling user's access profile. `modules_fields` shows a
module as a *user* sees it; `meta_read` shows it as it *is*.
