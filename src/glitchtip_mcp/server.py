"""GlitchTip MCP server — auto-discovery, grouping, and dispatch."""

import functools
import inspect
import re
import string
import types
import typing

import httpx
import pydantic_core
from mcp.server.mcpserver import Image, MCPServer
from mcp.types import ContentBlock, TextContent

from . import tools as _tools_module
from .annotations import ANNOTATIONS
from .client import GlitchTipError
from .registry import ROOT

mcp = MCPServer("glitchtip")


def _to_pascal(name: str) -> str:
    return "".join(w.capitalize() for w in name.split("_"))


def _compact(fn):
    """Serialize a data result as one-line JSON.

    The SDK pretty-prints non-string results (`indent=2`), which costs the
    caller ~20% more tokens for nothing; a ready TextContent passes through
    untouched. Strings, content blocks and images keep the SDK path. Mirrors
    fn's sync/async flavor so a sync tool stays on the SDK worker thread.
    """
    def to_content(result):
        if result is None or isinstance(result, str | ContentBlock | Image):
            return result
        return TextContent(
            type="text", text=pydantic_core.to_json(result, fallback=str).decode()
        )

    if inspect.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def async_compact(*args, **kwargs):
            return to_content(await fn(*args, **kwargs))
        return async_compact

    @functools.wraps(fn)
    def sync_compact(*args, **kwargs):
        return to_content(fn(*args, **kwargs))
    return sync_compact


def _parse_bool(val, default: bool) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("1", "true", "yes")
    return bool(val)


def _is_bool_hint(hint) -> bool:
    if hint is bool:
        return True
    args = typing.get_args(hint)
    return bool in args if args else False


def _get_literal_values(hint) -> list[str] | None:
    if hint is None:
        return None
    origin = typing.get_origin(hint)
    if origin is typing.Literal:
        return [str(v) for v in typing.get_args(hint)]
    if origin is typing.Union:
        for arg in typing.get_args(hint):
            if typing.get_origin(arg) is typing.Literal:
                return [str(v) for v in typing.get_args(arg)]
    return None


def _unwrap_optional(hint):
    origin = typing.get_origin(hint)
    if origin is typing.Union or isinstance(hint, types.UnionType):
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return hint


def _format_param(name: str, hint) -> str:
    if hint is None:
        return name
    lit_vals = _get_literal_values(hint)
    if lit_vals:
        return f"{name}: {'|'.join(lit_vals)}"
    inner = _unwrap_optional(hint)
    origin = typing.get_origin(inner)
    if origin is list:
        type_args = typing.get_args(inner)
        if type_args and hasattr(type_args[0], "__name__"):
            return f"{name}: list[{type_args[0].__name__}]"
        return f"{name}: list"
    if inner is str:
        return f"{name}: str"
    if inner is int:
        return f"{name}: int"
    if inner is bool:
        return f"{name}: bool"
    if inner is dict:
        return f"{name}: dict"
    return name


def _coerce_call(fn, params: dict):
    sig = inspect.signature(fn)
    valid = set(sig.parameters.keys())
    unknown = set(params.keys()) - valid
    if unknown:
        raise ValueError(
            f"Unknown parameters: {sorted(unknown)}. Valid: {sorted(valid)}"
        )
    missing = [
        name
        for name, param in sig.parameters.items()
        if param.default is inspect.Parameter.empty and name not in params
    ]
    if missing:
        raise ValueError(f"Missing required parameters: {', '.join(missing)}")
    hints = typing.get_type_hints(fn, include_extras=True)
    kwargs = {}
    for name, param in sig.parameters.items():
        if name not in params:
            continue
        val = params[name]
        hint = hints.get(name)
        lit_vals = _get_literal_values(hint)
        if lit_vals and val not in lit_vals:
            raise ValueError(
                f"Invalid value {val!r} for {name}. "
                f"Accepted: {', '.join(lit_vals)}"
            )
        if val is not None and hint and _is_bool_hint(hint) and not isinstance(val, bool):
            default = param.default
            if default is inspect.Parameter.empty or default is None:
                default = False
            val = _parse_bool(val, default)
        kwargs[name] = val
    return fn(**kwargs)


