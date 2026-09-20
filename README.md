# glitchtip-mcp

MCP server for [GlitchTip](https://glitchtip.com) — open-source Sentry-compatible error tracking.

Exposes the GlitchTip REST API as typed MCP tools, grouped by risk:

| Group | Operations |
|---|---|
| `glitchtip_read` | Issues, events, projects, organizations, teams, alerts, monitors, releases, performance, logs, stats |
| `glitchtip_write` | Create/update for the same resources |
| `glitchtip_delete` | Delete resources (irreversible) |
| `glitchtip_admin_read` | Auth tokens, billing, account, setup wizards, debug-file listings |
| `glitchtip_admin_write` | Token management, account changes, billing, recovery codes, debug-file uploads, SDK ingest |
| `glitchtip_version` | Server version + service status (root tool) |

## Install

```json
{
  "mcpServers": {
    "glitchtip": {
      "command": "uvx",
      "args": ["--refresh", "--extra-index-url", "https://nikitatsym.github.io/glitchtip-mcp/simple", "glitchtip-mcp"],
      "env": {
        "GLITCHTIP_URL": "https://errors.example.com",
        "GLITCHTIP_TOKEN": "..."
      }
    }
  }
}
```

Get a token from your profile → Auth Tokens.

### HTTP

`glitchtip-mcp --http` serves streamable HTTP at `http://127.0.0.1:8000/mcp` (`--host`, `--port`) instead of stdio, same environment variables. No authentication: put a gateway in front.

The package can also be imported: `mcp`, `Settings`, the client class, and `client_var` (a `ContextVar` the host sets per request) let one process serve several instances.

## Usage

Each group is a meta-tool. Call with `operation="help"` to list operations, or pass `operation` + `params`:

```
glitchtip_read(operation="ListIssues", params={"organization_slug": "my-org"})
glitchtip_write(operation="CreateProject",
                params={"organization_slug": "org", "team_slug": "team",
                        "name": "web", "platform": "javascript"})
```

## Codegen

`_generated.py` is built from `codegen/openapi.json` (snapshot of `/api/openapi.json`):

```
python codegen/generate.py
```

Update the snapshot, re-run, and edit `tools.py::_SCOPE_GROUPS` if new operations
need a non-default bucket.
