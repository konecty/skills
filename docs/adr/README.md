# Registros de Decisão de Arquitetura (ADR)

Este diretório contém os Architecture Decision Records do repositório KonectySkills.

## O que são ADRs?

ADRs são documentos leves que registram decisões arquiteturais importantes, com contexto e consequências. Servem como memória do projeto e ajudam a entender:

- **Por que** as decisões foram tomadas
- **Quais alternativas** foram consideradas
- **Quais trade-offs** foram aceitos
- **Como** o repositório evolui ao longo do tempo

## Quando criar um ADR?

Crie um ADR quando:

- Definir formato ou convenção para skills (estrutura, frontmatter, idioma)
- Estabelecer padrões para o repositório (pastas, docs, changelog)
- Escolher dependências ou integrações (spec, ferramentas)
- Tomar decisões que impactem outras skills ou consumidores (Cursor, outros agentes)

## Como criar um ADR?

1. Copie o [template](./template.md).
2. Atribua o próximo número sequencial (ex.: 0004).
3. Salve como `####-titulo-breve.md` (ex.: `0004-idioma-descricoes-skills.md`).
4. Preencha todas as seções: Contexto, Decisão, Alternativas, Consequências, Referências.
5. Atualize o índice abaixo e o changelog do repo.

## Estrutura e nomenclatura

```
docs/adr/
├── README.md (este arquivo)
├── template.md
├── 0001-formato-agent-skills.md
├── 0002-estrutura-repositorio.md
└── 0003-documentacao-changelog-obrigatorios.md
```

- **Formato do arquivo:** `####-titulo-breve.md` (4 dígitos, hífens, minúsculas).
- **Estados:** Proposto | Aceito | Implementado | Substituído por ADR-XXXX | Deprecado | Rejeitado.

## Índice de ADRs

| #   | Título                                      | Status      | Data       |
|-----|---------------------------------------------|------------|------------|
| 0001 | [Formato Agent Skills](./0001-formato-agent-skills.md) | Aceito     | 2026-03-16 |
| 0002 | [Estrutura do repositório](./0002-estrutura-repositorio.md) | Aceito     | 2026-03-16 |
| 0003 | [Documentação e changelog obrigatórios](./0003-documentacao-changelog-obrigatorios.md) | Aceito     | 2026-03-16 |
| 0004 | [Konecty Meta Skills](./0004-konecty-meta-skills.md) | Aceito     | 2026-03-16 |

---

**Nota:** Para dúvidas sobre ADRs, consulte a skill de registro de decisão de arquitetura no Cursor ou o Tech Lead.
