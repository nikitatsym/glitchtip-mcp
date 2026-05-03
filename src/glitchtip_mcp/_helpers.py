from .client import GlitchTipClient

_client: GlitchTipClient | None = None


def _get_client() -> GlitchTipClient:
    global _client
    if _client is None:
        _client = GlitchTipClient()
    return _client


def _ok(data):
    if data is None:
        return {"status": "ok"}
    return data
