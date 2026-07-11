# ADR-0008: Divergência conhecida do MCP em filtros aninhados (aceita, fix é no Konecty)

> O MCP silenciosamente enfraquece filtros com `filters` aninhados em 2+ níveis, retornando um
> superset de registros vs o REST. Aceitamos essa divergência na skill, documentamos com destaque, e
> o fix correto é no servidor Konecty (não na skill).

---

## Status

**Aceito**

Data: 2026-07-11

---

## Contexto

A verificação de paridade entre `records_find` (MCP) e `/rest/data/:document/find` (REST) — ambos chamam a
mesma `find()` — encontrou **uma divergência silenciosa** na camada de validação de filtro, anterior ao
`find()`:

- O REST **não valida** o filtro: faz `JSON.parse` e entrega direto à `find()`, cujo `parseFilterObject`
  recursa em `filters` a **profundidade arbitrária** (`filterUtils.js:591-593`).
- O MCP valida com `KonFilter.safeParse` (`filterNormalization.ts:127`). O schema `KonFilter`
  (`Filter.ts:31-45`) modela `filters` como array de `{ match?, conditions?, textSearch? }` — **sem** um campo
  `filters` aninhado. O Zod, por padrão, faz `.strip()` de chaves desconhecidas: um filtro com `filters` dentro
  de `filters` **passa na validação com o nível interno removido silenciosamente**, e `normalizeKonectyFilter`
  retorna sucesso com o objeto podado.

Efeito: para o **mesmo** filtro profundamente aninhado, o MCP aplica **menos** restrições e retorna **mais**
registros que o REST — sem erro, sem aviso. É a classe de bug "resultado silenciosamente errado".

Casos relacionados, para contexto:

- Filtro **Mongo-style pelado** (`{"status":"active"}`, sem chave reservada): o MCP **rejeita** com erro; o REST
  o **ignora** e retorna a coleção inteira. Como a skill trata erro de validação do tool como *surface, sem
  fallback* (ADR-0007), esse caso vira **erro claro** para o usuário — comportamento melhor que o "retorna tudo"
  silencioso de hoje. Não é o problema desta ADR.
- Filtros de **1 nível** (o que o `filter_build` do próprio Konecty produz) são **idênticos** entre MCP e REST.
  A divergência só aparece em `filters` aninhado 2+ níveis — algo raro, que o `filter_build` nem gera.

Precisava-se decidir **o que a skill faz diante dessa divergência**.

---

## Decisão

> Decidimos **não** tratar a divergência na skill: filtros aninhados vão ao MCP como qualquer outro. Em vez de
> mascarar na skill, **documentamos a divergência com destaque** para que o fix seja feito na origem — no
> `KonFilter`/`normalizeKonectyFilter` do Konecty, que deve modelar `filters` recursivo (ou rejeitar
> explicitamente em vez de podar em silêncio).

Concretamente na skill:
1. Nenhuma lógica de inspeção de profundidade de filtro (mantém o `--filter` como pass-through).
2. Uma seção **"Divergências conhecidas"** em `references/find.md` e uma nota no `design.md` descrevendo o caso,
   o gatilho (aninhamento 2+), o efeito (superset) e a orientação: para filtros profundos, prefira `KONECTY_MCP=0`
   (REST) até o fix no Konecty.
3. Um item de acompanhamento para o fix no repo Konecty.

---

## Alternativas Consideradas

### Alternativa 1: Skill detecta aninhamento e roteia pro REST

**Prós:** zero divergência silenciosa para o usuário final imediatamente.
**Contras:** coloca conhecimento do bug do servidor dentro da skill (acoplamento errado de camada); a skill
passa a "adivinhar" o que o MCP aceita; quando o Konecty for corrigido, a heurística vira código morto que pode
mandar pro REST à toa. Corrige no lugar errado.

### Alternativa 2: Skill rejeita filtros profundos com erro

**Prós:** nunca manda um filtro que diverge.
**Contras:** quebra filtros que **funcionam hoje no REST**; a skill vira mais restritiva que os dois backends;
péssima experiência por um caso raro.

### Alternativa 3: Aceitar e documentar, fix no Konecty (escolhida)

**Prós:** o fix mora onde o bug está (o schema do MCP); a skill fica simples e honesta; o caso é raro e o
`filter_build` não o gera.
**Contras:** existe uma janela em que um filtro aninhado via skill+MCP retorna superset. Mitigado pela
documentação destacada + orientação de usar `KONECTY_MCP=0` para filtros profundos.

---

## Consequências

### Positivas
- A skill não carrega workarounds de bugs do servidor; o fix acontece na origem e beneficia todos os clientes MCP.
- Código da skill permanece um pass-through simples de filtro.

### Negativas
- Janela de divergência silenciosa (superset) para o caso raro de `filters` aninhado enquanto o Konecty não for
  corrigido. Documentada, não mascarada.

### Neutras
- Registra o formato canônico esperado de `KonFilter` recursivo como requisito do fix no Konecty.

---

## Referências

- Konecty: `src/mcp/shared/filterNormalization.ts:113-127`, `src/imports/model/Filter.ts:31-45`,
  `src/imports/data/filterUtils.js:591-624`, `src/imports/data/api/find.ts`
- `.specs/features/find-via-mcp/design.md` — Risks & Concerns (divergência de filtro)
- ADR-0007 (fallback: por que erro de validação não faz fallback)
- `CONTEXT.md` — KonFilter

---

## Notas de Implementação

- **Fix no Konecty (fora deste repo):** doc acionável criado no repo Konecty em
  `.specs/quick/002-mcp-nested-filter-divergence/TASK.md` — descreve a reprodução (test-first), o root cause
  (`KonFilter.filters` não-recursivo em `src/imports/model/Filter.ts:34-44`) e duas opções de fix (tornar
  `filters` recursivo via `z.lazy`, recomendado; ou `.strict()` que rejeite o aninhamento em vez de podar).
- **Na skill:** a seção "Divergências conhecidas" de `references/find.md` deve citar este ADR.

---

_Autores: Leonardo Viva_
