# Modular Social Orchestrator Architecture

## Non-negotiable invariant

**Provider failure must never become Core failure. Every provider failure must be visible, measurable, alertable and recoverable.**

The application is modular at four levels:

1. Code isolation — every provider is an independent module.
2. Data isolation — provider/account identity, tokens, jobs, attempts and health are account-scoped.
3. Failure isolation — retries, circuit breakers and queues are isolated by provider/account.
4. Observability isolation — health, quota, latency, errors and alerts are tracked per provider/account.

## Core layers

```text
VideoMaker / ShortsMaker
        |
        v
Content + Revision + DistributionTarget
        |
        v
Scheduler + DurableJobs + EPS
        |
        v
Provider Kernel
  |       |        |        |        |
 Auth   Media   Webhooks  Health   Access
        |
        v
Capabilities
  |             |             |
Publishing   Messaging     Identity
        |
        v
Provider modules
```

The Core must not contain provider-specific endpoints, scopes, payloads or error parsing.

## Provider module contract

Each provider owns:

```text
manifest.yaml
auth.py
account.py
publish.py
media.py
status.py
webhook.py
reconcile.py
limits.py
tests/
```

Not every provider implements every capability. Unsupported capabilities must be declared as unsupported, never faked.

## Failure isolation

Each provider/account has:

```text
queue
retry policy
circuit breaker
health state
quota state
auth state
webhook state
```

A provider can move:

```text
healthy -> degraded -> open -> recovery_probe -> healthy
```

The scheduler skips new work for an open circuit while other providers continue normally.

## External API access

Provider approval states are first-class:

```text
NOT_CONFIGURED
AUTHORIZING
CONNECTED
SCOPES_MISSING
BUSINESS_VERIFICATION_REQUIRED
APP_REVIEW_REQUIRED
ADVANCED_ACCESS_REQUIRED
AUDIT_REQUIRED
LIVE
PARTNER_REQUIRED
TOKEN_EXPIRED
DEGRADED
DISCONNECTED
```

A provider module being present in the registry does **not** mean its external API access is approved.

## Current deployment boundary

SQLite remains the default single-host durable store. Durable jobs, outbox, publish attempts and webhook inbox are database-backed. The interfaces are intentionally storage-agnostic so PostgreSQL can be introduced later without rewriting providers.
