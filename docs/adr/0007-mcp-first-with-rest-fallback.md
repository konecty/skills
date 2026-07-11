# ADR-0007: Busca é MCP-first com fallback automático para REST

> O `find`/`query`/`sql` da `konecty-data` tenta o transporte MCP primeiro e, em falhas de
> infraestrutura (endpoint ausente, role não liberado, rate limit, indisponibilidade), cai
> automaticamente para o transporte REST existente — que continua no código como fallback.

---

## Status

**Aceito**

Data: 2026-07-11

---

## Contexto

Ao migrar a busca para o MCP, havia três posturas possíveis quanto ao REST atual. O ambiente real
mostrou que o MCP **não está sempre disponível**:

- O acesso ao MCP é gated pelo allowlist `mcpRoleIds` do namespace (deny-by-default). Verificado ao vivo:
  `POST https://brain-konecty.konecty.dev/mcp` com token válido retorna `403 mcp_access_denied — "MCP access
  not configured for this namespace"` (`sessionGuard.ts:45`). Ou seja, **namespaces sem o role liberado são o
  caso comum, não a exceção**.
- Konecty mais antigos **não têm** o endpoint `/mcp` (404).
- O MCP User tem **rate limit de 60 req/min por token**.

Uma regressão de "não consigo mais buscar registros" seria inaceitável. Precisava-se decidir **como a busca
se comporta quando o MCP não pode servir**.

---

## Decisão

> Decidimos que a busca é **MCP-first com fallback automático para REST**: tenta o MCP; em falha de
> transporte/infra, refaz a mesma intenção de busca no REST e retorna o resultado.

Matriz (resumo — detalhe em `design.md`):

- **200 OK** → adapta e imprime.
- **404** (endpoint ausente) → fallback **silencioso**.
- **403 / 429 / 5xx / erro de conexão / timeout / SSE malformado** → fallback **com uma frase curta no início**
  (ex.: *"Busca feita via API direta (REST)."*), no stderr, antes dos registros.
- **429 especificamente** → além do fallback, **desliga o MCP pelo resto do processo** (as próximas páginas vão
  direto ao REST — um aviso, não um por página).
- **401** (token inválido) → erro de auth, **sem** fallback (token ruim falharia no REST também).
- **200 com erro de validação do tool** (filtro/documento/sort inválido) → **mostra e aborta, sem fallback** —
  um problema de query não pode ser mascarado por um REST que se comporta diferente (ver ADR-0008).
- **MCP e REST falham** → mostra o erro do **REST** (o acionável), sai não-zero.

Controle por env `KONECTY_MCP`: `1`/unset = MCP-first (default); `0` = só REST (pula o MCP — evita round-trip
perdido onde se sabe que não há MCP); `only` = MCP estrito, sem fallback (diagnóstico/CI).

---

## Alternativas Consideradas

### Alternativa 1: MCP substitui o REST (sem fallback)

**Prós:** um caminho só; código mais simples; alinhado ao futuro.
**Contras:** quebra em Konecty sem `/mcp` e em qualquer namespace sem o role no allowlist — que é a
configuração default. Regressão inaceitável.

### Alternativa 2: Flag opt-in (`--mcp`), REST continua o default

**Prós:** migração gradual, zero risco de regressão.
**Contras:** ninguém liga a flag; o MCP nunca vira o caminho real; adia o objetivo indefinidamente.

### Alternativa 3: MCP-first com fallback (escolhida)

**Prós:** o MCP é exercido de verdade sempre que disponível; degrada sem regressão onde não está.
**Contras:** dois caminhos coexistem (mais teste); risco de divergência de resultado entre transportes
(endereçado na matriz + ADR-0008).

---

## Consequências

### Positivas
- Sem regressão: a busca sempre funciona, com ou sem MCP configurado.
- O MCP é adotado de fato onde o ambiente permite, sem exigir migração manual dos usuários.
- O env `KONECTY_MCP=0` dá saída limpa para ambientes sabidamente sem MCP (evita round-trip + 403 por call).

### Negativas
- Mantém os dois code paths vivos por mais tempo (custo de teste — cada linha da matriz é um teste).
- A mesma intenção de busca pode ser servida por dois caminhos; só é "indistinguível" onde os resultados são
  comprovadamente idênticos (a verificação de paridade cobriu isso; a exceção conhecida está no ADR-0008).
- Um round-trip extra por busca onde o MCP está ausente (mitigado: 404 é rápido; `KONECTY_MCP=0` desliga).

### Neutras
- Introduz o padrão "MCP-first + REST fallback" como referência para futuras migrações de skill ao MCP.

---

## Referências

- `.specs/features/find-via-mcp/design.md` — Error Handling Strategy (matriz de fallback)
- ADR-0006 (auth), ADR-0008 (divergência de filtro conhecida)
- Konecty: `src/mcp/shared/sessionGuard.ts:45`, `src/mcp/shared/rateLimiter.ts`
- `CONTEXT.md` — Transport, Fallback, Role allowlist

---

## Notas de Implementação

- A distinção "falha de infra → fallback" vs "erro de validação do tool → mostra e aborta" é **decidida pelo
  status HTTP + tipo de erro JSON-RPC**, não pelo conteúdo. Falha de transporte = fallback; `result.isError`
  de validação num 200 = surface.
- O flip de `KONECTY_MCP` desligado no 429 é **por processo** (cada invocação do CLI é um processo novo; não há
  cache entre invocações).

---

_Autores: Leonardo Viva_
