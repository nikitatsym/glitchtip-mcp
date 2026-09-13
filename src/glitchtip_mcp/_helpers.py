from contextvars import ContextVar

from .client import GlitchTipClient

# The host binds one client per request when it serves several instances in one process.
client_var: ContextVar[GlitchTipClient | None] = ContextVar("glitchtip_client", default=None)
_client: GlitchTipClient | None = None


def _get_client() -> GlitchTipClient:
    global _client
    if (bound := client_var.get()) is not None:
        return bound
    if _client is None:
        _client = GlitchTipClient()
    return _client


def _ok(data):
    if data is None:
        return {"status": "ok"}
    return data
