"""Единый HTTP-клиент для платформенных модулей.

См. docs/dev/03_API_STANDARDS.txt §2, решение A7 (04_DECISIONS):
  таймауты, backoff+jitter, Retry-After, маскирование секретов, TLS verify ON.
  debug_bodies → logs/http-debug, ≤10 МБ/запись, ретенция 7 дней, маскирование.
"""

from __future__ import annotations

import logging
import os
import random
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from . import __version__ as CORE_VERSION

logger = logging.getLogger(__name__)

# Секреты в URL/заголовках/телах — маскируем при логировании.
_SECRET_RE = re.compile(
    r"(Bearer\s+)[A-Za-z0-9._\-~+/=]+|"
    r"(access_token|refresh_token|client_secret|api[_-]?key|token)=([^&\s\"']+)|"
    r"(\"?(?:access_token|refresh_token|client_secret|api[_-]?key|token)\"?\s*:\s*\")([^\"]+)",
    re.IGNORECASE,
)

# A7: лимит тела и ретенция
_DEBUG_MAX_BYTES = 10 * 1024 * 1024  # 10 МБ
_DEBUG_RETENTION_SEC = 7 * 24 * 3600  # 7 дней


def mask_secrets(text: str) -> str:
    """Заменить токены/секреты на *** (для логов и сообщений об ошибках)."""
    if not text:
        return text

    def _sub(m: re.Match[str]) -> str:
        g = m.groups()
        if g[0]:  # Bearer ...
            return f"{g[0]}***"
        if g[1]:  # key=value
            return f"{g[1]}=***"
        if g[3]:  # "key": "value"
            return f'{g[3]}***'
        return "***"

    return _SECRET_RE.sub(_sub, text)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = (response.headers.get("retry-after") or "").strip()
    if not raw:
        return None
    try:
        return max(1.0, min(120.0, float(raw)))
    except ValueError:
        return None


def cleanup_debug_dir(debug_dir: Path, *, retention_sec: float = _DEBUG_RETENTION_SEC) -> int:
    """Удалить файлы старше retention. Возвращает число удалённых."""
    if not debug_dir.is_dir():
        return 0
    cutoff = time.time() - retention_sec
    removed = 0
    try:
        for p in debug_dir.iterdir():
            if not p.is_file():
                continue
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                pass
    except OSError:
        pass
    return removed


