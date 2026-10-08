# Rutube API Access

## External blocker
Partner / studio API access is required. Until granted:
- `platforms.rutube.enabled: false`
- Module returns honest `NotSupported` / auth_status.ok=false
- **No browser automation**

## After access
1. Implement upload + status poll + publication(date) in `platforms/rutube/`
2. Add e2e mock tests
3. Enable in stage config only

Application steps: contact Rutube partner/docs portal (owner responsibility).
