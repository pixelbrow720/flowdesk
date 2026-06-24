"""Auth-config fail-fast tests (live-readiness hardening).

The serving-path audit found two silent-failure modes that a real operator
would only discover via user-visible breakage at market open:

  1. Blank ``SESSION_SECRET`` -> any request bearing a session cookie raises an
     uncaught ``SignatureError`` -> HTTP 500 (not a clean 401). The app booted
     clean, so the misconfig is invisible until traffic hits.
  2. Blank ``DESK_ROLE_ID`` / ``DISCORD_DESK_ROLE_ID`` -> ``"" in roles`` is
     always False -> every authenticated user is treated as NO_DESK -> 403 on
     every data endpoint. A silent, total lockout that also boots clean.

Mirror the existing CORS fail-fast (``_validate_cors_config``): refuse to boot
when these are empty, so the misconfig screams in CI/staging instead of prod.
A dev/test bypass (``AUTH_CONFIG_OPTIONAL=1``) keeps unit tests that don't
exercise auth from having to set the full contract.
"""
from __future__ import annotations

import pytest

# Import at module top so the import-time ``app = create_app()`` in api.main runs
# ONCE under conftest's AUTH_CONFIG_OPTIONAL bypass. Each test below then calls
# create_app() explicitly with its own env — the module is already cached, so no
# import-time side effect re-fires outside the pytest.raises block.
from api.main import create_app


def _valid_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://app.flowdesk.example")


def test_boot_refuses_blank_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_cors(monkeypatch)
    monkeypatch.setenv("SESSION_SECRET", "")
    monkeypatch.setenv("DISCORD_DESK_ROLE_ID", "123")
    monkeypatch.delenv("AUTH_CONFIG_OPTIONAL", raising=False)

    with pytest.raises(RuntimeError, match=r"SESSION_SECRET"):
        create_app()


def test_boot_refuses_blank_desk_role(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_cors(monkeypatch)
    monkeypatch.setenv("SESSION_SECRET", "a-long-enough-secret-value")
    monkeypatch.delenv("DISCORD_DESK_ROLE_ID", raising=False)
    monkeypatch.delenv("DESK_ROLE_ID", raising=False)
    monkeypatch.delenv("AUTH_CONFIG_OPTIONAL", raising=False)

    with pytest.raises(RuntimeError, match=r"DESK_ROLE_ID"):
        create_app()


def test_boot_accepts_complete_auth_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _valid_cors(monkeypatch)
    monkeypatch.setenv("SESSION_SECRET", "a-long-enough-secret-value")
    monkeypatch.setenv("DISCORD_DESK_ROLE_ID", "1508008876258365461")
    monkeypatch.delenv("AUTH_CONFIG_OPTIONAL", raising=False)

    app = create_app()
    assert app is not None


def test_boot_bypass_allows_blank_auth_for_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    """AUTH_CONFIG_OPTIONAL=1 keeps non-auth unit tests building the app."""
    _valid_cors(monkeypatch)
    monkeypatch.setenv("SESSION_SECRET", "")
    monkeypatch.delenv("DISCORD_DESK_ROLE_ID", raising=False)
    monkeypatch.delenv("DESK_ROLE_ID", raising=False)
    monkeypatch.setenv("AUTH_CONFIG_OPTIONAL", "1")

    app = create_app()
    assert app is not None
