<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/logo-horizontal-white.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/logo-horizontal-color.png">
  <img alt="Konecty" src="docs/logo-horizontal-color.png" width="300">
</picture>

# KonectySkills

> **Instale, informe a URL da sua empresa, faça login no navegador — e converse com seu CRM.**

Skills MCP-first para agentes de IA como Claude Code. A execução acontece nos **servidores MCP do próprio Konecty** (`/mcp` e `/admin-mcp`); as skills ensinam o agente a usá-los corretamente — qual tool chamar, em que ordem e com quais guardrails. Nenhum script HTTP local, nenhuma edição de arquivo `.env`.

[![Known Vulnerabilities](https://snyk.io/test/github/konecty/skills/badge.svg)](https://snyk.io/test/github/konecty/skills)
[![agentskills.io](https://img.shields.io/badge/agentskills.io-compatível-6366f1?style=flat-square)](https://agentskills.io)
[![skills.sh](https://img.shields.io/badge/skills.sh-compatível-6366f1?style=flat-square)](https://skills.sh)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue?style=flat-square)](./LICENSE)

**[🇺🇸 English version →](./README.en.md)**

---

## Instalação rápida

```bash
uvx --from git+https://github.com/konecty/skills konecty-skills install
```

O instalador pergunta a URL do Konecty da sua empresa, valida (`https` + probe do
`/.well-known/oauth-protected-resource`), registra o servidor MCP `konecty`
(`<url>/mcp`, escopo de usuário no Claude Code), oferece o caminho admin e copia as
4 skills. No primeiro uso, o Claude Code abre o navegador para o login OAuth — e pronto:

> "quais oportunidades abertas do cliente X?"

**Pré-requisitos:**

- Python 3.9+ e `uv` (`pip install uv` ou `brew install uv`)
- Um Konecty com MCP habilitado (veja [Requisitos do servidor](#requisitos-do-servidor-konecty))
- Claude Code (sem o CLI `claude`, o instalador imprime os comandos `claude mcp add` para execução manual)

### Comandos do instalador

| Comando | O que faz |
|---------|-----------|
| `install` | URL → valida → registra MCP `konecty` → caminho admin opcional (OTP → `konecty-admin` com header Bearer) → copia as 4 skills |
| `configure` | Somente o token admin interino: login OTP → `~/.konecty/.env` + entrada MCP `konecty-admin` |
| `status` | Skills instaladas, engines, registro MCP e presença do token admin |
| `update` | Rebaixa as skills com proteção SHA-256 (nunca sobrescreve edições locais) |
| `doctor` | URL alcançável, well-known + audiência (`PLATFORM_MCP_RESOURCE_URL`), servidores MCP registrados, validade do token admin |
| `uninstall` | Remove as skills (`--purge` remove também credenciais e entradas MCP) |

Re-executar `install` é idempotente: entradas `konecty*` existentes são substituídas
(remove + add), nunca duplicadas; arquivos pré-existentes do usuário nunca são tocados.

### Configuração conversacional

Prefere fazer tudo dentro do Claude Code? A skill **konecty-setup** cobre o mesmo fluxo
por conversa: primeira configuração, troca de empresa/URL, re-autenticação e
troubleshooting de habilitação ("configurar konecty", "conectar meu CRM").

---

## Instalação via plugin (sem terminal)

Sem `uv`, sem terminal, sem copiar pastas. Instale as 4 skills direto pela interface do
Claude Code, em três passos:

1. **Adicione o marketplace** — no Claude Code, rode:

   ```
   /plugin marketplace add konecty/skills
   ```

2. **Abra o gerenciador** — rode `/plugin`, vá até a aba **Discover** e selecione o plugin
   **Konecty CRM Skills** (`konecty-crm`).

3. **Instale** — confirme o escopo (usuário / projeto / local) e pronto. Rode
   `/reload-plugins` para ativar. As 4 skills ficam disponíveis com namespace
   `konecty-crm:` (`konecty-crm:konecty-data`, `konecty-crm:konecty-meta`,
   `konecty-crm:konecty-setup`, `konecty-crm:konecty-dev`).

**Depois de instalar, só diga ao Claude a URL do seu Konecty** — por exemplo
_"configurar konecty, minha empresa é https://suaempresa.konecty.com"_. A skill
**konecty-setup** cuida do resto: registra o servidor MCP da sua empresa e abre o login
OAuth no navegador. O plugin **não** embute nenhuma URL de servidor — cada cliente tem a
sua, então o registro MCP é sempre conversacional e por empresa.

> Prefere o terminal? A [instalação rápida via `uvx`](#instalação-rápida) continua
> disponível e faz exatamente o mesmo registro MCP.

---

## As quatro skills

| Skill | Servidor MCP | O que ensina |
|-------|--------------|--------------|
| **konecty-data** | `konecty` (`/mcp`) | Conversas de dados do CRM: descoberta de módulos/campos, busca com filtros validados (`filter_build`), queries cross-module (`query_json`), criação, atualização fetch-first (`_updatedAt`), deleção com preview + confirmação, arquivos |
| **konecty-meta** | `konecty-admin` (`/admin-mcp`) | Administração de metadados: esquemas de documento, listas, views, perfis de acesso, pivots, hooks (validate → upsert), Namespace (incl. flags MCP), doctor e sync repo↔banco |
| **konecty-setup** | — | Setup e reconfiguração conversacional dos servidores MCP; matriz de troubleshooting |
| **konecty-dev** | — *(advisory)* | Código de integração com o Konecty: SDKs oficiais (Python/TS), REST API, hooks, receitas |

As skills **não executam HTTP** — elas nomeiam as tools MCP (`records_find`,
`query_json`, `meta_document_upsert`, …) e o Konecty executa.

---

## Autenticação

- **Usuário (`konecty`)**: OAuth nativo do Claude Code — DCR → authorize + PKCE →
  token, tudo no navegador. Escopos `read` (+ `write` quando o namespace habilita
  `mcpUserWriteEnabled`).
- **Admin (`konecty-admin`), caminho interino**: login OTP → `authTokenId` registrado
  como header `Authorization: Bearer` na entrada MCP. Quando expirar, `konecty-setup`
  guia o re-login.
- **Admin, caminho alvo (OAuth)**: Konecty concede o escopo `admin` no consentimento
  para **clientes confiáveis** (provisionados via `OAUTH_CLIENTS_JSON`;
  [konecty/Konecty#453](https://github.com/konecty/Konecty/pull/453)) quando o usuário
  tem `admin: true`. A troca é apenas re-registro do servidor MCP — nada muda nas skills.

---

## Requisitos do servidor Konecty

O Konecty da sua empresa precisa expor os servidores MCP (release com
`/mcp` + `/admin-mcp`) e habilitar no **Namespace**:

| Flag | Efeito |
|------|--------|
| `mcpUserEnabled` | Habilita `/mcp` (503 quando desligado) |
| `mcpAdminEnabled` | Habilita `/admin-mcp` |
| `mcpRoleIds` | Allowlist de roles com acesso ao MCP — **deny-by-default** (403 `mcp_access_denied` quando vazio) |
| `mcpUserWriteEnabled` | Escrita via MCP (padrão: somente leitura — writes retornam `insufficient_scope`) |

Deploy: `PLATFORM_MCP_RESOURCE_URL` deve ser exatamente a URL pública do `/mcp`
(validação de audiência dos tokens OAuth). Instâncias Konecty **sem MCP** não são
suportadas por esta versão — use a última tag script-based deste repositório.

---

## Testes E2E

A suíte E2E sobe uma stack Konecty descartável **construída do código-fonte local**
(worktree de `../Konecty`) e dirige as tools MCP documentadas com um cliente JSON-RPC
stdlib — cada fluxo que as skills descrevem tem ≥1 caso (find, query, create, update,
delete preview+confirm, upload, OTP, meta read/upserts/hook/doctor/sync, guard errors
e os cenários OAuth incluindo o escopo admin de cliente confiável).

```bash
make e2e   # purge → build+up → wait → bootstrap flags MCP → suítes → purge
```

**Pré-requisitos:** Docker, `uv`, Node 24 + Yarn (build do dist) e o repositório
Konecty clonado em `../Konecty`.

| Target | O que faz |
|--------|-----------|
| `make e2e` | Ciclo completo autocontido (sempre derruba a stack no final) |
| `make e2e-src` | Cria o worktree `e2e/.konecty-src` e faz o build do `dist/` |
| `make e2e-up` | Build da imagem + sobe a stack + aguarda + habilita flags MCP |
| `make e2e-down` / `e2e-reset` | Para a stack (reset apaga volumes — admin fresh no próximo boot) |
| `make e2e-token` | Extrai o token admin dos logs do container |
| `make e2e-run` | Roda as suítes contra uma stack já de pé |

---

## Estrutura do repositório

```
skills/              # As 4 skills (uma pasta por skill com SKILL.md + references/)
├── konecty-data/    # Guia do MCP de usuário (dados)
├── konecty-meta/    # Guia do MCP admin (metadados)
├── konecty-setup/   # Setup conversacional + troubleshooting
└── konecty-dev/     # Advisory: SDKs, REST API, hooks, receitas
installer/           # CLI konecty-skills (Python stdlib, uvx entry point)
e2e/                 # Stack Docker (compose + bootstrap) para os testes E2E
tests/e2e/           # Suítes E2E (cliente MCP stdlib + pytest)
.specs/              # Especificações SDD: projeto, análise de codebase, features
template/            # Template para criar novas skills
spec/                # Referência ao padrão Agent Skills
docs/                # Documentação, ADRs e changelog
```

---

## Desenvolvimento

```bash
make help            # lista todos os targets
make setup           # aponta git para .githooks (uma vez após clonar)
make check           # gate offline: py_compile + testes do instalador
make validate        # gh skill publish --dry-run (valida SKILL.md)
make audit           # codebase-intelligence + codebase-security (gate de PR)
make e2e             # ciclo E2E completo
```

### Criando uma nova skill

1. Crie uma pasta em `skills/` com um nome curto em minúsculas.
2. Adicione `SKILL.md` com frontmatter YAML (`name` + `description`) e instruções em Markdown.
3. Skills são **guias procedurais** — a execução fica nos servidores MCP do Konecty.
   Se uma capacidade falta no MCP, a lacuna vira feature upstream no Konecty, nunca
   um script local (ADR).
4. Documente a mudança em `docs/changelog/YYYY-MM-DD_slug.md`.

Consulte o [template/SKILL.md](./template/SKILL.md) e siga o workflow do **skill-creator**.

### Gate de conclusão (antes de qualquer PR)

```bash
make check   # verificação offline
make audit   # intelligence + security (um veredicto fail bloqueia o PR)
```

---

## Publicação em marketplaces

```bash
make publish VERSION=1.2.0 CHANGELOG="Descrição do que mudou"   # todos
make publish-gh       VERSION=1.2.0                              # GitHub via gh skill
make publish-clawhub  VERSION=1.2.0 CHANGELOG="..."              # OpenClaw
make publish-hermes                                              # Hermes (NousResearch)
```

Skills aparecem organicamente no [skills.sh](https://skills.sh) assim que o repositório
é público com `SKILL.md` válido (`npx skills add konecty/skills`). Anthropic/skills e
tech-leads-club são curados via Pull Request.

---

## Segurança

- Instalador e suíte E2E usam **Python stdlib apenas** — sem dependências de terceiros.
- As skills não contêm código executável: `grep -rE "urllib|http.client" skills/konecty-data skills/konecty-meta` → vazio.
- Auditorias: Snyk (badge acima), Socket (supply chain) e Gen Agent Trust Hub
  ([ai.gendigital.com/agent-trust-hub](https://ai.gendigital.com/agent-trust-hub)).

---

## Documentação

- [Architecture Decision Records (ADR)](./docs/adr/README.md)
- [Changelog](./docs/changelog/README.md)
- [🇺🇸 English version](./README.en.md)

---

## Licença

Este projeto é licenciado sob a **GNU Affero General Public License v3.0 (AGPL-3.0)**.
Veja o arquivo [`LICENSE`](./LICENSE) para o texto completo.

Desenvolvido com ❤️ pela equipe [Konecty](https://konecty.com).
