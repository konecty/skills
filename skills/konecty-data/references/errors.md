# Error Map — user MCP

Every failure below has a specific cause and a specific next step. Translate the
error for the user in plain language — never retry blindly and never fall back to
improvised HTTP calls.

## Matrix

| Signal | What it means | Tell the user | Next step |
|--------|---------------|---------------|-----------|
| **503 — MCP disabled** (`mcp_disabled` / service unavailable on `/mcp`) | The namespace flag `mcpUserEnabled` is off — MCP is switched off for this Konecty | "O MCP está desativado neste Konecty." | Ask a Konecty admin to enable `mcpUserEnabled` on the namespace (via konecty-meta / admin MCP). No user-side fix. |
| **403 — `mcp_access_denied`** | Your role is not in the namespace `mcpRoleIds` allowlist. The list is **deny-by-default**: empty/absent means nobody has access | "Seu perfil ainda não está liberado para usar o MCP." | Ask the admin to add the user's role `_id` to `mcpRoleIds`. |
| **`insufficient_scope` on a write/destructive tool** (`records_create/update/delete`, `file_upload/delete`) | Namespace is in read-only mode: `mcpUserWriteEnabled` absent or `false` strips the `write` scope from every caller | "Este ambiente está em modo somente leitura via MCP — consultas funcionam, edições não." | Read flows keep working. To enable writes an admin sets `mcpUserWriteEnabled: true`. Do **not** retry the write. |
| **401 / `UNAUTHORIZED`** (may carry a `WWW-Authenticate` header) | Token missing, expired, or invalid | "Sua sessão expirou — é preciso entrar de novo." | OAuth path: re-authenticate via Claude Code (konecty-setup "fix auth"). OTP path: re-run the `session_*` flow and pass the new `authTokenId` ([auth.md](auth.md)). |
| **Audience mismatch** (OAuth succeeds but every `/mcp` call is rejected as invalid token/audience) | Deployment misconfiguration: the token's audience does not match `PLATFORM_MCP_RESOURCE_URL` on the server | "O login funciona mas o servidor recusa o token — é um problema de configuração do servidor, não do seu acesso." | Ask the admin to align `PLATFORM_MCP_RESOURCE_URL` (and OAuth resource metadata) with the MCP URL. The installer/konecty-setup `doctor` detects this. |
| **Filter rejected (Mongo-style)** | A raw field map was passed instead of a Konecty filter | — (agent-side mistake) | Rebuild via `filter_build` ([find.md](find.md)). |
| **Optimistic-lock conflict** ("new version for records") | Record changed between fetch and write | "O registro foi alterado por outra pessoa nesse meio-tempo." | Re-fetch, show the diff, retry once after user confirmation ([create-update.md](create-update.md)). |
| **Permission errors on specific fields/records** ("You don't have permission to …") | Access-profile restriction (field access, `readFilter`/`updateFilter`, `isDeletable`) | "Seu perfil de acesso não permite essa operação nesse campo/registro." | Omit the restricted field or ask an admin to review the access profile. |

## General rules

- **One cause, one message**: report the specific cause and remediation above — a
  generic "something failed" is never acceptable.
- **Never escalate on your own**: enablement flags (`mcpUserEnabled`,
  `mcpRoleIds`, `mcpUserWriteEnabled`) are admin decisions made via the admin MCP
  (konecty-meta). This skill only explains them.
- **Setup problems** (server not registered, URL changed, OAuth loop): hand over to
  the **konecty-setup** skill.
