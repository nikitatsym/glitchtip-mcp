from __future__ import annotations

import httpx

from .config import get_settings


class GlitchTipError(Exception):
    """GlitchTip API error with full context."""

    def __init__(self, status: int, method: str, path: str, body):
        self.status = status
        self.method = method
        self.path = path
        self.body = body
        super().__init__(f"GlitchTip API {status} {method} {path}: {body}")


class GlitchTipClient:
    """REST client for GlitchTip API.

    Bearer token authentication. All paths relative to base URL.
    Returns parsed JSON or None for empty/204 responses.
    """

    def __init__(self, base_url: str | None = None, token: str | None = None):
        s = get_settings()
        self._base = (base_url or s.glitchtip_url).rstrip("/")
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {token or s.glitchtip_token}"},
            timeout=30.0,
        )

    def _call(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json: dict | list | None = None,
    ):
        r = self._http.request(
            method,
            f"{self._base}{path}",
            params=params,
            json=json,
        )
        if r.status_code >= 400:
            try:
                body = r.json()
            except Exception:
                body = r.text
            raise GlitchTipError(r.status_code, method, path, body)
        if r.status_code == 204 or not r.content:
            return None
        try:
            return r.json()
        except Exception:
            return r.text

    def get(self, path: str, params: dict | None = None):
        return self._call("GET", path, params=params)

    def post(self, path: str, json: dict | list | None = None, params: dict | None = None):
        return self._call("POST", path, params=params, json=json)

    def put(self, path: str, json: dict | list | None = None, params: dict | None = None):
        return self._call("PUT", path, params=params, json=json)

    def patch(self, path: str, json: dict | list | None = None, params: dict | None = None):
        return self._call("PATCH", path, params=params, json=json)

    def delete(self, path: str, params: dict | None = None):
        return self._call("DELETE", path, params=params)
