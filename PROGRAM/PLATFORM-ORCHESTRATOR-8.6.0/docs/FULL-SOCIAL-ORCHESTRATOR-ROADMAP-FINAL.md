# PLATFORM ORCHESTRATOR — FINAL MASTER ROADMAP
## Independent Native Social / Messaging Orchestrator — Postiz-Free, Modular, Fault-Isolated

**Revision:** FINAL v3
**Date:** 2026-10-01
**Basis:** current HARD_CUT archive + DEEP-ANALYSIS-AND-RESIDUAL-CLOSE + second-pass code audit + current provider documentation checked on 2026-10-01.

---

# 0. What this document means

This document supersedes the earlier `FULL-SOCIAL-ORCHESTRATOR-ROADMAP.md` and `FULL-SOCIAL-ORCHESTRATOR-ROADMAP-V2.md` for implementation planning.

The target is:

> **A self-hosted, native, modular social/messaging orchestrator for VideoMaker/ShortsMaker that has no Postiz runtime dependency, isolates provider failures, exposes provider health in real time, and can add or remove providers without changing the Core.**

This is not a promise that every platform on the internet will always expose a public server-side API. A provider is considered “supported” only when its official/current access model allows the capability being claimed. Restricted, partner-only, approval-only, or feasibility-gated providers remain explicitly represented in the system rather than being faked as fully supported.

The target is broader than the current HARD_CUT YT+TG scope, but it does not silently include multi-tenant SaaS, AI/RAG, a full unified inbox product, Temporal, or browser-agent automation as required dependencies.

---

# 1. The non-negotiable architecture rule: everything provider-specific is modular

## 1.1 Core must not know provider details

The Core must know only generic contracts:

```text
Domain
EPS
Content / Revisions
Scheduler
Jobs
Idempotency
Reconciliation
Auth lifecycle
Media transfer
Webhooks / Event Inbox
Provider registry
Health / Metrics / Alerts
```

The Core must NOT contain provider-specific `if platform == ...` branches.

Bad:

```python
if platform == "instagram":
    ...
elif platform == "youtube":
    ...
```

Good:

```text
Core
  -> Capability contract
  -> Provider registry
  -> Provider module
```

## 1.2 Capability interfaces

Do not force every provider into one `PlatformModule.publish()` API.

Required interface families:

```text
PublishingModule
MessagingModule
IdentityModule / AccountModule
MediaModule
WebhookModule
StatusModule
ReconciliationModule
AnalyticsModule (optional)
```

A provider implements only the capabilities it actually supports.

Examples:

```text
Instagram = Publishing + Identity + Media + Webhook + optional Messaging
Facebook  = Publishing + Identity + Media + Webhook
Threads   = Publishing + Identity + Media + Status
WhatsApp  = Messaging + Identity + Media + Webhook
Viber     = Messaging + Identity + Webhook
Telegram  = Publishing + Messaging + Identity + Webhook
Twitch    = Streaming/Publishing capabilities, not fake SocialPost semantics
```

## 1.3 Module isolation invariant

**Provider failure must never become Core failure.**

A failure in TikTok must not stop YouTube, Instagram, Telegram, etc.

A token failure in Instagram account A must not disable Instagram account B.

A webhook failure in Viber must not stop the scheduler.

Each provider/account is a failure domain.

---

# 2. Provider module structure

Every provider must have a standard module shape:

```text
platforms/<provider>/
    manifest.yaml
    module.py
    auth.py
    account.py
    media.py
    publish.py
    status.py
    reconcile.py
    webhook.py
    limits.py
    errors.py
    tests/
```

Some providers may share a vendor Core:

```text
platforms/meta/
    client.py
    auth.py
    token.py
    webhook.py

platforms/facebook/
platforms/instagram/
platforms/threads/
platforms/whatsapp/
```

Shared vendor infrastructure is allowed; shared provider state is not.

---

# 3. Provider SDK / module contract

Create an explicit internal Module SDK.

Each module declares:

```text
module_id
module_version
api_contract_version
provider_api_version
capabilities
account_types
auth_strategy
media strategies
status authority
webhook support
review/access requirements
```

Module lifecycle:

```text
load
validate
initialize
health_probe
ready
paused
shutdown
```

A module is not “installed” merely because its directory exists.

---

# 4. Canonical provider inventory — complete current target

The following is the canonical provider/integration inventory for this roadmap.

The baseline is the current Postiz documentation/provider tree, including the later-added channels such as Moltbook, MeWe, Whop, Skool and Tumblr. Postiz’s current documentation also distinguishes special connection variants such as LinkedIn Page and provider identifiers such as Warpcast/Farcaster and Google My Business. citeturn627273search0turn627273search1turn798675search3

## 4.1 Postiz-parity baseline — 33 current integration targets

| # | Integration target | Canonical internal name | Type | Module state target |
|---:|---|---|---|---|
| 1 | X | `x` | Social | Native |
| 2 | LinkedIn | `linkedin` | Social | Native |
| 3 | LinkedIn Page | `linkedin_page` | Social / Organization variant | Native |
| 4 | Reddit | `reddit` | Community/Social | Native, subject to current access model |
| 5 | Instagram | `instagram` | Social | Native |
| 6 | Facebook Pages | `facebook` | Social | Native |
| 7 | Threads | `threads` | Social | Native |
| 8 | YouTube | `youtube` | Video | Native |
| 9 | Google Business Profile | `gmb` | Business publishing | Native |
| 10 | TikTok | `tiktok` | Video/Social | Native Direct Post when approved |
| 11 | Pinterest | `pinterest` | Social | Native |
| 12 | Bluesky | `bluesky` | Social / AT Protocol | Native |
| 13 | Mastodon | `mastodon` | Federated Social | Native per instance |
| 14 | Lemmy | `lemmy` | Federated Community | Native per server |
| 15 | Farcaster (Warpcast) | `farcaster` | Protocol-native Social | Native protocol adapter |
| 16 | Telegram | `telegram` | Messaging + Publishing | Native |
| 17 | Nostr | `nostr` | Protocol-native Social | Native protocol adapter |
| 18 | VK | `vk` | Social | Native |
| 19 | Discord | `discord` | Community/Messaging | Native |
| 20 | Slack | `slack` | Messaging/Workspace | Native |
| 21 | Dribbble | `dribbble` | Creative Community | Native |
| 22 | Kick | `kick` | Streaming | Native if official access supports required operation |
| 23 | Twitch | `twitch` | Streaming | Native |
| 24 | Medium | `medium` | Publishing | Feasibility-gated |
| 25 | Dev.to | `devto` | Publishing | Native |
| 26 | Hashnode | `hashnode` | Publishing | Native |
| 27 | WordPress | `wordpress` | CMS/Publishing | Native |
| 28 | Listmonk | `listmonk` | Newsletter/Messaging | Native self-hosted API |
| 29 | Whop | `whop` | Community/Business | Native only for documented APIs |
| 30 | Skool | `skool` | Community | Native/API/approved mechanism only |
| 31 | Moltbook | `moltbook` | Agent-native Social | Native API if current official access permits |
| 32 | MeWe | `mewe` | Social | Native if current API access permits |
| 33 | Tumblr | `tumblr` | Social/Publishing | Native |

