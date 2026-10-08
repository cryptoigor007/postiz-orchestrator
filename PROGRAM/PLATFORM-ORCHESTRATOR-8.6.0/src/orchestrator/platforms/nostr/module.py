from __future__ import annotations

import logging
import hashlib
import json
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

from ..base import (
    AuthStatus,
    MediaSpec,
    ModuleError,
    ModuleErrorCode,
    PlatformModule,
    PreparedMedia,
    PublishMeta,
    PublishResult,
    PublishStatus,
    RemoteItem,
    RemotePage,
)
from ..manifest import load_manifest

_MANIFEST = Path(__file__).with_name("manifest.yaml")

# secp256k1 / BIP340 constants
_P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_GX = int("79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798", 16)
_GY = 32670510020758816978083085130507043184471273380659243275938904335757337482424
_G = (_GX, _GY)


def _inv(x: int) -> int:
    return pow(x, _P - 2, _P)


def _point_add(a: tuple[int, int] | None, b: tuple[int, int] | None) -> tuple[int, int] | None:
    if a is None:
        return b
    if b is None:
        return a
    x1, y1 = a
    x2, y2 = b
    if x1 == x2 and (y1 + y2) % _P == 0:
        return None
    if a == b:
        m = (3 * x1 * x1) * _inv(2 * y1) % _P
    else:
        m = (y2 - y1) * _inv(x2 - x1) % _P
    x3 = (m * m - x1 - x2) % _P
    y3 = (m * (x1 - x3) - y1) % _P
    return x3, y3


