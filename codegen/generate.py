"""Codegen: openapi.json → src/glitchtip_mcp/_generated.py.

Reads OpenAPI 3.1 spec from a snapshot (default codegen/openapi.json) and
emits a Python module of one function per operation. Each function:

  * matches the operation's HTTP verb to GlitchTipClient.{get,post,put,patch,delete}
  * exposes path parameters as required positional str args
  * exposes query parameters as keyword args with type hints (Literal for enums)
  * for POST/PUT/PATCH, flattens top-level fields of the request body schema
    into keyword args; nested objects are typed as dict

Run: python codegen/generate.py
"""
from __future__ import annotations

import json
import keyword
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "codegen" / "openapi.json"
OUT = ROOT / "src" / "glitchtip_mcp" / "_generated.py"

PY_KEYWORDS = set(keyword.kwlist) | {"params", "json"}


# ── Spec helpers ────────────────────────────────────────────────────────────


def load_spec(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def resolve(spec: dict, schema: dict | None) -> dict:
    if not schema:
        return {}
    seen: set[str] = set()
    while isinstance(schema, dict) and "$ref" in schema:
        ref = schema["$ref"]
        if ref in seen:
            return {}
        seen.add(ref)
        parts = ref.lstrip("#/").split("/")
        node: dict | list = spec
        for p in parts:
            node = node[p]
        schema = node  # type: ignore[assignment]
    return schema if isinstance(schema, dict) else {}


def py_type(spec: dict, schema: dict | None) -> tuple[str, list[str]]:
    """Map an OpenAPI schema to (python type expression, [literal values])."""
    s = resolve(spec, schema)
    if not s:
        return "dict", []

    # union (anyOf/oneOf) — collapse to first non-null variant
    for key in ("anyOf", "oneOf"):
        if key in s:
            variants = [v for v in s[key] if resolve(spec, v).get("type") != "null"]
            if variants:
                return py_type(spec, variants[0])
            return "dict", []

    if s.get("enum"):
        # only use Literal for string-enum
        if s.get("type") == "string" or all(isinstance(v, str) for v in s["enum"]):
            vals = [str(v) for v in s["enum"]]
            literal = "Literal[" + ", ".join(repr(v) for v in vals) + "]"
            return literal, vals

    t = s.get("type")
    if t == "integer":
        return "int", []
    if t == "number":
        return "float", []
    if t == "boolean":
        return "bool", []
    if t == "string":
        return "str", []
    if t == "array":
        inner, _ = py_type(spec, s.get("items") or {})
        return f"list[{inner}]", []
    if t == "object":
        return "dict", []
    return "dict", []


# ── Naming ──────────────────────────────────────────────────────────────────


def _strip_opid_prefix(op_id: str) -> str:
    # operationId shapes:
    #   apps_<app>_api_<op_name>  where <app> may contain underscores (e.g. "api_tokens")
    #   glitchtip_api_api_<op_name>
    if op_id.startswith("glitchtip_api_api_"):
        return op_id[len("glitchtip_api_api_"):]
    if op_id.startswith("apps_"):
        idx = op_id.find("_api_", 5)
        if idx > 0:
            return op_id[idx + 5:]
    return op_id


def fn_name(op_id: str | None, method: str, path: str) -> str:
    if op_id:
        name = _strip_opid_prefix(op_id)
    else:
        # fallback: method + path
        cleaned = re.sub(r"\{(\w+)\}", r"by_\1", path).strip("/")
        cleaned = re.sub(r"[^a-z0-9_]", "_", cleaned.lower())
        name = f"{method.lower()}_{cleaned}"
    # double underscores collapse
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def safe_arg(name: str) -> str:
    n = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if n in PY_KEYWORDS:
        n += "_"
    if n and n[0].isdigit():
        n = "_" + n
    return n


# ── Parameter analysis ──────────────────────────────────────────────────────


def collect_params(spec: dict, op: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Split OpenAPI `parameters` into path, required-query, optional-query."""
    path_params: list[dict] = []
    req_query: list[dict] = []
    opt_query: list[dict] = []
    for p in op.get("parameters", []):
        p = resolve(spec, p)
        loc = p.get("in")
        if loc == "path":
            path_params.append(p)
        elif loc == "query":
            (req_query if p.get("required") else opt_query).append(p)
    return path_params, req_query, opt_query


def body_fields(spec: dict, op: dict) -> tuple[str, list[tuple[str, dict, bool]]]:
    """Return (schema_name, [(field, schema, required)]). Empty list → opaque body."""
    body = op.get("requestBody")
    if not body:
        return "", []
    body = resolve(spec, body)
    media = body.get("content", {}).get("application/json")
    if not media or "schema" not in media:
        return "", []
    schema = media["schema"]
    raw_name = ""
    if "$ref" in schema:
        raw_name = schema["$ref"].rsplit("/", 1)[-1]
    s = resolve(spec, schema)
    if s.get("type") != "object":
        return raw_name, []
    props = s.get("properties") or {}
    required = set(s.get("required") or [])
    fields = [(n, p, n in required) for n, p in props.items()]
    return raw_name, fields


# ── Code emission ───────────────────────────────────────────────────────────


def emit_function(spec: dict, path: str, method: str, op: dict) -> str:
    op_id = op.get("operationId")
    name = fn_name(op_id, method, path)

    path_params, req_query, opt_query = collect_params(spec, op)
    body_schema_name, fields = body_fields(spec, op)

    # gather signature
    sig_parts: list[str] = []
    used: set[str] = set()
    arg_to_orig: dict[str, str] = {}

    for p in path_params:
        a = safe_arg(p["name"])
        used.add(a)
        arg_to_orig[a] = p["name"]
        sig_parts.append(f"{a}: str")

    # required body fields
    body_arg_names: list[tuple[str, str, str, list[str]]] = []
    if method.upper() in ("POST", "PUT", "PATCH") and fields:
        for fname, fschema, is_req in [(n, s, r) for n, s, r in fields if r]:
            a = safe_arg(fname)
            if a in used:
                a = a + "_body"
            used.add(a)
            arg_to_orig[a] = fname
            t, lits = py_type(spec, fschema)
            sig_parts.append(f"{a}: {t}")
            body_arg_names.append((a, fname, t, lits))

    # required query params (rare)
    query_arg_names: list[tuple[str, str, str, list[str]]] = []
    for q in req_query:
        a = safe_arg(q["name"])
        if a in used:
            a = a + "_query"
        used.add(a)
        arg_to_orig[a] = q["name"]
        t, lits = py_type(spec, q.get("schema") or {})
        sig_parts.append(f"{a}: {t}")
        query_arg_names.append((a, q["name"], t, lits))

    # optional query params
    for q in opt_query:
        a = safe_arg(q["name"])
        if a in used:
            a = a + "_query"
        used.add(a)
        arg_to_orig[a] = q["name"]
        t, lits = py_type(spec, q.get("schema") or {})
        sig_parts.append(f"{a}: {t} | None = None")
        query_arg_names.append((a, q["name"], t, lits))

    # optional body fields
    if method.upper() in ("POST", "PUT", "PATCH") and fields:
        for fname, fschema, is_req in [(n, s, r) for n, s, r in fields if not r]:
            a = safe_arg(fname)
            if a in used:
                a = a + "_body"
            used.add(a)
            arg_to_orig[a] = fname
            t, lits = py_type(spec, fschema)
            sig_parts.append(f"{a}: {t} | None = None")
            body_arg_names.append((a, fname, t, lits))

    # opaque body fallback when there are no flattenable fields but body is required
    has_opaque_body = (
        method.upper() in ("POST", "PUT", "PATCH")
        and not fields
        and op.get("requestBody")
    )
    if has_opaque_body:
        sig_parts.append("body: dict | list | None = None")

    # ── body assembly ──
    lines: list[str] = []
    lines.append(f"def {name}({', '.join(sig_parts)}):")
    summary = op.get("summary") or op.get("description") or name
    summary = summary.strip().splitlines()[0][:120]
    lines.append(f"    \"\"\"{summary}\"\"\"")

    # path interpolation
    f_path = path
    for p in path_params:
        original = p["name"]
        py = next((a for a, o in arg_to_orig.items() if o == original), original)
        f_path = f_path.replace("{" + original + "}", "{" + py + "}")

    # query dict
    has_query = bool(query_arg_names)
    if has_query:
        lines.append("    _q: dict = {}")
        for a, orig, _t, _lits in query_arg_names:
            lines.append(f"    if {a} is not None:")
            lines.append(f"        _q[{orig!r}] = {a}")

    # body dict
    has_body_fields = method.upper() in ("POST", "PUT", "PATCH") and bool(body_arg_names)
    if has_body_fields:
        lines.append("    _b: dict = {}")
        for a, orig, _t, _lits in body_arg_names:
            lines.append(f"    if {a} is not None:")
            lines.append(f"        _b[{orig!r}] = {a}")

    # call
    verb = method.lower()
    call_path = f"f\"{f_path}\""
    args = []
    if verb in ("post", "put", "patch"):
        if has_body_fields:
            args.append("_b or None")
        elif has_opaque_body:
            args.append("body")
        else:
            args.append("None")
        if has_query:
            args.append("params=_q or None")
        call_str = f"_get_client().{verb}({call_path}, {', '.join(args)})"
    elif verb == "delete":
        if has_query:
            args.append("params=_q or None")
            call_str = f"_get_client().delete({call_path}, {', '.join(args)})"
        else:
            call_str = f"_get_client().delete({call_path})"
    else:  # get
        if has_query:
            call_str = f"_get_client().get({call_path}, params=_q or None)"
        else:
            call_str = f"_get_client().get({call_path})"

    lines.append(f"    return _ok({call_str})")
    return "\n".join(lines)


def main() -> None:
    spec = load_spec(SPEC)
    out_lines: list[str] = [
        "# GENERATED by codegen/generate.py — DO NOT EDIT",
        "from __future__ import annotations",
        "",
        "from typing import Literal  # noqa: F401",
        "",
        "from ._helpers import _ok, _get_client",
        "",
        "",
    ]

    funcs: list[tuple[str, str]] = []  # (method, function-source)
    seen_names: dict[str, int] = {}
    method_order = {"get": 0, "post": 1, "put": 2, "patch": 3, "delete": 4}

    for path, item in spec["paths"].items():
        for method, op in item.items():
            if method.lower() not in method_order:
                continue
            src = emit_function(spec, path, method, op)
            # detect generated function name
            first = src.split("\n", 1)[0]
            m = re.match(r"def (\w+)", first)
            base = m.group(1) if m else "unknown"
            n = seen_names.get(base, 0)
            seen_names[base] = n + 1
            if n:
                src = src.replace(f"def {base}(", f"def {base}_{n}(", 1)
            funcs.append((method.lower(), src))

    funcs.sort(key=lambda x: (method_order[x[0]], x[1]))
    last_method = ""
    for m, src in funcs:
        if m != last_method:
            out_lines.append(f"# ── {m.upper()} ──")
            out_lines.append("")
            last_method = m
        out_lines.append(src)
        out_lines.append("")
        out_lines.append("")

    OUT.write_text("\n".join(out_lines).rstrip() + "\n")
    print(f"wrote {OUT} ({sum(1 for _ in funcs)} operations)")


if __name__ == "__main__":
    main()
