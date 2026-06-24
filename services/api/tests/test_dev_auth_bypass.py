"""DEV_AUTH_BYPASS gate tests (LOCAL-ONLY auth shortcut).

When Discord OAuth is unreachable (flaky network) or undesirable for a local
demo, ``DEV_AUTH_BYPASS=1`` makes ``require_desk`` treat every caller as a DESK
operator WITHOUT a session cookie. This is a deliberate local backdoor:

* Default OFF — absent/any-other value keeps the real gate (401/403).
* It must NEVER be set in a public/Vercel deploy (it disables all access control).

These tests pin both behaviors so the bypass can't silently regress to on-by-default.
"""
from __future__ import annotations

import pytest

from api.errors import Unauthenticated
from api.security import require_desk


def test_require_desk_still_401_without_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEV_AUTH_BYPASS", raising=False)
    with pytest.raises(Unauthenticated):
        require_desk(None)


def test_require_desk_still_401_when_bypass_not_exactly_1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEV_AUTH_BYPASS", "true")  # only "1" enables it
    with pytest.raises(Unauthenticated):
        require_desk(None)


def test_require_desk_bypass_grants_desk_without_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")
    sess = require_desk(None)
    assert sess.has_desk is True
    assert sess.is_member is True
