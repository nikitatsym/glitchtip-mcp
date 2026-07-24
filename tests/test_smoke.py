"""Smoke tests against a live GlitchTip instance.

Skipped unless ``GLITCHTIP_URL`` and ``GLITCHTIP_TOKEN`` are set.
"""

from __future__ import annotations

import pytest


@pytest.mark.smoke
def test_settings_reachable(configured_env):
    from glitchtip_mcp._helpers import _get_client

    info = _get_client().get("/api/settings/")
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
    assert result["service"]["status"] == "ok"
    assert isinstance(result["service"]["version"], str)


@pytest.mark.smoke
def test_who_am_i_tool_returns_safe_context(configured_env):
    from glitchtip_mcp.tools import who_am_i

    result = who_am_i()

    assert result["authenticated"] is True
    assert "token" not in repr(result)
    assert set(result["user"]) <= {"id", "username", "email", "name", "isSuperuser", "isActive"}
    assert set(result["auth"]) <= {"id", "label", "scopes", "created"}
