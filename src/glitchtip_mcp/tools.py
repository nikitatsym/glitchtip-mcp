"""GlitchTip tool operations grouped by risk level.

All generated functions are imported and assigned to MCP groups.
Functions not explicitly grouped become standalone ROOT tools.
"""

import inspect
import re
from importlib.metadata import version

from . import _generated
from ._generated import *  # re-export all generated ops
from ._helpers import _get_client
from .registry import ROOT, Group, _op

# ── Groups ──────────────────────────────────────────────────────────────────

glitchtip_read = Group(
    "glitchtip_read",
    "Query GlitchTip resources (safe, read-only).\n\n"
    "Call with operation=\"help\" to list all available read operations.\n"
    "Otherwise pass the operation name and a JSON object with parameters.\n\n"
    "Example: glitchtip_read(operation=\"ListIssues\", "
    "params={\"organization_slug\": \"my-org\"})",
)

glitchtip_write = Group(
    "glitchtip_write",
    "Create or update GlitchTip resources.\n\n"
    "Call with operation=\"help\" to list all available write operations.\n"
    "Otherwise pass the operation name and a JSON object with parameters.\n\n"
    "Example: glitchtip_write(operation=\"CreateProject\", "
    "params={\"organization_slug\": \"org\", \"team_slug\": \"team\", \"name\": \"web\"})",
)

glitchtip_delete = Group(
    "glitchtip_delete",
    "Delete GlitchTip resources (destructive, irreversible).\n\n"
    "Call with operation=\"help\" to list all available delete operations.\n"
    "Otherwise pass the operation name and a JSON object with parameters.\n\n"
    "Example: glitchtip_delete(operation=\"DeleteProject\", "
    "params={\"organization_slug\": \"org\", \"project_slug\": \"web\"})",
)

glitchtip_admin_read = Group(
    "glitchtip_admin_read",
    "Query auth tokens, billing, user account, setup wizards, debug-file uploads.\n\n"
    "Call with operation=\"help\" to list all available admin read operations.",
)