class ModuleHttpClient:
    """HTTP-клиент модулей: таймауты, backoff, Retry-After, маскирование.

    Инъектируемый: в тестах передаётся mock / httpx.MockTransport.
    A7: debug_bodies + debug_dir → запись тел (masked) ≤10 МБ, ретенция 7 дней.
    """

    def __init__(
        self,
        *,
        platform: str = "unknown",
        module_version: str = "0.0.0",
        connect_timeout: float = 10.0,
        read_timeout: float = 60.0,
        upload_read_timeout: float = 600.0,
        max_retries: int = 5,
        verify: bool = True,
        debug_bodies: bool = False,
        debug_dir: str | Path | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.platform = platform
        self.module_version = module_version
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.upload_read_timeout = upload_read_timeout
        self.max_retries = max(1, max_retries)
        self.verify = verify
        self.debug_bodies = debug_bodies
        self.debug_dir = Path(debug_dir) if debug_dir else Path(
            os.getenv("ORCH_HTTP_DEBUG_DIR") or "logs/http-debug"
        )
        self._transport = transport
        self._ua = (
            f"orchestrator/{CORE_VERSION} "
            f"({platform} module/{module_version})"
        )
        self._debug_cleanup_done = False

    def _client(self, *, upload: bool = False) -> httpx.Client:
        read = self.upload_read_timeout if upload else self.read_timeout
        timeout = httpx.Timeout(connect=self.connect_timeout, read=read, write=read, pool=10.0)
        kwargs: dict[str, Any] = {
            "timeout": timeout,
            "verify": self.verify,
            "headers": {"User-Agent": self._ua, "Accept": "application/json"},
            "follow_redirects": False,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.Client(**kwargs)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: Any = None,
        data: bytes | None = None,
        content: Any = None,
        idempotent: bool = True,
        upload: bool = False,
    ) -> httpx.Response:
        """Выполнить запрос с ретраями только для безопасных/TRANSIENT случаев."""
        method_u = method.upper()
        # POST создания ресурса — не ретраим 5xx/timeout (риск дубля).
        safe_retry = idempotent and method_u in ("GET", "HEAD", "PUT", "DELETE", "PATCH")
        last_exc: Exception | None = None
        delays = [1.0, 2.0, 4.0, 8.0, 16.0]

        for attempt in range(self.max_retries):
            t0 = time.monotonic()
            try:
                with self._client(upload=upload) as client:
                    resp = client.request(
                        method_u,
                        url,
                        headers=headers,
                        params=params,
                        json=json,
                        content=content if content is not None else data,
                    )
                elapsed = time.monotonic() - t0
                self._log(method_u, url, resp.status_code, elapsed, resp)

                if resp.status_code == 429:
                    sleep_for = _retry_after_seconds(resp)
                    if sleep_for is None:
                        sleep_for = delays[min(attempt, len(delays) - 1)]
                        sleep_for += random.uniform(0, sleep_for * 0.25)
                    last_exc = httpx.HTTPStatusError(
                        "rate limited", request=resp.request, response=resp
                    )
                    if attempt + 1 >= self.max_retries:
                        return resp
                    time.sleep(sleep_for)
                    continue

                if resp.status_code >= 500 and safe_retry:
                    last_exc = httpx.HTTPStatusError(
                        f"server {resp.status_code}", request=resp.request, response=resp
                    )
                    if attempt + 1 >= self.max_retries:
                        return resp
                    sleep_for = delays[min(attempt, len(delays) - 1)]
                    sleep_for += random.uniform(0, sleep_for * 0.25)
                    time.sleep(sleep_for)
                    continue

                return resp
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout, httpx.ReadTimeout) as e:
                last_exc = e
                if not safe_retry and method_u == "POST":
                    raise
                if attempt + 1 >= self.max_retries:
                    raise
                sleep_for = delays[min(attempt, len(delays) - 1)]
                sleep_for += random.uniform(0, sleep_for * 0.25)
                logger.warning(
                    "http %s %s transient %s, retry in %.1fs (%s/%s)",
                    method_u,
                    mask_secrets(url),
                    type(e).__name__,
                    sleep_for,
                    attempt + 1,
                    self.max_retries,
                )
                time.sleep(sleep_for)

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("http retry exhausted")

    def _log(
        self,
        method: str,
        url: str,
        status: int,
        elapsed: float,
        resp: httpx.Response,
    ) -> None:
        safe_url = mask_secrets(url)
        parsed = urlparse(safe_url)
        path = parsed.path or "/"
        logger.info(
            "http %s %s%s → %s (%.2fs)",
            method,
            parsed.netloc,
            path,
            status,
            elapsed,
        )
        if self.debug_bodies and status >= 400:
            try:
                body = resp.text[:2048]
            except Exception:
                body = ""
            logger.debug("http body: %s", mask_secrets(body))
            self._write_debug_body(method, safe_url, status, resp)

    def _write_debug_body(
        self,
        method: str,
        safe_url: str,
        status: int,
        resp: httpx.Response,
    ) -> None:
        """A7: записать masked body в debug_dir, ≤10 МБ, ретенция 7 дней."""
        try:
            if not self._debug_cleanup_done:
                cleanup_debug_dir(self.debug_dir)
                self._debug_cleanup_done = True
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            raw = resp.content or b""
            if len(raw) > _DEBUG_MAX_BYTES:
                raw = raw[:_DEBUG_MAX_BYTES] + b"\n...[truncated]"
            text = mask_secrets(raw.decode("utf-8", errors="replace"))
            ts = time.strftime("%Y%m%d_%H%M%S")
            name = f"{ts}_{self.platform}_{status}_{method}.txt"
            # безопасное имя
            name = re.sub(r"[^\w.\-]", "_", name)[:180]
            path = self.debug_dir / name
            header = f"{method} {safe_url}\nstatus={status}\n---\n"
            path.write_text(header + text, encoding="utf-8")
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        except Exception:
            logger.debug("http debug write failed", exc_info=True)

    def get_json(self, url: str, **kwargs: Any) -> Any:
        r = self.request("GET", url, **kwargs)
        r.raise_for_status()
        if not r.content:
            return {}
        return r.json()

    def request_json(self, method: str, url: str, **kwargs: Any) -> Any:
        r = self.request(method, url, **kwargs)
        r.raise_for_status()
        if not r.content:
            return {}
        return r.json()
