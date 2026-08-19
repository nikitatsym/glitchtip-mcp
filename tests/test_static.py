"""Static checks: codegen, import, group registration."""

from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path

import pytest


def test_generated_module_parses():
    src = Path(__file__).resolve().parents[1] / "src" / "glitchtip_mcp" / "_generated.py"
    ast.parse(src.read_text(encoding="utf-8"))


def test_module_imports():
    # Avoid crashing on empty config when client is lazy-init'd
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import server  # noqa: F401


def test_api_root_is_not_registered():
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import server

    assert "api_root" not in server.mcp._tool_manager._tools


def test_who_am_i_is_registered_in_read():
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import server

    assert "WhoAmI" in server._group_ops["glitchtip_read"]


def test_group_registration_full_count():
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import server

    expected = {
        "glitchtip_read": 60,
        "glitchtip_write": 34,
        "glitchtip_delete": 17,
        "glitchtip_admin_read": 17,
        "glitchtip_admin_write": 26,
    }
    actual = {g: len(ops) for g, ops in server._group_ops.items()}
    assert actual == expected, f"group counts changed: {actual}"


def test_every_generated_function_has_docstring():
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import _generated

    missing = [
        name
        for name, fn in inspect.getmembers(_generated, inspect.isfunction)
        if not name.startswith("_") and not fn.__doc__
    ]
    assert not missing, f"functions missing docstrings: {missing}"


def test_help_renders_for_every_group():
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import server

    for group_name in server._group_ops:
        text = server._build_help(group_name)
        assert "operations available" in text
        assert text.count("\n") >= len(server._group_ops[group_name])


def test_group_docs_resolve_operation_placeholders():
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import server, tools
    from glitchtip_mcp.registry import Group

    groups = [
        obj
        for _, obj in inspect.getmembers(tools, lambda o: isinstance(o, Group))
        if obj.name in server._group_ops
    ]
    assert len(groups) == len(server._group_ops)
    for group in groups:
        rendered = server._render_group_doc(
            group.name, group.doc, server._group_ops[group.name]
        )
        assert "$" not in rendered, f"{group.name} doc left a placeholder unrendered"


def test_render_group_doc_rejects_unknown_placeholder():
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import server

    with pytest.raises(RuntimeError, match="NoSuchOp"):
        server._render_group_doc(
            "glitchtip_read",
            'Example: glitchtip_read(operation="$NoSuchOp")',
            {"IssuesListIssues": None},
        )


def test_render_group_doc_rejects_hardcoded_operation():
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import server

    with pytest.raises(RuntimeError, match="hardcodes"):
        server._render_group_doc(
            "glitchtip_read",
            'Example: glitchtip_read(operation="IssuesListIssues")',
            {"IssuesListIssues": None},
        )

    with pytest.raises(RuntimeError, match="hardcodes"):
        server._render_group_doc(
            "glitchtip_read",
            'Example: glitchtip_read(operation = "IssuesListIssues")',
            {"IssuesListIssues": None},
        )


def test_render_group_doc_resolves_meta_and_keeps_generic_form():
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import server

    rendered = server._render_group_doc(
        "glitchtip_read", 'operation="$help" or operation="<OpName>"', {}
    )
    assert rendered == 'operation="help" or operation="<OpName>"'


class _VersionClient:
    def __init__(self, response):
        self._response = response

    def get(self, path: str):
        assert path == "/api/settings/"
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _WhoAmIClient:
    def __init__(self, response):
        self._response = response

    def get(self, path: str):
        assert path == "/api/0/"
        return self._response


def test_version_returns_only_safe_service_fields(monkeypatch):
    from glitchtip_mcp import tools

    response = {
        "version": "6.1.6",
        "user": {"email": "user@example.com"},
        "auth": {"token": "must-not-leak"},
    }
    monkeypatch.setattr(tools, "_get_client", lambda: _VersionClient(response))

    result = tools.glitchtip_version()

    assert result["service"] == {"status": "ok", "version": "6.1.6"}
    assert "must-not-leak" not in repr(result)


def test_version_does_not_expose_error_details(monkeypatch):
    from glitchtip_mcp import tools

    monkeypatch.setattr(
        tools,
        "_get_client",
        lambda: _VersionClient(RuntimeError("must-not-leak")),
    )

    result = tools.glitchtip_version()

    assert result["service"] == {"status": "error"}
    assert "must-not-leak" not in repr(result)


def test_who_am_i_returns_only_allowlisted_fields(monkeypatch):
    from glitchtip_mcp import tools

    response = {
        "version": "0",
        "user": {
            "id": "1",
            "username": "user@example.com",
            "email": "user@example.com",
            "name": "User",
            "isSuperuser": False,
            "isActive": True,
            "options": {"theme": "dark"},
            "identities": [{"provider": "github"}],
        },
        "auth": {
            "id": 1,
            "label": "MCP",
            "scopes": ["event:read"],
            "created": "2026-07-24T00:00:00Z",
            "token": "must-not-leak",
        },
    }
    monkeypatch.setattr(tools, "_get_client", lambda: _WhoAmIClient(response))

    result = tools.who_am_i()

    assert result == {
        "authenticated": True,
        "user": {
            "id": "1",
            "username": "user@example.com",
            "email": "user@example.com",
            "name": "User",
            "isSuperuser": False,
            "isActive": True,
        },
        "auth": {
            "id": 1,
            "label": "MCP",
            "scopes": ["event:read"],
            "created": "2026-07-24T00:00:00Z",
        },
    }
    assert "must-not-leak" not in repr(result)
    assert "theme" not in repr(result)
    assert "github" not in repr(result)


def test_who_am_i_returns_safe_anonymous_result(monkeypatch):
    from glitchtip_mcp import tools

    monkeypatch.setattr(
        tools,
        "_get_client",
        lambda: _WhoAmIClient({"version": "0", "user": None, "auth": None}),
    )

    assert tools.who_am_i() == {"authenticated": False}


def test_codegen_is_idempotent(tmp_path):
    """Running the codegen twice on the same spec yields identical output."""
    import subprocess
    import sys

    repo = Path(__file__).resolve().parents[1]
    out = repo / "src" / "glitchtip_mcp" / "_generated.py"
    before = out.read_text(encoding="utf-8")
    subprocess.run([sys.executable, "codegen/generate.py"], cwd=repo, check=True)
    after = out.read_text(encoding="utf-8")
    assert before == after
