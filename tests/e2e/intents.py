"""Deterministic intent router — no LLM required.

Maps a natural-language phrase (Portuguese or English) to a concrete Konecty
skill command via keyword/regex matching.  Designed for use in the e2e harness
so tests can drive skill scripts without talking to an LLM.

Usage::

    from tests.e2e.intents import route, INTENTS

    skill, script, argv = route("buscar registros", document="Contact", limit="10")
    # => ("konecty-data", "find", ["find", "Contact", "--limit", "10"])

Raises ``ValueError`` when no intent matches the phrase.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Intent:
    """Describes a single intent family."""

    phrase: str                  # canonical example phrase (for documentation)
    skill: str                   # "konecty-data" | "konecty-meta"
    script: str                  # module name under skills/<skill>/scripts/
    argv_template: list[str]     # may contain "{slot}" placeholders
    # compiled patterns — set during module init, not in the constructor
    _patterns: list[re.Pattern] = field(default_factory=list, init=False, repr=False)


# ---------------------------------------------------------------------------
# Intent catalogue
# ---------------------------------------------------------------------------
# Each entry carries:
#   phrase         — canonical human-readable description
#   skill          — which skill owns this command
#   script         — Python script module name (no .py)
#   argv_template  — argv list; "{slot}" tokens are filled by route()
#
# The _KEYWORDS dict maps each Intent (by index, inserted during _build()) to
# a list of (pattern, phrase) pairs that trigger it.

INTENTS: list[Intent] = [
    # --- konecty-data: modules ---
    Intent(
        phrase="listar módulos",
        skill="konecty-data",
        script="modules",
        argv_template=["list"],
    ),
    Intent(
        phrase="ver campos",
        skill="konecty-data",
        script="modules",
        argv_template=["fields", "{document}"],
    ),
    Intent(
        phrase="buscar módulos",
        skill="konecty-data",
        script="modules",
        argv_template=["search", "{term}"],
    ),
    # --- konecty-data: find ---
    Intent(
        phrase="buscar registros",
        skill="konecty-data",
        script="find",
        argv_template=["find", "{document}", "--limit", "{limit}"],
    ),
    Intent(
        phrase="consulta cross-module",
        skill="konecty-data",
        script="find",
        argv_template=["query", "{document}"],
    ),
    Intent(
        phrase="rodar sql",
        skill="konecty-data",
        script="find",
        argv_template=["sql", "{sql}"],
    ),
    # --- konecty-data: create ---
    Intent(
        phrase="criar contato",
        skill="konecty-data",
        script="create",
        argv_template=["create", "{document}", "--data", "{data}"],
    ),
    Intent(
        phrase="fazer lookup",
        skill="konecty-data",
        script="create",
        argv_template=["lookup", "{document}", "{term}"],
    ),
    # --- konecty-data: update ---
    Intent(
        phrase="atualizar registro",
        skill="konecty-data",
        script="update",
        argv_template=["patch", "{document}", "{term}", "--data", "{data}"],
    ),
    Intent(
        phrase="buscar antes de atualizar",
        skill="konecty-data",
        script="update",
        argv_template=["fetch", "{document}", "{term}"],
    ),
    # --- konecty-data: delete ---
    Intent(
        phrase="excluir registro",
        skill="konecty-data",
        script="delete",
        argv_template=["delete", "{document}", "{term}", "--confirm"],
    ),
    Intent(
        phrase="visualizar antes de excluir",
        skill="konecty-data",
        script="delete",
        argv_template=["preview", "{document}", "{term}"],
    ),
    # --- konecty-data: upload ---
    Intent(
        phrase="fazer upload de arquivo",
        skill="konecty-data",
        script="upload",
        argv_template=["upload", "{document}", "{record_id}", "{field}", "{file}"],
    ),
    Intent(
        phrase="listar arquivos",
        skill="konecty-data",
        script="upload",
        argv_template=["list", "{document}", "{record_id}", "{field}"],
    ),
    Intent(
        phrase="info do arquivo",
        skill="konecty-data",
        script="upload",
        argv_template=["info", "{document}", "{record_id}", "{field}"],
    ),
    # --- konecty-meta: meta_read ---
    Intent(
        phrase="listar metadados",
        skill="konecty-meta",
        script="meta_read",
        argv_template=["list"],
    ),
    Intent(
        phrase="obter metadado",
        skill="konecty-meta",
        script="meta_read",
        argv_template=["get", "{name}"],
    ),
    Intent(
        phrase="tipos de metadados",
        skill="konecty-meta",
        script="meta_read",
        argv_template=["types"],
    ),
    # --- konecty-meta: meta_document ---
    Intent(
        phrase="ver documento meta",
        skill="konecty-meta",
        script="meta_document",
        argv_template=["show", "{document}"],
    ),
    Intent(
        phrase="ver campos do documento",
        skill="konecty-meta",
        script="meta_document",
        argv_template=["fields", "{document}"],
    ),
    Intent(
        phrase="adicionar campo ao documento",
        skill="konecty-meta",
        script="meta_document",
        argv_template=["add-field", "{document}", "--data", "{data}"],
    ),
    Intent(
        phrase="remover campo do documento",
        skill="konecty-meta",
        script="meta_document",
        argv_template=["remove-field", "{document}", "{field}"],
    ),
    Intent(
        phrase="atualizar campo do documento",
        skill="konecty-meta",
        script="meta_document",
        argv_template=["update-field", "{document}", "{field}", "--data", "{data}"],
    ),
    # --- konecty-meta: meta_list ---
    Intent(
        phrase="ver lista meta",
        skill="konecty-meta",
        script="meta_list",
        argv_template=["show", "{document}"],
    ),
    Intent(
        phrase="ver colunas da lista",
        skill="konecty-meta",
        script="meta_list",
        argv_template=["columns", "{document}"],
    ),
    # --- konecty-meta: meta_view ---
    Intent(
        phrase="ver view meta",
        skill="konecty-meta",
        script="meta_view",
        argv_template=["show", "{document}"],
    ),
    Intent(
        phrase="ver visuais da view",
        skill="konecty-meta",
        script="meta_view",
        argv_template=["visuals", "{document}"],
    ),
    # --- konecty-meta: meta_access ---
    Intent(
        phrase="ver perfil de acesso",
        skill="konecty-meta",
        script="meta_access",
        argv_template=["show", "{document}"],
    ),
    Intent(
        phrase="ver permissões de acesso",
        skill="konecty-meta",
        script="meta_access",
        argv_template=["permissions", "{document}"],
    ),
    # --- konecty-meta: meta_hook ---
    Intent(
        phrase="criar hook",
        skill="konecty-meta",
        script="meta_hook",
        argv_template=["scaffold", "{hook}"],
    ),
    Intent(
        phrase="listar hooks",
        skill="konecty-meta",
        script="meta_hook",
        argv_template=["list"],
    ),
    Intent(
        phrase="ver hook",
        skill="konecty-meta",
        script="meta_hook",
        argv_template=["show", "{hook}"],
    ),
    Intent(
        phrase="validar hook",
        skill="konecty-meta",
        script="meta_hook",
        argv_template=["validate", "{hook}"],
    ),
    # --- konecty-meta: meta_namespace ---
    Intent(
        phrase="ver namespace",
        skill="konecty-meta",
        script="meta_namespace",
        argv_template=["show"],
    ),
    # --- konecty-meta: meta_pivot ---
    Intent(
        phrase="ver pivot",
        skill="konecty-meta",
        script="meta_pivot",
        argv_template=["show", "{document}"],
    ),
    # --- konecty-meta: meta_doctor ---
    Intent(
        phrase="validar integridade",
        skill="konecty-meta",
        script="meta_doctor",
        argv_template=["check"],
    ),
    Intent(
        phrase="verificar filas",
        skill="konecty-meta",
        script="meta_doctor",
        argv_template=["check-queues"],
    ),
    # --- konecty-meta: meta_sync ---
    Intent(
        phrase="planejar sincronização",
        skill="konecty-meta",
        script="meta_sync",
        argv_template=["plan"],
    ),
    Intent(
        phrase="aplicar sincronização",
        skill="konecty-meta",
        script="meta_sync",
        argv_template=["apply"],
    ),
    Intent(
        phrase="diff de sincronização",
        skill="konecty-meta",
        script="meta_sync",
        argv_template=["diff"],
    ),
    # --- konecty-meta: meta_remove ---
    Intent(
        phrase="remover módulo",
        skill="konecty-meta",
        script="meta_remove",
        argv_template=["plan", "{document}"],
    ),
]


# ---------------------------------------------------------------------------
# Trigger phrases for each intent
# Ordered from most-specific to least-specific within overlapping groups so the
# first match wins correctly when iterating INTENTS in order.
# ---------------------------------------------------------------------------
_TRIGGERS: dict[int, list[str]] = {
    # modules
    0: [
        "listar módulos", "listar modulos", "list modules", "show modules",
        "módulos disponíveis", "modulos disponiveis", "available modules",
        "quais módulos", "quais modulos", "which modules",
    ],
    1: [
        "ver campos", "show fields", "campos do", "fields of", "fields for",
        "exibir campos", "display fields", "listar campos", "list fields",
    ],
    2: [
        "buscar módulos", "search modules", "buscar modulos", "procurar módulos",
        "find modules", "search for modules",
    ],
    # find
    3: [
        "buscar registros", "find records", "buscar contatos", "find contacts",
        "pesquisar registros", "search records", "listar registros", "list records",
        "buscar em", "find in", "retrieve records", "get records",
    ],
    4: [
        "consulta cross-module", "cross module query", "cross-module query",
        "consulta cruzada", "cross module", "query across modules",
    ],
    5: [
        "rodar sql", "run sql", "executar sql", "execute sql",
        "sql query", "consulta sql", "run a sql",
    ],
    # create
    6: [
        "criar contato", "create a contact", "create contact", "novo contato",
        "new contact", "criar registro", "create record", "criar um", "create a",
        "inserir registro", "insert record", "adicionar registro", "add record",
    ],
    7: [
        "fazer lookup", "do lookup", "lookup", "busca lookup", "lookup search",
    ],
    # update
    8: [
        "atualizar registro", "update record", "atualizar contato", "update contact",
        "modificar registro", "modify record", "editar registro", "edit record",
        "patch record", "atualizar um", "update a",
    ],
    9: [
        "buscar antes de atualizar", "fetch before update", "fetch record",
        "buscar registro para atualizar", "get record for update",
    ],
    # delete
    10: [
        "excluir registro", "delete record", "deletar registro", "remover registro",
        "remove record", "apagar registro", "excluir contato", "delete contact",
        "excluir um", "delete a",
    ],
    11: [
        "visualizar antes de excluir", "preview before delete", "preview delete",
        "preview record", "visualizar registro",
    ],
    # upload
    12: [
        "fazer upload de arquivo", "upload file", "upload a file", "enviar arquivo",
        "attach file", "anexar arquivo",
    ],
    13: [
        "listar arquivos", "list files", "list attachments", "listar anexos",
    ],
    14: [
        "info do arquivo", "file info", "informações do arquivo", "attachment info",
    ],
    # meta_read
    15: [
        "listar metadados", "list metadata", "list meta", "listar meta",
        "all metadata", "todos os metadados",
    ],
    16: [
        "obter metadado", "get metadata", "get meta", "obter meta",
        "fetch metadata", "retrieve metadata",
    ],
    17: [
        "tipos de metadados", "metadata types", "meta types", "tipos de meta",
    ],
    # meta_document
    18: [
        "ver documento meta", "show meta document", "show document meta",
        "ver meta do documento", "exibir documento meta",
    ],
    19: [
        "ver campos do documento", "show document fields", "campos do documento",
        "document fields", "fields of document",
    ],
    20: [
        "adicionar campo ao documento", "add field to document", "add field",
        "adicionar campo", "new field",
    ],
    21: [
        "remover campo do documento", "remove field from document", "remove field",
        "remover campo",
    ],
    22: [
        "atualizar campo do documento", "update field in document", "update field",
        "atualizar campo", "modify field",
    ],
    # meta_list
    23: [
        "ver lista meta", "show meta list", "exibir lista meta",
    ],
    24: [
        "ver colunas da lista", "show list columns", "colunas da lista",
        "list columns",
    ],
    # meta_view
    25: [
        "ver view meta", "show meta view", "exibir view meta",
    ],
    26: [
        "ver visuais da view", "show view visuals", "visuais da view",
        "view visuals",
    ],
    # meta_access
    27: [
        "ver perfil de acesso", "show access profile", "perfil de acesso",
        "access profile",
    ],
    28: [
        "ver permissões de acesso", "show access permissions", "permissões de acesso",
        "access permissions",
    ],
    # meta_hook
    29: [
        "criar hook", "scaffold hook", "create hook", "novo hook", "new hook",
        "gerar hook", "generate hook",
    ],
    30: [
        "listar hooks", "list hooks", "show hooks", "hooks disponíveis",
    ],
    31: [
        "ver hook", "show hook", "exibir hook",
    ],
    32: [
        "validar hook", "validate hook", "verificar hook",
    ],
    # meta_namespace
    33: [
        "ver namespace", "show namespace", "exibir namespace", "namespace config",
        "configuração global", "global config",
    ],
    # meta_pivot
    34: [
        "ver pivot", "show pivot", "exibir pivot",
    ],
    # meta_doctor
    35: [
        "validar integridade", "check integrity", "verificar integridade",
        "validate integrity", "doctor check", "metadata integrity",
    ],
    36: [
        "verificar filas", "check queues", "check-queues", "filas do sistema",
        "system queues",
    ],
    # meta_sync
    37: [
        "planejar sincronização", "plan sync", "sync plan", "planejar sync",
        "plan synchronization",
    ],
    38: [
        "aplicar sincronização", "apply sync", "sync apply", "aplicar sync",
        "apply synchronization",
    ],
    39: [
        "diff de sincronização", "sync diff", "diff sync", "diferença de sync",
        "synchronization diff",
    ],
    # meta_remove
    40: [
        "remover módulo", "remove module", "remover modulo", "delete module",
        "excluir módulo",
    ],
}

# ---------------------------------------------------------------------------
# Build compiled patterns (once, at import time)
# ---------------------------------------------------------------------------
_COMPILED: list[tuple[re.Pattern, int]] = []


def _build() -> None:
    """Compile trigger phrases into case-insensitive regex patterns.

    Longer trigger phrases are placed first so that more-specific patterns
    win over shorter, overlapping ones (e.g. "ver campos do documento" must
    beat "ver campos").
    """
    raw: list[tuple[str, re.Pattern, int]] = []
    for intent_idx, phrases in _TRIGGERS.items():
        for phrase in phrases:
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            raw.append((phrase, pattern, intent_idx))
    # Sort by descending trigger length so most-specific patterns are tried first
    raw.sort(key=lambda t: len(t[0]), reverse=True)
    for _phrase, pattern, intent_idx in raw:
        _COMPILED.append((pattern, intent_idx))


_build()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def route(phrase: str, **slots: str) -> tuple[str, str, list[str]]:
    """Match *phrase* (case-insensitive) to an Intent and return
    ``(skill, script, argv)``.

    ``slots`` are substituted into ``argv_template`` for every ``{slot}``
    placeholder found in the template.  Unknown placeholders that have no
    matching slot key are left as-is (the test suite can then assert they
    are present exactly as typed).

    Raises ``ValueError`` if no intent matches.
    """
    normalized = phrase.strip()
    for pattern, intent_idx in _COMPILED:
        if pattern.search(normalized):
            intent = INTENTS[intent_idx]
            argv = [
                slots.get(tok[1:-1], tok) if tok.startswith("{") and tok.endswith("}")
                else tok
                for tok in intent.argv_template
            ]
            return intent.skill, intent.script, argv
    raise ValueError(f"no intent matched: {phrase!r}")