**Important correction versus V2:** `Tumblr` and `Moltbook` are now explicitly included. `LinkedIn Page` is treated as a first-class connection target/variant, not as an accidental omission.

**Source-consistency note:** the current Postiz documentation tree (`docs.json`) exposes `moltbook`, while the current Postiz Agent `SKILL.md` still describes a shorter 28+ channel list. This is a documentation-version mismatch on the upstream side; this roadmap uses the union of the current provider tree and current dedicated provider materials and therefore keeps Moltbook explicitly in the canonical inventory. citeturn627273search0turn627273search1

## 4.2 User-requested additional providers

These are not part of the Postiz parity baseline but are required by this project scope:

```text
WhatsApp Cloud API
Viber
LINE Official Account
Facebook Messenger
Instagram Messaging
```

## 4.3 Additional verified publishing provider

`beehiiv` is included because current Postiz configuration documentation lists beehiiv as a newsletter provider and beehiiv provides an official v2 Posts API with `posts:write` / `posts:read` scopes. Its Create Post endpoint is asynchronous and current 2026 behavior requires an explicit publication status for immediate publication. citeturn544513search1turn532253search0turn532253search2

## 4.4 Project-specific partner provider

`rutube` is a first-class canonical provider module in this project, but it is not part of the
Postiz-parity baseline above. Its production publishing capability is partner/API-access dependent.
Partner access is a mode/state of the `rutube` module, never a duplicate `rutube_partner` provider.

## 4.5 Feasibility-gated regional/special providers

These must appear in the roadmap and UI as explicit states, but must not be declared “Direct Publish” until the required official server-side capability is verified:

```text
WeChat Official Account
Signal
Snapchat
```

Future regional providers can be added to the same registry.

---

# 5. Provider classes — do not treat every integration as a social post publisher

## Social publishing

```text
X
LinkedIn
LinkedIn Page
Instagram
Facebook Pages
Threads
Pinterest
Reddit
Bluesky
Mastodon
VK
Moltbook
MeWe
Tumblr
```

## Video publishing

```text
YouTube
TikTok
```

## Business publishing

```text
Google Business Profile
```

## Messaging

```text
WhatsApp
Viber
Telegram
Facebook Messenger
Instagram Messaging
LINE Official Account
Discord
Slack
Listmonk
```

## Communities / federated

```text
Lemmy
Mastodon
Farcaster
Nostr
Skool
Whop
MeWe
Discord
```

## Streaming

```text
Twitch
Kick
```

## CMS / long-form publishing / newsletter

```text
WordPress
Medium
Dev.to
Hashnode
Listmonk
beehiiv
```

## Agent-native / protocol-native

```text
Moltbook
Farcaster
Nostr
```

## Restricted / partner / feasibility

```text
Rutube (partner/API access)
Reddit (access model can change)
Viber Business Messages
WhatsApp Embedded Signup multi-business onboarding
WeChat
Signal
Snapchat
```

---

# 6. P0 — absolute Postiz-zero

## 6.1 Runtime graph

The only production publish graph is:

```text
VideoMaker/Content
    -> Core domain
    -> Scheduler / Job Engine
    -> Publisher capability
    -> Module Registry
    -> Native provider module
```

No Postiz transport or dual-write is allowed.

## 6.2 Remove active legacy engines

Remove from active production resolution:

```text
n8n
browser
legacy direct
legacy Postiz transport
```

Archive historical implementations outside active runtime if needed.

## 6.3 Remove operational legacy reads

No runtime use of:

```text
legacy_post_id
legacy_scheduled_for
```

No `COALESCE` fallback from canonical fields to legacy fields in operational code after migration cutover.

## 6.4 Hard gate

CI must fail on:

```text
Postiz runtime imports
Postiz runtime URLs/clients
legacy transport resolution
n8n/browser/direct resolution
legacy operational reads
non-null legacy writes
```

---

# 7. P0 — true multi-account data model

The final EPS identity must be:

```text
(entity_type, entity_id, platform, account_id)
```

Required account entity:

```text
platform_accounts
    internal_account_id
    platform
    remote_account_id
    account_type
    username
    display_name
    enabled
    connection_state
    auth_provider
    token_ref
    granted_scopes
    expires_at
    refresh_status
    webhook_status
    review_state
    app_id
    provider_api_version
    metadata_json
```

Rules:

- `internal_account_id` is the primary internal identity.
- Provider ID is separate.
- Token reference is separate.
- Account A and account B may belong to the same platform.
- Disconnecting one account must not affect another.
- Every publishing/reconciliation/status query receives `account_id`.

Migration to the account-aware PK requires schema v21+ and a deterministic SQLite table rebuild where necessary.

---

# 8. P0 — content/revision/distribution model

Introduce:

```text
ContentItem
ContentRevision
MediaArtifact
DistributionTarget
PublishAttempt
RemoteObject
```

A cross-post is not one generic payload. Each target may contain provider-specific fields.

Per-target fields may include:

```text
title
caption/body
hashtags
mentions
link
alt_text
cover/thumbnail
privacy
comments/duet/stitch options
AIGC options
platform-specific settings
locale
revision_hash
```

Historical publish attempts always point to an immutable revision.

---

# 9. P0 — capability kernel

Manifest must be executable and honest.

Required fields include:

```yaml
provider_id:
module_version:
api_contract_version:
publish_mode: direct | orchestrator | inbox | manual | partner | unsupported
status_authority: authoritative | best_effort | unknown
media_transfer: file_upload | resumable | pull_from_url | container | mixed
review_requirement: none | app_review | audit | business_verification | partner | development_then_standard | trial_then_standard | project_access_approval | registration_required
account_types: []
content_kinds: []
messaging: {}
webhooks: {}
limits: {}
version_policy: {}
```

Capability honesty rule:

A module cannot declare a capability unless:

1. implementation exists;
2. implementation is not a stub;
3. contract test exists;
4. access state allows the capability;
5. status authority is declared correctly.

Example: an Inbox handoff is **not** Direct Publish.

---

# 10. P0 — authentication / token lifecycle

## 10.1 Token broker fix

The current second-pass audit found a concrete defect in the unified token path: `auth_tokens.get_access_token()` uses the wrong construction/method contract for the current `TokenBrokerClient`, causing the broker branch to fail and fall back to local token files.

