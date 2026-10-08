#!/bin/bash
# Social-stack architecture gate: module inventory, honest capability manifests,
# provider isolation primitives, shared HTTP boundary and version registry.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src:scripts
PY=python3

echo "[social-gate] provider catalog ↔ manifests"
$PY - <<'PY'
from pathlib import Path
from orchestrator.provider_catalog import load_provider_catalog
from orchestrator.platforms.manifest import load_manifest

catalog = load_provider_catalog()
ids = {e.id for e in catalog}
manifest_dirs = {p.parent.name for p in Path('src/orchestrator/platforms').glob('*/manifest.yaml')}
missing = sorted(ids - manifest_dirs)
if missing:
    raise SystemExit(f"provider catalog entries without manifests: {missing}")
for p in sorted(Path('src/orchestrator/platforms').glob('*/manifest.yaml')):
    load_manifest(p)
print(f"catalog={len(catalog)} manifests={len(manifest_dirs)} unique=OK")
PY

echo "[social-gate] no direct provider HTTP calls"
if grep -RniE 'httpx\.(get|post|put|patch|delete)|requests\.(get|post|put|patch|delete)' src/orchestrator/platforms --include='*.py'; then
  echo "SOCIAL HTTP GATE FAIL: use ModuleHttpClient"; exit 1
fi

echo "[social-gate] provider modules instantiate and planned modules stay unsupported"
SOCIAL_GATE_TMP=$(mktemp -d)
trap 'rm -rf "$SOCIAL_GATE_TMP"' EXIT
TIKTOK_INBOX_PATH="$SOCIAL_GATE_TMP/tiktok_inbox.json" $PY - <<'PY'
from orchestrator.platforms import default_registry
from orchestrator.platforms._scaffold import PlannedProviderModule
reg = default_registry()
required = set()
from orchestrator.provider_catalog import load_provider_catalog
for entry in load_provider_catalog():
    required.add(entry.id)
    if not reg.has(entry.id):
        raise SystemExit(f"provider not registered: {entry.id}")
    m = reg.create(entry.id)
    state = entry.implementation_state
    if state in {'SCAFFOLD', 'SCAFFOLD_TRANSITION', 'SCAFFOLD_PARTNER', 'FEASIBILITY'}:
        if getattr(m.manifest, 'publish_mode', 'unsupported') != 'unsupported':
            raise SystemExit(f"non-live provider advertises publish_mode: {entry.id}")
    if state in {'PARTIAL_NATIVE', 'IMPLEMENTED', 'IMPLEMENTED_INBOX', 'IMPLEMENTED_NATIVE'}:
        # A real/partial provider may not inherit the generic scaffold implementation
        # for any capability it advertises.
        if bool(getattr(m.manifest, 'capabilities', {}).get('publish', False)) and getattr(type(m), 'publish', None) is getattr(PlannedProviderModule, 'publish', None):
            raise SystemExit(f"provider {entry.id} advertises publish but still uses PlannedProviderModule.publish")
        mode = getattr(m.manifest, 'publish_mode', 'unsupported')
        if mode not in {'direct','orchestrator','inbox','unsupported','partner'}:
            raise SystemExit(f"provider has invalid publish_mode: {entry.id}")
print(f"registered={len(reg.ids())} catalog={len(required)}")
PY

echo "[social-gate] critical test tautologies"
if grep -RniE '^[[:space:]]*assert[[:space:]]+True([[:space:]]*(#.*)?)?$|assert[[:space:]].*[[:space:]]or[[:space:]]+True([[:space:]]*(#.*)?)?$' \
    tests/test_platform_zero*.py tests/test_p0*.py 2>/dev/null; then
  echo "SOCIAL TEST GATE FAIL"; exit 1
fi

echo "[social-gate] api versions"
$PY - <<'PY'
from orchestrator.api_versions import validate_no_sunset
errs = validate_no_sunset()
if errs:
    raise SystemExit("sunset API versions: " + "; ".join(errs))
print("api_versions=OK")
PY

echo "[social-gate] modular primitives"
$PY - <<'PY'
from orchestrator.provider_supervisor import ProviderSupervisor
from orchestrator.platforms.capabilities import PublishingModule, MessagingModule, IdentityModule, WebhookModule, MediaModule
for cls in (PublishingModule, MessagingModule, IdentityModule, WebhookModule, MediaModule):
    assert hasattr(cls, '__annotations__')
print('capability_interfaces=OK provider_supervisor=OK')
PY

echo "[social-gate] OK"
