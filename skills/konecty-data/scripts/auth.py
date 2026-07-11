#!/usr/bin/env python3
"""
Konecty OTP session: check login-options, request OTP, verify OTP and persist token.
Uses only stdlib (no pip install). Two-phase flow: request OTP → user receives code → verify OTP → write ~/.konecty/.env and ~/.konecty/credentials (shared for all skills).
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_HOST = "http://localhost:3000"
CREDENTIALS_DIR = os.path.expanduser("~/.konecty")
CREDENTIALS_FILE = os.path.join(CREDENTIALS_DIR, "credentials")
# Shared .env so all skills can load KONECTY_URL/KONECTY_TOKEN from one place
DEFAULT_ENV_FILE = os.path.join(CREDENTIALS_DIR, ".env")


def _json_request(
    method: str,
    url: str,
    data: dict | None = None,
) -> dict:
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            out = json.loads(err_body) if err_body.strip() else {}
        except Exception:
            out = {}
        raise SystemExit(
            f"Request failed: HTTP {e.code} - {out.get('errors', out) or e.reason}"
        )
    except urllib.error.URLError as e:
        raise SystemExit(f"Request failed: {e.reason}")
    except OSError as e:
        raise SystemExit(f"Request failed: {e}")


def cmd_login_options(host: str) -> None:
    url = f"{host.rstrip('/')}/api/auth/login-options"
    result = _json_request("GET", url)
    print(json.dumps(result, indent=2))
    email_otp = result.get("emailOtpEnabled", False)
    whatsapp_otp = result.get("whatsAppOtpEnabled", False)
    if not email_otp and not whatsapp_otp:
        print(
            "OTP login is not enabled for this namespace. This skill cannot open a session here.",
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_request_otp(host: str, email: str | None, phone: str | None) -> None:
    if (email is None) == (phone is None):
        print("Provide exactly one of --email or --phone (E.164)", file=sys.stderr)
        sys.exit(1)
    url = f"{host.rstrip('/')}/api/auth/request-otp"
    body: dict = {"email": email} if email else {"phoneNumber": phone}
    result = _json_request("POST", url, body)
    if not result.get("success"):
        errors = result.get("errors") or [{"message": "Unknown error"}]
        raise SystemExit("Request OTP failed: " + "; ".join(
            e.get("message", str(e)) for e in errors
        ))
    print(result.get("message", "OTP sent. Check your email or WhatsApp for the 6-digit code."))
    print("When you receive the code, run: python scripts/login.py verify-otp --host ... --email ... --otp <code>")


def ensure_env_file(path: str, url: str, token: str, user_id: str | None = None) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, mode=0o700, exist_ok=True)
    lines: list[str] = []
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("KONECTY_URL=") or line.strip().startswith("KONECTY_TOKEN=") or line.strip().startswith("KONECTY_USER_ID="):
                    continue
                lines.append(line)
    lines.append(f"KONECTY_URL={url}\n")
    lines.append(f"KONECTY_TOKEN={token}\n")
    if user_id:
        lines.append(f"KONECTY_USER_ID={user_id}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def ensure_credentials_ini(host: str, auth_id: str, user_id: str | None = None) -> None:
    os.makedirs(CREDENTIALS_DIR, mode=0o700, exist_ok=True)
    config = configparser.ConfigParser()
    if os.path.isfile(CREDENTIALS_FILE):
        config.read(CREDENTIALS_FILE, encoding="utf-8")
    section = host.rstrip("/")
    if "default" not in config:
        config["default"] = {}
    config["default"]["host"] = host.rstrip("/")
    config["default"]["authId"] = auth_id
    if user_id:
        config["default"]["userId"] = str(user_id)
    if section not in config:
        config[section] = {}
    config[section]["host"] = host.rstrip("/")
    config[section]["authId"] = auth_id
    if user_id:
        config[section]["userId"] = str(user_id)
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        config.write(f)


def cmd_verify_otp(
    host: str,
    email: str | None,
    phone: str | None,
    otp_code: str,
    env_file: str,
    no_env: bool,
    no_credentials: bool,
) -> None:
    if (email is None) == (phone is None):
        print("Provide exactly one of --email or --phone (E.164)", file=sys.stderr)
        sys.exit(1)
    if not otp_code or not otp_code.strip().isdigit() or len(otp_code.strip()) != 6:
        print("OTP code must be 6 digits", file=sys.stderr)
        sys.exit(1)
    url = f"{host.rstrip('/')}/api/auth/verify-otp"
    body: dict = {"email": email, "otpCode": otp_code.strip()} if email else {"phoneNumber": phone, "otpCode": otp_code.strip()}
    result = _json_request("POST", url, body)
    if not result.get("success") or not result.get("logged"):
        errors = result.get("errors") or [{"message": "Verification failed"}]
        raise SystemExit("Verify OTP failed: " + "; ".join(
            e.get("message", str(e)) for e in errors
        ))
    auth_id = result.get("authId")
    user_obj = result.get("user")
    user_id = user_obj.get("_id") if isinstance(user_obj, dict) else None
    if not auth_id:
        raise SystemExit("Verify succeeded but no authId in response")
    if not no_env:
        env_path = os.path.abspath(env_file)
        ensure_env_file(env_path, host.rstrip("/"), auth_id, str(user_id) if user_id else None)
        print(f"Wrote KONECTY_URL and KONECTY_TOKEN to {env_path}")
    if not no_credentials:
        ensure_credentials_ini(host.rstrip("/"), auth_id, str(user_id) if user_id else None)
        print(f"Wrote credentials to {CREDENTIALS_FILE}")
    print("Session stored. Token validity depends on namespace session expiration; when it expires, run this flow again.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Konecty OTP session: login-options, request-otp, verify-otp (persist token)."
    )
    parser.add_argument("--host", default=os.environ.get("KONECTY_URL", DEFAULT_HOST), help="Konecty base URL")
    sub = parser.add_subparsers(dest="command", required=True)

    # login-options
    p_opts = sub.add_parser("login-options", help="GET login-options; exit 1 if OTP not enabled")
    p_opts.set_defaults(func=lambda a: cmd_login_options((a.host or "").strip() or DEFAULT_HOST))

    # request-otp
    p_req = sub.add_parser("request-otp", help="POST request-otp (send OTP to email or phone)")
    p_req.add_argument("--email", default=os.environ.get("KONECTY_OTP_EMAIL"), help="User email")
    p_req.add_argument("--phone", default=os.environ.get("KONECTY_OTP_PHONE"), help="Phone E.164 (e.g. +5511999999999)")
    p_req.set_defaults(
        func=lambda a: cmd_request_otp(
            (a.host or "").strip() or DEFAULT_HOST,
            (a.email or "").strip() or None,
            (a.phone or "").strip() or None,
        )
    )

    # verify-otp
    p_ver = sub.add_parser("verify-otp", help="POST verify-otp and write .env + credentials")
    p_ver.add_argument("--email", default=os.environ.get("KONECTY_OTP_EMAIL"))
    p_ver.add_argument("--phone", default=os.environ.get("KONECTY_OTP_PHONE"))
    p_ver.add_argument("--otp", required=True, help="6-digit OTP code")
    p_ver.add_argument("--env-file", default=DEFAULT_ENV_FILE, help="Path to .env (default: ~/.konecty/.env, shared for all skills)")
    p_ver.add_argument("--no-env", action="store_true")
    p_ver.add_argument("--no-credentials", action="store_true")
    p_ver.set_defaults(
        func=lambda a: cmd_verify_otp(
            (a.host or "").strip() or DEFAULT_HOST,
            (a.email or "").strip() or None,
            (a.phone or "").strip() or None,
            a.otp,
            a.env_file,
            a.no_env,
            a.no_credentials,
        )
    )

    args = parser.parse_args()
    if not (args.host or "").strip():
        print("Missing --host or KONECTY_URL", file=sys.stderr)
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
