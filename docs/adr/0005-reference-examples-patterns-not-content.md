# ADR-0005: Reference-Project Examples Are Patterns, Not Content

> Hook/integration examples in `konecty-dev` derive *idiomatic patterns* from a real internal metas project, never its business rules, data, or name.

---

## Status

**Aceito**

Data: 2026-06-17

---

## Contexto

A skill `konecty-dev` (advisória, ensina desenvolvedores a escrever código contra o Konecty) precisa de exemplos ricos e realistas — sobretudo para hooks (`scriptBeforeValidation`, `validationScript`, `scriptAfterSave`). Existe um projeto interno de metas de referência (codinome `reference-metas`, caminho real só em `SOURCES.local.md`, git-ignored) com muitos exemplos reais de código de hook em produção.

Restrições:

- Este repositório é **público** e publicado em múltiplos marketplaces (gh skill, skills.sh, ClawHub, …).
- O projeto de referência pertence a um **cliente**: suas regras de negócio, nomes de campos, fórmulas, thresholds, dados e o próprio nome são confidenciais.
- O histórico git de um repo público é permanente: uma vez commitado, remover do working tree não apaga do histórico sem reescrita dolorosa.

Precisava-se decidir **como aproveitar esses exemplos sem vazar nada do cliente**.

---

## Decisão

> Decidimos usar `reference-metas` como fonte de **padrões idiomáticos**, nunca de **conteúdo**, para produzir exemplos 100% genéricos e didáticos na `konecty-dev`.

Concretamente:

1. **Extrair só a *forma***: a estrutura canônica de cada tipo de hook (como mutar um campo derivado, como enfileirar e-mail, como fazer lookup cross-document num `scriptAfterSave`). O formato, não a regra.
2. **Reescrever 100% dos exemplos** com módulos genéricos e neutros (`Contact`, `Opportunity`, `Product`, `Task`) e lógica inventada. Zero regras de negócio, nomes de campos proprietários, fórmulas/thresholds reais, dados, identificadores de cliente, URLs/endpoints internos.
3. **Checklist de sanitização** antes de cada exemplo entrar num doc.
4. **Nenhum nome de cliente em arquivo rastreado ou no histórico**: arquivos versionados usam o codinome `reference-metas`; o caminho real vive só em `SOURCES.local.md` (git-ignored). Uma task de `grep` no completion gate falha se qualquer nome de cliente conhecido aparecer no working tree.

---

## Alternativas Consideradas

### Alternativa 1: Vendorizar/copiar os exemplos reais

**Prós:** rápido, exemplos comprovadamente reais.
**Contras:** vaza regras e dados do cliente num repo público; inaceitável.

### Alternativa 2: Escrever na spec e "limpar depois"

**Prós:** rastreabilidade direta durante o desenvolvimento.
**Contras:** uma vez commitado num repo público, o nome fica no histórico; remover exige `filter-repo` arriscado. Garantir que *nunca entrou* é mais seguro que limpar depois.

### Alternativa 3: Não usar a fonte de referência

**Prós:** risco zero.
**Contras:** abre mão de exemplos realistas e idiomáticos que elevam muito a qualidade da skill.

---

## Consequências

### Positivas
- Exemplos idiomáticos e realistas sem qualquer exposição do cliente.
- A skill permanece publicável em marketplaces públicos sem revisão jurídica caso a caso.
- Padrão reutilizável para futuras skills que se inspirem em projetos reais.

### Negativas
- Custo de reescrita: cada exemplo precisa ser recriado do zero e revisado.
- Risco residual humano (esquecer de generalizar algo) — mitigado pelo checklist + `grep` gate + `codebase-security`.

### Neutras
- Introduz o conceito de "codename + SOURCES.local.md git-ignored" como padrão do repo para fontes sensíveis.

---

## Referências

- `.specs/features/konecty-dev/spec.md` (D10, D13)
- `.specs/features/konecty-dev/SOURCES.local.md` (git-ignored)
- `.specs/project/STATE.md` — konecty-dev decision log
- Konecty hooks: `docs/{en,pt-BR}/hooks.md` e ADR-0005 do repo Konecty (scriptAfterSave fora da transação)

---

## Notas de Implementação

- Lista de nomes de cliente conhecidos para o `grep` gate mora junto da task de verificação (não num arquivo rastreado que vire ele mesmo um vazamento — usar o `SOURCES.local.md` como referência local).
- O gate roda antes de qualquer PR/publish, ao lado de `make audit`.

---

_Autores: Derotino Silveira_
