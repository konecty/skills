"""Pure routing tests for the intent router.

No live server or credentials needed — every assertion is about the
deterministic mapping of a phrase to (skill, script, argv).

Run with::

    python3 -m pytest tests/e2e/test_inference.py -q
"""

from __future__ import annotations

import pytest
from pathlib import Path

from tests.e2e.intents import INTENTS, route

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"


def _script_file(skill: str, script: str) -> Path:
    return SKILLS_DIR / skill / "scripts" / f"{script}.py"


# ---------------------------------------------------------------------------
# 1. Each intent family routes correctly for both its PT and EN trigger phrase
# ---------------------------------------------------------------------------

# fmt: off
_INTENT_ROUTING_CASES: list[tuple[str, str, str, list[str]]] = [
    # (phrase, expected_skill, expected_script, expected_argv_fragment)
    # --- PT triggers ---
    ("criar contato",              "konecty-data",  "create",        ["create"]),
    ("buscar registros",           "konecty-data",  "find",          ["find"]),
    ("consulta cross-module",      "konecty-data",  "find",          ["query"]),
    ("rodar sql",                  "konecty-data",  "find",          ["sql"]),
    ("atualizar registro",         "konecty-data",  "update",        ["patch"]),
    ("excluir registro",           "konecty-data",  "delete",        ["delete"]),
    ("listar módulos",             "konecty-data",  "modules",       ["list"]),
    ("ver campos",                 "konecty-data",  "modules",       ["fields"]),
    ("listar metadados",           "konecty-meta",  "meta_read",     ["list"]),
    ("ver documento meta",         "konecty-meta",  "meta_document", ["show"]),
    ("validar integridade",        "konecty-meta",  "meta_doctor",   ["check"]),
    ("criar hook",                 "konecty-meta",  "meta_hook",     ["scaffold"]),
    ("planejar sincronização",     "konecty-meta",  "meta_sync",     ["plan"]),
    ("aplicar sincronização",      "konecty-meta",  "meta_sync",     ["apply"]),
    ("diff de sincronização",      "konecty-meta",  "meta_sync",     ["diff"]),
    ("remover módulo",             "konecty-meta",  "meta_remove",   ["plan"]),
    ("ver namespace",              "konecty-meta",  "meta_namespace",["show"]),
    ("ver pivot",                  "konecty-meta",  "meta_pivot",    ["show"]),
    ("verificar filas",            "konecty-meta",  "meta_doctor",   ["check-queues"]),
    ("listar hooks",               "konecty-meta",  "meta_hook",     ["list"]),
    ("ver lista meta",             "konecty-meta",  "meta_list",     ["show"]),
    ("ver colunas da lista",       "konecty-meta",  "meta_list",     ["columns"]),
    ("ver view meta",              "konecty-meta",  "meta_view",     ["show"]),
    ("ver visuais da view",        "konecty-meta",  "meta_view",     ["visuals"]),
    ("ver perfil de acesso",       "konecty-meta",  "meta_access",   ["show"]),
    ("ver permissões de acesso",   "konecty-meta",  "meta_access",   ["permissions"]),
    ("fazer upload de arquivo",    "konecty-data",  "upload",        ["upload"]),
    ("listar arquivos",            "konecty-data",  "upload",        ["list"]),
    ("info do arquivo",            "konecty-data",  "upload",        ["info"]),
    ("buscar antes de atualizar",  "konecty-data",  "update",        ["fetch"]),
    ("visualizar antes de excluir","konecty-data",  "delete",        ["preview"]),
    ("obter metadado",             "konecty-meta",  "meta_read",     ["get"]),
    ("tipos de metadados",         "konecty-meta",  "meta_read",     ["types"]),
    ("adicionar campo ao documento","konecty-meta", "meta_document", ["add-field"]),
    ("remover campo do documento", "konecty-meta",  "meta_document", ["remove-field"]),
    ("atualizar campo do documento","konecty-meta", "meta_document", ["update-field"]),
    ("ver campos do documento",    "konecty-meta",  "meta_document", ["fields"]),
    ("fazer lookup",               "konecty-data",  "create",        ["lookup"]),
    ("buscar módulos",             "konecty-data",  "modules",       ["search"]),
    ("ver hook",                   "konecty-meta",  "meta_hook",     ["show"]),
    ("validar hook",               "konecty-meta",  "meta_hook",     ["validate"]),
    # --- EN triggers ---
    ("create a contact",           "konecty-data",  "create",        ["create"]),
    ("find records",               "konecty-data",  "find",          ["find"]),
    ("cross module query",         "konecty-data",  "find",          ["query"]),
    ("run sql",                    "konecty-data",  "find",          ["sql"]),
    ("update record",              "konecty-data",  "update",        ["patch"]),
    ("delete record",              "konecty-data",  "delete",        ["delete"]),
    ("list modules",               "konecty-data",  "modules",       ["list"]),
    ("show fields",                "konecty-data",  "modules",       ["fields"]),
    ("list metadata",              "konecty-meta",  "meta_read",     ["list"]),
    ("show meta document",         "konecty-meta",  "meta_document", ["show"]),
    ("check integrity",            "konecty-meta",  "meta_doctor",   ["check"]),
    ("scaffold hook",              "konecty-meta",  "meta_hook",     ["scaffold"]),
    ("plan sync",                  "konecty-meta",  "meta_sync",     ["plan"]),
    ("apply sync",                 "konecty-meta",  "meta_sync",     ["apply"]),
    ("sync diff",                  "konecty-meta",  "meta_sync",     ["diff"]),
    ("remove module",              "konecty-meta",  "meta_remove",   ["plan"]),
    ("show namespace",             "konecty-meta",  "meta_namespace",["show"]),
    ("show pivot",                 "konecty-meta",  "meta_pivot",    ["show"]),
    ("check queues",               "konecty-meta",  "meta_doctor",   ["check-queues"]),
    ("list hooks",                 "konecty-meta",  "meta_hook",     ["list"]),
    ("upload file",                "konecty-data",  "upload",        ["upload"]),
    ("list files",                 "konecty-data",  "upload",        ["list"]),
    ("file info",                  "konecty-data",  "upload",        ["info"]),
    ("fetch before update",        "konecty-data",  "update",        ["fetch"]),
    ("preview before delete",      "konecty-data",  "delete",        ["preview"]),
    ("get metadata",               "konecty-meta",  "meta_read",     ["get"]),
    ("metadata types",             "konecty-meta",  "meta_read",     ["types"]),
    ("add field to document",      "konecty-meta",  "meta_document", ["add-field"]),
    ("remove field from document", "konecty-meta",  "meta_document", ["remove-field"]),
    ("update field in document",   "konecty-meta",  "meta_document", ["update-field"]),
    ("show document fields",       "konecty-meta",  "meta_document", ["fields"]),
    ("show list columns",          "konecty-meta",  "meta_list",     ["columns"]),
    ("show meta view",             "konecty-meta",  "meta_view",     ["show"]),
    ("show view visuals",          "konecty-meta",  "meta_view",     ["visuals"]),
    ("show access profile",        "konecty-meta",  "meta_access",   ["show"]),
    ("show access permissions",    "konecty-meta",  "meta_access",   ["permissions"]),
    ("validate hook",              "konecty-meta",  "meta_hook",     ["validate"]),
]
# fmt: on


