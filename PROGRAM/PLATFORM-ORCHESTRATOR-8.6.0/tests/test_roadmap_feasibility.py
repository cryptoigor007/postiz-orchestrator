from __future__ import annotations


def test_signal_is_explicit_feasibility_boundary():
    from orchestrator.platforms.signal.module import SignalFeasibilityModule

    mod = SignalFeasibilityModule()
    assert mod.manifest.capabilities["publish"] is False
    assert mod.manifest.publish_mode == "unsupported"
    assert mod.auth_status().ok is False


def test_skool_is_explicit_feasibility_boundary():
    from orchestrator.platforms.skool.module import SkoolFeasibilityModule

    mod = SkoolFeasibilityModule()
    assert mod.manifest.capabilities["publish"] is False
    assert mod.manifest.publish_mode == "unsupported"
    assert mod.auth_status().ok is False


def test_medium_is_explicit_api_deprecated_boundary():
    from orchestrator.platforms.medium.module import MediumDeprecatedModule
    from orchestrator.platforms.base import ModuleError, ModuleErrorCode

    mod = MediumDeprecatedModule()
    assert mod.manifest.capabilities["publish"] is False
    assert mod.manifest.publish_mode == "unsupported"
    assert mod.auth_status().ok is False
    try:
        mod.publish(None, None)
    except ModuleError as exc:
        assert exc.code == ModuleErrorCode.API_DEPRECATED
    else:
        raise AssertionError("Medium publish must fail closed as API_DEPRECATED")


def test_rutube_is_explicit_partner_boundary():
    from orchestrator.platforms.rutube.module import RutubePartnerModule
    from orchestrator.platforms.base import NotSupported

    mod = RutubePartnerModule()
    assert mod.manifest.publish_mode == "partner"
    assert mod.manifest.capabilities["publish"] is False
    assert mod.auth_status().ok is False
    try:
        mod.publish(None, None)
    except NotSupported:
        pass
    else:
        raise AssertionError("Rutube publish must remain partner-gated")
