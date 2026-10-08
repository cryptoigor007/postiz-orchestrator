# Runbook: Auth / OAuth
1. Set TOKEN_BROKER_URL + secrets, or tokens/<platform>.json
2. Start OAuth: GET /oauth/{provider}/start (PKCE)
3. Callback consumes session once; binds platform_accounts
4. auth_status via GET /api/ops
5. Fail-closed: no token → AUTH_REQUIRED
