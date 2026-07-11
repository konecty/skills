# Konecty Skills Consolidation Specification

## Problem Statement

18 skills separadas criam fricção de instalação e sobrecarga cognitiva para o usuário: instalar `konecty-find` exige conhecer que `konecty-session` e `konecty-modules` também existem. A manutenção é fragmentada — cada mudança de auth ou field discovery toca múltiplos repos. O objetivo é duas skills auto-suficientes: instalar `konecty-data` é suficiente para operar o sistema.

## Goals

- [ ] Usuário instala `konecty-data` e tem acesso a todas as operações de dados (find, create, update, delete, upload, auth, field discovery)
- [ ] Usuário instala `konecty-meta` e tem acesso a todas as operações de metadados (11 operações + auth + field discovery)
- [ ] Zero perda de funcionalidade das 18 skills existentes
- [ ] Arquivos compartilhados entre as duas skills são enforçados por automação (pre-commit + GH Action)
- [ ] Padrão de referências segue o modelo `tlc-spec-driven` (SKILL.md com routing table + references/ por operação)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Reescrita dos scripts Python | Migração, não refatoração de lógica — YAGNI |
| Publicação em marketplaces | Fase separada após validação end-to-end |
| Merge dos scripts em um único arquivo por skill | Aumenta risco sem ganho — scripts permanecem separados |
| Novos comportamentos ou operações | Zero features novas nesta refatoração |

---

## User Stories

### P1: Instalar `konecty-data` é suficiente para operar dados ⭐ MVP

**User Story**: Como desenvolvedor que usa o Konecty, quero instalar uma única skill e ter acesso a busca, criação, atualização, deleção, upload e autenticação, sem precisar descobrir e instalar skills adicionais.

**Why P1**: É o objetivo central da refatoração. Sem isso, nada mais importa.

**Acceptance Criteria**:

1. WHEN usuário instala `konecty-data` THEN SHALL ter acesso às operações: find, create, update, delete, upload, auth (OTP flow), field discovery
2. WHEN agente carrega `konecty-data/SKILL.md` THEN SHALL encontrar tabela de routing com trigger patterns em PT-BR e EN para cada operação
3. WHEN agente precisa de detalhes de uma operação THEN SHALL carregar o reference file correspondente (`references/find.md`, `references/create.md`, etc.)
4. WHEN credenciais não existem em `~/.konecty/.env` THEN `konecty-data` SHALL guiar o usuário pelo OTP flow via `references/auth.md`
5. WHEN `konecty-data` é instalado sem `konecty-session` THEN SHALL funcionar normalmente (session está bundled como `scripts/auth.py`)

**Independent Test**: Instalar apenas `konecty-data` em ambiente limpo e executar: autenticação OTP → listar registros → criar registro → atualizar → deletar.

---

### P1: Instalar `konecty-meta` é suficiente para operar metadados ⭐ MVP

**User Story**: Como administrador do Konecty, quero instalar uma única skill e ter acesso a todas as operações de metadados sem instalar 11 skills separadas.

**Why P1**: Paridade com `konecty-data` — mesma proposta de valor para o lado meta.

**Acceptance Criteria**:

1. WHEN usuário instala `konecty-meta` THEN SHALL ter acesso às 11 operações: read, document, list, view, access, pivot, hook, namespace, doctor, sync, remove
2. WHEN agente carrega `konecty-meta/SKILL.md` THEN SHALL encontrar tabela de routing com trigger patterns para todas as 11 operações
3. WHEN agente precisa de detalhes THEN SHALL carregar o reference file 1:1 correspondente à skill original
4. WHEN credenciais admin não existem THEN `konecty-meta` SHALL falhar com mensagem clara referenciando `references/auth.md`
5. WHEN `konecty-meta` é instalado sem `konecty-session` THEN SHALL funcionar normalmente (auth bundled)

**Independent Test**: Instalar apenas `konecty-meta` e executar: autenticação → listar documentos meta → inspecionar um hook → validar integridade via doctor.

---

### P1: Arquivos compartilhados nunca divergem ⭐ MVP

