"""CORS hardening tests (Phase 1 Item 1, beta-readiness).

Verifies the fail-fast guards added in `api.main._validate_cors_config`:
  1. `*` + `allow_credentials=True` is refused at boot (browsers reject this
     combo silently; we want it to scream in CI/staging instead).
  2. Empty `CORS_ORIGINS` is allowed but logs a WARN.
  3. Plain `http://` origins (other than localhost) are refused.
  4. Valid `https://...` and `http://localhost[:port]` origins boot clean.
"""
from __future__ import annotations

import logging

import pytest


def test_cors_rejects_star_with_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "*")
    from api.main import create_app

    with pytest.raises(RuntimeError, match=r"allow_credentials"):
        create_app()


def test_cors_warns_on_empty_origins(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "")
    from api.main import create_app

    caplog.set_level(logging.WARNING, logger="api.cors")
    app = create_app()
    assert app is not None
    assert any(
        "CORS_ORIGINS is empty" in rec.message
        for rec in caplog.records
        if rec.name == "api.cors"
    )


def test_cors_rejects_non_https_non_localhost_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://evil.example.com")
    from api.main import create_app

    with pytest.raises(RuntimeError, match=r"http://evil\.example\.com"):
        create_app()


def test_cors_accepts_valid_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS", "https://app.flowdesk.example,http://localhost:3000"
    )
    from api.main import create_app

    app = create_app()
    # Confirm CORSMiddleware is wired with the parsed origins.
    cors_mw = next(
        (mw for mw in app.user_middleware if mw.cls.__name__ == "CORSMiddleware"),
        None,
    )
    assert cors_mw is not None, "CORSMiddleware not registered"
    origins = cors_mw.kwargs["allow_origins"]
    assert "https://app.flowdesk.example" in origins
    assert "http://localhost:3000" in origins


def test_cors_rejects_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trailing slash is invalid origin per spec; the regex enforces no path."""
    monkeypatch.setenv("CORS_ORIGINS", "https://app.flowdesk.example/")
    from api.main import create_app

    with pytest.raises(RuntimeError, match=r"https://app\.flowdesk\.example/"):
        create_app()