Fix first.

Rules:

- configured broker factory creates the client;
- correct client method is used;
- broker failure is observable;
- no silent downgrade hiding a broken production secret/broker configuration.

## 10.2 Full token lifecycle

Support, per provider/account where supported:

```text
access token
refresh token
expires_at
refresh-before-expiry
exchange/upgrade
revoke/deauthorize
invalid-token quarantine
reconnect
scope inventory
last success/failure
rotation history
```

## 10.3 Account-scoped secrets

Never rely on:

```text
tokens/<provider>.json
```

as the permanent identity model for multi-account production.

Use a secret abstraction:

```text
SecretProvider
  -> file
  -> env
  -> encrypted store
  -> OS keychain/Vault
```

The provider module must not care where the secret is physically stored.

## 10.4 OAuth session safety

Bind an OAuth session to:

```text
state
provider
client_id
redirect_uri
PKCE verifier
account intent
created_at
expires_at
```

Callback handling must use atomic claim/compare-and-set semantics so duplicate callbacks cannot both succeed.

---

# 11. P0 — provider-specific OAuth registry

Each provider must explicitly declare:

```text
authorization endpoint
exchange endpoint
client credentials source
required scopes
optional scopes
PKCE requirement
refresh support
revoke support
account discovery method
redirect URI rules
review/verification requirements
```

Required initial registry entries:

```text
YouTube
Facebook Pages
Instagram via Facebook Login
Instagram Login
Threads
TikTok
LinkedIn
Pinterest
Reddit (if current approval allows)
```

Meta scopes must never be represented by an empty generic list for a real connection.

---

# 12. P0 — durable jobs

Process-local `jobs.py` is not sufficient for production recovery.

Add durable SQLite-backed:

```text
jobs
job_attempts
job_locks
dead_letter_jobs
```

The interface should later support PostgreSQL without provider rewrites.

Required behavior:

```text
restart
crash
SIGTERM
OOM
network interruption
```

must not lose the publication job state.

---

# 13. P0 — transactional outbox

Add:

```text
outbox_events
```

The rule is:

```text
DB transaction
    -> update EPS
    -> create outbox event
    -> COMMIT

outbox worker
    -> create/run durable job
```

This prevents:

```text
EPS committed
but job creation lost
```

which otherwise can create permanently stuck scheduled targets.

---

# 14. P0 — publish attempt ledger + idempotency

Persist:

```text
attempt_id
entity_id
platform
account_id
revision
idempotency_key
provider_request_id
upload_session_id
remote_object_id
started_at
finished_at
status
error_code
```

Dangerous scenario:

```text
provider created post
-> response lost
-> local system thinks failure
-> retry creates duplicate
```

Recovery rule:

```text
unknown result
    -> remote reconciliation first
    -> attach existing remote object if confidently matched
    -> only then retry creation
```

Never blindly retry a non-idempotent create after an ambiguous timeout.

---

# 15. P0 — webhook/event inbox

Add:

```text
webhook_events
provider_events
```

Fields:

```text
provider
event_id
account_id
received_at
signature_valid
payload_hash
processed
retry_count
dead_letter
error
```

Requirements:

- signature verification;
- provider challenge handling;
- duplicate suppression;
- out-of-order tolerance;
- replay support;
- dead-letter queue;
- provider subscription reconciliation;
- secret rotation;
- retention policy.

Viber’s current Bot API documents HMAC-SHA256 callback signing and retry behavior, which is a concrete example of why a generic event inbox and asynchronous processing are required. citeturn402800search2

LINE likewise recommends signature verification and asynchronous webhook processing, with webhook configuration and token management in its Messaging API. citeturn402800search0turn402800search6

---

# 16. P0 — shared HTTP boundary

Every provider request must pass through the approved HTTP/client abstraction or an explicitly wrapped provider SDK.

Hard CI rule:

```text
no raw requests/httpx/urllib provider calls outside approved boundary
```

Every request must have:

```text
timeout
retry policy
correlation ID
provider request ID capture
normalized errors
secret redaction
rate-limit handling
```

---

# 17. P0 — MediaTransferManager

Create a universal media layer supporting:

```text
local file
object storage
public HTTPS URL
signed URL
resumable upload
chunk upload
media container
provider processing session
cover/thumbnail
```

Security requirements:

- SSRF protection;
- DNS rebinding-safe validation;
- size limits;
- MIME sniffing;
- extension/type validation;
- path containment;
- symlink-safe containment;
- cleanup of orphaned remote media.

Provider-specific media requirements remain inside provider modules.

---

# 18. P0 — scheduler / lease / recovery

Scheduler must support:

```text
immediate
local orchestrator schedule
provider-native schedule
manual/inbox handoff
```

All stored timestamps use UTC.

Account timezone determines local scheduling behavior.

Must be:

```text
DST safe
restart safe
single-fire
cancelable
reschedulable
backpressure aware
```

Provider/account concurrency must be bounded independently.

---

# 19. P0 — status model

Never equate:

```text
API returned ID
API accepted upload
processing started
processing complete
published
publicly visible
```

Canonical states:

```text
created
uploaded
processing
ready
scheduled
published
private
blocked
rejected
failed
deleted
unknown
```

And every provider declares:

```text
authoritative
best_effort
unknown
```

Hard CI rule: live module cannot unconditionally return `published` without provider evidence.

---

# 20. P0 — Provider Supervisor and fault isolation

Create:

```text
ProviderSupervisor
```

Tracked per provider and per account:

```text
auth
health
quota
latency
error rate
429 rate
5xx rate
timeout rate
webhook freshness
queue lag
publish success
reconciliation drift
```

Provider state:

```text
HEALTHY
DEGRADED
PAUSED
AUTH_REQUIRED
QUOTA_EXHAUSTED
REVIEW_REQUIRED
PARTNER_REQUIRED
API_DEPRECATED
DISCONNECTED
RECOVERY_PROBE
```

Circuit breaker:

```text
HEALTHY
  -> DEGRADED
  -> OPEN/PAUSED
  -> RECOVERY_PROBE
  -> HEALTHY
```

A circuit opens per provider/account; it does not stop unrelated providers.

---

# 21. P0 — alerts and operator visibility

Dashboard must show provider/account health, not just global cycle failures.

Example:

```text
YouTube       HEALTHY
Instagram A   HEALTHY
Instagram B   TOKEN_EXPIRED
Facebook      HEALTHY
TikTok        DEGRADED / 429
WhatsApp      REVIEW_REQUIRED
Viber         NOT_CONFIGURED
```

Each incident must expose:

```text
provider
account
state
first_seen
last_seen
error class
recent request ID
retry count
next retry
circuit state
operator action
```

