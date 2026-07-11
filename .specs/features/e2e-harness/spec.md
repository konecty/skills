# E2E Harness Specification

## Problem Statement

As skills `konecty-data` e `konecty-meta` são validadas hoje por uma suíte de integração que **chama `cmd_*` diretamente** contra um Konecty que o desenvolvedor já tem rodando com credenciais pré-existentes. Isso deixa três lacunas: (1) cobertura travada em ~39% — os blocos `main()`/argparse e scripts inteiros (`upload.py`, meta-skill `modules.py`) nunca executam; (2) não há reprodutibilidade — exige um Konecty externo e um `~/.konecty/.env` montado à mão; (3) nenhum teste de segurança nem do caminho de "seleção de skill" (como um agente escolhe qual comando rodar).

O objetivo é um **harness e2e self-contained e reprodutível**: sobe um stack Konecty limpo via Docker, obtém o token admin do log do container, e um **pseudo-agente determinístico** dirige *toda* a superfície de CLI das duas skills (CRUD de dados + gestão de metadados), incluindo testes de segurança e de roteamento de intenção, atingindo ≥90% (ideal 100%) de cobertura de linha dos scripts.

## Goals

- [ ] Um `docker compose` sobe Mongo (replica set) + `mongodb-init` + RabbitMQ + `konecty/konecty`, com Mongo **limpo a cada rodada** (`down -v`).
- [ ] O harness obtém o **token admin a partir do log do container** Konecty (sem credenciais manuais) e escreve `~/.konecty/.env` automaticamente.
- [ ] Um **pseudo-agente** (in-process `main(argv)` + smoke subprocess) exercita **todos** os subcomandos de `konecty-data` e `konecty-meta`: create, find/query/sql, update/patch, delete, upload, e as 11 operações de meta.
- [ ] **Lifecycle isolado**: o agente cria um documento `E2E*` via `konecty-meta`, faz CRUD de dados nele, e o remove via `meta_remove` — sem corromper metas base.
- [ ] **Testes de segurança**: credential fast-fail, token inválido (401 sem traceback), guard de `--confirm` em delete/upload-delete, validações locais de OTP, hook/webhook inválidos, não-vazamento de token em stdout.
- [ ] **Mock de inferência**: roteador determinístico intent→comando (PT/EN) com asserts de roteamento, sem LLM.
- [ ] **Cobertura ≥90%** dos scripts das duas skills, com gate `--fail-under=90`; relatório term/HTML/XML.
- [ ] `make` targets de uma linha: subir, derrubar, resetar, pegar token, rodar e2e.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Mudar a lógica dos scripts das skills | Harness testa o comportamento atual; correções viram tarefas separadas se um teste revelar bug |
| OTP real por e-mail/SMS | Sem mail server no stack; branches locais de OTP são testadas, o roundtrip de rede é mockado |
| Publicação do harness como CI (GitHub Action) | Fase seguinte, após verde local (registrado em STATE.md como deferred) |
| Cobertura de `auth.py` via rede real | `auth.py` faz login OTP; só as validações locais são exercitadas |

---

## User Stories

### P1: Stack Konecty reprodutível e limpo ⭐ MVP

**User Story**: Como mantenedor das skills, quero subir um Konecty completo e limpo com um comando, para rodar o e2e de forma determinística sem depender de um servidor externo.

**Acceptance Criteria**:
1. WHEN rodo `make e2e-up` THEN o stack (mongo+init+rabbit+konecty) sobe e o Konecty fica `healthy` em `/liveness`.
2. WHEN rodo `make e2e-reset` THEN os volumes são dropados e o próximo boot gera um admin novo.
3. WHEN o Konecty está healthy THEN `make e2e-token` extrai a senha admin do log do container, faz `POST /rest/auth/login` (sha256) e grava `~/.konecty/.env` com `KONECTY_URL`/`KONECTY_TOKEN`.
4. WHEN o stack sobe THEN o Mongo está em replica set `rs0` (necessário para change streams das metas).

**Independent Test**: `make e2e-reset && make e2e-up && make e2e-token` → `~/.konecty/.env` válido e `modules list` lista ≥1 documento base.

---

### P1: Pseudo-agente exercita toda a superfície de CLI ⭐ MVP

**User Story**: Como mantenedor, quero um agente determinístico que rode cada subcomando das duas skills via `main(argv)`, para medir cobertura real incluindo argparse e caminhos de erro.

