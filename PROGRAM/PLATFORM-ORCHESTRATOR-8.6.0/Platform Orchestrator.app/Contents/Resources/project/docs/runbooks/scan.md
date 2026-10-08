# Runbook: Remote Scan
1. POST /api/inventory/scan
2. remote_scans may be partial
3. Matches: one candidate → claimable; two → pending_review (no auto-claim)
4. Badges: PLATFORM | ORCHESTRATOR | PARTIAL