def _point_mul(k: int, point: tuple[int, int] = _G) -> tuple[int, int] | None:
    k %= _N
    out = None
    addend = point
    while k:
        if k & 1:
            out = _point_add(out, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return out


def _tagged_hash(tag: str, data: bytes) -> bytes:
    tag_hash = hashlib.sha256(tag.encode("utf-8")).digest()
    return hashlib.sha256(tag_hash + tag_hash + data).digest()


def _schnorr_sign(msg32: bytes, secret32: bytes, aux32: bytes | None = None) -> tuple[bytes, bytes]:
    if len(msg32) != 32 or len(secret32) != 32:
        raise ValueError("BIP340 requires 32-byte message and secret")
    d0 = int.from_bytes(secret32, "big")
    if d0 <= 0 or d0 >= _N:
        raise ValueError("invalid secp256k1 private key")
    P = _point_mul(d0)
    if P is None:
        raise ValueError("invalid secp256k1 public point")
    px, py = P
    d = d0 if py % 2 == 0 else _N - d0
    aux = aux32 if aux32 is not None else bytes(32)
    if len(aux) != 32:
        raise ValueError("aux must be 32 bytes")
    t = bytes(a ^ b for a, b in zip(d.to_bytes(32, "big"), _tagged_hash("BIP0340/aux", aux)))
    k0 = int.from_bytes(_tagged_hash("BIP0340/nonce", t + px.to_bytes(32, "big") + msg32), "big") % _N
    if k0 == 0:
        raise ValueError("BIP340 nonce generation returned zero")
    R = _point_mul(k0)
    if R is None:
        raise ValueError("invalid nonce point")
    rx, ry = R
    k = k0 if ry % 2 == 0 else _N - k0
    e = int.from_bytes(_tagged_hash("BIP0340/challenge", rx.to_bytes(32, "big") + px.to_bytes(32, "big") + msg32), "big") % _N
    s = (k + e * d) % _N
    return rx.to_bytes(32, "big") + s.to_bytes(32, "big"), px.to_bytes(32, "big")


def _normalize_tags(raw: Any) -> list[list[str]]:
    if not raw:
        return []
    out: list[list[str]] = []
    for tag in raw:
        if isinstance(tag, (list, tuple)) and tag and all(x is not None for x in tag):
            out.append([str(x) for x in tag])
    return out


class _RelayClient:
    def __init__(self, relays: list[str], timeout: float = 12.0) -> None:
        self.relays = relays
        self.timeout = timeout

    @staticmethod
    def _socket_url(relay: str) -> str:
        r = relay.strip()
        if not r.startswith(("wss://", "ws://")):
            raise ValueError(f"invalid Nostr relay URL: {r}")
        return r

    def publish(self, event: dict[str, Any]) -> list[tuple[str, bool, str]]:
        import websocket

        results: list[tuple[str, bool, str]] = []
        message = json.dumps(["EVENT", event], ensure_ascii=False, separators=(",", ":"))
        for relay in self.relays:
            ws = None
            try:
                ws = websocket.create_connection(self._socket_url(relay), timeout=self.timeout)
                ws.send(message)
                raw = ws.recv()
                msg = json.loads(raw)
                if isinstance(msg, list) and len(msg) >= 4 and msg[0] == "OK":
                    results.append((relay, bool(msg[2]), str(msg[3] or "")))
                else:
                    results.append((relay, False, f"unexpected relay response: {msg!r}"))
            except Exception as exc:
                results.append((relay, False, str(exc)))
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception as exc:
                        logger.debug("Nostr relay close failed: %s", type(exc).__name__)
        return results

    def query(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        import websocket

        sub_id = f"orch-{uuid.uuid4().hex[:24]}"
        out: list[dict[str, Any]] = []
        for relay in self.relays:
            ws = None
            try:
                ws = websocket.create_connection(self._socket_url(relay), timeout=self.timeout)
                ws.send(json.dumps(["REQ", sub_id, filters], separators=(",", ":")))
                while True:
                    msg = json.loads(ws.recv())
                    if not isinstance(msg, list) or not msg:
                        continue
                    if msg[0] == "EVENT" and len(msg) >= 3 and isinstance(msg[2], dict):
                        out.append(msg[2])
                    elif msg[0] in {"EOSE", "CLOSED"}:
                        break
            except Exception:
                continue
            finally:
                if ws is not None:
                    try:
                        ws.send(json.dumps(["CLOSE", sub_id], separators=(",", ":")))
                    except Exception as exc:
                        logger.debug("Nostr relay close failed: %s", type(exc).__name__)
                    try:
                        ws.close()
                    except Exception as exc:
                        logger.debug("Nostr relay close failed: %s", type(exc).__name__)
        dedup: dict[str, dict[str, Any]] = {}
        for event in out:
            eid = str(event.get("id") or "")
            if eid:
                dedup[eid] = event
        return list(dedup.values())


class NostrModule(PlatformModule):
    """Native NIP-01 Nostr module using a BIP340 secp256k1 signer and relays."""

    def __init__(self, **deps: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.private_key = str(deps.get("private_key") or os.getenv("NOSTR_PRIVATE_KEY", "")).strip().lower().replace("0x", "")
        raw_relays = deps.get("relays")
        if raw_relays is None:
            raw_relays = os.getenv("NOSTR_RELAY_URLS", "")
        self.relays = [str(x).strip() for x in (raw_relays if isinstance(raw_relays, (list, tuple)) else str(raw_relays).split(",")) if str(x).strip()]
        self.default_kind = int(deps.get("kind") or os.getenv("NOSTR_DEFAULT_KIND", "1"))
        self._relay = deps.get("relay_client") or _RelayClient(self.relays)

    def _secret(self) -> bytes:
        if not self.private_key:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Nostr: NOSTR_PRIVATE_KEY is required")
        if len(self.private_key) != 64:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Nostr: private key must be 32-byte lowercase hex")
        try:
            raw = bytes.fromhex(self.private_key)
            int.from_bytes(raw, "big")
        except ValueError as exc:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Nostr: private key is not valid hex") from exc
        try:
            d = int.from_bytes(raw, "big")
            if d <= 0 or d >= _N:
                raise ValueError
        except ValueError as exc:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Nostr: private key is outside secp256k1 range") from exc
        return raw

    def _pubkey(self) -> str:
        point = _point_mul(int.from_bytes(self._secret(), "big"))
        if point is None:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Nostr: unable to derive public key")
        return point[0].to_bytes(32, "big").hex()

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not self.private_key:
            errors.append("Nostr: NOSTR_PRIVATE_KEY is required")
        elif len(self.private_key) != 64:
            errors.append("Nostr: NOSTR_PRIVATE_KEY must be 64 hex chars")
        if not self.relays:
            errors.append("Nostr: at least one NOSTR_RELAY_URLS relay is required")
        return errors

    def auth_status(self) -> AuthStatus:
        try:
            pubkey = self._pubkey()
            return AuthStatus(True, account=pubkey[:16], details=f"pubkey={pubkey}; relays={len(self.relays)}")
        except ModuleError as exc:
            return AuthStatus(False, account="nostr", details=exc.message)

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        if (media.kind or "text") != "text":
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Nostr: this module publishes text events; media should be represented by URL tags")
        return PreparedMedia(path=media.path, kind="text")

    def _build_event(self, content: str, *, kind: int, tags: list[list[str]], created_at: int | None = None) -> dict[str, Any]:
        pubkey = self._pubkey()
        created = int(created_at or time.time())
        serialized = json.dumps([0, pubkey, created, int(kind), tags, content], ensure_ascii=False, separators=(",", ":"),) .encode("utf-8")
        event_id = hashlib.sha256(serialized).digest()
        secret = self._secret()
        sig, _ = _schnorr_sign(event_id, secret, aux32=bytes(32))
        return {"id": event_id.hex(), "pubkey": pubkey, "created_at": created, "kind": int(kind), "tags": tags, "content": content, "sig": sig.hex()}

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        extra = dict(meta.extra or {})
        content = str(extra.get("content") or meta.description or meta.title or "").strip()
        if not content:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Nostr: event content is empty")
        kind = int(extra.get("kind") or self.default_kind)
        tags = _normalize_tags(extra.get("tags"))
        for url in extra.get("urls") or []:
            url_s = str(url).strip()
            if url_s:
                tags.append(["r", url_s])
        event = self._build_event(content, kind=kind, tags=tags, created_at=extra.get("created_at"))
        results = self._relay.publish(event)
        accepted = [r for r in results if r[1]]
        if not accepted:
            detail = "; ".join(f"{relay}: {msg}" for relay, _, msg in results) or "no relays configured"
            raise ModuleError(ModuleErrorCode.TRANSIENT, f"Nostr: no relay accepted event {event['id']}: {detail}", retryable=True)
        return PublishResult(external_id=event["id"], url="", state="published")

    def get_status(self, external_id: str) -> PublishStatus:
        rows = self._relay.query({"ids": [str(external_id)], "limit": 1})
        if not rows:
            return PublishStatus(state="deleted", raw={"id": external_id})
        return PublishStatus(state="published", raw=rows[0])

    def delete(self, external_id: str) -> bool:
        extra_tags = [["e", str(external_id)]]
        event = self._build_event("", kind=5, tags=extra_tags)
        results = self._relay.publish(event)
        if not any(ok for _, ok, _ in results):
            raise ModuleError(ModuleErrorCode.TRANSIENT, f"Nostr: no relay accepted deletion event {event['id']}", retryable=True)
        return True

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        author = self._pubkey()
        filter_: dict[str, Any] = {"authors": [author], "limit": min(max(1, int(limit)), 100)}
        if kinds:
            filter_["kinds"] = [int(k) for k in kinds if str(k).isdigit()]
        else:
            filter_["kinds"] = [1]
        if since:
            filter_["since"] = int(since.timestamp())
        if until:
            filter_["until"] = int(until.timestamp())
        rows = self._relay.query(filter_)
        rows.sort(key=lambda e: (int(e.get("created_at") or 0), str(e.get("id") or "")), reverse=True)
        start = int(cursor or 0) if str(cursor or "").isdigit() else 0
        page = rows[start : start + filter_["limit"]]
        next_cursor = str(start + len(page)) if start + len(page) < len(rows) else None
        items = [
            RemoteItem(
                platform="nostr",
                external_id=str(row.get("id") or ""),
                title=str(row.get("content") or "")[:120],
                description=str(row.get("content") or ""),
                published_at=(str(row.get("created_at") or "") if row.get("created_at") is not None else None),
                status="published",
                media_type="text",
                raw=row,
            )
            for row in page
            if isinstance(row, dict) and row.get("id")
        ]
        return RemotePage(items=items, next_cursor=next_cursor)


def create_module(**deps: Any) -> NostrModule:
    return NostrModule(**deps)