**Acceptance Criteria**:
1. WHEN o agente roda `run(skill, argv)` THEN ele importa e chama `main(argv)` do script, capturando stdout/stderr e o exit code (`SystemExit`).
2. WHEN o lifecycle e2e roda THEN ele cobre, em ordem: `meta document` (criar doc `E2E*` + campos, incl. campo file) → `meta access` (liberar CRUD ao admin) → `meta list/view/pivot/hook` (criar/ler) → `meta reload` → `data create/find/query/sql/lookup/update/patch/upload/delete` no doc `E2E*` → `meta sync` (plan/apply/diff/pull contra repo fixture) → `meta doctor` → `meta remove` (teardown do doc).
3. WHEN um subcomando depende de um anterior que falhou THEN o passo é reportado SKIP (cascading), não FAIL.
4. WHEN ao menos um smoke test roda via `subprocess` THEN ele prova que o entrypoint CLI executa de fato.
5. WHEN os scripts de meta tocam metas THEN nenhuma meta base (Contact, Activity) é modificada ou removida.

**Independent Test**: `make e2e-run` → todos os subcomandos reportam PASS/SKIP (0 FAIL) e o doc `E2E*` não existe ao final.

---

### P1: Cobertura ≥90% com gate ⭐ MVP

**User Story**: Como mantenedor, quero um gate de cobertura, para garantir que a superfície permaneça exercitada.

**Acceptance Criteria**:
1. WHEN o e2e roda com coverage THEN mede `skills/konecty-data/scripts` e `skills/konecty-meta/scripts`.
2. WHEN a cobertura total < 90% THEN o comando falha (exit ≠ 0) via `--fail-under=90`.
3. WHEN o e2e roda THEN emite relatório term-missing + HTML + XML.
4. WHEN `upload.py` não puder ser exercitado ao vivo (R2) THEN suas linhas são cobertas por testes HTTP-mockados e o skip vivo é documentado — sem afundar o total < 90%.

**Independent Test**: `make e2e-cov` imprime ≥90% e sai 0.

---

### P2: Testes de segurança

**User Story**: Como mantenedor, quero testes de segurança sobre as skills, para garantir falha segura e ausência de vazamentos.

**Acceptance Criteria**:
1. WHEN qualquer subcomando roda sem credenciais (HOME vazio) THEN falha com mensagem legível **antes** de qualquer HTTP — verificado via `subprocess` com env limpo.
2. WHEN um token inválido é usado THEN a saída é `HTTP 401: ...` legível, nunca um traceback Python.
3. WHEN `delete delete` roda sem `--confirm` THEN sai 1 sem chamar DELETE.
4. WHEN `upload delete` roda sem `--confirm` THEN é dry-run (exit 0, nenhum DELETE).
5. WHEN OTP recebe `--email` e `--phone` juntos, ou um OTP não-6-dígitos THEN falha localmente sem rede.
6. WHEN `meta hook`/`namespace set-webhook` recebe nome/evento inválido THEN sai 1 antes de qualquer HTTP.
7. WHEN qualquer comando imprime saída THEN o `KONECTY_TOKEN` não aparece em stdout/stderr.
8. WHEN um `--filter`/`sql` contém aspas/`;`/payload THEN é transmitido via JSON/urllib (sem shell), e entradas inválidas são rejeitadas com mensagem — não execução.

**Independent Test**: `make e2e-sec` → todos os asserts de segurança verdes.

---

### P2: Mock de inferência (roteamento de intenção)

**User Story**: Como mantenedor, quero validar que frases de usuário (PT/EN) roteiam para o comando de skill correto, sem depender de um LLM.

**Acceptance Criteria**:
1. WHEN o roteador recebe uma frase de intenção THEN retorna `(skill, argv)` determinístico.
2. WHEN o conjunto de intenções cobre criar/buscar/atualizar/excluir/meta THEN cada uma roteia para o subcomando esperado (asserts).
3. WHEN o roteador resolve uma intenção THEN a sequência resultante é executável pelo pseudo-agente (integração com a US P1).

**Independent Test**: `make e2e-infer` → todos os asserts de roteamento verdes.

---

## Traceability

| ID | Requirement | Verified by |
|----|-------------|-------------|
| R-STACK | compose sobe mongo rs0 + init + rabbit + konecty; reset limpa | task T2/T3 |
| R-TOKEN | token admin do log → `~/.konecty/.env` | task T4 |
| R-AGENT | pseudo-agente `run(skill, argv)` in-process + smoke subprocess | task T5 |
| R-LIFE | lifecycle meta-create → data CRUD → meta-remove, doc isolado | task T7/T8 |
| R-COV | ≥90% gate, term/HTML/XML | task T11 |
| R-SEC | testes de segurança (8 critérios) | task T9 |
| R-INFER | roteador determinístico intent→comando | task T6 |
| R-MAKE | targets make de uma linha | task T10 |
