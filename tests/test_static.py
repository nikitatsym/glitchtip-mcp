"""Static checks: codegen, import, group registration."""

from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path


def test_generated_module_parses():
    src = Path(__file__).resolve().parents[1] / "src" / "glitchtip_mcp" / "_generated.py"
    ast.parse(src.read_text())


def test_module_imports():
    # Avoid crashing on empty config when client is lazy-init'd
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    import glitchtip_mcp.server as server  # noqa: F401


def test_group_registration_full_count():
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import server

    expected = {
        "glitchtip_read": 59,
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


def test_codegen_is_idempotent(tmp_path):
    """Running the codegen twice on the same spec yields identical output."""
    import subprocess
    import sys

    repo = Path(__file__).resolve().parents[1]
    out = repo / "src" / "glitchtip_mcp" / "_generated.py"
    before = out.read_text()
    subprocess.run([sys.executable, "codegen/generate.py"], cwd=repo, check=True)
    after = out.read_text()
    assert before == after
