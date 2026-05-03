"""Smoke tests against a live GlitchTip instance.

Skipped unless ``GLITCHTIP_URL`` and ``GLITCHTIP_TOKEN`` are set.
"""

from __future__ import annotations

import pytest


@pytest.mark.smoke
def test_api_root_reachable(configured_env):
    from glitchtip_mcp._helpers import _get_client

    info = _get_client().get("/api/0/")
    assert isinstance(info, dict)
    assert "version" in info


@pytest.mark.smoke
def test_list_organizations(configured_env):
    from glitchtip_mcp._generated import list_organizations

    result = list_organizations()
    # Either returns a list or {"status":"ok"} when None
    assert isinstance(result, (list, dict))


@pytest.mark.smoke
def test_glitchtip_version_tool(configured_env):
    from glitchtip_mcp.tools import glitchtip_version

    result = glitchtip_version()
    assert "mcp" in result
    assert "service" in result
    assert result["service"]["status"] in ("ok", "error")
