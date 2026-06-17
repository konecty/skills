# E2E Harness — Tasks

Cada task = um commit atômico. Mensagem referencia o ID (ex.: `T1`). Verificação obrigatória antes de marcar concluída.

| ID | Task | Verifica | Status |
|----|------|----------|--------|
| T1 | **Spike de de-risking**: subir o stack company-brain-like manualmente, confirmar base metas (R1), criar doc+access+reload+data-create (R3), tentar upload real (R2). Registrar achados em STATE.md. | stack healthy; achados R1–R3 documentados | ✅ |
| T2 | `e2e/docker-compose.yml` + `.env.example` (mongo rs0 + init + rabbit + konecty). | `docker compose -f e2e/docker-compose.yml config` válido; sobe healthy | ✅ |
| T3 | `e2e/scripts/wait_for_konecty.py` (poll /liveness, stdlib). | retorna 0 quando healthy, !=0 no timeout | ✅ |
| T4 | `e2e/scripts/konecty_admin_token.py` (pw do log → login → grava `~/.konecty/.env`), stdlib urllib. | gera `~/.konecty/.env` válido; `modules list` funciona | ✅ |
| T5 | `tests/e2e/agent.py` (`PseudoAgent.run` in-process + `.smoke` subprocess) + `reporter.py`. | unit: `run` captura stdout/exit de um script trivial; smoke roda CLI real | ✅ |
| T6 | `tests/e2e/intents.py` + `tests/e2e/test_inference.py` (router determinístico, R-INFER). | asserts de roteamento verdes | ✅ |
| T7 | `tests/conftest.py` (fixtures: creds, agente, doc E2E setup/teardown idempotente). | fixtures importam; teardown remove doc E2E | ✅ |
| T8a | `tests/e2e/test_live_data.py` — **live** konecty-data subset the 3.8.10 image supports (auth login-options, modules, find find, create, update explicit-ids); records cleaned via direct API. | runs green vs live stack; skipped if down | ✅ |
| T8b | Extend `tests/e2e/mock_konecty.py` to a full Konecty mock (data CRUD + query/json + query/sql + explorer/modules + file + auth) atop the existing meta mock, with an in-memory per-document record store. | mock self-test covers data+query+file+auth | ✅ |
| T8c | `tests/e2e/test_data_mock.py` + `test_meta_mock.py` — **mock** suites driving EVERY subcommand of both skills (incl. drifted query/lookup/patch/delete + all meta ops) → coverage. | every cmd_* exercised; 0 FAIL | ✅ |
| T9 | `tests/e2e/test_security.py` — 8 critérios R-SEC (subprocess env-limpo onde aplicável). | todos asserts verdes | ✅ |
| T10 | `e2e/fixtures/MetaObjects/` (repo fixture p/ `meta sync`). | `meta sync plan` detecta diffs; `apply` aplica | ✅ |
| T11 | Config de cobertura (`.coveragerc`/pyproject) + fechar gaps até ≥90% (incl. `upload.py` mockado se R2 negativo, meta-skill `modules.py`, `meta_sync`/`meta_remove` apply). | `coverage report` ≥90%, `--fail-under=90` sai 0 | ✅ |
| T12 | Targets `make e2e-*` + `make e2e` (reset→up→token→cov→down) (R-MAKE). | `make e2e` verde da estaca zero | ✅ |
| T13 | Docs: README (seção e2e), changelog entry, atualizar AGENTS.md (test targets), STATE.md. | changelog + README atualizados | ✅ |
| T14 | Completion gate: `make check` + `make audit` limpos. | ambos passam | ✅ |

## Notas de execução
- T1 é spike — pode não virar commit (ou commit só do STATE.md). Os achados ajustam T2/T8/T11.
- Se a execução revelar >5 passos não previstos, parar e atualizar este arquivo (regra AGENTS.md).
- Delegar implementação paralelizável a subagentes Sonnet (preferência do usuário).