glitchtip_admin_write = Group(
    "glitchtip_admin_write",
    "Manage auth tokens, user account, billing, recovery codes, debug-file uploads, "
    "Sentry SDK ingest endpoints, setup wizards.\n\n"
    "Call with operation=\"help\" to list all available admin write operations.",
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _to_snake(name: str) -> str:
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()


# ── Group assignments (snake_case generated names) ──────────────────────────

_SCOPE_GROUPS: dict[Group, list[str]] = {
    glitchtip_read: [
        # Issues, comments, events, hashes, user reports
        "issues_list_issues",
        "issues_get_issue",
        "issues_list_project_issues",
        "issues_list_issue_commits",
        "issues_list_issue_tags",
        "issues_issue_stats",
        "comments_list_comments",
        "events_list_issue_event",
        "events_get_issue_event",
        "events_get_latest_issue_event",
        "events_list_project_issue_event",
        "events_get_project_issue_event",
        "events_get_event_json",
        "hashes_list_issue_hashes",
        "user_reports_list_user_reports",
        # Logs
        "list_logs",
        "get_log",
        "get_log_stats",
        "list_log_resources",
        # Organizations & members
        "list_organizations",
        "get_organization",
        "list_organization_members",
        "get_organization_member",
        "list_team_organization_members",
        # Environments
        "list_environments",
        "list_environment_projects",
        # Projects, keys
        "list_projects",
        "get_project",
        "list_organization_projects",
        "list_team_projects",
        "list_project_keys",
        "get_project_key",
        # Teams
        "list_teams",
        "get_team",
        "list_project_teams",
        # Alerts
        "list_project_alerts",
        # Monitors (uptime)
        "list_monitors",
        "get_monitor",
        "list_monitor_checks",
        # Status pages
        "list_status_pages",
        # Releases, deploys, commits, files
        "list_releases",
        "get_release",
        "list_project_releases",
        "get_project_release",
        "list_release_files",
        "get_organization_release_file",
        "list_project_release_files",
        "get_project_release_file",
        "list_deploys",
        "list_commits",
        # Repositories
        "list_repositories",
        # Performance / transactions / spans / N+1
        "list_transaction_groups",
        "get_transaction_group",
        "list_transaction_spans",
        "list_span_groups",
        "list_n_plus_one_patterns",
        "get_transaction_trend",
        # Stats
        "stats_v2",
        # Users (listing)
        "list_users",
    ],
    glitchtip_write: [
        # Issues, comments
        "issues_update_issue",
        "issues_update_issues",
        "issues_update_organization_issue",
        "comments_add_comment",
        "comments_update_comment",
        # Organizations & members
        "create_organization",
        "update_organization",
        "create_organization_member",
        "update_organization_member",
        "set_organization_owner",
        # Projects, keys
        "create_project",
        "update_project",
        "create_project_key",
        "update_project_key",
        # Teams
        "create_team",
        "update_team",
        "add_member_to_team",
        "add_team_to_project",
        # Environments
        "update_environment_project",
        # Alerts
        "create_project_alert",
        "update_project_alert",
        "test_project_alert",
        # Monitors
        "create_monitor",
        "update_monitor",
        "heartbeat_check",
        # Status pages
        "create_status_page",
        # Releases, deploys, commits
        "create_release",
        "update_release",
        "create_project_release",
        "update_project_release",
        "assemble_release",
        "create_deploy",
        "create_commits",
        # Repositories
        "create_repository",
    ],
    glitchtip_delete: [
        "issues_delete_issue",
        "issues_delete_issues",
        "hashes_delete_hash",
        "comments_delete_comment",
        "delete_organization",
        "delete_organization_member",
        "delete_member_from_team",
        "delete_team_from_project",
        "delete_team",
        "delete_project",
        "delete_project_key",
        "delete_project_alert",
        "delete_monitor",
        "delete_organization_release",
        "delete_organization_release_file",
        "delete_project_release",
        "delete_project_release_file",
    ],
    glitchtip_admin_read: [
        "get_settings",
        "list_api_tokens",
        "get_user",
        "list_emails",
        "get_notifications",
        "user_notification_alerts",
        "get_accept_invite",
        "generate_recovery_codes",
        "setup_wizard",
        "setup_wizard_hash",
        "list_stripe_products",
        "get_stripe_subscription",
        "subscription_events_count_for_period",
        "subscription_events_count_daily",
        "list_dsyms",
        "get_chunk_upload_info",
        "get_embed_error_page",
    ],
    glitchtip_admin_write: [
        # Auth tokens
        "create_api_token",
        "delete_api_token",
        # Account
        "update_user",
        "delete_user",
        "create_email",
        "delete_email",
        "set_email_as_primary",
        "send_confirm_email",
        "update_notifications",
        "update_user_notification_alerts",
        # Recovery & invites
        "set_recovery_codes",
        "accept_invite",
        # Setup wizard
        "setup_wizard_set_token",
        "setup_wizard_delete",
        # Stripe
        "create_stripe_session",
        "stripe_billing_portal_session",
        "stripe_create_subscription",
        # SDK ingest (Sentry-compat)
        "event_store",
        "event_security",
        # Debug-file uploads / source maps
        "dsyms",
        "chunk_upload",
        "difs_assemble_api",
        "project_reprocessing",
        "artifact_bundle_assemble",
        # Embed user feedback
        "submit_embed_error_page",
        # Importer
        "importer",
    ],
}


# ── Register grouped ops ────────────────────────────────────────────────────

_grouped: set[str] = set()


def _register_groups():
    for group, op_names in _SCOPE_GROUPS.items():
        for snake in op_names:
            fn = getattr(_generated, snake, None)
            if fn is None:
                raise RuntimeError(
                    f"tools.py references {snake!r} but it does not exist in _generated"
                )
            _op(group)(fn)
            _grouped.add(snake)


_register_groups()


# ── Custom operations ───────────────────────────────────────────────────────

def _present_fields(value: dict, names: tuple[str, ...]) -> dict:
    return {name: value[name] for name in names if value.get(name) is not None}


def who_am_i():
    """Get the authenticated account and token metadata."""
    response = _get_client().get("/api/0/")
    user = response["user"]
    auth = response["auth"]
    if user is not None and not isinstance(user, dict):
        raise TypeError("GlitchTip API returned an invalid user")
    if auth is not None and not isinstance(auth, dict):
        raise TypeError("GlitchTip API returned invalid auth metadata")

    result = {"authenticated": user is not None}
    if user is not None:
        result["user"] = _present_fields(
            user,
            ("id", "username", "email", "name", "isSuperuser", "isActive"),
        )
    if auth is not None:
        result["auth"] = _present_fields(auth, ("id", "label", "scopes", "created"))
    return result


_op(glitchtip_read)(who_am_i)


# ── Custom ROOT operation: version ──────────────────────────────────────────


def glitchtip_version():
    """Get the MCP server version and GlitchTip service status."""
    try:
        response = _get_client().get("/api/settings/")
        service = {
            "status": "ok",
            "version": response["version"],
        }
    except Exception:  # noqa: BLE001 - version check must not crash the whole tool
        service = {"status": "error"}
    return {
        "mcp": version("glitchtip-mcp"),
        "service": service,
    }


_op(ROOT)(glitchtip_version)
_grouped.add("glitchtip_version")

_GENERATED_ROOT_EXCLUSIONS = frozenset({"api_root"})


# ── Auto-ROOT for any ungrouped generated function ──────────────────────────

for _name, _fn in inspect.getmembers(_generated, inspect.isfunction):
    if _name.startswith("_"):
        continue
    if _name not in _grouped and _name not in _GENERATED_ROOT_EXCLUSIONS:
        _op(ROOT)(_fn)
