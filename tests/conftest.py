"""Test fixtures.

Two modes:

* **Static** — no environment required. Imports the module, validates the
  generated code shape, asserts group registration. Runs in CI.

* **Smoke** — set ``GLITCHTIP_URL`` and ``GLITCHTIP_TOKEN`` to point at a real
  instance. The ``smoke`` marker on a test triggers it.

Full docker-compose integration is left to manual runs (``docker compose up``
with ``tests/docker-compose.yml``); user/token bootstrap requires Django shell
access and is out of scope for the test suite here.
"""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("GLITCHTIP_URL") and os.environ.get("GLITCHTIP_TOKEN"):
        return
    skip_smoke = pytest.mark.skip(reason="set GLITCHTIP_URL and GLITCHTIP_TOKEN to enable smoke tests")
    for item in items:
        if "smoke" in item.keywords:
            item.add_marker(skip_smoke)


@pytest.fixture(scope="session")
def configured_env():
    """Reset cached settings so live env vars take effect."""
    import glitchtip_mcp._helpers as helpers
    from glitchtip_mcp.config import _reset_settings

    _reset_settings()
    helpers._client = None
    yield
    helpers._client = None
