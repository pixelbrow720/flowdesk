"""Pytest-wide fixtures / env defaults for the API test suite.

``api.main`` instantiates ``app = create_app()`` at import time (the uvicorn
entrypoint target). With the live-readiness auth fail-fast in place, importing
the module without a full auth contract would raise at collection. Default the
dev/test bypass ON here so unit tests that do not exercise the auth path can
import the app freely; tests that verify the fail-fast explicitly ``delenv`` it.

This only affects the test process — production runs under uvicorn, which does
not load conftest, so the fail-fast still guards real deploys.
"""
from __future__ import annotations

import os

os.environ.setdefault("AUTH_CONFIG_OPTIONAL", "1")