Alerts must be deduplicated and resolved automatically when health recovers.

---

# 22. P0 — consistency sweeper

Add a periodic:

```text
ConsistencyReconciler
```

It compares local EPS and remote provider state.

Examples:

```text
LOCAL scheduled + REMOTE published
-> repair local state

LOCAL published + REMOTE deleted
-> mark remote_deleted / reconcile

LOCAL error + REMOTE exists
-> attach remote object where identity is certain
```

This is a safety net in addition to normal publish jobs and webhooks.

---

# 23. P0 — configuration and migration safety

Startup must fail before publishing if:

```text
invalid schema
invalid config
invalid OAuth URL
missing required credentials
missing media host for required provider
duplicate YAML keys
multiple daemon writers
capability contradiction
```

Migrations:

- preflight backup;
- deterministic transaction where possible;
- no silent critical exceptions;
- verify columns/indexes before schema bump;
- rollback/restore procedure;
- migration audit log.

Config itself should be versioned separately from DB schema.

---

# 24. P0 — security

Required:

```text
OAuth callback rate limiting
Webhook rate limiting
HTTPS outside localhost
Host/origin validation
SSRF defenses
secret redaction
secret rotation
encrypted backups
audit logs
least-privilege scopes
retention/deletion policy
admin authorization
```

No plaintext tokens in logs or debug payloads.

No arbitrary filesystem paths exposed through media APIs.

---

# 25. P0 — deployment / readiness

Separate:

```text
liveness
readiness
provider health
```

One SQLite-writer daemon per DB.

Required operations:

```text
backup before migration
restore drill
auto restart
graceful shutdown
disk-space alert
clock synchronization
log rotation
credential rotation
media cleanup
webhook cleanup
```

---

# 26. P1 — Meta platform family

Meta must be treated as a **vendor platform family with separate modules**, not a single monolith.

```text
Meta Core
    Meta HTTP client
    Meta OAuth
    Meta token lifecycle
    Meta version registry
    Meta webhook verification

Facebook Pages module
Instagram module
Threads module
WhatsApp module
Messenger module (messaging)
Instagram Messaging module (messaging)
```

The project must pin/verify a current Meta Graph API version at implementation time using Meta’s official changelog. Never hardcode an obsolete version without a sunset check.

## 26.1 Facebook Pages

Implement:

```text
Page discovery
Page identity
Page token resolution
text/link
photo
video
Reels
status
remote listing
reconciliation
webhooks
```

Personal Facebook profile publishing must not be implied if the current official API does not support it.

## 26.2 Instagram

Support the relevant official auth families separately:

```text
Facebook Login + linked Page + Professional Instagram
Instagram Login for Professional accounts
```

Do not assume consumer Instagram accounts are supported by all programmatic publishing paths.

Implement by capability:

```text
Feed image
Video/Reels
Carousel
Story where eligible
Container processing/status
Permalink
Delete/status/reconciliation
Comments where approved
Messaging separately
```

## 26.3 Threads

Implement actual official API flow:

```text
Meta app / Threads use case
OAuth
Threads user identity
Text container
Image container
Video container
Carousel
threads_publish
container status
final remote status
read/reconciliation
repost/quote where officially supported and needed
```

Meta’s current official Threads workspace documents container creation, `threads_publish`, carousel support and publishing-status states. citeturn978229search5turn978229search11turn978229search0

The implementation must not leave a live `publish()` stub while manifest says `publish=true`.

## 26.4 WhatsApp Cloud API

WhatsApp is Messaging, not a fake social-post publisher.

Core entities:

```text
WhatsAppBusinessAccount
PhoneNumber
Conversation
Template
Message
WebhookEvent
```

Capabilities:

```text
text
image
video
audio
document
location
interactive
template
inbound message
outbound message
delivery/read/failed
media retrieval
```

Meta’s current WhatsApp Cloud API documentation states that Cloud API is the official business messaging API and requires a Meta Business Portfolio, WABA and business phone number. citeturn372092search10turn372092search5

## 26.5 WhatsApp Embedded Signup

Treat this as a separate onboarding module for multi-business use.

Flow:

```text
Embedded Signup
-> WABA assignment
-> system user
-> phone registration
-> app subscription
-> templates
-> webhooks
-> production
```

Meta’s current Embedded Signup documentation states that released apps need App Review and Advanced Access for the relevant business permissions, and the flow requires WABA/system-user/phone/subscription operations. citeturn372092search0turn372092search11turn372092search12

There is no official “almost 100% approval” method. The best operational strategy is compliance-first staged onboarding with real end-to-end testing, minimal permissions and review evidence.

## 26.6 Facebook Messenger / Instagram Messaging

Keep as separate MessagingModules.

Do not place conversations, replies and media messages into social-post EPS tables as if they were posts.

Required access state:

```text
permissions_ok
business_verification_ok
advanced_access_ok
webhook_ok
```

---

# 27. P1 — Viber

Add:

```text
ViberAccount
ViberMessagingModule
ViberWebhookModule
SubscriberRegistry
```

Capabilities:

```text
text
picture
video
file
broadcast where permitted
subscriber lifecycle
conversation_started
subscribed
unsubscribed
delivery/seen/failure events
```

Viber’s official documentation states that new bots have been commercial since 5 February 2024, require an authentication token and webhook, and that callback requests are signed. citeturn402800search2

Viber Business Messages is a separate commercial/partner product and must not be conflated with ordinary bot messaging.

---

# 28. P1 — TikTok Direct Post

Target:

```text
creator_info
Direct Post video
Direct Post photo
chunk/resumable upload
status
webhook/final state
audited/unaudited state
```

TikTok’s official 2026 documentation requires Content Posting API configuration, approval for `video.publish`, creator-info driven UI, and states that unaudited clients are restricted to private viewing. URL pull requires a verified domain/prefix. citeturn620968search0turn620968search1turn372092search7

Therefore:

```text
DIRECT_POST = real publish
UPLOAD = inbox/manual handoff
```

must remain distinct.

---

# 29. P1 — YouTube production

Implement:

```text
OAuth
resumable upload
upload-session persistence
processing status
metadata
thumbnail
playlist
channel identity
reconciliation
quota meter
compliance/audit runbook
```

Current official YouTube documentation states that uploads from unverified API projects created after 28 July 2020 are private until the project passes a compliance audit; `videos.insert` currently has its own quota bucket and the general API default is 10,000 units/day. citeturn978229search2turn372092search3

The roadmap must not assume audit approval or expanded quota is guaranteed.

---

# 30. P1 — X

Implement:

```text
OAuth/token lifecycle
account identity
image
video
multi-media
threads
processing status
remote read/reconciliation
delete where supported
rate-limit headers
current access-plan verification
```

