# Runbook: Incident
1. ORCH_READ_ONLY=1 to stop publishes
2. pause_platform via API/UI
3. Check publish_log + last_error on EPS
4. lease_until stuck publishing: auto-reclaim after expiry
