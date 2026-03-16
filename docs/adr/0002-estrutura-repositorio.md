# ADR-0002: Estrutura do repositório (template, spec, skills, docs)

> Definição da estrutura de pastas e artefatos do repositório KonectySkills.

---

## Status

**Aceito**

Data: 2026-03-16

---

## Contexto

Ao inicializar o KonectySkills, era necessário definir onde colocar skills, como oferecer um ponto de partida para novas skills, onde referenciar o padrão e onde manter documentação e histórico. O repositório [anthropics/skills](https://github.com/anthropics/skills) já adota uma estrutura clara: `skills/`, `template/`, `spec/`, além de README e documentação.

Requisitos:
- Uma pasta dedicada para as skills.
- Um template reutilizável para criar novas skills.
- Referência ao padrão Agent Skills (spec).
- Documentação do projeto e changelog em `docs/`.

---

## Decisão

> Decidimos adotar a **estrutura de pastas** inspirada em anthropics/skills, com **template/**, **spec/**, **skills/** e **docs/**, garantindo um único lugar para skills, um template padrão e documentação e changelog obrigatórios.

### Estrutura

```
KonectySkills/
├── README.md           # Visão geral, como criar e usar skills
├── .gitignore
├── template/           # Template para novas skills (SKILL.md)
├── spec/               # Referência ao padrão Agent Skills (README.md)
├── skills/             # Skills do projeto Konecty (ex.: konecty-session)
├── agents/skills/      # Skills externas/referência (ex.: skill-creator, de anthropics/skills)
└── docs/               # Documentação do repo
    ├── README.md       # Índice da documentação
    ├── development.md  # Como contribuir e adicionar skills
    ├── adr/            # Architecture Decision Records
    └── changelog/       # Changelog por data
```

- **template/:** contém um único `SKILL.md` de referência com frontmatter e seções (Examples, Guidelines).
- **spec/:** contém `README.md` com link e resumo do padrão (agentskills.io / anthropics/skills); sem duplicar a spec completa.
- **skills/:** skills do projeto Konecty (cada subpasta é uma skill, ex.: `skills/konecty-session/SKILL.md`).
- **agents/skills/:** skills de referência ou externas ao produto (ex.: skill-creator, copiado de anthropics/skills).
- **docs/:** documentação do repositório (não das skills em si); ADRs em `docs/adr/`; changelog em `docs/changelog/`.

---

## Alternativas Consideradas

### Alternativa 1: Skills na raiz, sem template

**Prós:** Menos pastas.  
**Contras:** Raiz poluída; sem template claro; difícil escalar.

### Alternativa 2: Estrutura anthropics/skills (escolhida)

**Prós:** Consistência com referência conhecida; separação clara de responsabilidades; template e spec explícitos.  
**Contras:** Nenhum relevante para o escopo atual.

### Alternativa 3: Monorepo com categorias (ex.: skills/backend, skills/frontend)

**Prós:** Organização por domínio.  
**Contras:** Prematuro; pode ser introduzido depois se o número de skills crescer.

---

## Consequências

### Positivas
- Qualquer pessoa encontra rapidamente onde criar skills (`skills/`) e como começar (`template/`).
- Spec concentrada em `spec/` evita dúvidas sobre o padrão.
- docs/ e changelog suportam rastreabilidade e onboarding.

### Negativas
- Nenhuma significativa.

### Neutras
- Manutenção de `docs/changelog/README.md` e entradas por data ao fazer mudanças relevantes.

---

## Referências

- [anthropics/skills – estrutura](https://github.com/anthropics/skills)
- [README principal do KonectySkills](../../README.md)

---

## Notas de Implementação

- Foi criada a skill de exemplo `skills/example-skill/` para servir de referência além do template.
- O arquivo `skills/.gitkeep` mantém a pasta `skills/` versionada mesmo sem outras skills.

---

_Autores: Equipe Konecty_
