"""
Security checks (R-SEC criteria) for konecty-data and konecty-meta skill scripts.

Tests are organised by criterion:
  SEC-1  Credential fast-fail (clean env / no ~/.konecty/.env)
  SEC-2  Bad token → clean HTTP 401, no Python traceback
  SEC-3  delete without --confirm refuses before HTTP
  SEC-4  upload delete dry-run without --confirm (advisory, exit 0)
  SEC-5  OTP mutual-exclusivity and 6-digit validation (no network)
  SEC-6  Invalid hook name / webhook event fail before HTTP
  SEC-7  Token never leaks to stdout or stderr
  SEC-8  Injection payloads handled safely (no crash, no shell, no traceback)

Tests that need no live stack use agent.smoke() (subprocess with stripped creds)
or agent.run() with mock_konecty.  Only SEC-2 needs live_creds; it is skipped
when the stack is unreachable.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TRACEBACK_MARKER = "Traceback (most recent call last)"


def _combined(r) -> str:
    """Return stdout + stderr as one searchable string."""
    return r.stdout + r.stderr


# ---------------------------------------------------------------------------
# SEC-1  Credential fast-fail in a truly clean environment
# ---------------------------------------------------------------------------
#
# Each entry is (skill, script, benign_argv).
# We use agent.smoke(creds=False, home=tmp_path) so:
#   - KONECTY_URL / KONECTY_TOKEN are absent from the env
#   - HOME points at an empty tmpdir → no ~/.konecty/.env can be found
#
_CRED_FASTFAIL_CASES = [
    ("konecty-data", "find",       ["find", "Contact", "--limit", "1"]),
    ("konecty-data", "create",     ["create", "Contact", "--data", "{}"]),
    ("konecty-data", "upload",     ["info", "Contact", "picture"]),
    ("konecty-meta", "meta_read",  ["list"]),
]


@pytest.mark.parametrize(
    "skill,script,argv",
    _CRED_FASTFAIL_CASES,
    ids=[f"{s}/{sc}" for s, sc, _ in _CRED_FASTFAIL_CASES],
)
def test_sec1_credential_fastfail(agent, tmp_path, skill, script, argv):
    """Scripts must exit non-zero and mention missing credentials when creds are absent."""
    result = agent.smoke(skill, script, argv, creds=False, home=str(tmp_path))

    assert result.code != 0, (
        f"{skill}/{script}: expected non-zero exit without credentials, got 0.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    combined = _combined(result)
    cred_words = ("KONECTY_URL", "KONECTY_TOKEN", "credential", "session")
    assert any(w.lower() in combined.lower() for w in cred_words), (
        f"{skill}/{script}: error output should mention missing credentials.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# SEC-2  Bad token → clean HTTP 401, no Python traceback
# ---------------------------------------------------------------------------


def test_sec2_bad_token_clean_401(agent, live_creds):
    """A wrong token must produce a clean error message containing '401' or
    an auth-related word, without raising a Python traceback.

    We use the 'query' subcommand (POST /rest/query/json) because that
    endpoint returns a real HTTP 401 for bad credentials — unlike the
    'find' subcommand (POST /rest/data/:doc/find) which returns HTTP 200
    with success:false.
    """
    url, _good_token = live_creds
    bad_token = "DEADBEEF-invalid-token-sec2"

    result = agent.run(
        "konecty-data", "find",
        ["query", "Contact", "--limit", "1"],
        host=url,
        token=bad_token,
    )

    assert result.code != 0, (
        "Expected non-zero exit with a bad token.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    combined = _combined(result)
    auth_words = ("401", "user", "auth", "unauthorized", "token", "permission")
    assert any(w.lower() in combined.lower() for w in auth_words), (
        "Expected '401' or an auth-related word in output with a bad token.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    assert _TRACEBACK_MARKER not in combined, (
        "A Python traceback must not be shown to the user for a bad token.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# SEC-3  delete without --confirm refuses before making any HTTP call
# ---------------------------------------------------------------------------


def test_sec3_delete_requires_confirm(agent):
    """delete <Document> <term> without --confirm must be refused.

    We use a clearly-bogus host so that if the guard is missing and the script
    tries to make an HTTP call, it will immediately fail with a connection
    error — which counts as evidence the guard is absent.  The correct
    behaviour is that the script bails with a 'confirm' message and
    non-zero exit before attempting any network activity.
    """
    result = agent.run(
        "konecty-data", "delete",
        # delete subcommand → argparse requires --confirm
        # We pass it without --confirm; argparse makes it required=True so
        # this will fail at argument parsing.  That means we never call main
        # body logic.  We confirm by checking the error message.
        ["delete", "Contact", "1"],
        host="http://bogus-host-sec3.invalid",
        token="dummy-token",
    )

    assert result.code != 0, (
        "Expected non-zero exit when --confirm is missing from delete.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    combined = _combined(result)
    # argparse will complain about missing --confirm, or our guard message
    guard_words = ("confirm", "refus", "required")
    assert any(w.lower() in combined.lower() for w in guard_words), (
        "Expected a 'confirm'/'required'/'refus' message when --confirm is absent.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# SEC-4  upload delete dry-run without --confirm prints advisory, exits 0
# ---------------------------------------------------------------------------


def test_sec4_upload_delete_dryrun_no_confirm(agent):
    """upload delete without --confirm must print a dry-run advisory and exit 0
    (no actual deletion performed).

    The guard in cmd_delete() checks args.confirm before any HTTP call,
    prints a 'Run with --confirm to actually delete.' message, then returns.
    We give real-looking but bogus creds; the guard should fire before HTTP.
    """
    result = agent.run(
        "konecty-data", "upload",
        ["delete", "Contact", "rec-001", "picture", "photo.jpg"],
        host="http://bogus-host-sec4.invalid",
        token="dummy-token",
    )

    assert result.code == 0, (
        "Expected exit 0 for upload delete dry-run without --confirm.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    combined = _combined(result)
    advisory_words = ("confirm", "dry", "would", "--confirm")
    assert any(w.lower() in combined.lower() for w in advisory_words), (
        "Expected an advisory message mentioning '--confirm' or dry-run intent.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    # Confirm no actual delete attempt happened — no HTTP error should appear
    assert "HTTP" not in combined, (
        "Unexpected HTTP call detected; guard should prevent network access.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# SEC-5  OTP mutual-exclusivity and 6-digit validation — no network required
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "argv,reason",
    [
        # Both email and phone provided → mutual exclusivity failure
        (
            ["request-otp", "--email", "a@b.com", "--phone", "+5511999999999"],
            "both email and phone",
        ),
        # 5-digit OTP (too short)
        (
            ["verify-otp", "--email", "a@b.com", "--otp", "12345"],
            "5-digit OTP",
        ),
        # Non-numeric OTP
        (
            ["verify-otp", "--email", "a@b.com", "--otp", "abcdef"],
            "non-numeric OTP",
        ),
    ],
    ids=["both-email-and-phone", "otp-5-digits", "otp-non-numeric"],
)
def test_sec5_otp_validation_no_network(agent, argv, reason):
    """OTP input validation must fail before any HTTP call.

    We pass a clearly-bogus host so that if validation is skipped and the
    script actually tries to hit the network, it will get a connection error
    rather than the expected validation message.  The test asserts that:
      - exit code is non-zero
      - a relevant validation message is present
    """
    result = agent.run(
        "konecty-data", "auth",
        argv,
        host="http://bogus-host-sec5.invalid",
        token="dummy",
    )

    assert result.code != 0, (
        f"Expected non-zero exit for {reason}.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    combined = _combined(result)
    # We don't assert a single exact message — just that it looks like a validation
    # error rather than a connection error.
    connection_words = ("Connection error", "connection refused", "Name or service not known",
                        "nodename nor servname", "getaddrinfo")
    validation_words = ("exactly one", "email", "phone", "digit", "otp", "6", "provide")
    assert any(w.lower() in combined.lower() for w in validation_words), (
        f"Expected a validation message for {reason}, got output that looks like "
        f"a network error instead.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# SEC-6  Invalid hook name / webhook event fail before HTTP
# ---------------------------------------------------------------------------


def test_sec6_invalid_hook_name_scaffold_no_creds(agent):
    """meta_hook scaffold with an invalid hook name must fail without any creds/network.

    scaffold() only checks VALID_HOOKS and prints the template; it never calls
    _creds() or makes HTTP requests.  An invalid hook name must exit non-zero
    with a relevant message.
    """
    result = agent.run(
        "konecty-meta", "meta_hook",
        ["scaffold", "badHookName"],
        host="",
        token="",
    )

    assert result.code != 0, (
        "Expected non-zero exit for invalid scaffold hook name.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    combined = _combined(result)
    assert any(w.lower() in combined.lower() for w in ("invalid", "valid", "hook")), (
        "Expected a message mentioning hook validity.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


def test_sec6_invalid_webhook_event(agent, mock_konecty):
    """meta_namespace set-webhook with an invalid event name must reject it.

    set-webhook calls _get_namespace (HTTP) before the event validation check,
    so we supply the mock to handle the GET /Namespace request.  The event
    validation then fires and must exit non-zero with an 'invalid' or 'event'
    message, without making the PUT call.
    """
    with mock_konecty.patch():
        result = agent.run(
            "konecty-meta", "meta_namespace",
            ["set-webhook", "onBadEvent", "http://example.com/webhook"],
            host="http://mock.konecty.local",
            token="mock-admin-token",
        )

    assert result.code != 0, (
        "Expected non-zero exit for invalid webhook event name.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    combined = _combined(result)
    assert any(w.lower() in combined.lower() for w in ("invalid", "event", "oncreate", "onupdate", "ondelete")), (
        "Expected an 'invalid event' message.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# SEC-7  Token never leaks to stdout or stderr
# ---------------------------------------------------------------------------

_SENTINEL_TOKEN = "SENTINEL-TOKEN-SEC7-DO-NOT-LOG"


def test_sec7_token_not_leaked_to_output(agent, mock_konecty):
    """The auth token must never appear in stdout or stderr.

    We run a normal meta_read list against the mock and assert the sentinel
    token is absent from all output.
    """
    with mock_konecty.patch():
        result = agent.run(
            "konecty-meta", "meta_read",
            ["list"],
            host="http://mock.konecty.local",
            token=_SENTINEL_TOKEN,
        )

    combined = _combined(result)
    assert _SENTINEL_TOKEN not in combined, (
        "The auth token was found in the script output — this is a security leak!\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# SEC-8  Injection-ish payloads are handled safely
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filter_value,label",
    [
        ('{"term":"name","operator":"equals","value":"O\'Reilly; drop table"}', "sql-injection-like"),
        ('{"term":"name","operator":"equals","value":"$(id)"}', "shell-subshell"),
        ('{"term":"name","operator":"equals","value":"<script>alert(1)</script>"}', "xss-like"),
    ],
    ids=["sql-injection", "shell-subshell", "xss-like"],
)
def test_sec8_injection_payload_handled_safely(agent, mock_konecty, filter_value, label):
    """Injection-ish filter payloads must be transported as data, not executed.

    We patch urlopen so the mock intercepts the HTTP call (which means the
    payload goes through the JSON encoding path without shell involvement).
    The test asserts: no Python traceback, and the process either succeeds
    or returns a clean controlled error — never a crash.

    Note: find.py hits /rest/data/ and /rest/query/json — endpoints NOT served
    by the meta mock.  The mock will raise a 404 for unknown paths, which the
    script converts to a clean SystemExit (non-zero).  That is the acceptable
    controlled-error outcome.
    """
    with mock_konecty.patch():
        result = agent.run(
            "konecty-data", "find",
            ["find", "Contact", "--filter", filter_value, "--limit", "1"],
            host="http://mock.konecty.local",
            token="mock-token",
        )

    combined = _combined(result)
    assert _TRACEBACK_MARKER not in combined, (
        f"Python traceback leaked for injection payload ({label}).\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


def test_sec8_malformed_json_filter_rejected(agent, mock_konecty):
    """A malformed JSON --filter must produce a clear error message, not a traceback."""
    with mock_konecty.patch():
        result = agent.run(
            "konecty-data", "find",
            ["find", "Contact", "--filter", "{not valid json{{", "--limit", "1"],
            host="http://mock.konecty.local",
            token="mock-token",
        )

    assert result.code != 0, (
        "Expected non-zero exit for malformed --filter JSON.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    combined = _combined(result)
    assert _TRACEBACK_MARKER not in combined, (
        "Python traceback shown for malformed filter JSON.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    error_words = ("invalid", "json", "filter", "error", "parse", "decode")
    assert any(w.lower() in combined.lower() for w in error_words), (
        "Expected a clear error message for malformed filter JSON.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
