# 2026-03-16: Konecty Meta Skills (10 skills)

## Resumo

Criação de 10 skills para gerenciamento de metadados do Konecty: read, document, list, view, access, pivot, hook, namespace, doctor, sync.

## Motivação

Agentes de IA precisam de orientações claras e scripts utilitários para manipular os metadados que definem a estrutura de dados, formulários, permissões, hooks e configurações globais do Konecty.

## O que mudou

- `skills/konecty-meta-read/` — Leitura de qualquer tipo de meta via API admin
- `skills/konecty-meta-document/` — CRUD de document schemas, fields, events
- `skills/konecty-meta-list/` — CRUD de list metas (columns, filters, sorters)
- `skills/konecty-meta-view/` — CRUD de view/FormSchema metas (visuals tree)
- `skills/konecty-meta-access/` — CRUD de access profiles (permissions, filters)
- `skills/konecty-meta-pivot/` — CRUD de pivot metas
- `skills/konecty-meta-hook/` — Geração e gestão de hook code (4 tipos)
- `skills/konecty-meta-namespace/` — Configuração global do tenant (Namespace)
- `skills/konecty-meta-doctor/` — Validação de integridade dos metas
- `skills/konecty-meta-sync/` — Sincronização repo ↔ database (plan/apply)
- `docs/adr/0004-konecty-meta-skills.md` — ADR da decisão arquitetural

Cada skill inclui SKILL.md, scripts Python (stdlib only), e references/ onde necessário.

## Impacto técnico

- Todas as skills de escrita dependem dos endpoints `/api/admin/meta/*` (admin-only) criados no branch `feature/meta-crud-api` do repo Konecty
- Scripts Python usam apenas stdlib (sem dependências externas)
- Documentação de referência criada para: field architecture, access architecture, hook contracts, hook patterns, document events, namespace schema, meta schemas

## Impacto externo

- Agentes com estas skills podem gerenciar metadados completos de uma instância Konecty
- Skill de sync permite workflow terraform-like (plan → approve → apply) entre repo e database

## Como validar

1. Verificar que cada skill possui `SKILL.md` com frontmatter válido
2. Verificar que cada script Python executa sem erros de sintaxe: `python3 -c "import ast; ast.parse(open('scripts/meta_X.py').read())"`
3. Para testes funcionais: garantir que endpoints `/api/admin/meta/*` estão ativos no Konecty

## Arquivos afetados

```
skills/konecty-meta-read/
skills/konecty-meta-document/
skills/konecty-meta-list/
skills/konecty-meta-view/
skills/konecty-meta-access/
skills/konecty-meta-pivot/
skills/konecty-meta-hook/
skills/konecty-meta-namespace/
skills/konecty-meta-doctor/
skills/konecty-meta-sync/
docs/adr/0004-konecty-meta-skills.md
docs/changelog/2026-03-16_konecty-meta-skills.md
```

## Existe migração?

Não.