Do not hardcode long-form/character capabilities when provider/account capability can be queried or changes independently.

---

# 31. P1 — VK

Implement:

```text
account/group identity
wall photo
video
remote IDs
authoritative status
remote inventory
reconciliation
delete
schedule semantics
token probe
```

Do not claim native scheduling where the current official API does not support it; use the orchestrator scheduler explicitly.

---

# 32. P1 — LinkedIn / LinkedIn Page

Treat member and organization/page publishing as separate account types under one provider family.

Implement:

```text
OAuth
member identity
organization/page identity
role/permission probe
image/video/document upload
single post
multi-image where supported
status/reconciliation where supported
API version handling
```

LinkedIn’s current documentation uses versioned Marketing APIs and reports regular version sunset dates; the current migration page says Marketing Version 202510 sunsets 15 October 2026 and version 202609 is active through 15 September 2027. citeturn402800search1turn402800search11

Therefore the version registry is mandatory.

---

# 33. P1 — Pinterest

Implement:

```text
OAuth
boards/sections discovery
image Pin
video Pin
media processing
remote reconciliation
sandbox tests
```

Pinterest maintains an API sandbox; its current developer docs list Pin/Board operations and sandbox support. citeturn978229search10

---

# 34. P1 — Google Business Profile

Use the current provider name in product UI:

```text
Google Business Profile
```

Legacy/internal identifier may remain:

```text
gmb
```

Implement:

```text
OAuth
account discovery
location discovery
local posts
CTA
offer/event post types where supported
media
get/list/delete/patch
reconciliation
```

Google’s current API documentation exposes `accounts.locations.localPosts` create/get/list/delete/patch/reportInsights. citeturn620968search2turn620968search5

---

# 35. P1 — Reddit

Keep Reddit as an explicit provider but with dynamic access state.

Required:

```text
APPROVAL_REQUIRED / APPROVED / MIGRATION_REQUIRED
```

Do not assume classic external API access is permanent.

Current Reddit developer guidance indicates an API-access transition toward the Developer Platform and a timeline beginning January 2027, so this provider must have a migration-aware adapter. 

---

# 36. P1/P2 — Bluesky / AT Protocol

Module:

```text
BlueskyPublishing
BlueskyIdentity
```

Support:

```text
session/auth
DID identity
facets
media
posts
thread/reply semantics
remote reads
```

Protocol-specific identity must not be flattened into OAuth-only assumptions.

---

# 37. P1/P2 — Mastodon

Treat each server/instance as its own provider endpoint configuration.

Support:

```text
instance discovery
OAuth per instance
media
status
visibility
content warning
replies
idempotency key
per-instance rate limits
```

---

# 38. P1/P2 — Lemmy

Per-server module configuration:

```text
server URL
community
account
login/token
post
comment
media
reconciliation
```

No assumption that one Lemmy server behaves as a global API endpoint.

---

# 39. P1/P2 — Farcaster (Warpcast)

Canonical provider name:

```text
Farcaster
```

UI may display:

```text
Farcaster / Warpcast
```

Support protocol-native identity/signing and casts/replies rather than treating it as a generic OAuth social network.

---

# 40. P1/P2 — Nostr

Support:

```text
key management
signing
relay discovery/configuration
publish event
thread/reply
relay acknowledgements
reconciliation
```

Secrets must be protected more strictly because private keys are persistent identities, not ordinary expiring OAuth tokens.

---

# 41. P1/P2 — Discord

Separate:

```text
webhook mode
bot mode
```

Support:

```text
servers/channels
messages
attachments
embeds
permission probes
rate limits
```

A Discord webhook is not equivalent to a Discord user account.

---

# 42. P1/P2 — Slack

Support:

```text
OAuth
workspace discovery
channel discovery
chat.postMessage
files
Events API/webhooks
scope verification
```

Workspace/account identity must remain separate from user identity.

---

# 43. P2 — Streaming providers

## Twitch

Separate streaming identity from social-post identity.

Potential capabilities:

```text
channel identity
stream metadata
announcement/chat where official API permits
```

## Kick

Do not implement an unofficial/scraped server-side publishing path. Use the provider access registry to determine current official/approved APIs before declaring native capabilities.

---

# 44. P2 — CMS / publishing providers

## WordPress

```text
site discovery
auth
media
post/page
publish/update/delete
canonical URL
```

## Medium

```text
identity
post creation
media/embedding according to current API
publication targeting
status
```

## Dev.to

```text
articles
media
publish/update
canonical URL
```

## Hashnode

```text
publication discovery
post
draft/publish/update
media
canonical URL
```

## Listmonk

Treat as newsletter/messaging, not social media.

```text
lists
subscribers
campaign
schedule
send
status
```

---

# 45. P2 — community providers

## Skool

Use official/approved API if available. Browser automation must NOT be introduced as a hidden replacement for an API.

## Whop

Treat business/community identity separately from general social publishing.

## MeWe

Use official/current API access only; access state must determine whether the module is enabled.

## Dribbble

Creative community publishing with explicit account/media rules.

---

# 46. P2 — Tumblr

Add as an explicit module:

```text
TumblrIdentity
TumblrMedia
TumblrPublishing
TumblrStatus
TumblrReconciliation
```

Do not omit it from the provider inventory; it is present in the current Postiz provider documentation tree. citeturn627273search0

---

# 47. P2 — Moltbook

Add explicit module:

```text
MoltbookIdentity
MoltbookPublishing
MoltbookCommunity
MoltbookComments
```

Target-specific setting:

```text
submolt
```

Current Postiz materials explicitly treat Moltbook as a supported channel and expose submolt targeting and scheduling, so parity requires it to appear in our provider registry. citeturn798675search0turn798675search2

Before declaring the module production-ready, validate the current official Moltbook API/auth contract directly at implementation time.

---

# 48. Additional messaging providers

## LINE Official Account

Treat as a dedicated MessagingModule.

Capabilities include:

```text
text
sticker
image
video
audio
location
template
Flex
reply/push
webhook
content retrieval
account linking
```

LINE’s current official Messaging API documentation describes send/receive flows, webhooks, channel access-token issue/verify/revoke and asynchronous webhook processing. citeturn402800search0turn402800search5turn402800search6

## WeChat Official Account

Feasibility-gated until the exact current official account/API access model for the intended business and region is documented and approved.

## Signal

Feasibility-gated. Do not use reverse-engineered/private protocols as a “native provider” in the production roadmap.

## Snapchat

Feasibility-gated. Creative Kit/mobile handoff is not automatically equivalent to server-side publisher access.

---

# 49. Provider Access / Approval Control Plane

Create a provider-access state machine.

Per provider/account:

```text
NOT_CONFIGURED
CREDENTIALS_MISSING
AUTHORIZING
CONNECTED
SCOPES_MISSING
BUSINESS_VERIFICATION_REQUIRED
APP_REVIEW_REQUIRED
ADVANCED_ACCESS_REQUIRED
AUDIT_REQUIRED
PARTNER_REQUIRED
TOKEN_EXPIRED
WEBHOOK_BROKEN
CAPABILITY_RESTRICTED
LIVE
DISCONNECTED
```

Store a structured checklist:

```text
credentials_ok
redirect_ok
account_ok
token_ok
scopes_ok
verification_ok
review_ok
audit_ok
webhook_ok
media_host_ok
smoke_test_ok
live_ok
```

This becomes the single source of truth for onboarding.

---

# 50. API access wizard

Every provider with difficult access must use staged onboarding.

Generic stages:

```text
Stage 0  Developer account
Stage 1  Business/account assets
Stage 2  App creation
Stage 3  Redirect/privacy/legal setup
Stage 4  Sandbox/test connection
Stage 5  Real E2E test on owned assets
Stage 6  Minimal permissions/scopes
Stage 7  Webhooks
Stage 8  Evidence generation
Stage 9  Verification
Stage 10 App Review / Advanced Access
Stage 11 Audit if required
Stage 12 Live
Stage 13 One external pilot
Stage 14 Scale
```

This is a reliability pattern, not an approval guarantee.

---

# 51. Review Evidence Generator

Generate provider-review material from the actual product:

```text
permission
purpose
UI screen
user action
API endpoint
result
security/privacy explanation
```

For Meta/TikTok/YouTube/LinkedIn/other approval-based APIs, generate a repeatable test script and screen-recording checklist.

Never claim a permission is required unless the actual implemented feature uses it.

---

# 52. Provider contract test suite

Every module receives the same abstract tests:

```text
manifest
connect
missing scope
expiry
refresh
revoke
account discovery
media validation
upload
processing
publish
duplicate retry
4xx
429
5xx
timeout-after-side-effect
status authority
remote scan
reconciliation
delete/cancel
webhook signature
duplicate webhook
out-of-order webhook
restart during publish
quota exhaustion
```

No module is “production ready” solely because its happy-path unit test passes.

---

# 53. Live canary framework

Every live-capable provider gets a protected canary account.

Modes:

```text
DRY_RUN
SANDBOX
LIVE_CANARY
PRODUCTION
```

Canary flow:

```text
auth
-> account probe
-> media upload
-> publish
-> remote status/read
-> reconciliation
-> safe cleanup if supported
```

A green unit suite without live canary evidence is not full production verification.

---

# 54. Provider version / deprecation registry

Store:

```text
provider
api_version
released_at
sunset_at
changelog_url
last_checked
migration_status
```

Hard rules:

```text
sunset passed -> CI failure
sunset soon   -> alert
new version   -> compatibility test
```

LinkedIn already demonstrates why this matters: its official migration documentation lists explicit sunset dates, including Marketing 202510 on 15 October 2026. citeturn402800search1

The same pattern must exist for Meta, TikTok, YouTube, Reddit, Pinterest and all versioned providers.

---

# 55. Provider quota / rate-limit model

Never represent a heuristic local limit as an official provider quota.

Each limit record should say:

```yaml
source: official | verified_empirical | local_safety
source_url: ...
checked_at: ...
expires_check_at: ...
```

When headers expose rate-limit information, store the actual values.

Quota exhaustion must affect only the relevant provider/account queue.

---

# 56. Backpressure / provider queue isolation

Queues:

```text
queue.youtube
queue.meta.facebook
queue.meta.instagram
queue.meta.threads
queue.meta.whatsapp
queue.tiktok
queue.x
queue.vk
queue.linkedin
queue.viber
...
```

At minimum, isolation can remain logical inside one process.

The architecture must allow later promotion to separate worker processes without rewriting provider modules.

---

# 57. Failure taxonomy

Normalize provider errors to:

```text
AUTH_EXPIRED
SCOPE_MISSING
RATE_LIMIT
QUOTA_EXHAUSTED
MEDIA_INVALID
MEDIA_HOST_INVALID
PLATFORM_REJECTED
PROVIDER_DOWN
TIMEOUT
DEPENDENCY_DOWN
WEBHOOK_INVALID
WEBHOOK_LAGGING
API_DEPRECATED
REVIEW_REQUIRED
AUDIT_REQUIRED
PARTNER_REQUIRED
ACCOUNT_DISABLED
CONFIG_INVALID
TRANSIENT
PERMANENT
UNKNOWN
```

Each class determines retry/circuit/alert behavior.

---

# 58. Retry policy

Retry only errors classified as retryable.

Use:

```text
exponential backoff
jitter
max attempts
per-provider policy
Retry-After support
circuit breaker
```

Do not retry permanent validation errors.

Do not blindly retry a non-idempotent create after an ambiguous timeout.

---

# 59. Observability

Metrics:

```text
publish_success_total
publish_failure_total
publish_latency
queue_lag
webhook_lag
provider_429_total
provider_5xx_total
auth_failure_total
token_refresh_total
reconciliation_drift_total
media_upload_latency
circuit_open_total
```

Structured logs:

```text
request_id
correlation_id
provider
account_id
operation
attempt_id
remote_id
error_class
```

Secrets must be redacted.

---

# 60. Audit log

Persist operator/security events:

```text
account connected
account disconnected
token rotated
token revoked
scope changed
provider paused/provider resumed
config changed
manual publish approved
manual retry
migration run
secret rotation
```

This is required for troubleshooting and security, even in a single-user/self-hosted environment.

---

# 61. Data retention

Define separate retention for:

```text
OAuth sessions
webhook payloads
publish attempts
provider errors
remote inventories
logs
media artifacts
backup copies
disconnected account data
```

Automatic cleanup must exist.

---

# 62. Backup / restore

Backup must cover:

```text
SQLite DB
config
encrypted secrets
module configuration
```

Do not package plaintext tokens into public release archives.

Restore drill must be tested, not merely documented.

---

# 63. CI — final hard gates

CI must fail on:

```text
Postiz runtime dependency
legacy runtime transport
legacy operational reads
raw provider HTTP outside shared boundary
missing capability implementation
stub advertised as live
optimistic authoritative published
non-account-scoped production token
critical migration exception swallowing
duplicate YAML keys
API version past sunset
missing provider contract tests
missing retry/idempotency tests
missing webhook verification test
```

Also keep:

```text
ruff strict when installed
pytest 0 failed
gate_platform_zero PASS
```

---

# 64. Acceptance tests — mandatory

## Auth

```text
broker success
broker failure visible
near-expiry refresh
refresh failure quarantine
revoke
same OAuth state twice -> one success
wrong provider/client/redirect state -> reject
```