@pytest.mark.parametrize(
    "phrase,exp_skill,exp_script,argv_fragment",
    _INTENT_ROUTING_CASES,
    ids=[c[0] for c in _INTENT_ROUTING_CASES],
)
def test_routing(
    phrase: str,
    exp_skill: str,
    exp_script: str,
    argv_fragment: list[str],
) -> None:
    """Each trigger phrase resolves to the correct skill and script."""
    skill, script, argv = route(phrase)
    assert skill == exp_skill, f"wrong skill for {phrase!r}: {skill!r}"
    assert script == exp_script, f"wrong script for {phrase!r}: {script!r}"
    for token in argv_fragment:
        assert token in argv, (
            f"expected {token!r} in argv for {phrase!r}, got {argv!r}"
        )


# ---------------------------------------------------------------------------
# 2. Slot-filling works correctly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "phrase,slots,expected_in_argv",
    [
        (
            "create a contact",
            {"document": "Contact", "data": '{"name": {}}'},
            ["create", "Contact", "--data", '{"name": {}}'],
        ),
        (
            "find records",
            {"document": "Lead", "limit": "20"},
            ["find", "Lead", "--limit", "20"],
        ),
        (
            "update record",
            {"document": "Contact", "term": "abc123", "data": '{"status":"active"}'},
            ["patch", "Contact", "abc123", "--data", '{"status":"active"}'],
        ),
        (
            "delete record",
            {"document": "Contact", "term": "abc123"},
            ["delete", "Contact", "abc123", "--confirm"],
        ),
        (
            "show fields",
            {"document": "Lead"},
            ["fields", "Lead"],
        ),
        (
            "scaffold hook",
            {"hook": "beforeSave"},
            ["scaffold", "beforeSave"],
        ),
        (
            "show meta document",
            {"document": "Contact"},
            ["show", "Contact"],
        ),
        (
            "run sql",
            {"sql": "SELECT * FROM Contact LIMIT 5"},
            ["sql", "SELECT * FROM Contact LIMIT 5"],
        ),
        (
            "cross module query",
            {"document": "Contact"},
            ["query", "Contact"],
        ),
        (
            "upload file",
            {"document": "Contact", "record_id": "abc", "field": "photo", "file": "/tmp/x.jpg"},
            ["upload", "Contact", "abc", "photo", "/tmp/x.jpg"],
        ),
    ],
    ids=[
        "create-slot",
        "find-slot",
        "update-slot",
        "delete-slot",
        "show-fields-slot",
        "scaffold-hook-slot",
        "show-meta-document-slot",
        "run-sql-slot",
        "cross-module-query-slot",
        "upload-file-slot",
    ],
)
def test_slot_filling(
    phrase: str,
    slots: dict[str, str],
    expected_in_argv: list[str],
) -> None:
    """Slots are substituted into the argv template."""
    _skill, _script, argv = route(phrase, **slots)
    assert argv == expected_in_argv, (
        f"slot-filled argv mismatch for {phrase!r}:\n  got:      {argv}\n  expected: {expected_in_argv}"
    )


# ---------------------------------------------------------------------------
# 3. Unmatched phrase raises ValueError
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "phrase",
    [
        "xyzzy nonsense phrase",
        "   ",
        "blah blah blah completely unknown intent blah",
        "123456",
        "フォームを送信",  # Japanese — definitely not matched
    ],
    ids=["gibberish", "whitespace-only", "long-unknown", "digits", "japanese"],
)
def test_unmatched_raises(phrase: str) -> None:
    """Phrases that match no intent raise ValueError."""
    with pytest.raises(ValueError, match="no intent matched"):
        route(phrase)


# ---------------------------------------------------------------------------
# 4. Every INTENTS entry's (skill, script) references a real script file
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "intent",
    INTENTS,
    ids=[f"{i.skill}/{i.script}:{i.phrase}" for i in INTENTS],
)
def test_intent_script_exists(intent) -> None:
    """Each Intent's script file must exist on disk."""
    path = _script_file(intent.skill, intent.script)
    assert path.exists(), (
        f"Script file missing for intent {intent.phrase!r}: {path}"
    )
