<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/logo-horizontal-white.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/logo-horizontal-color.png">
  <img alt="Konecty" src="docs/logo-horizontal-color.png" width="300">
</picture>

# KonectySkills

> **Seu agente de IA agora fala Konecty.**

Skills que conectam agentes de IA como Claude Code e Cursor diretamente à plataforma Konecty. Busque registros, crie contatos, gerencie esquemas e escreva integrações — tudo com linguagem natural, sem consultar a documentação da API.

[![Known Vulnerabilities](https://snyk.io/test/github/konecty/skills/badge.svg)](https://snyk.io/test/github/konecty/skills)
[![Cobertura E2E](https://img.shields.io/badge/cobertura_e2e-93%25-22c55e?style=flat-square)](#testes-e2e)
[![agentskills.io](https://img.shields.io/badge/agentskills.io-compatível-6366f1?style=flat-square)](https://agentskills.io)
[![skills.sh](https://img.shields.io/badge/skills.sh-compatível-6366f1?style=flat-square)](https://skills.sh)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue?style=flat-square)](./LICENSE)

**[🇺🇸 English version →](./README.en.md)**

---

## Instalação rápida

Um comando detecta seu ambiente de IA, instala as três skills e configura suas credenciais Konecty — você estará operacional em menos de dois minutos:

```bash
uvx --from git+https://github.com/konecty/skills konecty-skills install
```

**Pré-requisitos:** Python 3.9+ e `uv` (`pip install uv` ou `brew install uv`).

### Comandos do instalador

| Comando | O que faz |
|---------|-----------|
| `install` | Detecta engines → seleciona skills → baixa → copia → configura credenciais (OTP) → grava manifesto |
| `configure` | Somente credenciais: grava `~/.konecty/.env` (URL + token OTP) |
| `status` | O que está instalado, em quais engines, e se as credenciais estão presentes |
| `update` | Rebaixa as skills com proteção SHA-256 (nunca sobrescreve edições locais) |
| `doctor` | Valida arquivos instalados vs manifesto e testa a conexão com o Konecty |
| `uninstall` | Remove as skills instaladas (credenciais são mantidas, a não ser que `--purge` seja passado) |

Todos os comandos aceitam `--yes` / `--engine` / `--scope` / `--url` / `--ref` para uso não-interativo (CI/CD, scripts de provisionamento).

### Instalar via marketplace

**[skills.sh](https://skills.sh)**
```bash
npm i -g @agentskill.sh/cli
npx skills add konecty/skills
```

**[OpenClaw (clawhub)](https://clawhub.io)**
```bash
npm i -g clawhub
clawhub skill install konecty-data
clawhub skill install konecty-meta
clawhub skill install konecty-dev
```

**[Hermes (NousResearch)](https://hermes.nousresearch.com)**
```bash
hermes skills tap add konecty/skills
hermes skills install konecty-data
hermes skills install konecty-meta
hermes skills install konecty-dev
```

### Instalação manual

Se preferir instalar sem o CLI:

```bash
# Clone o repositório
git clone https://github.com/konecty/skills
cd skills

# Copie as skills para seu engine de IA
# Claude Code (por projeto)
cp -r skills/konecty-data  .claude/skills/
cp -r skills/konecty-meta  .claude/skills/
cp -r skills/konecty-dev   .claude/skills/

# Claude Code (global)
cp -r skills/konecty-data  ~/.claude/skills/
cp -r skills/konecty-meta  ~/.claude/skills/
cp -r skills/konecty-dev   ~/.claude/skills/

# Cursor
cp -r skills/konecty-data  .cursor/skills/
cp -r skills/konecty-meta  .cursor/skills/
cp -r skills/konecty-dev   .cursor/skills/
```

---

## As três skills

### `konecty-data` — Operações de dados

Operações completas sobre registros Konecty: autenticação OTP, descoberta de campos e CRUD completo com gestão de arquivos.

| Quando usar | Exemplos de frases |
|-------------|-------------------|
| Autenticar / obter token | "faça login no Konecty", "autenticar via OTP", "abrir sessão" |
| Descobrir campos e módulos | "quais campos tem o módulo Contato?", "listar módulos disponíveis" |
| Buscar registros | "buscar contatos criados hoje", "filtrar oportunidades por status", "query SQL" |
| Criar registros | "criar contato João Silva", "inserir nova oportunidade", "criar atividade" |
| Atualizar registros | "atualizar status do contato #123", "modificar campo email" |
| Deletar registros | "deletar registro #456 do módulo Leads" |
| Upload de arquivos | "anexar contrato.pdf ao registro", "fazer upload da foto de perfil" |

**Requer:** credenciais em `~/.konecty/.env` (`KONECTY_URL` + `KONECTY_TOKEN`).

---

### `konecty-meta` — Gestão de metadados *(admin)*

Gerenciamento completo de esquemas e configurações da plataforma: documentos, listas, views, perfis de acesso, hooks, namespace e sincronização repositório↔banco.

| Quando usar | Exemplos de frases |
|-------------|-------------------|
| Inspecionar esquemas | "listar documentos", "ler metadata do módulo CRM", "inspecionar campos" |
| Gerenciar documento | "adicionar campo ao módulo", "criar documento", "remover campo" |
| Configurar listas e views | "adicionar coluna na lista", "criar view de formulário", "configurar layout" |
| Perfis de acesso | "configurar permissões de leitura", "gerenciar perfil de acesso" |
| Gerar hooks | "gerar hook scriptBeforeValidation", "criar validationScript" |
| Configurar Namespace | "configurar SMTP", "configurar fila RabbitMQ", "atualizar namespace" |
| Validar integridade | "validar metadados", "checar integridade", "auditoria de meta" |
| Sincronizar | "sincronizar metas para produção", "aplicar schema", "deploy metas" |
| Remover módulo | "remover módulo completo", "deletar metadata", "excluir documento meta" |

**Requer:** credenciais de **admin** em `~/.konecty/.env` (usuário com `admin: true`).

---

### `konecty-dev` — Integração por código *(advisory)*

Skill consultiva para escrever código que integra com o Konecty — priorizando os SDKs oficiais (Python e TypeScript/Node), com a API REST completa documentada para outras linguagens.

| Quando usar | Exemplos de frases |
|-------------|-------------------|
| Começar uma integração | "como conectar meu app ao Konecty?", "qual SDK usar?", "primeiro cliente" |
| SDK Python | "exemplo Python", "usar konecty_sdk_python", "cliente Python" |
| SDK TypeScript/Node | "exemplo TypeScript", "usar @konecty/sdk", "cliente Node" |
| API REST (outras linguagens) | "chamar API com Go", "integração Java", "cliente HTTP sem SDK" |
| Filtros e queries | "como filtrar por data?", "operadores de busca", "query com relações" |
| Hooks no servidor | "escrever scriptBeforeValidation", "lógica após salvar", "validationScript" |
| Receitas e padrões | "paginação", "retry", "sincronização incremental", "upload de arquivo" |

**Não executa operações ao vivo** — gera código para você incorporar na sua aplicação. Para operações imediatas, use `konecty-data`.

---

## Credenciais

### Configuração inicial

```bash
# Opção 1: via instalador (recomendado — faz o fluxo OTP completo)
uvx --from git+https://github.com/konecty/skills konecty-skills configure

# Opção 2: manual
cp .env.example .env
# Preencha KONECTY_URL e KONECTY_TOKEN
```

O arquivo `~/.konecty/.env` é compartilhado por todas as skills:

```dotenv
KONECTY_URL=https://sua-instancia.konecty.com
KONECTY_TOKEN=<authId obtido via OTP login>
```

### Outras credenciais

| Credencial | Quando necessária | Como obter |
|------------|------------------|------------|
| `KONECTY_TOKEN` (admin) | `konecty-meta` | Usuário com `admin: true` no Konecty |
| `SNYK_TOKEN` | Auditoria de segurança | [app.snyk.io/account](https://app.snyk.io/account) |
| GitHub auth | Publicar via `gh skill publish` | `gh auth login` (interativo, uma vez) |
| Socket auth | Scan de supply chain | `socket login` (interativo, uma vez) |
| clawhub auth | Publicar no OpenClaw | `clawhub login` (interativo, uma vez) |

> A auditoria do Gen Agent Trust Hub é apenas via web — cole a URL da skill em [ai.gendigital.com/agent-trust-hub](https://ai.gendigital.com/agent-trust-hub).

---

## Segurança

### Auditorias realizadas

| Ferramenta | Resultado | Verificado em | Detalhes |
|-----------|----------|--------------|---------|
| **Snyk** | badge ao vivo | contínuo | Badge acima reflete o scan mais recente — [importar repo no snyk.io](https://snyk.io/test/github/konecty/skills) para ativar |
| **Gen Agent Trust Hub** | ✅ PASS | 2026-06-17 | Sem prompt injection, payloads maliciosos ou riscos críticos de agente |
| **Socket** | ✅ PASS | 2026-06-17 | Supply chain limpa — sem dependências maliciosas ou comprometidas |

> Gen Agent Trust Hub e Socket são verificações manuais pontuais (ferramentas sem badge ao vivo). Snyk é o único com badge contínuo — requer que o repo esteja importado em [snyk.io](https://snyk.io).

Todas as scripts usam **Python stdlib apenas** — sem dependências de terceiros, eliminando a maior classe de riscos de supply chain.

### Como reproduzir as auditorias

```bash
# Gen Agent Trust Hub — web only
# Acesse https://ai.gendigital.com/agent-trust-hub e cole a URL do skill

# Socket — supply chain
npm i -g @socketsecurity/cli
socket login
socket scan create ./skills/konecty-data
socket scan create ./skills/konecty-meta
socket scan create ./skills/konecty-dev
socket ci

# Snyk Agent Scan
export SNYK_TOKEN=<seu-token>
uvx snyk-agent-scan@latest --skills                    # todas as skills
uvx snyk-agent-scan@latest ./skills/konecty-data       # skill específica
```

---

## Testes E2E

Uma suíte de testes dockerizada inicializa uma stack Konecty descartável e executa todos os subcomandos de ambas as skills operacionais via um pseudo-agente determinístico.

**Cobertura atual: 93%** (gate `--fail-under=90`). 472 testes passando + 1 xfail documentado.

### Início rápido

```bash
make e2e   # purge → up → wait → gate de cobertura → purge (sempre derruba a stack)
```

**Pré-requisitos:** Docker (para a stack) e `uv` (a suíte roda via `uv run`).

### O que é testado

| Suite | Descrição |
|-------|-----------|
| **konecty-data (live)** | Contra a imagem pública `konecty/konecty:3.8.10`: auth, modules, find, create, update |
| **konecty-data (mock)** | Paths que exigem endpoints ainda não publicados: query SQL, lookup, delete |
| **konecty-meta (mock)** | Todos os 11 subcomandos contra um mock fiel do contrato `/api/admin/meta/*` |
| **Security suite** | Credential fast-fail, 401 sem traceback, guards de delete/upload, OTP validation, injection payloads |
| **Intent router** | Roteador determinístico PT/EN de frases → skill-command (sem LLM, zero custo de API) |

### Targets Make

| Target | O que faz |
|--------|-----------|
| `make e2e` | Ciclo completo: purge → up → wait → cobertura → purge |
| `make e2e-up` | Sobe a stack e aguarda `/liveness` |
| `make e2e-down` | Para a stack (mantém volumes) |
| `make e2e-reset` | Para e **apaga volumes** — DB limpo + admin fresh no próximo boot |
| `make e2e-token` | Extrai o token admin dos logs do container |
| `make e2e-run` | Roda a suíte completa (sem gate de cobertura) |
| `make e2e-cov` | Roda com cobertura e o gate `≥90%` |
| `make e2e-sec` | Apenas a security suite |
| `make e2e-infer` | Apenas o intent router |

---

## Estrutura do repositório

```
skills/              # Skills da plataforma Konecty (uma pasta por skill com SKILL.md)
├── konecty-data/    # Operações de dados: auth, modules, find, create, update, delete, upload
├── konecty-meta/    # Metadados: document, list, view, access, pivot, hook, namespace, sync
└── konecty-dev/     # Advisory: SDKs Python/TS, REST API, hooks, filtros, receitas
installer/           # CLI konecty-skills (Python stdlib, uvx entry point)
e2e/                 # Docker Compose stack para testes (MongoDB + RabbitMQ + Konecty)
tests/e2e/           # Suíte de testes E2E (pseudo-agente + mocks + suítes)
.agents/skills/      # Skills externas instaladas via CLI (rastreadas em skills-lock.json)
.specs/              # Especificações SDD: projeto, análise de codebase, features
template/            # Template para criar novas skills
spec/                # Referência ao padrão Agent Skills
docs/                # Documentação, ADRs e changelog
```

---

## Desenvolvimento

### Comandos principais

```bash
make help            # lista todos os targets disponíveis
make setup           # aponta git para .githooks (execute uma vez após clonar)
make check           # gate offline: compila scripts + guard de shared-files + testes do instalador
make lint            # py_compile em todos os scripts das skills
make installer-test  # testes unitários do instalador (128 testes, stdlib, offline)
make validate        # gh skill publish --dry-run nas skills (valida SKILL.md)
make audit           # codebase-intelligence + codebase-security (gate de PR)
make e2e             # ciclo completo E2E
make clean           # remove __pycache__, .coverage e artefatos de cobertura
```

### Criando uma nova skill

1. Crie uma pasta em `skills/` com um nome curto em minúsculas.
2. Adicione `SKILL.md` com frontmatter YAML (`name` + `description`) e instruções em Markdown.
3. Scripts devem usar **Python stdlib apenas** — sem dependências externas.
4. Documente a mudança em `docs/changelog/YYYY-MM-DD_slug.md`.

Consulte o [template/SKILL.md](./template/SKILL.md) e siga o workflow do **skill-creator**.

### Invariante de shared-files

`scripts/auth.py` e `scripts/modules.py` são **byte-idênticos** em `konecty-data` e `konecty-meta`. Edite sempre os dois lados juntos — divergência é detectada pelo hook de pré-commit e pela GitHub Action `check-shared-files`.

### Gate de conclusão (antes de qualquer PR)

```bash
make check   # verificação offline
make audit   # intelligence + security (um veredicto fail bloqueia o PR)
```

---

## Publicação em marketplaces

Use `make publish` para publicar as três skills em todos os marketplaces de uma só vez, ou targets individuais por plataforma:

```bash
# Publicar em tudo (após gh auth login + clawhub login)
make publish VERSION=1.2.0 CHANGELOG="Descrição do que mudou"

# Por marketplace
make publish-gh       VERSION=1.2.0  # GitHub via gh skill
make publish-clawhub  VERSION=1.2.0 CHANGELOG="Fix de autenticação"
make publish-hermes                  # sem parâmetros extras
```

`VERSION` detecta automaticamente a última tag git (`git describe --tags`); passe explicitamente se quiser sobrescrever.

### skills.sh

Skills aparecem organicamente no [skills.sh](https://skills.sh) assim que o repositório é público no GitHub com um `SKILL.md` válido — não há passo de publicação separado. Para instalar:

```bash
npx skills add konecty/skills
```

### GitHub (gh skill)

```bash
gh auth login                           # autenticação única
make publish-gh VERSION=1.2.0           # publica as três skills
# ou manualmente:
cd skills/konecty-data && gh skill publish --fix
```

### OpenClaw (clawhub)

```bash
npm i -g clawhub
clawhub login                           # autenticação única
make publish-clawhub VERSION=1.2.0 CHANGELOG="Fix de autenticação"
# ou manualmente:
clawhub skill publish ./skills/konecty-data --slug konecty-data --version 1.2.0 --changelog "..."
clawhub skill publish ./skills/konecty-meta --slug konecty-meta --version 1.2.0 --changelog "..."
clawhub skill publish ./skills/konecty-dev  --slug konecty-dev  --version 1.2.0 --changelog "..."
```

### Hermes (NousResearch)

```bash
make publish-hermes                     # usa o GitHub como backend
# ou manualmente:
hermes skills publish skills/konecty-data --to github --repo konecty/skills
hermes skills publish skills/konecty-meta --to github --repo konecty/skills
hermes skills publish skills/konecty-dev  --to github --repo konecty/skills
```

### Anthropic/skills e tech-leads-club

Ambos os registros são curados via Pull Request. Faça fork do repositório, adicione a pasta da skill e abra um PR.

---

## Documentação

- [Desenvolvimento e contribuição](./docs/development.md)
- [Publicação em marketplaces](./docs/publishing.md)
- [Architecture Decision Records (ADR)](./docs/adr/README.md)
- [Changelog](./docs/changelog/README.md)
- [🇺🇸 English version](./README.en.md)

---

## Licença

Este projeto é licenciado sob a **GNU Affero General Public License v3.0 (AGPL-3.0)**. Veja o arquivo [`LICENSE`](./LICENSE) para o texto completo.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Desenvolvido com ❤️ pela equipe [Konecty](https://konecty.com).
