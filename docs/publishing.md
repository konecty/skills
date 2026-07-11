# Publicando no marketplace

Guia passo a passo para publicar as skills nos principais marketplaces. Execute `make check` e `make audit` antes de qualquer publicação.

---

## Pré-requisito: validar antes de publicar

```bash
make check    # lint + shared-files + testes do instalador (offline)
make validate # gh skill publish --dry-run nas três skills
make audit    # intelligence + security (veredicto fail bloqueia)
```

---

## GitHub (gh skill) — agentskills.io

**Auth necessária:** `gh auth login` (uma vez por máquina).

```bash
gh auth login
make publish-gh VERSION=1.2.0
```

O que acontece por baixo:
```bash
cd skills/konecty-data && gh skill publish --fix
cd skills/konecty-meta && gh skill publish --fix
cd skills/konecty-dev  && gh skill publish --fix
```

`--fix` auto-corrige metadados menores (slug, campos opcionais). Use `--dry-run` para validar sem publicar.

> **Nota:** o erro `name does not match directory "."` é um quirk do ambiente do `gh skill` — não impede a publicação.

---

## skills.sh

**Sem passo de publicação.** Skills aparecem organicamente no [skills.sh](https://skills.sh) assim que o repositório é público no GitHub com um `SKILL.md` válido.

Para verificar que as skills foram indexadas:
```bash
npx skills add konecty/skills   # instala e confirma que foram encontradas
npx skills list
```

---

## OpenClaw (clawhub)

**Auth necessária:** `npm i -g clawhub` + `clawhub login` (uma vez por máquina).

```bash
npm i -g clawhub
clawhub login
make publish-clawhub VERSION=1.2.0 CHANGELOG="O que mudou nessa versão"
```

O que acontece por baixo:
```bash
clawhub skill publish ./skills/konecty-data --slug konecty-data --version 1.2.0 --changelog "..."
clawhub skill publish ./skills/konecty-meta --slug konecty-meta --version 1.2.0 --changelog "..."
clawhub skill publish ./skills/konecty-dev  --slug konecty-dev  --version 1.2.0 --changelog "..."
```

> **Nota:** O clawhub roda VirusTotal em cada publicação. As variáveis de ambiente e binários declarados no `SKILL.md` devem corresponder exatamente ao que o código usa.

---

## Hermes (NousResearch)

**Sem auth separada** — usa o GitHub como backend.

```bash
make publish-hermes
```

O que acontece por baixo:
```bash
hermes skills publish skills/konecty-data --to github --repo konecty/skills
hermes skills publish skills/konecty-meta --to github --repo konecty/skills
hermes skills publish skills/konecty-dev  --to github --repo konecty/skills
```

Outros usuários instalam via:
```bash
hermes skills tap add konecty/skills
hermes skills install konecty-data
hermes skills install konecty-meta
hermes skills install konecty-dev
```

---

## Anthropic/skills e tech-leads-club

Ambos os registros são **curados via Pull Request** — não há CLI de publicação.

1. Fork do repositório de destino
2. Copie a pasta da skill para dentro do fork
3. Abra um PR seguindo o template do repositório
4. Aguarde revisão do mantenedor

---

## Publicar em tudo de uma vez

```bash
# Requer: gh auth login + clawhub login
make publish VERSION=1.2.0 CHANGELOG="Descrição do que mudou"
```

Ordem de execução: `validate` → `publish-gh` → `publish-clawhub` → `publish-hermes`.

---

## Snyk (badge ao vivo)

Para ativar o badge de vulnerabilidades contínuo no README:

1. Acesse [snyk.io](https://snyk.io) e faça login com o GitHub
2. **Add project** → selecione o repo `konecty/skills`
3. O badge `https://snyk.io/test/github/konecty/skills/badge.svg` passa a refletir scans reais automaticamente

---

## Auditorias manuais (sem badge ao vivo)

### Gen Agent Trust Hub
1. Acesse [ai.gendigital.com/agent-trust-hub](https://ai.gendigital.com/agent-trust-hub)
2. Cole a URL de uma das skills (ex: `https://github.com/konecty/skills/tree/main/skills/konecty-data`)
3. Atualize a data em `docs/publishing.md` e na seção de segurança do README após cada verificação

### Socket
```bash
npm i -g @socketsecurity/cli
socket login
socket scan create ./skills/konecty-data
socket scan create ./skills/konecty-meta
socket scan create ./skills/konecty-dev
socket ci
```
Atualize a data no README após cada verificação.

### Snyk Agent Scan (especializado para agentes)
```bash
export SNYK_TOKEN=<seu-token>   # app.snyk.io/account
uvx snyk-agent-scan@latest --skills
```
