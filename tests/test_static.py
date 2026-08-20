"""Static checks: codegen, import, group registration."""

from __future__ import annotations

import ast
import inspect
import json
import keyword
import os
import re
import typing
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


class _BodyRecorder:
    def __init__(self):
        self.bodies = []
        self.calls = []

    def _record(self, method, path, json=None, params=None):
        self.calls.append((method, path, params, json))
        self.bodies.append(json)

    def post(self, path, json=None, params=None):
        return self._record("POST", path, json=json, params=params)

    def put(self, path, json=None, params=None):
        return self._record("PUT", path, json=json, params=params)

    def patch(self, path, json=None, params=None):
        return self._record("PATCH", path, json=json, params=params)

    def delete(self, path, json=None, params=None):
        return self._record("DELETE", path, json=json, params=params)

_FREE_FORM_MAP_OPERATIONS = frozenset(
    {"difs_assemble_api", "update_user_notification_alerts"}
)
_HTTP_METHODS = ("get", "post", "put", "patch", "delete")
_PYTHON_RESERVED_NAMES = set(keyword.kwlist) | {"params", "json"}


def _sample_for_hint(hint):
    origin = typing.get_origin(hint)
    args = typing.get_args(hint)
    if origin is typing.Literal:
        return args[0]
    if origin is list:
        return []
    if origin is dict:
        return {}
    if args:
        return _sample_for_hint(next(arg for arg in args if arg is not type(None)))
    if hint is bool:
        return True
    if hint is int:
        return 1
    if hint is float:
        return 1.0
    return "value"


