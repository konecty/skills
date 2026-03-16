# ADR-0003: Documentação e changelog obrigatórios

> Decisão de manter documentação do repositório e changelog obrigatórios para mudanças relevantes.

---

## Status

**Aceito**

Data: 2026-03-16

---

## Contexto

Os repositórios do ecossistema Konecty (ui, Konecty) seguem regras de documentação obrigatória: docs em `docs/`, changelog em `docs/changelog/` e ADRs em `docs/adr/` para decisões que afetem arquitetura, padrões ou uso. O KonectySkills é um repositório de artefatos (skills) consumidos por agentes e por outros projetos; mudanças em estrutura, formato ou convenções impactam quem cria ou consome skills.

Era necessário definir se KonectySkills também teria documentação e changelog obrigatórios e em que formato.

---

## Decisão

> Decidimos que o KonectySkills **terá documentação obrigatória** em `docs/` e **changelog obrigatório** em `docs/changelog/`, com entrada por data para mudanças que afetem estrutura, formato de skills, convenções ou uso do repositório. ADRs serão usados para decisões arquiteturais e de padrão (formato, estrutura, convenções).

### Regras

- **docs/:** README (índice), guia de desenvolvimento/contribuição (`development.md`), ADRs em `docs/adr/`, changelog em `docs/changelog/`.
- **Changelog:** cada mudança relevante gera `docs/changelog/YYYY-MM-DD_slug.md` e atualização do índice em `docs/changelog/README.md`.
- **ADRs:** criados para decisões que afetem formato de skills, estrutura do repo, convenções de documentação ou integração com agentes/ferramentas.
- Conteúdo das **skills** (instruções dentro de cada SKILL.md) não exige entrada de changelog por si só; mudanças no repositório (estrutura, template, docs, convenções) sim.

---

## Alternativas Consideradas

### Alternativa 1: Sem documentação obrigatória

**Prós:** Menos overhead.  
**Contras:** Inconsistente com ui/Konecty; perda de rastreabilidade e onboarding.

### Alternativa 2: Documentação e changelog obrigatórios (escolhida)

**Prós:** Alinhado ao resto do ecossistema; histórico claro; ADRs para decisões importantes.  
**Contras:** Exige disciplina ao commitar mudanças (mitigado por template e README do changelog).

### Alternativa 3: Changelog apenas para “releases” de conjunto de skills

**Prós:** Menos arquivos de changelog.  
**Contras:** Menos granularidade; atraso na documentação de mudanças pontuais.

---

## Consequências

### Positivas
- Consistência com ui e Konecty na abordagem de documentação.
- Histórico de mudanças e decisões (changelog + ADRs) facilita revisão e onboarding.
- ADRs explicam o “porquê” de formato e estrutura, não só o “como”.

### Negativas
- Desenvolvedores precisam criar/atualizar changelog e índice ao fazer mudanças relevantes.

### Neutras
- Template de changelog e README do `docs/` indicam o formato esperado.

---

## Referências

- [docs/README.md](../README.md)
- [docs/development.md](../development.md)
- [docs/changelog/README.md](../changelog/README.md)
- Regras de documentação obrigatória dos workspaces ui/Konecty

---

## Notas de Implementação

- Formato do changelog: resumo, motivação, o que mudou, impacto técnico, como validar, arquivos afetados, migração (se houver).
- ADRs seguem o [template](../adr/template.md) e a nomenclatura `####-titulo.md` em `docs/adr/`.

---

_Autores: Equipe Konecty_