## Publishing

```text
worker restart during publish
provider 500 after side effect
lost HTTP response after successful remote create
duplicate worker race
lease expiry recovery
manual/inbox vs direct capability distinction
```

## Events

```text
valid webhook
bad signature
duplicate event
out-of-order event
provider retry
poison event -> DLQ
replay
```

## Accounts

```text
two accounts same provider
one token expires
other continues
one disconnects
other untouched
```

## Scheduler

```text
timezone
DST
restart
local due-fire
native scheduling
cancel
reschedule
```

---

# 65. Product UI requirements for provider health

The UI must never show only:

```text
Connected
```

Instead:

```text
Connected
Auth OK
Scopes OK
Capabilities OK
Webhooks OK
Media OK
Quota OK
Live Canary OK
Health: HEALTHY
```

Failures are actionable:

```text
TikTok
DEGRADED
Reason: video.publish approval missing
Action: complete app approval
```

or:

```text
Instagram @A
TOKEN_EXPIRED
Action: reconnect
```

---

# 66. Current implementation status — important honesty

The current HARD_CUT archive is **not yet the final implementation of this full roadmap**.

Already present in the current codebase from the prior HARD_CUT work:

```text
YouTube module
Telegram module
Instagram module
Facebook module
Threads scaffold/module
TikTok module/inbox path
VK module
X module
Rutube NotSupported scaffold
OAuth callback path
local_schedule hold
manual EPS adoption
StatusSync token path
RemoteScan adapters
health payload
install/start tooling
```

The previous audit documented 777 passing tests with 5 skipped, but this is local deterministic evidence only; it does not prove external provider approval, live credentials, quota expansion, webhook delivery or production recovery.

The second-pass audit also found concrete remaining issues including the TokenBroker constructor/method mismatch, missing Threads OAuth registration, empty generic Meta scopes, provider-global token persistence, non-atomic OAuth consumption, optimistic status paths, legacy runtime branches, raw provider HTTP calls and process-local jobs.

These are implementation tasks, not “nice to have” items.

---

# 67. Final implementation order

## Phase A — Core / Postiz-zero

1. Remove legacy Postiz/n8n/browser/direct runtime.
2. Remove legacy operational reads.
3. Account-aware EPS schema.
4. Account-scoped token references.
5. Token broker fix + lifecycle.
6. OAuth provider registry and atomic sessions.
7. Capability kernel / executable manifests.
8. Content + revision model.
9. Distribution targets.
10. Durable jobs.
11. Transactional outbox.
12. Publish attempt ledger.
13. Idempotency/reconciliation recovery.
14. Webhook/event inbox.
15. MediaTransferManager.
16. Shared HTTP boundary.
17. Scheduler/lease recovery.
18. Honest status model.
19. ProviderSupervisor / circuit breakers.
20. Consistency sweeper.
21. Security / secrets / SSRF.
22. Observability / alerts.
23. Backup/restore/readiness.
24. CI contract gates.

## Phase B — Meta family

25. Meta Core.
26. Facebook Pages.
27. Instagram.
28. Threads.
29. WhatsApp Cloud API.
30. WhatsApp Embedded Signup.
31. Messenger/Instagram Messaging if required.
32. Meta review/access wizard.

## Phase C — primary video/social

33. TikTok Direct Post.
34. YouTube production/audit/quota.
35. X.
36. VK.
37. LinkedIn / LinkedIn Page.
38. Pinterest.
39. Google Business Profile.
40. Reddit.

## Phase D — messaging / community

41. Telegram Messaging.
42. Viber.
43. LINE Official Account.
44. Discord.
45. Slack.
46. Bluesky.
47. Mastodon.
48. Lemmy.
49. Farcaster.
50. Nostr.

## Phase E — parity completion

51. Tumblr.
52. Moltbook.
53. MeWe.
54. Whop.
55. Skool.
56. Dribbble.
57. Twitch.
58. Kick.
59. WordPress.
60. Medium.
61. Dev.to.
62. Hashnode.
63. Listmonk.
64. beehiiv.

## Phase F — feasibility-gated

65. Snapchat.
66. Signal.
67. WeChat Official Account.
68. additional regional networks only after official-access feasibility review.

---

# 68. Provider readiness definition

The canonical catalog contains 42 provider module IDs. This count includes `rutube` and `beehiiv`, and excludes `linkedin_page` as a separate module because LinkedIn Page is a connection variant under `linkedin`. Rutube partner access is a mode of the `rutube` provider, not a second network. The roadmap therefore has 43 named integration targets/variants when `linkedin_page` is counted as a distinct connection target, but exactly 42 executable module IDs.

A provider is **READY** only when all relevant conditions are true:

```text
module implemented
manifest honest
contract tests pass
auth works
account discovery works
tokens refresh/revoke works where supported
media transfer works
publish/messaging works
status is honest
reconciliation works
webhook works where supported
retry/idempotency works
quota handling works
health probe works
canary works
access review/audit complete where required
documentation/runbook exists
```

A provider may instead be:

```text
PLANNED
IMPLEMENTING
SANDBOX
APPROVAL_REQUIRED
AUDIT_REQUIRED
PARTNER_REQUIRED
FEASIBILITY_GATED
MANUAL_ONLY
UNSUPPORTED
```

Never collapse all of these into `enabled=true/false`.

---

# 69. Final definition of modular fault isolation

These are hard system invariants:

### Invariant 1
One provider failing must not stop other providers.

### Invariant 2
One account failing must not stop other accounts on the same provider.

### Invariant 3
Provider retry/backoff must not block unrelated queues.

### Invariant 4
Provider health must be observable independently.

### Invariant 5
Every degraded provider must generate an actionable signal.

### Invariant 6
Automatic recovery must be possible after transient failures.

### Invariant 7
Permanent provider/access failures must pause only affected targets and explain why.

### Invariant 8
The Core must never emulate missing provider APIs through hidden browser automation.

---

# 70. Final network coverage statement

For the defined target scope, the roadmap now explicitly covers:

```text
Postiz parity baseline:
X
LinkedIn
LinkedIn Page
Reddit
Instagram
Facebook Pages
Threads
YouTube
Google Business Profile
TikTok
Pinterest
Bluesky
Mastodon
Lemmy
Farcaster / Warpcast
Telegram
Nostr
VK
Discord
Slack
Dribbble
Kick
Twitch
Medium
Dev.to
Hashnode
WordPress
Listmonk
Whop
Skool
Moltbook
MeWe
Tumblr

Project-required additions:
WhatsApp
Viber
Facebook Messenger
Instagram Messaging
LINE Official Account

Feasibility-gated additions:
WeChat Official Account
Signal
Snapchat
future regional providers
```

