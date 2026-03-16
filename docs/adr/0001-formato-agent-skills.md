# ADR-0001: Formato Agent Skills (SKILL.md e frontmatter)

> Adoção do padrão Agent Skills para definição de skills: SKILL.md com YAML frontmatter e corpo em Markdown.

---

## Status

**Aceito**

Data: 2026-03-16

---

## Contexto

O repositório KonectySkills foi criado para centralizar skills usadas por agentes (Cursor, Claude Code, etc.) no ecossistema Konecty. Era necessário definir um formato único e estável para cada skill, que permitisse:

- Identificação e descrição para seleção automática pelo agente
- Instruções claras e versionadas
- Compatibilidade com ferramentas e marketplaces existentes
- Simplicidade de criação e manutenção (sem build ou runtime próprio)

Não havia convenção interna prévia; havia referência ao repositório [anthropics/skills](https://github.com/anthropics/skills) e ao padrão [agentskills.io](https://agentskills.io).

---

## Decisão

> Decidimos adotar o **formato Agent Skills** para todas as skills do repositório: cada skill é uma pasta contendo ao menos um arquivo **SKILL.md** com **YAML frontmatter** (campos `name` e `description`) e **corpo em Markdown** (instruções, exemplos e diretrizes).

### Regras

- **name:** identificador único da skill, em minúsculas, com hífens (ex.: `codigo-limpo`, `template-skill`).
- **description:** descrição em linguagem natural do que a skill faz e **quando** o agente deve usá-la; usada para disparo/trigger da skill.
- **Corpo:** Markdown livre (títulos, listas, código, etc.) com instruções que o agente segue quando a skill está ativa.
- Recursos opcionais (scripts, configs, outros arquivos) podem coexistir na mesma pasta e ser referenciados no SKILL.md.

---

## Alternativas Consideradas

### Alternativa 1: Formato proprietário (JSON + MD separados)

**Prós:** Controle total do schema.  
**Contras:** Incompatível com Agent Skills; duplicação de esforço; menos interoperável com Cursor/Claude.

### Alternativa 2: Apenas Markdown, sem frontmatter

**Prós:** Máxima simplicidade.  
**Contras:** Sem metadados estruturados; difícil para o agente saber “quando” usar a skill; fora do padrão Agent Skills.

### Alternativa 3: Adotar formato Agent Skills (escolhida)

**Prós:** Alinhado a agentskills.io e anthropics/skills; um único arquivo por skill; descrição serve de trigger; ampla adoção.  
**Contras:** Dependência de um padrão externo (mitigada por ser aberto e estável).

---

## Consequências

### Positivas
- Interoperabilidade com Cursor, Claude Code e outros agentes que suportam Agent Skills.
- Onboarding simples: copiar template e editar SKILL.md.
- Descrição no frontmatter permite seleção automática da skill pelo agente.
- Repositório pode ser referenciado ou integrado a marketplaces/plugins no futuro.

### Negativas
- Qualquer mudança futura no padrão Agent Skills pode exigir migração (risco baixo no estado atual).

### Neutras
- Pasta `spec/` no repo mantém referência ao padrão para consulta.

---

## Referências

- [agentskills.io](https://agentskills.io)
- [anthropics/skills](https://github.com/anthropics/skills) (estrutura e exemplos)
- [spec/README.md](../../spec/README.md) neste repositório

---

## Notas de Implementação

- Novas skills devem seguir o [template](../template/SKILL.md).
- O campo `description` deve ser específico o suficiente para o agente escolher a skill nos contextos corretos; evite descrições genéricas.

---

_Autores: Equipe Konecty_
