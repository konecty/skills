# Tasks — oauth-only-0.3.0

Gate por task: `make lint` + testes afetados; gate de release: `make check` + `make validate`.

## Phase 1 — Purga OTP/authTokenId nas skills
- [ ] **T1** `konecty-data`: remover fallback OTP de `SKILL.md` (linhas ~20,28,51) e reescrever `references/auth.md` OAuth-only; `references/errors.md` recuperação 401 → re-auth OAuth. _Verify:_ `grep -ri 'otp\|authTokenId' skills/konecty-data/` vazio (AC-1).
- [ ] **T2** `konecty-meta`: `SKILL.md:21` + `references/auth.md` → caminho único OAuth trusted client (ADR-0011); `references/namespace.md` mantém `otpConfig` com nota de que é config de login da UI Konecty, não auth do MCP. _Verify:_ grep sem `authTokenId`; sem instrução OTP fora do `otpConfig` (AC-1).
- [ ] **T3** `konecty-setup`: remover fluxo OTP admin (`SKILL.md:174-225`) e reescrever `references/troubleshooting.md` (sem consent SPA / sem navegador → upgrade do backend ou trusted client via `OAUTH_CLIENTS_JSON`). _Verify:_ grep limpo (AC-1).

## Phase 2 — Purga no instalador
- [ ] **T4** Remover `--admin-auth otp` e o fluxo OTP de credenciais (`cli.py`, `credentials.py`, `engines.py`, `mcp_config.py` conforme aplicável); atualizar testes do instalador. _Verify:_ `make installer-test` verde; grep OTP no `installer/` limpo (AC-2).

## Phase 3 — Novos contratos do Konecty
- [ ] **T5** `konecty-data`: documentar `file_upload` como single-use upload URL (tool devolve URL + curl; bytes nunca pelo modelo; chat-only não faz upload — limitação declarada); atualizar e2e que citam o contrato antigo. `konecty-meta`: documentar `meta_delete` (dry-run/confirm, `MetaObjects.Trash`, namespace indeletável). _Verify:_ conteúdo bate com as specs do Konecty (`mcp-file-upload-url`, `admin-mcp-meta-delete`); marcar para re-verificação quando os PRs do Konecty mergearem (AC-3).

## Phase 4 — Release 0.3.0
- [ ] **T6** Bump `pyproject.toml` + `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` para 0.3.0; changelog (breaking: instalador sem OTP). _Verify:_ `make check` e `make validate` verdes (AC-4).

## Phase 5 — Validação empírica + publish
- [ ] **T7** Validar `/plugin marketplace add konecty/skills` → install numa sessão Claude Code real; registrar resultado no changelog/STATE. Depois `make publish` (gh, clawhub, hermes). _Verify:_ instalação funcional observada; publish sem erro (AC-5).

Dependências: T1–T4 paralelos; T5 após contratos congelados (specs já congelam; re-verificar pós-merge); T6 após T1–T5; T7 por último.