_group_ops: dict[str, dict] = {}
_all_grouped: dict[str, str] = {}


def _build_help(group_name: str) -> str:
    ops = _group_ops[group_name]
    lines = []
    for pascal_name, fn in ops.items():
        sig = inspect.signature(fn)
        hints = typing.get_type_hints(fn, include_extras=True)
        parts = [_format_param(p, hints.get(p)) for p in sig.parameters]
        desc = ANNOTATIONS.get(pascal_name, f"{pascal_name}.")
        lines.append(f"  {pascal_name}({', '.join(parts)}) — {desc}")
    return f"{len(lines)} operations available:\n" + "\n".join(lines)


def _dispatch(operation: str, group_name: str, params: dict):
    ops = _group_ops[group_name]
    if operation not in ops:
        if operation in _all_grouped:
            correct = _all_grouped[operation]
            return {
                "error": f"{operation} belongs to {correct}. Use {correct}() instead."
            }
        return {
            "error": f"Unknown operation: {operation}. "
                     "Use operation=\"help\" to list available operations."
        }
    fn = ops[operation]
    try:
        return _coerce_call(fn, params)
    except ValueError as exc:
        return {"error": str(exc)}
    except GlitchTipError as exc:
        return {"error": str(exc)}
    except httpx.RequestError as exc:
        request = exc.request
        return {
            "error": (
                f"GlitchTip request failed: {request.method} {request.url.path}: "
                f"{type(exc).__name__}: {exc}"
            )
        }


_HARDCODED_OPERATION = re.compile(r"""\boperation\s*=\s*["'](?![$<])""")


def _render_group_doc(group_name: str, doc: str, ops: dict) -> str:
    """Resolve $OpName placeholders in a group doc against the registered operations.

    Examples are hand-written while operation names come from OpenAPI operationIds;
    rendering the names from the registry keeps the two from drifting apart, and an
    unresolved placeholder aborts startup. A hardcoded operation name is rejected
    outright; `<...>` stays available for deliberately generic placeholders.
    """
    if _HARDCODED_OPERATION.search(doc):
        raise RuntimeError(
            f"{group_name} doc hardcodes an operation name; use the $OpName form"
        )
    names = {name: name for name in ops} | {"help": "help"}
    try:
        return string.Template(doc).substitute(names)
    except (KeyError, ValueError) as exc:
        raise RuntimeError(
            f"{group_name} doc references an unknown operation placeholder: {exc}"
        ) from exc


def _register_tools():
    groups: dict[str, tuple] = {}

    for name, fn in inspect.getmembers(_tools_module, inspect.isfunction):
        if name.startswith("_"):
            continue
        if not hasattr(fn, "_mcp_group"):
            continue
        assert fn.__doc__, f"Missing docstring for {name}"
        group = fn._mcp_group
        if group is ROOT:
            mcp.tool(structured_output=False)(_compact(fn))
        else:
            if group.name not in groups:
                groups[group.name] = (group, {})
            groups[group.name][1][name] = fn

    for group_name, (group, fns) in groups.items():
        ops = {_to_pascal(n): fn for n, fn in fns.items()}
        _group_ops[group_name] = ops
        doc = _render_group_doc(group_name, group.doc, ops)
        for pascal_name in ops:
            _all_grouped[pascal_name] = group_name

        def _make_tool(gname, gdoc):
            def tool_fn(operation: str, params: dict | None = None):
                params = params or {}
                if operation == "help":
                    return _build_help(gname)
                return _dispatch(operation, gname, params)
            tool_fn.__name__ = gname
            tool_fn.__qualname__ = gname
            tool_fn.__doc__ = gdoc
            return tool_fn

        mcp.tool(structured_output=False)(_compact(_make_tool(group_name, doc)))


_register_tools()
