# E2E Harness Design

## Overview

Self-contained harness em duas camadas: **infra** (Docker stack + bootstrap de token) e **driver** (pseudo-agente + suíte pytest com cobertura). Espelha o `company-brain` mas adaptado a skills que são CLIs Python stdlib-only.

## Directory layout (new)

```
e2e/
├── docker-compose.yml          # mongo(rs0) + mongodb-init + rabbitmq + konecty/konecty
├── .env.example                # KONECTY_PORT, MONGO_PORT, KONMETA_NAMESPACE, image tag
├── scripts/
│   ├── konecty_admin_token.py  # pw do `docker logs` → POST /rest/auth/login → authId → grava ~/.konecty/.env
│   └── wait_for_konecty.py     # poll /liveness até healthy (timeout)
└── fixtures/
    └── MetaObjects/            # repo fixture mínimo para exercitar `meta sync` (plan/apply/diff/pull)

tests/
├── conftest.py                 # NEW: fixtures de sessão (creds, agente, doc E2E), config de coverage
├── e2e/                        # NEW
│   ├── agent.py                # PseudoAgent.run(skill, argv) → main(argv) in-process; .smoke(...) → subprocess
│   ├── intents.py              # router determinístico intent(PT/EN) → (skill, argv)
│   ├── reporter.py             # record() PASS/FAIL/SKIP + contadores (padrão company-brain)
│   ├── test_lifecycle.py       # meta-create doc E2E → data CRUD/upload → meta sync/doctor → meta-remove
│   ├── test_security.py        # 8 critérios R-SEC (alguns via subprocess com env limpo)
│   └── test_inference.py       # asserts do router (R-INFER)
└── integration/                # existente — mantida; gaps fechados migrando para main(argv) quando útil
```

`make` targets (root Makefile): `e2e-up`, `e2e-down`, `e2e-reset`, `e2e-token`, `e2e-run`, `e2e-cov`, `e2e-sec`, `e2e-infer`, `e2e` (reset→up→token→cov→down).

## Components

### 1. Docker stack (`e2e/docker-compose.yml`)
Adaptado do company-brain, **sem** os serviços brain. Serviços: `mongodb` (`mongo:8.2`, `--replSet rs0`), `mongodb-init` (inicia rs0), `rabbitmq` (`4.1.0-management-alpine`), `konecty` (`konecty/konecty:3.2.3`, env igual ao company-brain: `KONECTY_MODE=development`, `MONGO_URL=...rs0`, namespace configurável, healthcheck `wget /liveness`). Volumes nomeados; `down -v` zera. Portas via `.env` (default 3000/27017) para não colidir com um Konecty de dev já rodando.

### 2. Token bootstrap (`e2e/scripts/konecty_admin_token.py`)
Porta direta do company-brain: regex `admin\) with password (\S+)` sobre `docker logs <container>`, `POST /rest/auth/login` com `password_SHA256 = sha256(pw)`, lê `authId`. **Estende**: grava `~/.konecty/.env` (`KONECTY_URL`, `KONECTY_TOKEN`) — formato que os scripts já consomem. stdlib `urllib` (não `httpx`) para manter zero-dep.

### 3. PseudoAgent (`tests/e2e/agent.py`)
```
class PseudoAgent:
  def run(skill, argv) -> Result(stdout, stderr, code):
     # importa o módulo do script (sys.path += skills/<skill>/scripts), chama main(argv)
     # captura redirect_stdout/stderr; SystemExit → code (None→0); coverage.py rastreia in-process
  def smoke(skill, script, argv) -> subprocess.CompletedProcess   # prova CLI real
```
O dispatch por skill/subcomando mapeia para o script certo (`find.py`, `create.py`, …, `meta_document.py`, …). Cada `main(argv)` cobre argparse + dispatch + `cmd_*`.

### 4. Intent router (`tests/e2e/intents.py`)
Dict determinístico `{frase: (skill, argv-template)}` PT/EN. `route(phrase, **slots)` preenche slots (document, id, data) e devolve `(skill, argv)`. Sem LLM. Usado tanto pelos asserts de roteamento (R-INFER) quanto como fonte das ações do lifecycle (prova que o caminho de "seleção" é executável).

### 5. Reporter (`tests/e2e/reporter.py`)
`record(step, status, detail)` com `PASS/FAIL/SKIP`, acumula lista + print streaming; resumo `N passed, M failed, K skipped`; exit 1 se algum FAIL. Cascading SKIP quando um passo-pré falhou.

### 6. Coverage (`tests/conftest.py` + Makefile)
`coverage run -m pytest tests/e2e tests/integration` com `source=skills/konecty-data/scripts,skills/konecty-meta/scripts`, `omit=*/__pycache__/*`. `--fail-under=90`. Relatórios term-missing/HTML(`tests/coverage_html`)/XML. `.coveragerc` ou config em pyproject.

## Test data lifecycle (R-LIFE)

1. `meta document add` cria documento `E2EThing` (nome único por run) com campos: `name` (text), `qty` (number), `attachment` (file) — cobre `add-field`, `update-field`, `upsert`, `events`.
2. `meta access upsert` cria/garante um access profile que dá CRUD ao usuário admin (nome descoberto lendo o access de um doc base via `meta read`/`meta access`).
3. `meta list/view/pivot upsert` + `meta hook upsert` criam metas filhas (cobrem essas ops).
4. `POST /api/admin/meta/reload` (via os próprios scripts que já chamam reload) torna o doc usável.
5. `data create/lookup/find/query/sql/update/patch/upload/delete` operam em `E2EThing`.
6. `meta sync plan/apply/diff/pull` contra `e2e/fixtures/MetaObjects/`.
7. `meta doctor check`.
8. `meta remove plan` + `apply --yes` removem `E2EThing` e filhos (teardown). Idempotente: se um run anterior deixou resto, limpa no setup.

## Risk mitigations (de STATE.md R1–R3)

- **R1 (base metas):** spike T1 confirma; se ausentes, adicionamos um seed mínimo via mongo (`e2e/scripts/seed_metas.py`) — fallback documentado.
- **R2 (upload/file storage):** spike T1 testa um upload real. Se exigir storage externo, `upload.py` é coberto por testes com `urllib` mockado (monkeypatch de `urlopen`) + um teste vivo marcado `skipif`. Mantém ≥90%.
- **R3 (doc usável pós-create):** spike T1 cria doc + access + reload e tenta um `data create`. Se falhar, ajustamos o conjunto mínimo de access/namespace e registramos em STATE.md.

## Security model (R-SEC)
Testes que exigem env limpo (credential fast-fail, token não-vazado) rodam via `subprocess` com `env` controlado (`HOME=tmpdir`, sem `KONECTY_*`). Os demais rodam in-process. Asserts sobre mensagens (não tracebacks) e exit codes.

## Decisions referenced
D1–D5 em `.specs/project/STATE.md`.
