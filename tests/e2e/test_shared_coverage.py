"""Coverage closers for the shared / auth / credential-loader code paths.

These exercise the parts the main mock suites can't reach:
- the ``konecty-meta`` copies of ``modules.py`` and ``auth.py`` (byte-identical
  to the konecty-data copies, but distinct files → counted separately);
- the OTP happy paths in ``auth.py`` (login-options / request-otp / verify-otp);
- every script's ``_load_credentials()`` env / dotenv / credentials-ini /
  missing branches, which the PseudoAgent normally short-circuits by injecting
  ``KONECTY_URL`` / ``KONECTY_TOKEN`` directly.
"""

from __future__ import annotations

import pytest

from e2e.agent import PseudoAgent

pytestmark = pytest.mark.mock

MOCK_HOST = "http://mock.konecty.local"
MOCK_TOKEN = "mock-admin-token"

# Every script that defines _load_credentials() (auth.py does not).
CRED_SCRIPTS = [
    ("konecty-data", "modules"),
    ("konecty-data", "find"),
    ("konecty-data", "create"),
    ("konecty-data", "update"),
    ("konecty-data", "delete"),
    ("konecty-data", "upload"),
    ("konecty-meta", "modules"),
    ("konecty-meta", "meta_read"),
    ("konecty-meta", "meta_document"),
    ("konecty-meta", "meta_list"),
    ("konecty-meta", "meta_view"),
    ("konecty-meta", "meta_access"),
    ("konecty-meta", "meta_hook"),
    ("konecty-meta", "meta_namespace"),
    ("konecty-meta", "meta_pivot"),
    ("konecty-meta", "meta_doctor"),
    ("konecty-meta", "meta_sync"),
    ("konecty-meta", "meta_remove"),
]


# --------------------------------------------------------------------------- #
# konecty-meta copies of the shared modules.py (cmd paths)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("argv", [["list"], ["fields", "Contact"], ["search", "Contact"]])
def test_meta_modules_commands(agent, mock_konecty, argv):
    with mock_konecty.patch():
        r = agent.run("konecty-meta", "modules", argv, host=MOCK_HOST, token=MOCK_TOKEN)
    assert r.code == 0, r.stderr


# --------------------------------------------------------------------------- #
# auth.py OTP happy paths — driven via BOTH skills to cover both copies
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("skill", ["konecty-data", "konecty-meta"])
def test_auth_login_options(agent, mock_konecty, skill):
    with mock_konecty.patch():
        r = agent.run(skill, "auth", ["login-options"], host=MOCK_HOST, token=MOCK_TOKEN)
    assert r.code == 0, r.stderr


@pytest.mark.parametrize("skill", ["konecty-data", "konecty-meta"])
@pytest.mark.parametrize(
    "argv",
    [
        ["request-otp", "--email", "user@example.com"],
        ["request-otp", "--phone", "+5511999999999"],
    ],
)
def test_auth_request_otp(agent, mock_konecty, skill, argv):
    with mock_konecty.patch():
        r = agent.run(skill, "auth", argv, host=MOCK_HOST, token=MOCK_TOKEN)
    assert r.code == 0, r.stderr


@pytest.mark.parametrize("skill", ["konecty-data", "konecty-meta"])
def test_auth_verify_otp_writes_env(agent, mock_konecty, skill, tmp_path):
    env_file = tmp_path / ".env"
    with mock_konecty.patch():
        r = agent.run(
            skill,
            "auth",
            ["verify-otp", "--email", "user@example.com", "--otp", "123456",
             "--env-file", str(env_file), "--no-credentials"],
            host=MOCK_HOST,
            token=MOCK_TOKEN,
        )
    assert r.code == 0, r.stderr
    assert env_file.exists()
    content = env_file.read_text()
    assert "KONECTY_URL" in content and "KONECTY_TOKEN" in content


# --------------------------------------------------------------------------- #
# _load_credentials() — env / dotenv / credentials-ini / missing branches
# --------------------------------------------------------------------------- #
def _module(skill: str, script: str):
    return PseudoAgent()._load(skill, script)


@pytest.mark.parametrize("skill,script", CRED_SCRIPTS, ids=lambda v: v if isinstance(v, str) else "")
def test_load_credentials_env(monkeypatch, skill, script):
    monkeypatch.setenv("KONECTY_URL", "http://env.example/")
    monkeypatch.setenv("KONECTY_TOKEN", "env-token")
    mod = _module(skill, script)
    url, token = mod._load_credentials()
    assert "env.example" in url and token == "env-token"


@pytest.mark.parametrize("skill,script", CRED_SCRIPTS, ids=lambda v: v if isinstance(v, str) else "")
def test_load_credentials_dotenv(monkeypatch, tmp_path, skill, script):
    monkeypatch.delenv("KONECTY_URL", raising=False)
    monkeypatch.delenv("KONECTY_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    konecty_dir = tmp_path / ".konecty"
    konecty_dir.mkdir(parents=True, exist_ok=True)
    (konecty_dir / ".env").write_text("KONECTY_URL=http://dotenv.example\nKONECTY_TOKEN=dotenv-token\n")
    mod = _module(skill, script)
    url, token = mod._load_credentials()
    assert "dotenv.example" in url and token == "dotenv-token"


@pytest.mark.parametrize("skill,script", CRED_SCRIPTS, ids=lambda v: v if isinstance(v, str) else "")
def test_load_credentials_ini(monkeypatch, tmp_path, skill, script):
    monkeypatch.delenv("KONECTY_URL", raising=False)
    monkeypatch.delenv("KONECTY_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    konecty_dir = tmp_path / ".konecty"
    konecty_dir.mkdir(parents=True, exist_ok=True)
    (konecty_dir / "credentials").write_text(
        "[default]\nhost = http://ini.example\nauthid = ini-token\n"
    )
    mod = _module(skill, script)
    url, token = mod._load_credentials()
    assert "ini.example" in url and token == "ini-token"


@pytest.mark.parametrize("skill,script", CRED_SCRIPTS, ids=lambda v: v if isinstance(v, str) else "")
def test_load_credentials_missing(monkeypatch, tmp_path, skill, script):
    """Missing creds: most scripts return falsy; upload.py raises SystemExit."""
    monkeypatch.delenv("KONECTY_URL", raising=False)
    monkeypatch.delenv("KONECTY_TOKEN", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))  # empty — no ~/.konecty
    mod = _module(skill, script)
    try:
        url, token = mod._load_credentials()
    except SystemExit:
        return  # upload.py fast-fails here — acceptable
    assert not url or not token