def _load_openapi_spec() -> dict:
    path = Path(__file__).resolve().parents[1] / "codegen" / "openapi.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_openapi_ref(spec: dict, value: object) -> dict:
    """Resolve local OpenAPI references without depending on the generator."""
    current = value
    seen: set[str] = set()
    while isinstance(current, dict) and "$ref" in current:
        ref = current["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            raise AssertionError(f"invalid or cyclic OpenAPI reference: {ref!r}")
        seen.add(ref)
        target: object = spec
        try:
            for part in ref[2:].split("/"):
                if not isinstance(target, dict):
                    raise TypeError
                target = target[part.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError) as exc:
            raise AssertionError(f"unresolvable OpenAPI reference: {ref}") from exc
        siblings = {key: child for key, child in current.items() if key != "$ref"}
        current = {**target, **siblings} if siblings else target
    if not isinstance(current, dict):
        raise TypeError(f"OpenAPI reference does not resolve to an object: {current!r}")
    return current


def _schema_allows_null(spec: dict, schema: object) -> bool:
    """Independently identify the OpenAPI forms that allow JSON null."""
    resolved = _resolve_openapi_ref(spec, schema)
    schema_type = resolved.get("type")
    if (
        resolved.get("nullable") is True
        or schema_type == "null"
        or (isinstance(schema_type, list) and "null" in schema_type)
    ):
        return True
    for key in ("anyOf", "oneOf"):
        variants = resolved.get(key, [])
        if isinstance(variants, list) and any(
            _schema_allows_null(spec, variant) for variant in variants
        ):
            return True
    return False


def _expected_python_name(raw_name: str) -> str:
    """Map an OpenAPI name under Python's identifier rules, independently."""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", raw_name)
    if name in _PYTHON_RESERVED_NAMES:
        name += "_"
    if name and name[0].isdigit():
        name = "_" + name
    return name


def _expected_function_name(
    operation_id: object, method: str, path: str
) -> str:
    if isinstance(operation_id, str) and operation_id:
        if operation_id.startswith("glitchtip_api_api_"):
            name = operation_id.removeprefix("glitchtip_api_api_")
        elif operation_id.startswith("apps_"):
            prefix_end = operation_id.find("_api_", 5)
            name = (
                operation_id[prefix_end + 5 :]
                if prefix_end > 0
                else operation_id
            )
        else:
            name = operation_id
    else:
        name = re.sub(r"\{(\w+)\}", r"by_\1", path).strip("/")
        name = f"{method}_{re.sub(r'[^a-z0-9_]', '_', name.lower())}"
    return re.sub(r"_+", "_", name).strip("_")


def _expected_generated_names(spec: dict) -> dict[tuple[str, str], str]:
    seen: dict[str, int] = {}
    names: dict[tuple[str, str], str] = {}
    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if method not in _HTTP_METHODS:
                continue
            base = _expected_function_name(operation.get("operationId"), method, path)
            duplicate_index = seen.get(base, 0)
            seen[base] = duplicate_index + 1
            names[(path, method)] = (
                base if not duplicate_index else f"{base}_{duplicate_index}"
            )
    return names


def _operation_parameters(
    spec: dict, operation: dict, location: str, required: bool | None
) -> list[dict]:
    parameters = []
    for raw_parameter in operation.get("parameters", []):
        parameter = _resolve_openapi_ref(spec, raw_parameter)
        if parameter.get("in") != location:
            continue
        if required is not None and bool(parameter.get("required")) != required:
            continue
        parameters.append(parameter)
    return parameters


def _expected_required_arguments(
    spec: dict,
    operation: dict,
    required_fields: tuple[tuple[str, bool], ...],
    has_opaque_body: bool,
) -> tuple[tuple[str, ...], dict[str, str]]:
    used: set[str] = set()
    required_args: list[str] = []
    for parameter in _operation_parameters(spec, operation, "path", None):
        name = _expected_python_name(parameter["name"])
        used.add(name)
        required_args.append(name)

    field_args: dict[str, str] = {}
    for field, _nullable in required_fields:
        name = _expected_python_name(field)
        if name in used:
            name += "_body"
        used.add(name)
        required_args.append(name)
        field_args[field] = name

    for parameter in _operation_parameters(spec, operation, "query", True):
        name = _expected_python_name(parameter["name"])
        if name in used:
            name += "_query"
        used.add(name)
        required_args.append(name)

    if has_opaque_body:
        required_args.append("body")
    return tuple(required_args), field_args


def _required_openapi_bodies(spec: dict):
    function_names = _expected_generated_names(spec)
    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if method not in _HTTP_METHODS:
                continue
            if not operation or "requestBody" not in operation:
                continue
            request_body = _resolve_openapi_ref(spec, operation["requestBody"])
            if not request_body.get("required"):
                continue
            json_content = request_body.get("content", {}).get("application/json")
            if not isinstance(json_content, dict) or "schema" not in json_content:
                continue
            schema = _resolve_openapi_ref(spec, json_content["schema"])
            has_declared_properties = (
                schema.get("type") == "object"
                and isinstance(schema.get("properties"), dict)
            )
            properties = schema["properties"] if has_declared_properties else {}
            required_fields = tuple(
                (field, _schema_allows_null(spec, properties[field]))
                for field in schema.get("required", [])
                if field in properties
            )
            yield {
                "name": function_names[(path, method)],
                "has_declared_properties": has_declared_properties,
                "is_free_form_map": (
                    schema.get("type") == "object"
                    and not has_declared_properties
                    and "additionalProperties" in schema
                ),
                "has_opaque_body": not has_declared_properties,
                "properties": properties,
                "required_fields": required_fields,
                "operation": operation,
            }


def _json_request_body_methods(spec: dict) -> set[str]:
    """Return every OpenAPI method whose operation accepts a JSON body."""
    methods = set()
    for path_item in spec["paths"].values():
        for method, operation in path_item.items():
            if not isinstance(operation, dict) or "requestBody" not in operation:
                continue
            request_body = _resolve_openapi_ref(spec, operation["requestBody"])
            if "application/json" in request_body.get("content", {}):
                methods.add(method)
    return methods


def test_openapi_json_body_methods_are_all_audited():
    spec = _load_openapi_spec()
    assert _json_request_body_methods(spec) <= set(_HTTP_METHODS)


def _hint_allows_null(hint: object) -> bool:
    return hint is type(None) or type(None) in typing.get_args(hint)


def test_required_openapi_bodies_cannot_be_omitted_at_wire(monkeypatch):
    """Required JSON bodies and fields preserve the independently parsed contract."""
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import _generated, server
    spec = _load_openapi_spec()
    cases = tuple(_required_openapi_bodies(spec))
    free_form_maps = {
        case["name"] for case in cases if case["is_free_form_map"]
    }
    failures = []
    missing_maps = _FREE_FORM_MAP_OPERATIONS - free_form_maps
    if missing_maps:
        failures.append(
            "required free-form map operations missing from the OpenAPI guard: "
            f"{sorted(missing_maps)}"
        )
    expected_operations = set(_expected_generated_names(spec).values())
    actual_operations = {
        name
        for name, function in inspect.getmembers(_generated, inspect.isfunction)
        if not name.startswith("_")
    }
    if actual_operations != expected_operations:
        failures.append(
            "generated operation names disagree with the OpenAPI naming contract: "
            f"expected {sorted(expected_operations)}, got {sorted(actual_operations)}"
        )

    recorder = _BodyRecorder()
    monkeypatch.setattr(_generated, "_get_client", lambda: recorder)
    for body_info in cases:
        try:
            fn = getattr(_generated, body_info["name"])
        except AttributeError:
            failures.append(
                f"{body_info['name']} is absent from generated public operations"
            )
            continue

        signature = inspect.signature(fn)
        hints = typing.get_type_hints(fn)
        expected_required, field_args = _expected_required_arguments(
            spec,
            body_info["operation"],
            body_info["required_fields"],
            body_info["has_opaque_body"],
        )
        actual_required = tuple(
            name
            for name, parameter in signature.parameters.items()
            if parameter.default is inspect.Parameter.empty
        )
        if actual_required != expected_required:
            failures.append(
                f"{body_info['name']} required argument order is {actual_required}, "
                f"expected {expected_required}"
            )
        base_params = {
            name: _sample_for_hint(hints.get(name)) for name in actual_required
        }

        if body_info["has_opaque_body"]:
            body_parameter = signature.parameters.get("body")
            if (
                body_parameter is None
                or body_parameter.default is not inspect.Parameter.empty
            ):
                failures.append(
                    f"{body_info['name']} allows its required opaque body to be omitted"
                )
                continue
            if set(typing.get_args(hints.get("body"))) != {dict, list}:
                failures.append(
                    f"{body_info['name']} does not expose body: dict | list"
                )

            opaque_body = {"caller-key": {"nested": True}}
            recorder.bodies.clear()
            try:
                server._coerce_call(fn, {**base_params, "body": opaque_body})
            except (TypeError, ValueError) as exc:
                failures.append(
                    f"{body_info['name']} rejected a valid opaque body: {exc}"
                )
                continue
            if not recorder.bodies:
                failures.append(f"{body_info['name']} made no request")
            elif recorder.bodies[-1] is not opaque_body:
                failures.append(
                    f"{body_info['name']} did not serialize the opaque body verbatim"
                )

            recorder.bodies.clear()
            try:
                server._coerce_call(fn, {**base_params, "body": None})
            except (TypeError, ValueError):
                if recorder.bodies:
                    failures.append(
                        f"{body_info['name']} sent an explicit null required body"
                    )
            else:
                failures.append(
                    f"{body_info['name']} accepted an explicit null required body"
                )
        else:
            recorder.bodies.clear()
            try:
                server._coerce_call(fn, base_params)
            except (TypeError, ValueError) as exc:
                failures.append(
                    f"{body_info['name']} rejected a valid required body: {exc}"
                )
                continue
            if not recorder.bodies:
                failures.append(f"{body_info['name']} made no request")
                continue
            body = recorder.bodies[-1]
            if body is None:
                failures.append(f"{body_info['name']} sent no required request body")
                continue
            required_names = {
                field for field, _nullable in body_info["required_fields"]
            }
            if not required_names and body != {}:
                failures.append(
                    f"{body_info['name']} did not serialize an empty declared object"
                )
            for field in body_info["properties"]:
                if field not in required_names and field in body:
                    failures.append(
                        f"{body_info['name']}.{field} serialized despite omission"
                    )

        for field, nullable in body_info["required_fields"]:
            field_arg = field_args[field]
            parameter = signature.parameters.get(field_arg)
            if parameter is None or parameter.default is not inspect.Parameter.empty:
                failures.append(
                    f"{body_info['name']}.{field} allows required-field omission"
                )
                continue
            if _hint_allows_null(hints.get(field_arg)) != nullable:
                failures.append(
                    f"{body_info['name']}.{field} nullability disagrees with OpenAPI"
                )

            recorder.bodies.clear()
            try:
                server._coerce_call(fn, {**base_params, field_arg: None})
            except (TypeError, ValueError):
                if nullable:
                    failures.append(
                        f"{body_info['name']}.{field} rejected a nullable JSON null"
                    )
                elif recorder.bodies:
                    failures.append(
                        f"{body_info['name']}.{field} reached the wire before rejection"
                    )
                continue

            if not nullable:
                failures.append(
                    f"{body_info['name']}.{field} accepted an explicit null"
                )
            elif (
                not recorder.bodies
                or recorder.bodies[-1].get(field, object()) is not None
            ):
                failures.append(
                    f"{body_info['name']}.{field} did not serialize a nullable JSON null"
                )

    assert not failures, "; ".join(failures)


def test_delete_email_forwards_required_json_body(monkeypatch):
    os.environ.setdefault("GLITCHTIP_URL", "https://example.invalid")
    os.environ.setdefault("GLITCHTIP_TOKEN", "noop")
    from glitchtip_mcp import _generated, server

    recorder = _BodyRecorder()
    monkeypatch.setattr(_generated, "_get_client", lambda: recorder)

    assert server._coerce_call(
        _generated.delete_email,
        {"user_id": "42", "email": "delete@example.com"},
    ) == {"status": "ok"}
    assert recorder.calls == [
        (
            "DELETE",
            "/api/0/users/42/emails/",
            None,
            {"email": "delete@example.com"},
        )
    ]

    recorder.calls.clear()
    with pytest.raises(ValueError, match="Required request field email cannot be null"):
        server._coerce_call(
            _generated.delete_email,
            {"user_id": "42", "email": None},
        )
    assert not recorder.calls


def test_client_delete_forwards_json_without_losing_query_params(monkeypatch):
    from glitchtip_mcp.client import GlitchTipClient

    client = GlitchTipClient.__new__(GlitchTipClient)
    calls = []
    payload = {"email": "delete@example.com"}
    params = {"audit": "true"}

    def record(method, path, params=None, json=None):
        calls.append((method, path, params, json))
        return {"status": "ok"}

    monkeypatch.setattr(client, "_call", record)

    assert client.delete("/api/0/users/42/emails/", json=payload, params=params) == {
        "status": "ok"
    }
    assert calls == [("DELETE", "/api/0/users/42/emails/", params, payload)]


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
