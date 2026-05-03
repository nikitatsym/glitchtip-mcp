"""GlitchTip MCP server — auto-discovery, grouping, and dispatch."""

import inspect
import types
import typing

from mcp.server.fastmcp import FastMCP

from . import tools as _tools_module
from .annotations import ANNOTATIONS
from .registry import ROOT

mcp = FastMCP("glitchtip")


def _to_pascal(name: str) -> str:
    return "".join(w.capitalize() for w in name.split("_"))


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
        if hint and _is_bool_hint(hint) and not isinstance(val, bool):
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
    return _coerce_call(fn, params)


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
            mcp.tool()(fn)
        else:
            if group.name not in groups:
                groups[group.name] = (group, {})
            groups[group.name][1][name] = fn

    for group_name, (group, fns) in groups.items():
        ops = {_to_pascal(n): fn for n, fn in fns.items()}
        _group_ops[group_name] = ops
        for pascal_name in ops:
            _all_grouped[pascal_name] = group_name

        def _make_tool(gname, gdoc):
            def tool_fn(operation: str, params: dict = {}):
                if operation == "help":
                    return _build_help(gname)
                return _dispatch(operation, gname, params)
            tool_fn.__name__ = gname
            tool_fn.__qualname__ = gname
            tool_fn.__doc__ = gdoc
            return tool_fn

        mcp.tool()(_make_tool(group_name, group.doc))


_register_tools()
