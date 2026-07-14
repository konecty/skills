# ADR-0006: MCP-first skills — o MCP do Konecty executa, as skills guiam

> As skills deixam de embarcar scripts HTTP: a execução acontece nos servidores MCP do próprio Konecty (`/mcp`, `/admin-mcp`); as skills viram guias procedurais e lacunas de capacidade viram features upstream no Konecty.

---

## Status

**Aceito**

Data: 2026-07-13

---

## Contexto

As skills `konecty-data` e `konecty-meta` embarcavam scripts Python (stdlib) que chamavam a REST API do Konecty diretamente. Com os servidores MCP nativos do Konecty (`/mcp` de usuário e `/admin-mcp` admin, Streamable HTTP stateless), isso passou a duplicar a camada de execução:

- Cada mudança de endpoint precisava ser mantida em dois lugares — e drift real já tinha sido observado entre os scripts e as imagens públicas (STATE.md, decisões D6–D9 do e2e-harness).
- O setup (OTP + arquivos `.env`) tinha fricção muito maior que o OAuth remoto nativo do Claude Code (DCR → authorize+PKCE → token no navegador).
- O invariante de shared-files (`auth.py`/`modules.py` byte-idênticos entre skills) existia só para sustentar os scripts.

## Decisão

> Decidimos tornar o repositório **MCP-first**: as skills nunca embarcam clientes HTTP; elas nomeiam as tools MCP do Konecty e ensinam ordem, payloads e guardrails. O contrato do consumidor é `Konecty/docs/en/mcp.md` — as skills condensam, nunca contradizem.

Consequências estruturais:

1. **Zero scripts nas skills.** `skills/konecty-data` e `skills/konecty-meta` são guias (`SKILL.md` + `references/`); `grep -rE "urllib|http.client"` nelas retorna vazio. O invariante de shared-files foi dissolvido (guard de pre-commit, GitHub Action e `make shared-check` removidos).
2. **Nomes estáveis de servidor MCP:** `konecty` (usuário, `<url>/mcp`) e `konecty-admin` (`<url>/admin-mcp`), registrados com `claude mcp add --transport http --scope user`. Nomes estáveis permitem referenciar tools e substituir entradas idempotentemente (remove + add).
3. **Lacunas vão para upstream.** Se uma capacidade falta no MCP (ex.: deleção completa de módulo), a skill documenta a lacuna e o caminho manual seguro; a solução robusta é uma feature no repositório Konecty — nunca um workaround local. Primeiro exemplo: o escopo OAuth `admin` para clientes confiáveis ([konecty/Konecty#453](https://github.com/konecty/Konecty/pull/453), ADR-0011 lá).
4. **Auth:** usuário via OAuth nativo do Claude Code; admin interino via `authTokenId` de OTP como header Bearer (único uso restante de `~/.konecty/.env`); admin alvo via cliente confiável provisionado por `OAUTH_CLIENTS_JSON` — a troca é só re-registro do servidor.
5. **E2E orientado a MCP:** a stack sobe o Konecty **buildado do código-fonte local** (worktree de `../Konecty`), habilita as flags de namespace (`mcpUserEnabled`, `mcpAdminEnabled`, `mcpRoleIds`, `mcpUserWriteEnabled`) e um cliente JSON-RPC stdlib dirige cada fluxo documentado (gate = pass/fail das suítes; o gate de cobertura % morreu com os scripts).
6. **Instâncias Konecty sem MCP não são suportadas** a partir desta versão — usuários fixam a última tag script-based.

## Alternativas Consideradas

### Alternativa 1: manter scripts como fallback (dual-mode)

**Prós:** suporta Konecty antigo sem MCP.
**Contras:** dobra a manutenção para sempre; o drift já demonstrado continuaria; a promessa de setup em 1 comando morre. Rejeitada.

### Alternativa 2: skills chamarem o MCP via scripts próprios

**Prós:** controle fino de I/O.
**Contras:** re-duplica a camada de execução que o host (Claude Code) já provê nativamente, com OAuth incluso. Rejeitada.

## Consequências

- README, AGENTS.md e installer contam a nova história (install → URL → login no navegador → conversar com o CRM).
- `konecty-setup` (nova skill) cobre o caminho conversacional de setup/troubleshooting.
- Este ADR não substitui ADRs anteriores de formato (0001–0005); ele muda a camada de execução das skills operacionais.
