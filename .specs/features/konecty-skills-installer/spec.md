# Konecty Skills Installer (CLI) Specification

## Problem Statement

Hoje instalar as skills do Konecty é manual: o usuário precisa saber onde clonar, em qual pasta de cada engine (`.claude/skills/`, `.cursor/skills/`, …) copiar, e depois descobrir sozinho o fluxo OTP que grava `~/.konecty/.env`. Não há comando único, nem detecção de engine, nem proteção contra sobrescrever edições locais. O objetivo é um instalador one-command — inspirado no [Reversa](https://github.com/sandeco/reversa) (`npx reversa install`) — adaptado à nossa stack Python stdlib: **`uvx --from git+https://github.com/konecty/KonectySkills konecty-skills install`** que detecta engines, copia as duas skills, parametriza credenciais (URL + OTP) e grava um manifest SHA-256 para updates seguros — **sem nunca apagar ou modificar arquivos preexistentes do usuário**.

## Goals

- [ ] Usuário roda **um comando** (`uvx … konecty-skills install`) e sai com as skills instaladas e credenciais configuradas
- [ ] Instalador **detecta os engines** presentes (Claude Code, Cursor, Codex, AGENTS.md) e instala nos paths corretos de cada um
- [ ] Skills são **baixadas do git em runtime** (tarball de uma branch/tag) — desacopladas da versão da CLI, sempre a última publicada
- [ ] Parametrização de credenciais via **fluxo OTP no install** (request-otp → verify-otp → grava `~/.konecty/.env`), reusando `scripts/auth.py`
- [ ] **Nunca destrói** arquivos do usuário — entry files (`CLAUDE.md`/`AGENTS.md`) recebem bloco anexado idempotente; updates protegidos por manifest SHA-256
- [ ] Banner ASCII colorido (7 letras = 7 cores do globo Konecty) em estilo blocado, no espírito do `hermes-agent`
- [ ] Zero dependências fora da stdlib (fiel à regra do repo); empacotado em `installer/` neste mesmo repo

## Out of Scope

| Feature | Reason |
|---------|--------|
| Publicação no PyPI | Fase posterior; `uvx --from git+…` cobre o MVP |
| Repo separado para a CLI | Decisão travada: mora em `installer/` neste repo |
| Empacotar skills como package data | Decisão travada: download do git em runtime |
| Gerenciar credenciais de outras ferramentas (Snyk, gh, clawhub) | Fora do escopo; instalador cuida só de `~/.konecty/.env` |
| Suporte a engines além de Claude Code / Cursor / Codex | Adicionar sob demanda; arquitetura deve permitir extensão |
| Auto-update da própria CLI | `uvx` já resolve a versão a cada execução |

---

## User Stories

### P1: Instalar tudo com um comando ⭐ MVP

**User Story**: Como desenvolvedor que adota o Konecty, quero rodar um único comando e ter as skills instaladas no meu agente e as credenciais configuradas, sem saber paths internos nem o fluxo OTP.

**Why P1**: É a razão de existir do instalador. Sem isso, nada mais importa.

**Acceptance Criteria**:

1. WHEN o usuário roda `konecty-skills install` THEN SHALL exibir o banner colorido e detectar os engines presentes no diretório atual
2. WHEN há mais de um engine detectado THEN SHALL listar todos pré-marcados e permitir desmarcar (padrão = todos)
3. WHEN nenhum engine é detectado THEN SHALL perguntar o engine-alvo e oferecer escopo global (`~/.claude/skills`) como fallback
4. WHEN o usuário confirma THEN SHALL baixar as skills `konecty-data` e `konecty-meta` do git e copiá-las para o(s) path(s) de cada engine selecionado
5. WHEN a cópia termina THEN SHALL gravar `~/.konecty/manifest.json` com o SHA-256 de cada arquivo instalado
6. WHEN tudo termina THEN SHALL imprimir resumo (engines, skills, paths, status de credenciais) e próximos passos

**Independent Test**: Em diretório limpo com `.claude/`, rodar `install` não-interativo (`--yes`) → verificar que `.claude/skills/konecty-data/SKILL.md` e `konecty-meta/SKILL.md` existem e que `~/.konecty/manifest.json` lista seus hashes.

---

### P1: Parametrizar credenciais (URL + OTP) durante o install ⭐ MVP

**User Story**: Como usuário, quero que o instalador me peça a URL do Konecty e faça o login OTP ali mesmo, gravando o token, para eu não precisar rodar a skill de sessão manualmente depois.

**Why P1**: É a diferença-chave do nosso instalador frente ao Reversa — parametrização, não só cópia de arquivos.

**Acceptance Criteria**:

1. WHEN o passo de credenciais inicia THEN SHALL perguntar `KONECTY_URL` (com validação básica de URL)
2. WHEN a URL é informada THEN SHALL oferecer rodar o OTP agora (identifier → request-otp → código → verify-otp) ou pular
3. WHEN o OTP é concluído THEN SHALL gravar `KONECTY_URL` e `KONECTY_TOKEN` em `~/.konecty/.env` reusando a lógica de `scripts/auth.py` (sem duplicar o fluxo)
4. WHEN o usuário pula o OTP THEN SHALL gravar só `KONECTY_URL` e instruir a rodar `konecty-skills configure` ou a skill `konecty-data` depois
5. WHEN `~/.konecty/.env` já existe THEN SHALL mostrar os valores atuais e pedir confirmação antes de sobrescrever
6. IF a request OTP retorna erro (URL inválida, 4xx) THEN SHALL exibir mensagem clara e permitir reentrar a URL sem abortar o install

**Independent Test**: Rodar `konecty-skills configure` apontando para um Konecty de teste, completar o OTP e verificar que `~/.konecty/.env` contém URL + token válido (`doctor` retorna conexão OK).

---

### P2: Updates seguros e status

**User Story**: Como usuário que já instalou, quero atualizar as skills sem perder edições locais e ver o que está instalado.

**Why P2**: Mantém a instalação viva sem retrabalho; depende do MVP existir primeiro.

**Acceptance Criteria**:

1. WHEN o usuário roda `konecty-skills status` THEN SHALL listar engines com skills instaladas, versão/commit de origem e se `~/.konecty/.env` tem URL + token
2. WHEN o usuário roda `konecty-skills update` THEN SHALL baixar a versão nova e comparar cada arquivo com o hash do manifest
3. IF um arquivo instalado foi modificado localmente (hash diverge do manifest) THEN SHALL preservá-lo e reportar conflito em vez de sobrescrever
4. WHEN o update termina THEN SHALL regravar o manifest com os novos hashes dos arquivos efetivamente atualizados

**Independent Test**: Instalar, editar um `SKILL.md` instalado, rodar `update` e verificar que a edição local é preservada e reportada como conflito.

---

### P2: Diagnóstico e desinstalação limpa

**User Story**: Como usuário, quero validar que tudo está funcionando e poder remover as skills sem deixar lixo.

**Why P2**: Fecha o ciclo de vida; não bloqueia o MVP.

**Acceptance Criteria**:

1. WHEN o usuário roda `konecty-skills doctor` THEN SHALL validar arquivos instalados vs manifest, presença de credenciais e testar conexão com o Konecty (health + token não-401)
2. WHEN o usuário roda `konecty-skills uninstall` THEN SHALL remover apenas os arquivos listados no manifest e deixar `~/.konecty/.env` intacto (a menos que `--purge`)
3. WHEN um arquivo a remover foi modificado localmente THEN SHALL pedir confirmação antes de apagar

**Independent Test**: Após instalar, rodar `doctor` (espera-se tudo verde) e depois `uninstall` → verificar que os skill folders sumiram e `~/.konecty/.env` permanece.

---

## Non-Functional Requirements

- **NFR1 — Stdlib only**: a CLI não pode ter dependências fora da stdlib do Python (≥3.9), idêntico à regra das skills.
- **NFR2 — Idempotência**: rodar `install` duas vezes não duplica blocos em entry files nem corrompe o manifest.
- **NFR3 — Segurança**: nunca apagar/sobrescrever arquivo não rastreado pelo manifest; token nunca ecoado em log; `.env` com permissão `600`.
- **NFR4 — Shared-files invariant**: a cópia das skills preserva os arquivos de `shared-files.txt` byte-idênticos entre `konecty-data` e `konecty-meta`.
- **NFR5 — Não-interativo**: todo comando aceita flags (`--yes`, `--engine`, `--url`, `--scope`) para rodar em CI sem prompts.

## Open Questions (validar no EXECUTE)

- **Q1.** Download do git: tarball via `https://codeload.github.com/.../tar.gz/<ref>` (stdlib `urllib` + `tarfile`) ou `git clone --depth 1`? Tarball evita dependência de `git` no PATH — preferência inicial.
- **Q2.** Reuso de `scripts/auth.py`: importar como módulo do tarball baixado, ou a CLI carrega o fluxo OTP via `runpy`? Definir contrato mínimo sem duplicar lógica.
- **Q3.** Paths por engine: confirmar destinos canônicos (Claude Code projeto `./.claude/skills/`, global `~/.claude/skills/`; Cursor `./.cursor/skills/`; Codex `AGENTS.md`-based). Validar empiricamente.
