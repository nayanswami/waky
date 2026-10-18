"""Keep-alive HTTPS connections to Groq. Re-using one TLS connection saves roughly 0.3 to 0.8 s per request."""
from __future__ import annotations

import http.client
import threading

HOST = "api.groq.com"


class Pool:
    def __init__(self, host: str = HOST) -> None:
        self.host = host
        self._conn: http.client.HTTPSConnection | None = None
        self._lock = threading.Lock()

    def _close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None

    def request(self, method: str, path: str, body: bytes | None, headers: dict[str, str], timeout: float = 30) -> tuple[int, dict[str, str], bytes]:
        """Returns (status, headers, body). Retries once on a stale connection."""
        with self._lock:
            last: Exception | None = None
            for _attempt in range(2):
                try:
                    if self._conn is None:
                        self._conn = http.client.HTTPSConnection(self.host, timeout=timeout)
                    self._conn.timeout = timeout
                    self._conn.request(method, path, body=body, headers=headers)
                    resp = self._conn.getresponse()
                    data = resp.read()
                    hdrs = {k.lower(): v for k, v in resp.getheaders()}
                    if hdrs.get("connection", "").lower() == "close":
                        self._close()
                    return resp.status, hdrs, data
                except (http.client.HTTPException, OSError) as exc:
                    last = exc
                    self._close()
            raise last or OSError("request failed")


CHAT = Pool()
STT = Pool()


def warm(api_key: str) -> None:
    """Open both connections ahead of the first dictation (a cheap authenticated GET)."""
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "Waky/1.0"}
    for pool in (CHAT, STT):
        try:
            pool.request("GET", "/openai/v1/models", None, headers, timeout=8)
        except Exception:
            pass