**User Story**: Como mantenedor do repo, quero que `auth.py`, `modules.py` e seus reference files sejam idênticos nas duas skills, enforçado automaticamente — sem depender de disciplina humana.

**Why P1**: DRY enforcement é o mecanismo de segurança central da arquitetura escolhida.

**Acceptance Criteria**:

1. WHEN desenvolvedor tenta commitar com `auth.py` diferente entre as duas skills THEN pre-commit hook SHALL bloquear o commit com mensagem indicando qual arquivo diverge
2. WHEN PR é aberto no GitHub THEN GH Action SHALL comparar SHAs dos arquivos listados em `shared-files.txt` e falhar se divergirem
3. WHEN novo arquivo compartilhado é adicionado THEN basta adicioná-lo em `shared-files.txt` para que os gates passem a enforçá-lo automaticamente
4. WHEN `make setup` é executado THEN SHALL configurar `core.hooksPath .githooks` no repositório local
5. WHEN `shared-files.txt` lista um arquivo que não existe em uma das skills THEN gate SHALL falhar com mensagem clara

**Independent Test**: Modificar `auth.py` em apenas uma das skills e tentar commitar — deve ser bloqueado. Reverter e tentar novamente com ambas idênticas — deve passar.

---

### P2: Migração paralela sem quebrar as 18 skills existentes

**User Story**: Como mantenedor, quero que as 18 skills antigas coexistam com as 2 novas durante a migração, para validar end-to-end antes de qualquer deleção.

**Why P2**: Reduz risco de regressão. A deleção é irreversível (sem git reset).

**Acceptance Criteria**:

1. WHEN `konecty-data` e `konecty-meta` são criadas THEN as 18 skills em `skills/` SHALL permanecer intactas
2. WHEN ambas as novas skills são validadas end-to-end THEN as 18 skills SHALL ser deletadas em um único commit atômico separado
3. WHEN commit de deleção é feito THEN `AGENTS.md` SHALL ser atualizado no mesmo commit (mapa de skills + API surface migrada para os SKILL.md)

**Independent Test**: Após criar as novas skills, executar todas as operações das 18 skills originais via as 2 novas e confirmar paridade.

---

### P2: `make setup` configura o ambiente de desenvolvimento

**User Story**: Como novo contribuidor do repo, quero um único comando que prepare meu ambiente local com todos os hooks necessários.

**Why P2**: Sem `make setup`, o pre-commit hook depende de instrução manual — propenso a ser esquecido.

**Acceptance Criteria**:

1. WHEN `make setup` é executado THEN SHALL rodar `git config core.hooksPath .githooks`
2. WHEN `make setup` é executado novamente THEN SHALL ser idempotente (sem erros)
3. WHEN `.githooks/pre-commit` é executado THEN SHALL ler `shared-files.txt` e comparar os arquivos listados entre `konecty-data` e `konecty-meta`

**Independent Test**: Clonar o repo em ambiente limpo, rodar `make setup`, modificar `auth.py` em uma skill, tentar commitar — deve ser bloqueado.

---

### P3: SKILL.md segue exatamente o padrão tlc-spec-driven

**User Story**: Como desenvolvedor familiar com o tlc-spec-driven, quero que os SKILL.md das novas skills usem o mesmo padrão de routing table e seção Commands, reduzindo a curva de aprendizado.

**Why P3**: Consistência de DX, mas não bloqueia funcionalidade.

**Acceptance Criteria**:

1. WHEN agente lê SKILL.md de `konecty-data` THEN SHALL encontrar seção `## Commands` com tabela `Trigger Pattern | Reference`
2. WHEN frontmatter `description` é avaliado THEN SHALL ter menos de 1024 caracteres e cobrir semânticamente todas as operações
3. WHEN triggers em PT-BR são usados THEN agente SHALL identificar corretamente a operação e carregar o reference file correto

**Independent Test**: Usar apenas frases em PT-BR para invocar cada operação e confirmar que o agente carrega o reference correto.

---

## Edge Cases

