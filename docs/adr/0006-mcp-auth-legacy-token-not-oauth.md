# ADR-0006: MCP usa o token first-party (authId) em Bearer, não OAuth

> As skills de busca autenticam no MCP do Konecty com o `authId` existente enviado como `Authorization: Bearer`, e deliberadamente **não** adotam a camada OAuth 2.1 do Konecty.

---

## Status

**Aceito**

Data: 2026-07-11

---

## Contexto

O Konecty ganhou um servidor **User MCP** (`POST /mcp`) cujo `records_find`/`query_json`/`query_sql`
chamam as mesmas funções internas (`find()`, `crossModuleQuery()`) que os endpoints REST. Queremos que
o `find` da skill `konecty-data` fale MCP. O MCP aceita duas formas de credencial:

1. **OAuth 2.1** (authorization-code + PKCE S256, public client, dynamic client registration) — tokens
   opacos, escopados (`read`/`write`), TTL 1h. Endpoints `/.well-known/oauth-*`, `/oauth/*` existem.
2. **Token first-party** (`authId` de sessão) — o mesmo que as skills já guardam em `~/.konecty/.env`.
   Resolvido como credencial de escopo pleno.

Restrições que pesaram na decisão:

- As skills são **CLI headless** (scripts Python stdlib). Não há navegador no loop.
- O OAuth do Konecty **não tem grant `client_credentials`** (`grant_types_supported` = `authorization_code`
  + `refresh_token`) — obter um token OAuth **exige consentimento interativo no navegador**.
- Verificado no código (`user/server.ts:31-44`): o `/mcp` remove o prefixo `Bearer ` se presente e trata o
  resto como token; se não for um grant OAuth válido, cai no resolvedor de sessão first-party. Ou seja o
  `authId` legado **já autentica** no `/mcp`, cru ou com `Bearer`.
- Pré-requisito ortogonal: o role do usuário precisa estar no allowlist `mcpRoleIds` do namespace (senão 403),
  independentemente da forma de credencial.

Precisava-se decidir **qual credencial a skill apresenta ao `/mcp`**.

---

## Decisão

> Decidimos autenticar no MCP com o `authId` first-party existente, enviado como
> `Authorization: Bearer <authId>`, e **não** introduzir nenhum fluxo OAuth na skill.

Concretamente:

1. O header `Authorization: Bearer <authId>` é **obrigatório** — é o que passa pelo preHandler `requireUserAuth`
   (401 sem ele).
2. O mesmo `authId` também vai no argumento `authTokenId` do tool (defensivo: `resolveToken` prefere o
   argumento, imunizando contra o drop de AsyncLocalStorage que o próprio transport do Konecty documenta).
3. Nenhuma mudança na aquisição de credencial: o fluxo OTP/`~/.konecty/.env` (`auth.py`) fica intacto. Só muda
   *como o token é apresentado* ao `/mcp` (agora com prefixo `Bearer`).

---

## Alternativas Consideradas

### Alternativa 1: Adotar OAuth 2.1 completo

**Prós:** tokens escopados/revogáveis/TTL curto; alinhado ao "jeito MCP" idiomático; consentimento explícito.
**Contras:** exige navegador + dynamic client registration + callback local + troca de código + refresh —
pesado e frágil para um CLI headless; sem `client_credentials`, não há caminho não-interativo para CI/scripts.

### Alternativa 2: OAuth primário com fallback para o token legado

**Prós:** cobre uso interativo e headless.
**Contras:** dobra a superfície de auth e de teste para um ganho marginal enquanto o token legado já dá acesso
pleno ao `/mcp`. Custo desproporcional agora.

### Alternativa 3: Token cru (`Authorization: <authId>`, sem `Bearer`)

**Prós:** é literalmente o que a skill já faz hoje no REST; zero mudança.
**Contras:** funciona, mas `Bearer` é a convenção idiomática de MCP e deixa o código pronto para um eventual
token OAuth sem retrabalho de formatação. Diferença de esforço nula.

---

## Consequências

### Positivas
- Zero fricção nova de credencial: quem já usa as skills continua com o mesmo `~/.konecty/.env`.
- Funciona headless (CI, scripts) sem navegador.
- Prova o caminho MCP+auth com o menor risco antes de qualquer investimento em OAuth.

### Negativas
- Não colhe os benefícios do OAuth (escopos finos, revogação, TTL). Aceitável: busca é read-only e o token
  legado já é o modelo de confiança das outras operações da skill.
- O acesso ainda depende do allowlist `mcpRoleIds` — a skill degrada para REST quando o namespace não libera
  (ver ADR-0007).

### Neutras
- Fixa a convenção `Authorization: Bearer <authId>` como padrão para qualquer futura adoção de MCP nas skills
  (ex.: `konecty-meta` → `/admin-mcp`).

---

## Referências

- `.specs/features/find-via-mcp/spec.md` (Assumptions: auth), `design.md` (Token-source resolution)
- Konecty: `src/mcp/user/server.ts:31-44`, `src/mcp/user/tools/common.ts:23-39` (`resolveToken`), `src/imports/auth/oauth/*`
- `CONTEXT.md` — authId, first-party credential, OAuth access token

---

## Notas de Implementação

- Enviar o token **no header e no argumento `authTokenId`** — mesmo valor nos dois lugares.
- Não logar o token em stderr/stdout nem em mensagens de erro.

---

_Autores: Leonardo Viva_
