# ADR-0004: Konecty Meta Skills

## Status

Aceito

## Data

2026-03-16

## Contexto

Konecty armazena todos os metadados (document, list, view, access, pivot, hook, namespace, card, composite) numa coleção única `MetaObjects`, discriminados pelo campo `type`. Gerenciar esses metadados exige conhecimento profundo da estrutura de cada tipo, do ciclo de vida dos hooks, das permissões de acesso e da configuração global (Namespace).

Agentes de IA precisam de orientações claras, exemplos reais e scripts utilitários para ler, editar e sincronizar metadados de forma segura. Uma única skill monolítica seria grande demais, gerando desperdício de tokens e perda de foco.

## Decisão

Criar **10 skills** separadas, cada uma com escopo bem definido:

| Skill | Escopo |
|-------|--------|
| `konecty-meta-read` | Leitura de qualquer tipo de meta |
| `konecty-meta-document` | CRUD de document metas (schema, fields, events) |
| `konecty-meta-list` | CRUD de list metas (columns, filters, sorters) |
| `konecty-meta-view` | CRUD de view/FormSchema metas (visuals tree) |
| `konecty-meta-access` | CRUD de access profiles (permissions, filters) |
| `konecty-meta-pivot` | CRUD de pivot metas |
| `konecty-meta-hook` | Geração e gestão de hook code (4 tipos) |
| `konecty-meta-namespace` | Configuração global do tenant |
| `konecty-meta-doctor` | Validação de integridade dos metas |
| `konecty-meta-sync` | Sincronização repo ↔ database (plan/apply) |

Cada skill contém:
- `SKILL.md` com frontmatter, pré-requisitos e workflow
- `scripts/` com CLI Python (stdlib only)
- `references/` com documentação de referência onde necessário

Todas dependem dos endpoints admin-only `/api/admin/meta/*` implementados no Konecty backend (ADR-0006 do repo Konecty).

## Alternativas consideradas

1. **Skill única monolítica**: Descartada por exceder limites práticos de tokens e misturar responsabilidades.
2. **Skills sem scripts (apenas instruções)**: Descartada por forçar o agente a montar chamadas HTTP manualmente, aumentando chance de erro.
3. **Dependência de ferramentas externas (httpie, jq)**: Descartada em favor de Python stdlib para zero-dependency.

## Consequências

### Positivas
- Cada skill pode ser carregada isoladamente, economizando tokens
- Scripts Python testáveis e reutilizáveis
- Documentação de referência serve tanto para agentes quanto para humanos
- `meta-doctor` e `meta-sync` reduzem erros operacionais

### Negativas
- 10 skills para manter e versionar
- Dependência forte nos endpoints `/api/admin/meta/*` — sem eles, nenhuma skill de escrita funciona

## Plano de implementação

1. Onda 0: Documentação de referência (field-architecture, access-architecture, hook-contracts, hook-patterns, document-events, namespace-schema)
2. Onda 1: Endpoints no Konecty (feature/meta-crud-api)
3. Onda 2: konecty-meta-read
4. Onda 3: konecty-meta-document, list, view, access, pivot, namespace
5. Onda 4: konecty-meta-hook
6. Onda 5: konecty-meta-doctor, konecty-meta-sync
7. Onda 6: ADRs, changelogs, push

## Referências

- Konecty ADR-0006: `/api/admin/meta/*` endpoints
- MetaObjects collection schema em `skills/konecty-meta-read/references/meta-schemas.md`
- Hook contracts em `skills/konecty-meta-hook/references/hook-contracts.md`