- WHEN usuário tem `konecty-session` instalada standalone THEN as novas skills SHALL funcionar sem conflito (auth.py é independente)
- WHEN usuário instala `konecty-data` E `konecty-meta` THEN `shared-files.txt` SHALL ser idêntico em ambas
- WHEN pre-commit é executado em repo sem `konecty-meta` instalado THEN gate SHALL passar (não é erro ter só uma das skills)
- WHEN reference file de uma operação está ausente THEN SKILL.md SHALL apontar claramente para o arquivo esperado na tabela de routing
- WHEN sub-references existentes (ex: `filter-operators.md`, `field-types.md`) são migrados THEN SHALL virar seções dentro do reference file pai, não arquivos separados

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|---------------|-------|-------|--------|
| CONS-01 | P1: konecty-data auto-suficiente | Tasks | Pending |
| CONS-02 | P1: konecty-meta auto-suficiente | Tasks | Pending |
| CONS-03 | P1: gates de arquivos compartilhados | Tasks | Pending |
| CONS-04 | P2: migração paralela | Tasks | Pending |
| CONS-05 | P2: make setup | Tasks | Pending |
| CONS-06 | P3: padrão tlc no SKILL.md | Tasks | Pending |

---

## Estrutura Final

```
skills/
├── konecty-data/
│   ├── SKILL.md                        # frontmatter + seção Commands (routing table)
│   ├── shared-files.txt                # manifest dos arquivos gateados
│   ├── scripts/
│   │   ├── auth.py                     # [GATED] idêntico em konecty-meta
│   │   ├── modules.py                  # [GATED] idêntico em konecty-meta
│   │   ├── find.py
│   │   ├── create.py
│   │   ├── update.py
│   │   ├── delete.py
│   │   └── upload.py
│   └── references/
│       ├── auth.md                     # [GATED] OTP flow + credential setup
│       ├── field-discovery.md          # [GATED] modules discovery
│       ├── find.md                     # inclui: cross-module-query, filter-operators
│       ├── create.md                   # inclui: field-types
│       ├── update.md
│       ├── delete.md
│       └── upload.md
├── konecty-meta/
│   ├── SKILL.md
│   ├── shared-files.txt                # mesmo conteúdo que konecty-data
│   ├── scripts/
│   │   ├── auth.py                     # [GATED]
│   │   ├── modules.py                  # [GATED]
│   │   ├── meta_read.py
│   │   ├── meta_document.py
│   │   ├── meta_list.py
│   │   ├── meta_view.py
│   │   ├── meta_access.py
│   │   ├── meta_pivot.py
│   │   ├── meta_hook.py
│   │   ├── meta_namespace.py
│   │   ├── meta_doctor.py
│   │   ├── meta_sync.py
│   │   └── meta_remove.py
│   └── references/
│       ├── auth.md                     # [GATED]
│       ├── field-discovery.md          # [GATED]
│       ├── read.md
│       ├── document.md                 # inclui: field-architecture, document-events
│       ├── list.md
│       ├── view.md
│       ├── access.md                   # inclui: access-architecture
│       ├── pivot.md
│       ├── hook.md                     # inclui: hook-contracts, hook-patterns
│       ├── namespace.md                # inclui: namespace-schema
│       ├── doctor.md
│       ├── sync.md
│       └── remove.md                   # inclui: deletion-order
.githooks/
└── pre-commit                          # lê shared-files.txt, compara SHAs
.github/workflows/
└── check-shared-files.yml
Makefile                                # make setup → git config core.hooksPath .githooks
```

## Success Criteria

- [ ] `konecty-data` instalada isoladamente: autenticação + todas as operações de dados funcionam end-to-end
- [ ] `konecty-meta` instalada isoladamente: autenticação + todas as 11 operações meta funcionam end-to-end
- [ ] Modificar `auth.py` em uma skill sem a outra bloqueia o commit
- [ ] GH Action falha em PR com arquivos compartilhados divergentes
- [ ] `make setup` + `pre-commit` funcionam em ambiente limpo
- [ ] Nenhuma operação das 18 skills originais perdida (auditoria 1:1)
- [ ] 18 skills deletadas em commit separado após validação