No earlier roadmap entry is intentionally omitted from this canonical list.

---

# 71. External-access reality check

The code can implement a provider module, but it cannot grant itself a provider's approval.

External dependencies remain:

```text
Meta App Review / Advanced Access / Business Verification
TikTok approval/audit
YouTube compliance audit/quota
LinkedIn access tiers and permission model
Reddit current API access / transition
Viber commercial bot/Business Messages access
Rutube partner/API access
provider-specific quotas
provider-specific regional restrictions
```

There is no legitimate “guaranteed approval” shortcut. The recommended pattern is:

```text
own assets
-> complete E2E
-> minimal permissions
-> legal/HTTPS/webhook hygiene
-> evidence
-> verification
-> review/audit
-> live
-> one external pilot
-> scale
```

---

# 72. Final master Definition of Done

The project may be called:

> **Independent native social/messaging orchestrator, ready for production field operation.**

only when:

```text
[ ] Postiz is absent from runtime publication.
[ ] Legacy transport is absent from runtime.
[ ] Legacy operational reads are absent.
[ ] Multi-account EPS is live.
[ ] Tokens are account-scoped.
[ ] Token lifecycle works.
[ ] OAuth sessions are atomic and bound to provider/client/redirect.
[ ] Capability manifests are executable and honest.
[ ] Content revisions are immutable per attempt.
[ ] Durable jobs survive restart.
[ ] Transactional outbox is live.
[ ] Publish attempts are durable.
[ ] Ambiguous side effects are reconciled before retry.
[ ] Webhook inbox is durable and replayable.
[ ] MediaTransferManager is live.
[ ] Provider HTTP is centrally controlled.
[ ] Scheduler is DST/restart safe.
[ ] Status authority is explicit.
[ ] ProviderSupervisor isolates failures.
[ ] Circuit breakers isolate provider/account failures.
[ ] Provider health is visible.
[ ] Alerts are actionable and deduplicated.
[ ] Consistency sweeper is active.
[ ] Security gates pass.
[ ] Backup/restore works.
[ ] CI hard gates pass.
[ ] Each live provider passes contract tests.
[ ] Each live provider has a canary.
[ ] Meta family is live for the intended approved capabilities.
[ ] WhatsApp is implemented as MessagingModule.
[ ] Viber is implemented as MessagingModule.
[ ] TikTok Direct Post is separate from Inbox.
[ ] YouTube production compliance is complete for intended visibility.
[ ] Postiz-parity provider inventory is complete or explicitly marked with its correct access state.
[ ] Feasibility-gated providers are never falsely advertised as Direct Publish.
```

---

# 73. Canonical engineering rule for future additions

When a new network appears:

```text
1. Add Provider Coverage Registry entry.
2. Verify official/current API model.
3. Determine capability family.
4. Determine auth/account model.
5. Determine media transfer model.
6. Determine webhook/status model.
7. Determine approval/partner/audit barriers.
8. Implement isolated module.
9. Add contract tests.
10. Add live canary.
11. Add health/alerts.
12. Add version/sunset tracking.
13. Only then expose capability as READY.
```

No provider-specific shortcuts in Core.

---

# 74. Sources checked for this revision

- Postiz current documentation/provider tree: https://github.com/gitroomhq/postiz-docs/blob/main/docs.json
- Postiz agent/channel list: https://github.com/gitroomhq/postiz-agent/blob/main/SKILL.md
- Postiz current Moltbook support material: https://postiz.com/claude-code/moltbook
- TikTok Content Posting API — Direct Post: https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post
- TikTok Content Posting API — Get Started: https://developers.tiktok.com/docs/en/content-posting-api-get-started
- YouTube videos.insert: https://developers.google.com/youtube/v3/docs/videos/insert
- YouTube quota/compliance audits: https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
- Meta/WhatsApp Cloud API Postman collection: https://www.postman.com/meta/whatsapp-business-platform/collection/wlk6lh4/whatsapp-cloud-api
- Meta/WhatsApp Embedded Signup: https://www.postman.com/meta/whatsapp-business-platform/documentation/du6gzjv/embedded-signup
- Meta Threads official Postman workspace: https://www.postman.com/meta/threads/overview
- Meta Threads API documentation: https://www.postman.com/meta/threads/documentation/dht3nzz/threads-api
- Viber REST Bot API: https://developers.viber.com/docs/api/rest-bot-api/
- LINE Messaging API overview: https://developers.line.biz/en/docs/messaging-api/overview/
- LINE Messaging API reference: https://developers.line.biz/en/reference/messaging-api/
- LinkedIn API migrations/versioning: https://learn.microsoft.com/en-us/linkedin/marketing/integrations/migrations
- Pinterest sandbox: https://developers.pinterest.com/docs/developer-tools/sandbox/
- Google Business Profile API: https://developers.google.com/my-business/reference/rest/
- Reddit Developer Platform app registration: https://developers.reddit.com/app-registration

**Verification policy:** external provider rules, API versions, quotas, approval requirements and partner programs are time-sensitive. Before enabling a provider in production, re-check the provider's current official documentation and access console and record the checked date/version in the Provider Coverage Registry.

# 75. Prepared archive implementation addendum — 2026-10-01

This section records what was actually added to the prepared archive after the
master roadmap review. It must not be interpreted as claiming external provider
approval or a completed production integration where the provider is marked
SCAFFOLD/PARTNER/FEASIBILITY.

Implemented in code:
- fixed TokenBrokerClient construction/method usage in auth_tokens;
- added account-aware token-file lookup;
- added atomic OAuth session claim/release support;
- registered Threads OAuth with explicit scopes;
- centralized Meta Graph default at v26.0 for implemented Meta modules;
- implemented Threads live container/status/publish/read path;
- replaced X optimistic live status with remote status read;
- routed X/VK/Telegram multipart uploads through ModuleHttpClient;
- added provider capability interfaces;
- added ProviderSupervisor with persisted per-provider/per-account health and a single half-open recovery probe;
- added durable DB primitives for provider health/access, publish attempts,
  outbox events, webhook events, durable jobs, distribution targets, media
  artifacts and consistency runs;
- added provider catalog and honest module scaffolds for the canonical provider inventory;
- added modular architecture/provider matrix documentation.

Still explicitly preparation rather than completion:
- full account-aware EPS primary-key cutover;
- full transactional integration of the outbox into every domain mutation;
- provider-specific remote repair logic in the consistency sweeper;
- live implementations for scaffold/partner/feasibility providers;
- real third-party credentials, approvals, audits, partner contracts and live canaries.

A prepared provider module may implement only the capability families that the
provider actually exposes. No provider-specific detail should be added to the
Core scheduler/publisher/database code merely to make a missing provider API
appear supported.
