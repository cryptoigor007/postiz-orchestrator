from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from pathlib import Path

from .platforms import ModuleRegistry, default_registry
from .platforms.base import AuthStatus, MediaSpec, ModuleError, ModuleErrorCode, NotSupported, PreparedMedia, PublishMeta
from .platforms.manifest import load_manifest
from .platforms.module_sdk import ModuleSDK


@dataclass
class CanaryResult:
    module_id: str
    static_ok: bool = False
    dry_ok: bool = False
    live_ok: bool = False
    state: str = "blocked"
    notes: list[str] = field(default_factory=list)


class ProviderContractCanary:
    """Provider contract/canary harness with explicit non-publishing live mode."""

    def __init__(self, registry: ModuleRegistry | None = None):
        self.registry = registry or default_registry()

    def static(self, module_id: str) -> CanaryResult:
        result = CanaryResult(module_id=module_id)
        manifest_path = Path(__file__).resolve().parent / "platforms" / module_id / "manifest.yaml"
        manifest = load_manifest(manifest_path)
        ModuleSDK.validate_manifest(manifest)
        result.static_ok = True
        result.notes.append(f"manifest={manifest.module_version}")
        result.notes.append(f"publish={bool(manifest.capabilities.get('publish', False))}")
        return result

    def dry(self, module_id: str) -> CanaryResult:
        result = self.static(module_id)
        try:
            module = self.registry.create(module_id, dry_run=True)
        except ModuleError as exc:
            if exc.code in {ModuleErrorCode.AUTH_REQUIRED, ModuleErrorCode.AUTH_EXPIRED, ModuleErrorCode.REVIEW_REQUIRED, ModuleErrorCode.DEPENDENCY_DOWN}:
                result.dry_ok = True
                result.state = "dry_access_blocked"
                result.notes.append(f"constructor-access-blocked:{exc.code}")
                return result
            raise
        try:
            st = module.auth_status()
            if not isinstance(st, AuthStatus):
                raise TypeError(f"{module_id}: auth_status() must return AuthStatus")
        except ModuleError as exc:
            if exc.code not in {ModuleErrorCode.AUTH_REQUIRED, ModuleErrorCode.AUTH_EXPIRED, ModuleErrorCode.REVIEW_REQUIRED, ModuleErrorCode.DEPENDENCY_DOWN}:
                raise
            st = AuthStatus(False, account=module_id, details=str(exc))
        errors = getattr(module, "validate_config", lambda cfg: [])({})
        if not isinstance(errors, list):
            raise TypeError(f"{module_id}: validate_config() must return list[str]")
        # Media preparation is intentionally not exercised with a fake file here.
        # Provider-specific media contracts already have dedicated fixtures; this harness
        # validates static/capability/auth/config lifecycle without inventing media bytes.
        result.dry_ok = True
        result.state = "dry_ready"
        if st.ok:
            result.notes.append("dry-auth-ok")
        else:
            result.notes.append(f"dry-auth-blocked:{st.details[:160]}")
        if errors:
            result.notes.append(f"config:{'; '.join(str(x) for x in errors)[:240]}")
        return result

    def dry_all(self) -> list[CanaryResult]:
        out: list[CanaryResult] = []
        for mid in self.registry.ids():
            try:
                out.append(self.dry(mid))
            except Exception as exc:
                out.append(CanaryResult(module_id=mid, state="error", notes=[f"{type(exc).__name__}: {exc}"]))
        return out

    def live_read_only(self, module_ids: list[str] | None = None) -> list[CanaryResult]:
        if os.getenv("ORCH_CANARY_LIVE", "").lower() not in {"1", "true", "yes"}:
            return [CanaryResult(module_id="__live__", state="disabled", notes=["set ORCH_CANARY_LIVE=1 to enable read-only live canary"])]
        ids = module_ids or self.registry.ids()
        out: list[CanaryResult] = []
        for mid in ids:
            result = self.static(mid)
            try:
                module = self.registry.create(mid, dry_run=False)
                auth = module.auth_status()
                if not isinstance(auth, AuthStatus):
                    raise TypeError("auth_status did not return AuthStatus")
                result.live_ok = bool(auth.ok)
                result.state = "live_auth_ok" if auth.ok else "live_auth_blocked"
                result.notes.append(auth.details[:240])
                try:
                    page = module.list_remote_items(limit=1)
                    result.notes.append(f"inventory_items={len(page.items)}")
                except NotSupported:
                    result.notes.append("inventory=not_supported")
            except Exception as exc:
                result.state = "live_error"
                result.notes.append(f"{type(exc).__name__}: {exc}")
            out.append(result)
        return out


    def live_write(self, module_ids: list[str] | None = None) -> list[CanaryResult]:
        """Run an explicitly armed real-account canary with cleanup.

        This method is intentionally fail-closed: a real write requires both
        ORCH_CANARY_LIVE_WRITE=1 and ORCH_CANARY_CONFIRM=PUBLISH_A_CANARY.
        A public/uncleanable provider additionally requires
        ORCH_CANARY_ALLOW_PUBLIC=1. The media file is supplied via
        ORCH_CANARY_MEDIA and is never invented by the harness.
        """
        armed = os.getenv("ORCH_CANARY_LIVE_WRITE", "").lower() in {"1", "true", "yes"}
        confirmed = os.getenv("ORCH_CANARY_CONFIRM", "") == "PUBLISH_A_CANARY"
        if not (armed and confirmed):
            return [CanaryResult(module_id="__live_write__", state="disabled", notes=[
                "requires ORCH_CANARY_LIVE_WRITE=1 and ORCH_CANARY_CONFIRM=PUBLISH_A_CANARY"
            ])]
        media_path = Path(os.getenv("ORCH_CANARY_MEDIA", "")).expanduser()
        if not media_path.is_file():
            return [CanaryResult(module_id="__live_write__", state="blocked", notes=[
                f"ORCH_CANARY_MEDIA not found: {media_path}"
            ])]
        ids = module_ids or [x.strip() for x in os.getenv("ORCH_CANARY_MODULES", "youtube,telegram,facebook").split(",") if x.strip()]
        allow_public = os.getenv("ORCH_CANARY_ALLOW_PUBLIC", "").lower() in {"1", "true", "yes"}
        out: list[CanaryResult] = []
        for mid in ids:
            result = self.static(mid)
            external_id = ""
            module = None
            try:
                module = self.registry.create(mid, dry_run=False)
                auth = module.auth_status()
                if not isinstance(auth, AuthStatus) or not auth.ok:
                    result.state = "live_auth_blocked"
                    result.notes.append(getattr(auth, "details", "auth_status failed")[:240])
                    out.append(result)
                    continue
                caps = module.capabilities()
                cleanup_capable = bool(caps.get("delete"))
                if not cleanup_capable and not allow_public:
                    result.state = "live_blocked_cleanup"
                    result.notes.append("provider has no delete capability; set ORCH_CANARY_ALLOW_PUBLIC=1 to override")
                    out.append(result)
                    continue
                prepared: PreparedMedia = module.prepare(MediaSpec(path=str(media_path), kind="video"))
                meta = PublishMeta(
                    title=f"ORCHESTRATOR CANARY {datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
                    description="Automated canary — cleanup immediately after verification.",
                    extra={"canary": True, "post_mode": "media"},
                )
                if mid == "youtube" and not allow_public and hasattr(module, "upload"):
                    upload = module.upload(prepared, meta)
                    external_id = upload.external_id
                    result.notes.append(f"uploaded_private:{external_id}")
                else:
                    if not allow_public:
                        result.state = "live_blocked_public"
                        result.notes.append("provider publish is public; set ORCH_CANARY_ALLOW_PUBLIC=1")
                        out.append(result)
                        continue
                    published = module.publish(prepared, meta)
                    external_id = published.external_id
                    result.notes.append(f"published:{external_id}")
                if not external_id:
                    raise ModuleError(ModuleErrorCode.FATAL, "canary returned empty external_id")
                try:
                    status = module.get_status(external_id)
                    result.notes.append(f"status:{status.state}")
                except NotSupported:
                    result.notes.append("status=not_supported")
                if cleanup_capable:
                    cleaned = bool(module.delete(external_id))
                    result.notes.append(f"cleanup:{cleaned}")
                    if not cleaned:
                        raise ModuleError(ModuleErrorCode.FATAL, "canary cleanup returned false")
                elif not allow_public:
                    raise ModuleError(ModuleErrorCode.FATAL, "uncleanable live write without explicit public override")
                result.live_ok = True
                result.state = "live_write_ok"
            except Exception as exc:
                result.state = "live_write_error"
                result.notes.append(f"{type(exc).__name__}: {exc}")
                if external_id and module is not None:
                    try:
                        if bool(module.capabilities().get("delete")):
                            module.delete(external_id)
                            result.notes.append("cleanup_after_error=attempted")
                    except Exception as cleanup_exc:
                        result.notes.append(f"cleanup_after_error_failed:{type(cleanup_exc).__name__}:{cleanup_exc}")
            out.append(result)
        return out

    def summary(self, results: list[CanaryResult]) -> dict[str, Any]:
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "count": len(results),
            "static_ok": sum(1 for r in results if r.static_ok),
            "dry_ok": sum(1 for r in results if r.dry_ok),
            "live_ok": sum(1 for r in results if r.live_ok),
            "states": {s: sum(1 for r in results if r.state == s) for s in sorted({r.state for r in results})},
            "results": [asdict(r) for r in results],
        }
